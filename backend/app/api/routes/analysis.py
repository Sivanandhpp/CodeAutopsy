"""
Analysis API Routes — Two-Phase Pipeline with Streaming SSE
=============================================================
Phase 1 (2-5s): Clone → Static Analysis → instant results to frontend
Phase 2 (10-60s): Ollama AI → per-file streaming results to frontend

The key insight: users see real findings within seconds (Phase 1), while
AI analysis streams progressively in the background (Phase 2). The frontend
renders both layers independently, so the UX is never blocking.

SSE Event Types:
  - status         → generic progress (cloning, analyzing, etc.)
  - static_complete → Phase 1 done: all static issues + file tree + health score
  - stack_detected  → detected language + frameworks badge
  - ai_summary_start → AI summary starting
  - ai_summary_chunk → streamed markdown chunk from Ollama
  - ai_summary_error → non-fatal AI summary failure
  - ai_summary_complete → Phase 2 done: final summary state
  - complete        → everything done, final summary
  - analysis_error  → fatal analysis failure, analysis aborted
"""

import uuid
import json
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_standalone_session
from app.models.analysis import AnalysisResult
from app.models.project import Project, UserProject
from app.models.user import User
from app.models.schemas import (
    AnalyzeRequest, AnalyzeResponse, AnalysisResultResponse,
    IssueDetail,
)
from pydantic import BaseModel as PydanticBaseModel
from app.services.git_service import git_service
from app.services.static_analyzer import static_analyzer
from app.services.ai import get_ai_gateway
from app.utils.progress import progress_tracker
from app.api.deps import get_current_user, get_current_user_optional
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# ─── Concurrent analysis tracking ───────────────────────────
_active_analyses: dict[str, asyncio.Task] = {}
_analysis_semaphore: Optional[asyncio.Semaphore] = None


def _get_analysis_semaphore() -> asyncio.Semaphore:
    global _analysis_semaphore
    if _analysis_semaphore is None:
        settings = get_settings()
        _analysis_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_ANALYSES)
    return _analysis_semaphore


async def _get_latest_analysis(
    db: AsyncSession,
    repo_url: str,
    project_id: Optional[object],
    status_filter: Optional[list[str]] = None,
) -> Optional[AnalysisResult]:
    query = select(AnalysisResult).where(AnalysisResult.repo_url == repo_url)
    if project_id:
        query = query.where(AnalysisResult.project_id == project_id)
    else:
        query = query.where(AnalysisResult.project_id.is_(None))
    if status_filter:
        query = query.where(AnalysisResult.status.in_(status_filter))
    query = query.order_by(AnalysisResult.created_at.desc())
    result = await db.execute(query)
    return result.scalars().first()


# ─── Per-user rate limiter ───────────────────────────────────
_user_rate_limit: dict[str, list[float]] = {}


def check_rate_limit(user_id: str):
    """Per-user rate limiting for analysis requests."""
    settings = get_settings()
    now = datetime.now(timezone.utc).timestamp()

    if user_id not in _user_rate_limit:
        _user_rate_limit[user_id] = []

    _user_rate_limit[user_id] = [
        t for t in _user_rate_limit[user_id] if now - t < 3600
    ]

    if len(_user_rate_limit[user_id]) >= settings.MAX_ANALYSIS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit: max {settings.MAX_ANALYSIS_PER_HOUR} analyses per hour.",
        )

    _user_rate_limit[user_id].append(now)


# ─── SSE Event Queue ────────────────────────────────────────
# Each analysis gets an asyncio.Queue for typed SSE events.
# The stream endpoint drains this queue to the client.
_event_queues: dict[str, asyncio.Queue] = {}
_event_subscribers: dict[str, int] = {}


def _get_event_queue(analysis_id: str) -> asyncio.Queue:
    """Get or create the SSE event queue for an analysis."""
    if analysis_id not in _event_queues:
        _event_queues[analysis_id] = asyncio.Queue(maxsize=500)
    return _event_queues[analysis_id]


