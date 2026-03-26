"""
Analysis API Routes
Endpoints for starting analysis, getting results, streaming progress, and reading files.
"""

import os
import uuid
import json
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db, AnalysisResult, get_session_factory
from app.models.schemas import (
    AnalyzeRequest, AnalyzeResponse, AnalysisResultResponse, IssueDetail
)
from app.services.git_service import git_service
from app.services.static_analyzer import static_analyzer
from app.utils.progress import progress_tracker

router = APIRouter()


# ─── In-memory rate limiter (simple) ─────────────────────────

_rate_limit = {}  # IP -> list of timestamps
MAX_ANALYSES_PER_HOUR = 5


def check_rate_limit(request: Request):
    """Simple IP-based rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).timestamp()
    
    if client_ip not in _rate_limit:
        _rate_limit[client_ip] = []
    
    # Remove entries older than 1 hour
    _rate_limit[client_ip] = [t for t in _rate_limit[client_ip] if now - t < 3600]
    
    if len(_rate_limit[client_ip]) >= MAX_ANALYSES_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {MAX_ANALYSES_PER_HOUR} analyses per hour."
        )
    
    _rate_limit[client_ip].append(now)


# ─── Background Analysis Task ────────────────────────────────

async def run_analysis_task(analysis_id: str, repo_url: str):
    """Background task that clones repo, runs analysis, and stores results via JSON caching and DB."""
    async_session = get_session_factory()
    
    async with async_session() as db:
        try:
            # Step 1: Clone repository
            progress_tracker.update(analysis_id, 'cloning', 10, 'Cloning/syncing repository...', 'clone')
            
            repo_path, repo_name, has_updates, changed_files = git_service.sync_repository(repo_url)
            
            progress_tracker.update(analysis_id, 'cloning', 25, f'Repository synced: {repo_name}', 'clone')
            
            # Update DB record
            result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == analysis_id))
            record = result.scalars().first()
            if record:
                record.repo_name = repo_name
                record.repo_path = repo_path
                record.status = 'analyzing'
                await db.commit()
            
            report_file = os.path.join(repo_path, 'codeautopsy_report.json')
            cached_data = None
            
            if not has_updates and os.path.exists(report_file):
                # Load from cache
                progress_tracker.update(analysis_id, 'analyzing', 90, 'Loading cached analysis...', 'cache')
                with open(report_file, 'r') as f:
                    cached_data = json.load(f)
                    
                health_score = cached_data.get('health_score', 0)
                issues = cached_data.get('issues', [])
                file_tree = cached_data.get('file_tree', [])
                languages = cached_data.get('languages', {})
                total_lines = cached_data.get('total_lines', 0)
            else:
                # Step 2: Extract file tree
                progress_tracker.update(analysis_id, 'analyzing', 35, 'Extracting file tree...', 'file_tree')
                
                file_tree = git_service.get_file_tree(repo_path)
                languages = git_service.get_language_stats(file_tree)
                total_lines = git_service.get_total_lines(file_tree)
                
                progress_tracker.update(
                    analysis_id, 'analyzing', 45,
                    f'Found {len(file_tree)} files, {total_lines} lines of code',
                    'file_tree'
                )
                
                # Step 3: Run static analysis
                progress_tracker.update(analysis_id, 'analyzing', 55, 'Running security analysis...', 'static_analysis')
                
                # For partial updates in the future, we could pass `changed_files` to `run_analysis`.
                # Currently doing full analysis if updates exist.
                issues = static_analyzer.run_analysis(repo_path, file_tree)
                
                progress_tracker.update(
                    analysis_id, 'analyzing', 80,
                    f'Found {len(issues)} potential issues',
                    'static_analysis'
                )
                
                # Step 4: Calculate health score
                progress_tracker.update(analysis_id, 'analyzing', 90, 'Calculating health score...', 'scoring')
                
                health_score = static_analyzer.calculate_health_score(issues)
                
                # Add issue counts to file tree
                issue_counts = {}
                for issue in issues:
                    fp = issue.get('file_path', '')
                    issue_counts[fp] = issue_counts.get(fp, 0) + 1
                
                for f in file_tree:
                    f['issue_count'] = issue_counts.get(f['path'], 0)
                
                # Save cache
                cached_data = {
                    'health_score': health_score,
                    'total_issues': len(issues),
                    'file_count': len(file_tree),
                    'total_lines': total_lines,
                    'languages': languages,
                    'issues': issues,
                    'file_tree': file_tree
                }
                with open(report_file, 'w') as f:
                    json.dump(cached_data, f)
            
            # Step 5: Store results in DB
            progress_tracker.update(analysis_id, 'analyzing', 95, 'Saving results...', 'saving')
            
            result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == analysis_id))
            record = result.scalars().first()
            if record:
                record.status = 'complete'
                record.health_score = health_score
                record.total_issues = len(issues)
                record.file_count = len(file_tree)
                record.total_lines = total_lines
                record.set_languages(languages)
                record.set_issues(issues)
                record.set_file_tree(file_tree)
                record.completed_at = datetime.now(timezone.utc)
                await db.commit()
            
            progress_tracker.update(
                analysis_id, 'complete', 100,
                f'Analysis complete! Health score: {health_score}/100, {len(issues)} issues found. Handled {"caching" if not has_updates else "new changes"}.',
                'complete'
            )
            
        except Exception as e:
            # Update status to failed
            progress_tracker.update(analysis_id, 'failed', 0, f'Analysis failed: {str(e)}', 'error')
            
            result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == analysis_id))
            record = result.scalars().first()
            if record:
                record.status = 'failed'
                record.error_message = str(e)
                await db.commit()


# ─── Endpoints ────────────────────────────────────────────────

@router.post("/analyze/github", response_model=AnalyzeResponse)
async def analyze_github_repo(
    req: AnalyzeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start analysis of a GitHub repository."""
    # Rate limiting
    check_rate_limit(request)
    
    # Create analysis record
    analysis_id = str(uuid.uuid4())
    
    record = AnalysisResult(
        id=analysis_id,
        repo_url=req.repo_url,
        status='queued',
    )
    db.add(record)
    await db.commit()
    
    # Initialize progress tracker
    progress_tracker.create(analysis_id)
    
    background_tasks.add_task(
        run_analysis_task,
        analysis_id,
        req.repo_url,
    )
    
    return AnalyzeResponse(
        analysis_id=analysis_id,
        status='queued',
        message='Analysis started. Use the analysis ID to track progress.',
    )


