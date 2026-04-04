"""
Archaeology API Routes (Async + Auth)
======================================
Endpoints for git blame, bug origin tracing, commit timeline, and heatmaps.
All endpoints require authentication.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.services.archaeology_service import archaeology_service
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/archaeology", tags=["Archaeology"])


async def _get_repo_path(analysis_id: str, db: AsyncSession) -> str:
    """Look up repo_path from analysis record."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not record.repo_path:
        raise HTTPException(status_code=400, detail="Repository data not available")
    return record.repo_path


# ─── Blame ───────────────────────────────────────────────────

@router.get("/blame/{analysis_id}")
async def get_blame(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get line-by-line blame data for a file."""
    repo_path = await _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_file_blame(repo_path, file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Blame failed for {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Blame failed: {str(e)}")


# ─── Bug Origin Trace ───────────────────────────────────────

@router.get("/trace/{analysis_id}")
async def trace_origin(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    line: int = Query(..., description="Line number to trace"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trace a line back to its origin commit with evolution chain."""
    repo_path = await _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.trace_bug_origin(repo_path, file_path, line)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Trace failed for {file_path}:{line}: {e}")
        raise HTTPException(status_code=500, detail=f"Trace failed: {str(e)}")


# ─── Commit Timeline ────────────────────────────────────────

@router.get("/timeline/{analysis_id}")
async def get_timeline(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    max_commits: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chronological commit timeline for a file."""
    repo_path = await _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_commit_timeline(
            repo_path, file_path, max_commits
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Timeline failed for {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Timeline failed: {str(e)}")


# ─── Blame Heatmap ───────────────────────────────────────────

@router.get("/heatmap/{analysis_id}")
async def get_heatmap(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get blame heatmap data for visualization."""
    repo_path = await _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_blame_heatmap(repo_path, file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Heatmap failed for {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Heatmap failed: {str(e)}")