def _cleanup_event_queue(analysis_id: str):
    """Remove queue state once analysis work is finished and no stream is attached."""
    if _event_subscribers.get(analysis_id, 0) > 0:
        return
    if analysis_id in _active_analyses:
        return
    _event_queues.pop(analysis_id, None)
    _event_subscribers.pop(analysis_id, None)


async def _emit_event(analysis_id: str, event_type: str, data: dict):
    """Push a typed SSE event into the queue for the given analysis."""
    queue = _get_event_queue(analysis_id)
    try:
        queue.put_nowait({
            "event": event_type,
            "data": data,
        })
    except asyncio.QueueFull:
        # Drop oldest event if queue is full (prevent memory leak)
        try:
            queue.get_nowait()
            queue.put_nowait({"event": event_type, "data": data})
        except Exception:
            pass

    # Also update the legacy progress tracker for backward compat
    if event_type == "status":
        progress_tracker.update(
            analysis_id,
            data.get("status", "analyzing"),
            data.get("progress", 0),
            data.get("message", ""),
            data.get("step", ""),
        )


# ─── Background Analysis Task ───────────────────────────────

async def run_analysis_task(analysis_id: str, repo_url: str):
    """
    Background task that runs the two-phase analysis pipeline.
    Phase 1: Clone + Static Analysis (results pushed immediately)
    Phase 2: Ollama AI Analysis (results streamed per-file)
    """
    semaphore = _get_analysis_semaphore()

    async with semaphore:
        async with get_standalone_session() as db:
            try:
                await _execute_analysis(analysis_id, repo_url, db)
            except asyncio.CancelledError:
                logger.info(f"Analysis {analysis_id[:8]} was cancelled")
                await _update_status(db, analysis_id, "cancelled", error="Analysis was cancelled by user")
                await _emit_event(analysis_id, "analysis_error", {
                    "message": "Analysis cancelled", "status": "cancelled"
                })
            except Exception as e:
                logger.error(f"Analysis {analysis_id[:8]} failed: {e}", exc_info=True)
                try:
                    await _update_status(db, analysis_id, "failed", error=str(e)[:2000])
                except Exception:
                    pass
                await _emit_event(analysis_id, "analysis_error", {
                    "message": f"Analysis failed: {str(e)[:200]}",
                    "status": "failed",
                })
            finally:
                # Signal end-of-stream so the SSE generator exits cleanly
                await _emit_event(analysis_id, "_done", {})
                _active_analyses.pop(analysis_id, None)
                _cleanup_event_queue(analysis_id)


