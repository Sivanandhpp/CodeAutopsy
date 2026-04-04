"""
Analysis API Routes (Async + Auth)
====================================
Endpoints for starting analysis, getting results, streaming progress,
reading files, and re-analysis. Supports concurrent analysis with proper
cancellation and error handling.
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
    IssueDetail, OllamaFinding,
)
from app.services.git_service import git_service
from app.services.static_analyzer import static_analyzer
from app.services.ollama_service import analyze_files_batch
from app.services.reanalysis_service import get_latest_commit_sha
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


# ─── Background Analysis Task ───────────────────────────────

async def run_analysis_task(analysis_id: str, repo_url: str):
    """
    Background task that clones repo, runs analysis, and stores results.
    Handles cancellation and errors gracefully without crashing.
    """
    semaphore = _get_analysis_semaphore()

    async with semaphore:
        async with get_standalone_session() as db:
            try:
                await _execute_analysis(analysis_id, repo_url, db)
            except asyncio.CancelledError:
                logger.info(f"Analysis {analysis_id[:8]} was cancelled")
                await _update_status(db, analysis_id, "cancelled", error="Analysis was cancelled by user")
                progress_tracker.update(analysis_id, "cancelled", 0, "Analysis cancelled", "cancelled")
            except Exception as e:
                logger.error(f"Analysis {analysis_id[:8]} failed: {e}", exc_info=True)
                try:
                    await _update_status(db, analysis_id, "failed", error=str(e)[:2000])
                except Exception:
                    pass
                progress_tracker.update(analysis_id, "failed", 0, f"Analysis failed: {str(e)[:200]}", "error")
            finally:
                _active_analyses.pop(analysis_id, None)


async def _execute_analysis(analysis_id: str, repo_url: str, db: AsyncSession):
    """Core analysis pipeline — separated for clean error handling."""

    # Step 1: Clone repository
    progress_tracker.update(analysis_id, "cloning", 10, "Cloning repository...", "clone")

    repo_path, repo_name = await asyncio.to_thread(
        git_service.clone_repository, repo_url
    )

    progress_tracker.update(analysis_id, "cloning", 25, f"Repository cloned: {repo_name}", "clone")

    # Get HEAD SHA for caching
    head_sha = await asyncio.to_thread(_get_head_sha, repo_path)

    # Update DB record with repo info
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
    progress_tracker.update(analysis_id, "analyzing", 35, "Extracting file tree...", "file_tree")

    file_tree = await asyncio.to_thread(git_service.get_file_tree, repo_path)
    languages = await asyncio.to_thread(git_service.get_language_stats, file_tree)
    total_lines = await asyncio.to_thread(git_service.get_total_lines, file_tree)

    progress_tracker.update(
        analysis_id, "analyzing", 45,
        f"Found {len(file_tree)} files, {total_lines:,} lines of code",
        "file_tree",
    )

    # Step 3: Run static analysis (Semgrep / regex)
    progress_tracker.update(analysis_id, "analyzing", 50, "Running security analysis...", "static_analysis")

    issues = await asyncio.to_thread(static_analyzer.run_analysis, repo_path, file_tree)

    progress_tracker.update(
        analysis_id, "analyzing", 65,
        f"Found {len(issues)} potential issues",
        "static_analysis",
    )

    # Step 4: Run Ollama AI analysis (if available)
    progress_tracker.update(analysis_id, "analyzing", 68, "Running AI deep analysis...", "ai_analysis")

    ollama_findings = []
    try:
        async def ollama_progress(done, total):
            pct = 68 + int((done / max(total, 1)) * 17)  # 68% → 85%
            progress_tracker.update(
                analysis_id, "analyzing", pct,
                f"AI analyzing files ({done}/{total})...",
                "ai_analysis",
            )

        ollama_findings = await analyze_files_batch(
            files=file_tree,
            repo_path=repo_path,
            progress_callback=ollama_progress,
        )
    except Exception as e:
        logger.warning(f"Ollama analysis failed (non-fatal): {e}")

    progress_tracker.update(
        analysis_id, "analyzing", 85,
        f"AI analysis complete: {len(ollama_findings)} findings",
        "ai_analysis",
    )

    # Step 5: Calculate health score
    progress_tracker.update(analysis_id, "analyzing", 90, "Calculating health score...", "scoring")

    health_score = static_analyzer.calculate_health_score(issues)

    # Step 6: Store results
    progress_tracker.update(analysis_id, "analyzing", 95, "Saving results...", "saving")

    # Add issue counts to file tree
    issue_counts: dict[str, int] = {}
    for issue in issues:
        fp = issue.get("file_path", "")
        issue_counts[fp] = issue_counts.get(fp, 0) + 1

    for f in file_tree:
        f["issue_count"] = issue_counts.get(f["path"], 0)

    # Update database record
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.status = "complete"
        record.health_score = health_score
        record.total_issues = len(issues)
        record.file_count = len(file_tree)
        record.total_lines = total_lines
        record.set_languages(languages)
        record.set_issues(issues)
        record.set_file_tree(file_tree)
        record.set_ollama_findings(ollama_findings)
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

    progress_tracker.update(
        analysis_id, "complete", 100,
        f"Analysis complete! Health score: {health_score}/100, {len(issues)} issues found",
        "complete",
    )


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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start analysis of a GitHub repository."""
    check_rate_limit(str(user.id))

    analysis_id = str(uuid.uuid4())
    project_id = req.project_id

    # If no project specified, create one automatically
    if project_id is None:
        repo_name = req.repo_url.split("github.com/")[-1].strip("/")
        project = Project(repo_url=req.repo_url, repo_name=repo_name)
        db.add(project)
        await db.flush()

        user_project = UserProject(user_id=user.id, project_id=project.id, role="owner")
        db.add(user_project)
        await db.flush()

        project_id = project.id

    # Create analysis record
    record = AnalysisResult(
        id=analysis_id,
        project_id=project_id,
        repo_url=req.repo_url,
        status="queued",
    )
    db.add(record)
    await db.flush()

    # Initialize progress tracker
    progress_tracker.create(analysis_id)

    # Start background analysis task
    task = asyncio.create_task(run_analysis_task(analysis_id, req.repo_url))
    _active_analyses[analysis_id] = task

    logger.info(f"Analysis started: {analysis_id[:8]} for {req.repo_url} by {user.username}")

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get analysis results by ID."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Build response
    issues = record.get_issues()
    ollama_findings = record.get_ollama_findings()

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
        ollama_findings=[
            OllamaFinding(**f) for f in ollama_findings
            if isinstance(f, dict) and "description" in f
        ],
        error_message=record.error_message,
        created_at=record.created_at.isoformat() if record.created_at else None,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )


@router.get("/analyze/stream/{analysis_id}")
async def stream_progress(analysis_id: str):
    """Server-Sent Events endpoint for real-time progress updates."""

    async def event_generator():
        while True:
            progress = progress_tracker.get(analysis_id)

            event_data = json.dumps({
                "analysis_id": analysis_id,
                "status": progress.get("status", "unknown"),
                "progress": progress.get("progress", 0),
                "message": progress.get("message", ""),
                "current_step": progress.get("current_step", ""),
            })

            yield f"data: {event_data}\n\n"

            if progress.get("status") in ("complete", "failed", "cancelled", "unknown"):
                break

            await asyncio.sleep(1)

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get file content from an analyzed repository."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not record.repo_path:
        raise HTTPException(status_code=400, detail="Repository data not available")

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