@router.get("/results/{analysis_id}", response_model=AnalysisResultResponse)
async def get_results(analysis_id: str, db: AsyncSession = Depends(get_db)):
    """Get analysis results by ID."""
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == analysis_id))
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return AnalysisResultResponse(
        id=record.id,
        repo_url=record.repo_url,
        repo_name=record.repo_name,
        status=record.status,
        health_score=record.health_score,
        total_issues=record.total_issues,
        file_count=record.file_count,
        total_lines=record.total_lines,
        languages=record.get_languages(),
        issues=[IssueDetail(**i) for i in record.get_issues()],
        file_tree=record.get_file_tree(),
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
                'analysis_id': analysis_id,
                'status': progress.get('status', 'unknown'),
                'progress': progress.get('progress', 0),
                'message': progress.get('message', ''),
                'current_step': progress.get('current_step', ''),
            })
            
            yield f"data: {event_data}\n\n"
            
            # Stop streaming if analysis is complete or failed
            if progress.get('status') in ('complete', 'failed', 'unknown'):
                break
            
            await asyncio.sleep(1)  # Poll every second
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/files/{analysis_id}")
async def get_file_content(
    analysis_id: str,
    file_path: str,
    db: AsyncSession = Depends(get_db),
):
    """Get file content from an analyzed repository."""
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == analysis_id))
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if not record.repo_path:
        raise HTTPException(status_code=400, detail="Repository data not available")
    
    try:
        content = git_service.get_file_content(record.repo_path, file_path)
        language = git_service.detect_language(file_path.split('/')[-1])
        
        return {
            'file_path': file_path,
            'content': content,
            'language': language,
            'lines': content.count('\n') + 1,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