async def _execute_analysis(analysis_id: str, repo_url: str, db: AsyncSession):
    """
    Two-phase analysis pipeline.
    Phase 1 delivers results in ~2-5 seconds.
    Phase 2 streams AI results progressively.
    """
    repo_path = None

    try:
        # ═══════════════════════════════════════════════════════
        # PHASE 1: Clone + Static Analysis (instant results)
        # ═══════════════════════════════════════════════════════

        # Step 1: Clone or refresh repository
        await _emit_event(analysis_id, "status", {
            "status": "cloning", "progress": 5,
            "message": "Preparing repository...", "step": "clone",
        })

        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.id == analysis_id)
        )
        record = result.scalar_one_or_none()

        existing_path = None
        if record:
            candidate = record.clone_path or record.repo_path
            if candidate and os.path.isdir(candidate):
                existing_path = candidate

        if existing_path:
            try:
                await _emit_event(analysis_id, "status", {
                    "status": "cloning", "progress": 8,
                    "message": "Refreshing repository...", "step": "clone",
                })
                repo_path = await asyncio.to_thread(
                    git_service.refresh_repository, existing_path
                )
                repo_name = git_service.extract_repo_name(repo_url)
            except Exception as e:
                logger.warning(f"Repo refresh failed, recloning: {e}")
                repo_path, repo_name = await asyncio.to_thread(
                    git_service.clone_repository, repo_url, analysis_id
                )
        else:
            repo_path, repo_name = await asyncio.to_thread(
                git_service.clone_repository, repo_url, analysis_id
            )

        await _emit_event(analysis_id, "status", {
            "status": "cloning", "progress": 20,
            "message": f"Cloned: {repo_name}", "step": "clone",
        })

        # Get HEAD SHA for caching
        head_sha = await asyncio.to_thread(_get_head_sha, repo_path)

        # Update DB with repo info
        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.id == analysis_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.repo_name = repo_name
            record.clone_path = repo_path
            record.repo_path = repo_path
            record.status = "analyzing"
            record.commit_sha = head_sha
            await db.commit()

        # Step 2: Extract file tree
        await _emit_event(analysis_id, "status", {
            "status": "analyzing", "progress": 25,
            "message": "Mapping file structure...", "step": "file_tree",
        })

        file_tree = await asyncio.to_thread(git_service.get_file_tree, repo_path)
        languages = await asyncio.to_thread(git_service.get_language_stats, file_tree)
        total_lines = await asyncio.to_thread(git_service.get_total_lines, file_tree)

        await _emit_event(analysis_id, "status", {
            "status": "analyzing", "progress": 35,
            "message": f"Found {len(file_tree)} files, {total_lines:,} lines",
            "step": "file_tree",
        })

        # Step 3: Run static analysis (Semgrep / regex patterns)
        await _emit_event(analysis_id, "status", {
            "status": "analyzing", "progress": 40,
            "message": "Running security scan...", "step": "static_analysis",
        })

        issues = await static_analyzer.run_analysis(repo_path, db, file_tree)

        # Calculate health score immediately (Phase 1 result)
        health_score = static_analyzer.calculate_health_score(issues)

        # Enhance issues with batch git blame
        await _emit_event(analysis_id, "status", {
            "status": "analyzing", "progress": 45,
            "message": "Enriching issues with git history...", "step": "git_blame",
        })
        await asyncio.to_thread(git_service.get_issue_blame_batch, repo_path, issues)

        # Calculate contributor stats
        contributor_stats: dict[str, dict] = {}
        for issue in issues:
            email = issue.get("origin_author_email", "unknown@example.com")
            name = issue.get("origin_author_name", "Unknown")
            if email not in contributor_stats:
                contributor_stats[email] = {"name": name, "email": email, "count": 0}
            contributor_stats[email]["count"] += 1

        # Add issue counts to file tree
        issue_counts: dict[str, int] = {}
        for issue in issues:
            fp = issue.get("file_path", "")
            issue_counts[fp] = issue_counts.get(fp, 0) + 1
        for f in file_tree:
            f["issue_count"] = issue_counts.get(f["path"], 0)

        # ── PHASE 1 COMPLETE: Push static results immediately ──
        await _emit_event(analysis_id, "static_complete", {
            "issues": issues,
            "total_issues": len(issues),
            "health_score": health_score,
            "file_tree": file_tree,
            "languages": languages,
            "total_lines": total_lines,
            "repo_name": repo_name,
            "progress": 50,
            "message": f"Security scan complete: {len(issues)} issues, health {health_score}/100",
        })

        # Save Phase 1 results to DB immediately (user can view results
        # even if Phase 2 fails or takes a long time)
        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.id == analysis_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.health_score = health_score
            record.total_issues = len(issues)
            record.file_count = len(file_tree)
            record.total_lines = total_lines
            record.set_languages(languages)
            record.set_issues(issues)
            record.set_file_tree(file_tree)
            record.set_contributor_stats(contributor_stats)
            await db.commit()

        # ═══════════════════════════════════════════════════════
        # PHASE 2: Streaming AI Summary
        # ═══════════════════════════════════════════════════════

        await _emit_event(analysis_id, "status", {
            "status": "ai_scanning", "progress": 55,
            "message": "Generating AI summary...", "step": "ai_analysis",
        })

        # Create a send_event callback that emits through our queue
        async def send_ai_event(event_type: str, data: dict):
            await _emit_event(analysis_id, event_type, data)

        ai_summary_text: str = ""
        model_info: str = "Local AI"
        try:
            gateway = get_ai_gateway()
            
            # Predict the model info that will be used
            providers = gateway._ordered_providers()
            if providers:
                p = providers[0]
                from app.config import get_settings
                m_str = get_settings().GROQ_MODEL if p.name == "Groq" else get_settings().OLLAMA_MODEL
                model_info = f"{p.name} - {m_str}"

            ai_summary_text = await gateway.stream_summary(issues, send_ai_event)
        except Exception as e:
            logger.warning(f"AI summary failed (non-fatal): {e}")
            await _emit_event(analysis_id, "ai_summary_complete", {
                "summary": "",
                "message": f"AI summary unavailable: {str(e)[:100]}",
            })

        # ═══════════════════════════════════════════════════════
        # FINALIZE: Save all results + emit completion
        # ═══════════════════════════════════════════════════════

        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.id == analysis_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = "complete"
            record.set_ai_summary(ai_summary_text)
            
            # Save the guessed model info so we have it on reload
            findings = record.get_ollama_findings()
            findings.append({"type": "ai_meta", "model_info": model_info})
            record.set_ollama_findings(findings)

            record.completed_at = datetime.now(timezone.utc)

            # Update project's last commit SHA
            if record.project_id:
                proj_result = await db.execute(
                    select(Project).where(Project.id == record.project_id)
                )
                project = proj_result.scalar_one_or_none()
                if project and head_sha:
                    project.last_commit_sha = head_sha

            await db.commit()

        await _emit_event(analysis_id, "complete", {
            "status": "complete", "progress": 100,
            "health_score": health_score,
            "total_issues": len(issues),
            "message": (
                f"Analysis complete! Score: {health_score}/100, "
                f"{len(issues)} static issues found."
            ),
        })

        progress_tracker.update(
            analysis_id, "complete", 100,
            f"Analysis complete! Health score: {health_score}/100",
            "complete",
        )

    finally:
        # Removed automatic repo cleanup here so users can still explore/edit code later.
        pass


