"""
Archaeology API Routes
Endpoints for git blame, bug origin tracing, commit timeline, and heatmaps.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, AnalysisResult
from app.services.archaeology_service import archaeology_service

router = APIRouter(prefix="/api/archaeology")


def _get_repo_path(analysis_id: str, db: Session) -> str:
    """Look up repo_path from analysis record."""
    record = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not record.repo_path:
        raise HTTPException(status_code=400, detail="Repository data not available")
    return record.repo_path


# ─── Blame ────────────────────────────────────────────────────

@router.get("/blame/{analysis_id}")
async def get_blame(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    db: Session = Depends(get_db),
):
    """Get line-by-line blame data for a file."""
    repo_path = _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_file_blame(repo_path, file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blame failed: {str(e)}")


# ─── Bug Origin Trace ────────────────────────────────────────

@router.get("/trace/{analysis_id}")
async def trace_origin(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    line: int = Query(..., description="Line number to trace"),
    db: Session = Depends(get_db),
):
    """Trace a line back to its origin commit with evolution chain."""
    repo_path = _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.trace_bug_origin(repo_path, file_path, line)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trace failed: {str(e)}")


# ─── Commit Timeline ─────────────────────────────────────────

@router.get("/timeline/{analysis_id}")
async def get_timeline(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    max_commits: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get chronological commit timeline for a file."""
    repo_path = _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_commit_timeline(
            repo_path, file_path, max_commits
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeline failed: {str(e)}")


# ─── Blame Heatmap ────────────────────────────────────────────

@router.get("/heatmap/{analysis_id}")
async def get_heatmap(
    analysis_id: str,
    file_path: str = Query(..., description="Path to file within repo"),
    db: Session = Depends(get_db),
):
    """Get blame heatmap data for visualization."""
    repo_path = _get_repo_path(analysis_id, db)

    try:
        return archaeology_service.get_blame_heatmap(repo_path, file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heatmap failed: {str(e)}")
