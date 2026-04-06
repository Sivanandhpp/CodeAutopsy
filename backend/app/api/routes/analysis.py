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

        # Step 1: Clone repository
        await _emit_event(analysis_id, "status", {
            "status": "cloning", "progress": 5,
            "message": "Cloning repository...", "step": "clone",
        })

        repo_path, repo_name = await asyncio.to_thread(
            git_service.clone_repository, repo_url
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

        issues = await asyncio.to_thread(static_analyzer.run_analysis, repo_path, file_tree)

        # Calculate health score immediately (Phase 1 result)
        health_score = static_analyzer.calculate_health_score(issues)

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
        try:
            gateway = get_ai_gateway()
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

    # Only create/link projects for authenticated users
    if user and project_id is None:
        repo_name = req.repo_url.split("github.com/")[-1].strip("/")
        project = Project(repo_url=req.repo_url, repo_name=repo_name)
        db.add(project)
        await db.flush()

        user_project = UserProject(user_id=user.id, project_id=project.id, role="owner")
        db.add(user_project)
        await db.flush()

        project_id = project.id

    # Create analysis record (project_id is None for anonymous users)
    record = AnalysisResult(
        id=analysis_id,
        project_id=project_id,
        repo_url=req.repo_url,
        status="queued",
    )
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

    return AnalysisResultResponse(
        id=record.id,
        project_id=record.project_id,
        repo_url=record.repo_url,
        repo_name=record.repo_name,
        status=record.status,
        health_score=record.health_score,
        total_issues=record.total_issues,
        file_count=record.file_count,
        total_lines=record.total_lines,
        languages=record.get_languages(),
        issues=[IssueDetail(**i) for i in issues],
        file_tree=record.get_file_tree(),
        ollama_findings=[],
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
    import os
    if not record.repo_path or not os.path.exists(record.repo_path):
        raise HTTPException(
            status_code=410,
            detail="Repository files have been cleaned up after analysis. File content is no longer available.",
        )

    try:
        content = git_service.get_file_content(record.repo_path, file_path)
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

from pydantic import BaseModel

class FileUpdateRequest(BaseModel):
    file_path: str
    content: str

@router.put("/files/{analysis_id}")
async def update_file_content(
    analysis_id: str,
    req: FileUpdateRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Update file content in an analyzed repository (sandbox edit). Works for both authenticated and anonymous users."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    import os
    if not record.repo_path or not os.path.exists(record.repo_path):
        raise HTTPException(
            status_code=410,
            detail="Repository files have been cleaned up. Cannot save edits.",
        )

    try:
        git_service.put_file_content(record.repo_path, req.file_path, req.content)
        return {"message": "File updated successfully"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