async def _update_status(db: AsyncSession, analysis_id: str, status_val: str, error: str = None):
    """Helper to safely update analysis status."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.status = status_val
        if error:
            record.error_message = error
        await db.commit()


def _get_head_sha(repo_path: str) -> Optional[str]:
    """Get HEAD commit SHA from a git repo."""
    try:
        from git import Repo
        repo = Repo(repo_path)
        return str(repo.head.commit.hexsha)
    except Exception:
        return None


def _normalize_issue(issue: dict) -> dict:
    data = dict(issue)
    if "defect_family" not in data:
        data["defect_family"] = data.get("category") or data.get("issue_type") or "unknown"
    if "rule_id" not in data:
        data["rule_id"] = data.get("issue_type") or "unknown"
    if "severity" not in data:
        data["severity"] = "medium"
    if "message" not in data:
        data["message"] = "Issue detected"
    if "line_number" not in data:
        data["line_number"] = 0
    if "engine_source" not in data:
        data["engine_source"] = "unknown"
    data.setdefault("fix_hint", None)
    data.setdefault("cwe_id", None)
    data.setdefault("owasp_ref", None)
    data.setdefault("code_snippet", "")
    data.setdefault("origin_author_name", None)
    data.setdefault("origin_author_email", None)
    data.setdefault("origin_author", None)
    data.setdefault("origin_commit", None)
    data.setdefault("origin_date", None)
    return data


def _format_sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _build_snapshot_events(analysis_id: str) -> list[tuple[str, dict]]:
    async with get_standalone_session() as db:
        result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            return []

        issues = [_normalize_issue(i) for i in analysis.get_issues()]
        file_tree = analysis.get_file_tree()
        languages = analysis.get_languages()

        has_static = bool(
            analysis.health_score is not None or analysis.file_count
            or analysis.total_lines or file_tree or issues
        )

        events: list[tuple[str, dict]] = []
        if has_static:
            events.append(("static_complete", {
                "issues": issues,
                "total_issues": len(issues),
                "health_score": analysis.health_score or 0,
                "file_tree": file_tree,
                "languages": languages,
                "total_lines": analysis.total_lines or 0,
                "repo_name": analysis.repo_name or analysis.repo_url.split("github.com/")[-1].strip("/"),
                "progress": 50,
                "message": "Static analysis complete (snapshot)",
            }))

        if analysis.ai_summary:
            events.append(("ai_summary_complete", {
                "summary": analysis.ai_summary,
                "status": "complete",
                "message": "AI summary available (snapshot)",
            }))

        if analysis.status == "complete":
            events.append(("complete", {
                "status": "complete",
                "progress": 100,
                "health_score": analysis.health_score or 0,
                "total_issues": analysis.total_issues or len(issues),
                "message": "Analysis complete (snapshot)",
            }))
        elif analysis.status in ("failed", "cancelled"):
            events.append(("analysis_error", {
                "status": analysis.status,
                "message": analysis.error_message or "Analysis failed",
            }))

        return events


# ─── Endpoints ───────────────────────────────────────────────

@router.post("/analyze/github", response_model=AnalyzeResponse)
async def analyze_github_repo(
    req: AnalyzeRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Start analysis of a GitHub repository. Works for both authenticated and anonymous users."""
    # Rate-limit authenticated users only
    if user:
        check_rate_limit(str(user.id))

    analysis_id = str(uuid.uuid4())
    project_id = req.project_id
    force_rerun = bool(req.force) if user else False

    # Reuse existing project for authenticated users if possible
    if user and project_id is None:
        existing_project = await db.execute(
            select(Project)
            .join(UserProject)
            .where(UserProject.user_id == user.id, Project.repo_url == req.repo_url)
            .order_by(Project.created_at.desc())
        )
        project = existing_project.scalars().first()
        if project:
            project_id = project.id
        else:
            repo_name = req.repo_url.split("github.com/")[-1].strip("/")
            project = Project(repo_url=req.repo_url, repo_name=repo_name)
            db.add(project)
            await db.flush()

            user_project = UserProject(user_id=user.id, project_id=project.id, role="owner")
            db.add(user_project)
            await db.flush()

            project_id = project.id

    # If an analysis is already running, return it
    in_progress = await _get_latest_analysis(
        db,
        req.repo_url,
        project_id,
        status_filter=["queued", "cloning", "analyzing"],
    )
    if in_progress:
        return AnalyzeResponse(
            analysis_id=in_progress.id,
            project_id=project_id,
            status=in_progress.status,
            message="Analysis already in progress.",
        )

    # Latest completed analysis for reuse
    latest_complete = await _get_latest_analysis(
        db,
        req.repo_url,
        project_id,
        status_filter=["complete"],
    )

    if not user and latest_complete:
        return AnalyzeResponse(
            analysis_id=latest_complete.id,
            project_id=project_id,
            status=latest_complete.status,
            message="Returning existing analysis for this repository.",
        )

    if user and latest_complete and not force_rerun:
        reuse_message = None
        if latest_complete.commit_sha:
            remote_head = await asyncio.to_thread(
                git_service.get_remote_head_sha, req.repo_url
            )
            if remote_head and remote_head == latest_complete.commit_sha:
                reuse_message = "No new commits detected. Returning existing analysis."
            elif remote_head is None:
                reuse_message = "Remote HEAD check unavailable. Returning existing analysis."
        if reuse_message:
            return AnalyzeResponse(
                analysis_id=latest_complete.id,
                project_id=project_id,
                status=latest_complete.status,
                message=reuse_message,
            )

    reuse_clone_path = None
    if latest_complete and (force_rerun or user):
        candidate = latest_complete.clone_path or latest_complete.repo_path
        if candidate and os.path.exists(candidate):
            reuse_clone_path = candidate

    # Create analysis record (project_id is None for anonymous users)
    record = AnalysisResult(
        id=analysis_id,
        project_id=project_id,
        repo_url=req.repo_url,
        status="queued",
    )
    if reuse_clone_path:
        record.clone_path = reuse_clone_path
        record.repo_path = reuse_clone_path
    db.add(record)
    await db.flush()

    # Initialize progress tracker + event queue
    progress_tracker.create(analysis_id)
    _get_event_queue(analysis_id)

    # Start background analysis task
    task = asyncio.create_task(run_analysis_task(analysis_id, req.repo_url))
    _active_analyses[analysis_id] = task

    who = user.username if user else "anonymous"
    logger.info(f"Analysis started: {analysis_id[:8]} for {req.repo_url} by {who}")

    return AnalyzeResponse(
        analysis_id=analysis_id,
        project_id=project_id,
        status="queued",
        message="Analysis started. Use the analysis ID to track progress.",
    )


