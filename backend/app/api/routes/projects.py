"""
Projects API Routes
===================
CRUD operations for projects and collaboration management.
Supports owner, editor, and viewer roles.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.project import Project, UserProject
from app.models.analysis import AnalysisResult
from app.models.schemas import (
    ProjectCreateRequest, ProjectResponse, ProjectListResponse,
    CollaboratorAddRequest, CollaboratorResponse,
    AnalysisResultResponse, IssueDetail, OllamaFinding,
)
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["Projects"])


# ─── Helpers ─────────────────────────────────────────────────

def _build_project_response(
    project: Project,
    user_role: str,
    include_analysis: bool = True,
) -> ProjectResponse:
    """Convert a Project ORM object to a ProjectResponse schema."""
    collaborators = [
        CollaboratorResponse(
            user_id=up.user.id,
            username=up.user.username,
            email=up.user.email,
            role=up.role,
            added_at=up.added_at,
        )
        for up in project.users
        if up.user is not None
    ]

    latest_analysis = None
    if include_analysis and project.analyses:
        a = project.analyses[0]  # Already ordered desc by created_at
        latest_analysis = AnalysisResultResponse(
            id=a.id,
            project_id=a.project_id,
            repo_url=a.repo_url,
            repo_name=a.repo_name,
            clone_path=a.clone_path,
            status=a.status,
            health_score=a.health_score,
            total_issues=a.total_issues,
            file_count=a.file_count,
            total_lines=a.total_lines,
            languages=a.get_languages(),
            issues=[],     # Don't include full issues in project listing
            file_tree=[],  # Don't include full file tree in project listing
            error_message=a.error_message,
            created_at=a.created_at.isoformat() if a.created_at else None,
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
        )

    return ProjectResponse(
        id=project.id,
        repo_url=project.repo_url,
        repo_name=project.repo_name,
        description=project.description,
        last_commit_sha=project.last_commit_sha,
        created_at=project.created_at,
        updated_at=project.updated_at,
        role=user_role,
        collaborators=collaborators,
        latest_analysis=latest_analysis,
    )


async def _get_user_project(
    project_id: UUID,
    user: User,
    db: AsyncSession,
    required_roles: list[str] | None = None,
) -> tuple[Project, UserProject]:
    """Fetch a project and verify user access. Raises 403/404 as needed."""
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.users).selectinload(UserProject.user),
            selectinload(Project.analyses),
        )
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Find user's role in this project
    user_project = None
    for up in project.users:
        if up.user_id == user.id:
            user_project = up
            break

    if user_project is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    if required_roles and user_project.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires one of these roles: {', '.join(required_roles)}",
        )

    return project, user_project


# ─── List Projects ───────────────────────────────────────────

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all projects the authenticated user has access to."""
    result = await db.execute(
        select(UserProject)
        .options(
            selectinload(UserProject.project)
            .selectinload(Project.users)
            .selectinload(UserProject.user),
            selectinload(UserProject.project)
            .selectinload(Project.analyses),
        )
        .where(UserProject.user_id == user.id)
        .order_by(UserProject.added_at.desc())
    )
    user_projects = result.scalars().unique().all()

    projects = [
        _build_project_response(up.project, up.role)
        for up in user_projects
    ]

    return ProjectListResponse(projects=projects, total=len(projects))


# ─── Create Project ─────────────────────────────────────────

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project. The creator becomes the owner."""
    # Extract repo name from URL
    repo_name = req.repo_url.split("github.com/")[-1].strip("/")

    project = Project(
        repo_url=req.repo_url,
        repo_name=repo_name,
        description=req.description,
    )
    db.add(project)
    await db.flush()

    # Link user as owner
    user_project = UserProject(
        user_id=user.id,
        project_id=project.id,
        role="owner",
    )
    db.add(user_project)
    await db.flush()
    await db.refresh(project)

    logger.info(f"Project created: {repo_name} by {user.username}")

    return _build_project_response(project, "owner", include_analysis=False)


# ─── Get Project Details ────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed project information including collaborators."""
    project, user_project = await _get_user_project(project_id, user, db)
    return _build_project_response(project, user_project.role)


# ─── Add Collaborator ───────────────────────────────────────

@router.post("/{project_id}/collaborators", response_model=CollaboratorResponse)
async def add_collaborator(
    project_id: UUID,
    req: CollaboratorAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a user to the project. Only owners can add collaborators."""
    project, _ = await _get_user_project(project_id, user, db, required_roles=["owner"])

    # Find target user by username
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{req.username}' not found",
        )

    # Check if already a collaborator
    result = await db.execute(
        select(UserProject).where(
            and_(
                UserProject.user_id == target_user.id,
                UserProject.project_id == project_id,
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{req.username}' is already a collaborator",
        )

    # Add collaborator
    new_up = UserProject(
        user_id=target_user.id,
        project_id=project_id,
        role=req.role,
    )
    db.add(new_up)
    await db.flush()

    logger.info(
        f"Collaborator added: {target_user.username} as {req.role} "
        f"to project {project.repo_name} by {user.username}"
    )

    return CollaboratorResponse(
        user_id=target_user.id,
        username=target_user.username,
        email=target_user.email,
        role=req.role,
        added_at=new_up.added_at,
    )


# ─── Remove Collaborator ────────────────────────────────────

@router.delete("/{project_id}/collaborators/{target_user_id}")
async def remove_collaborator(
    project_id: UUID,
    target_user_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a collaborator from the project. Only owners can remove."""
    await _get_user_project(project_id, user, db, required_roles=["owner"])

    # Can't remove yourself as owner
    if target_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself as owner. Transfer ownership first.",
        )

    result = await db.execute(
        select(UserProject).where(
            and_(
                UserProject.user_id == target_user_id,
                UserProject.project_id == project_id,
            )
        )
    )
    up = result.scalar_one_or_none()

    if up is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found",
        )

    await db.delete(up)
    await db.flush()

    logger.info(f"Collaborator {target_user_id} removed from project {project_id}")
    return {"message": "Collaborator removed successfully"}

# ─── Delete Project ─────────────────────────────────────────

@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project, its analyses, and physically remove repositories from the sandbox."""
    project, _ = await _get_user_project(project_id, user, db, required_roles=["owner"])

    import os
    import shutil
    import asyncio
    
    # 1. Physically delete repository folders
    # Project loads analyses thanks to selectinload setup in _get_user_project
    for analysis in project.analyses:
        repo_path = analysis.clone_path or analysis.repo_path
        if repo_path and os.path.exists(repo_path):
            try:
                # Do safely in a thread to not block event loop
                await asyncio.to_thread(shutil.rmtree, repo_path, ignore_errors=True)
                logger.info(f"Deleted physical repo sandbox: {repo_path}")
            except Exception as e:
                logger.error(f"Failed to delete repo sandbox {repo_path}: {e}")

    # 2. Delete the Project record. 
    # Provided that SQLAlchemy relationships are configured with cascade="all, delete-orphan",
    # deleting the project will cascade delete AnalysisResult and UserProject associations.
    await db.delete(project)
    await db.commit()

    logger.info(f"Project {project_id} and all tied analyses deleted by {user.username}")
    return {"message": "Project and sandbox data deleted successfully"}