@router.post("/analyze/cancel/{analysis_id}")
async def cancel_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
):
    """Cancel a running analysis."""
    task = _active_analyses.get(analysis_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis not found or already completed")

    task.cancel()
    logger.info(f"Analysis {analysis_id[:8]} cancelled by {user.username}")
    return {"message": "Analysis cancellation requested"}


@router.get("/results/{analysis_id}", response_model=AnalysisResultResponse)
async def get_results(
    analysis_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis results by ID. Works for both authenticated and anonymous users."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Build response
    issues = record.get_issues()
    ai_summary = record.get_ai_summary()

    normalized_issues = [_normalize_issue(i) for i in issues]

    return AnalysisResultResponse(
        id=record.id,
        project_id=record.project_id,
        repo_url=record.repo_url,
        repo_name=record.repo_name,
        clone_path=record.clone_path,
        status=record.status,
        health_score=record.health_score,
        total_issues=record.total_issues,
        file_count=record.file_count,
        total_lines=record.total_lines,
        languages=record.get_languages(),
        issues=[IssueDetail(**i) for i in normalized_issues],
        file_tree=record.get_file_tree(),
        ollama_findings=[],
        contributor_stats=record.get_contributor_stats(),
        ai_summary=ai_summary,
        error_message=record.error_message,
        created_at=record.created_at.isoformat() if record.created_at else None,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )


@router.get("/analyze/stream/{analysis_id}")
async def stream_progress(analysis_id: str, request: Request):
    """
    Server-Sent Events endpoint with typed events for the two-phase pipeline.

    The frontend receives named events like 'static_complete',
    'ai_summary_chunk', and 'complete', each carrying structured JSON payloads.

    Client disconnects no longer cancel the background analysis. This lets
    Phase 1 results persist and AI summary generation finish even across refreshes.
    """

    async def event_generator():
        queue = _get_event_queue(analysis_id)
        _event_subscribers[analysis_id] = _event_subscribers.get(analysis_id, 0) + 1

        try:
            snapshot_events = await _build_snapshot_events(analysis_id)
            for event_type, data in snapshot_events:
                yield _format_sse_event(event_type, data)
                if event_type in ("complete", "analysis_error"):
                    return

            while True:
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected for {analysis_id[:8]}")
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                event_type = event.get("event", "status")
                event_data = event.get("data", {})

                if event_type == "_done":
                    break

                data_str = json.dumps(event_data)
                yield f"event: {event_type}\ndata: {data_str}\n\n"

                if event_type in ("complete", "analysis_error"):
                    break
        finally:
            remaining = _event_subscribers.get(analysis_id, 0) - 1
            if remaining > 0:
                _event_subscribers[analysis_id] = remaining
            else:
                _event_subscribers.pop(analysis_id, None)
            _cleanup_event_queue(analysis_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/files/{analysis_id}")
async def get_file_content(
    analysis_id: str,
    file_path: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get file content from an analyzed repository. Works for both authenticated and anonymous users."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Repo may have been cleaned up after analysis — check if path is still accessible
    repo_path = record.clone_path or record.repo_path
    if not repo_path or not os.path.exists(repo_path):
        raise HTTPException(
            status_code=410,
            detail="Repository files have been cleaned up after analysis. File content is no longer available.",
        )

    try:
        content = git_service.get_file_content(repo_path, file_path)
        language = git_service.detect_language(file_path.split("/")[-1])

        return {
            "file_path": file_path,
            "content": content,
            "language": language,
            "lines": content.count("\n") + 1,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class FileUpdateRequest(PydanticBaseModel):
    file_path: str
    content: str

@router.put("/files/{analysis_id}")
async def update_file_content(
    analysis_id: str,
    req: FileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update file content in an analyzed repository (sandbox edit). Requires authentication."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    repo_path = record.clone_path or record.repo_path
    if not repo_path or not os.path.exists(repo_path):
        raise HTTPException(
            status_code=410,
            detail="Repository files have been cleaned up. Cannot save edits.",
        )

    try:
        git_service.put_file_content(repo_path, req.file_path, req.content)
        return {"message": "File updated successfully"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
