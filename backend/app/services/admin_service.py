"""
Admin Service
=============
Core business logic for admin operations.
All operations are atomic (single DB session) with proper cascade deletes
and filesystem cleanup.
"""

import json
import logging
import os
import shutil
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.project import Project, UserProject
from app.models.analysis import AnalysisResult
from app.models.audit_log import AuditLog
from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Audit Logging Helper ──────────────────────────────────────

async def _log_action(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str = None,
    target_id: str = None,
    details: dict = None,
) -> None:
    """Record an admin action in the audit log."""
    entry = AuditLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        details=json.dumps(details, default=str) if details else None,
    )
    db.add(entry)
    await db.flush()


# ─── System Stats ──────────────────────────────────────────────

async def get_system_stats(db: AsyncSession) -> dict:
    """Get global system statistics."""
    # Total users
    user_count = (await db.execute(
        select(func.count()).select_from(User)
    )).scalar() or 0

    # Total projects
    project_count = (await db.execute(
        select(func.count()).select_from(Project)
    )).scalar() or 0

    # Total analyses
    analysis_count = (await db.execute(
        select(func.count()).select_from(AnalysisResult)
    )).scalar() or 0

    # Completed analyses
    completed_count = (await db.execute(
        select(func.count()).select_from(AnalysisResult).where(
            AnalysisResult.status == "complete"
        )
    )).scalar() or 0

    # Total storage (scan filesystem)
    settings = get_settings()
    total_storage = 0
    repos_dir = settings.REPOS_DIR
    try:
        if os.path.exists(repos_dir):
            total_storage = await asyncio.to_thread(_get_dir_size, repos_dir)
    except Exception as e:
        logger.warning(f"Could not calculate storage: {e}")

    return {
        "total_users": user_count,
        "total_projects": project_count,
        "total_analyses": analysis_count,
        "completed_analyses": completed_count,
        "total_storage_bytes": total_storage,
        "total_storage_mb": round(total_storage / (1024 * 1024), 2) if total_storage else 0,
    }


# ─── User Management ──────────────────────────────────────────

async def get_all_users(db: AsyncSession) -> list[dict]:
    """List all users with enriched data (repo count, storage)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.projects).selectinload(UserProject.project))
        .order_by(User.created_at.desc())
    )
    users = result.scalars().unique().all()

    user_list = []
    for u in users:
        # Count repos this user owns/collaborates on
        project_ids = [up.project_id for up in u.projects]
        repo_count = len(project_ids)

        # Calculate storage for user's repos
        storage = 0
        if project_ids:
            analyses_result = await db.execute(
                select(AnalysisResult).where(
                    AnalysisResult.project_id.in_(project_ids)
                )
            )
            analyses = analyses_result.scalars().all()
            for a in analyses:
                clone_path = a.clone_path or a.repo_path
                if clone_path and os.path.exists(clone_path):
                    try:
                        storage += _get_dir_size(clone_path)
                    except Exception:
                        pass

        projects_data = []
        for up in u.projects:
            proj = up.project
            if proj:
                projects_data.append({
                    "id": str(proj.id),
                    "repo_name": proj.repo_name,
                    "repo_url": proj.repo_url,
                    "role": up.role,
                })

        user_list.append({
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "repo_count": repo_count,
            "storage_bytes": storage,
            "storage_mb": round(storage / (1024 * 1024), 2) if storage else 0,
            "projects": projects_data,
        })

    return user_list


async def delete_user(db: AsyncSession, user_id: UUID, admin: User) -> dict:
    """
    Delete a user and cascade-delete all associated data.
    
    Logic:
    - For each project the user is linked to:
      - If user is sole member → delete project + analyses + filesystem
      - If shared → only remove user's link
    - Delete user record (cascades UserProject via ORM)
    """
    if user_id == admin.id:
        raise ValueError("Cannot delete your own admin account")

    # Fetch user with projects
    result = await db.execute(
        select(User).where(User.id == user_id)
        .options(selectinload(User.projects))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")

    deleted_projects = []
    orphaned_projects = []

    # Get all projects this user belongs to
    for up in user.projects:
        project_id = up.project_id

        # Check how many other users share this project
        member_count_result = await db.execute(
            select(func.count()).select_from(UserProject).where(
                UserProject.project_id == project_id,
                UserProject.user_id != user_id,
            )
        )
        other_members = member_count_result.scalar() or 0

        if other_members == 0:
            # Sole member — delete entire project
            proj_result = await db.execute(
                select(Project).where(Project.id == project_id)
                .options(selectinload(Project.analyses))
            )
            project = proj_result.scalar_one_or_none()
            if project:
                # Delete filesystem repos
                for analysis in project.analyses:
                    await _cleanup_repo_files(analysis)

                await db.delete(project)
                deleted_projects.append(str(project_id))
        else:
            orphaned_projects.append(str(project_id))

    # Delete user record (cascades user_projects via ORM)
    await db.delete(user)
    await db.flush()

    details = {
        "username": user.username,
        "email": user.email,
        "deleted_projects": deleted_projects,
        "removed_from_projects": orphaned_projects,
    }

    await _log_action(db, admin, "user_deleted", "user", str(user_id), details)

    logger.info(f"Admin {admin.username} deleted user {user.username} (id={user_id})")
    return details


# ─── Repository Management ────────────────────────────────────

async def get_all_repos(db: AsyncSession) -> list[dict]:
    """List all repositories with enriched data."""
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.users).selectinload(UserProject.user),
            selectinload(Project.analyses),
        )
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().unique().all()

    repo_list = []
    for p in projects:
        # Users linked to this project
        users_data = []
        for up in p.users:
            if up.user:
                users_data.append({
                    "id": str(up.user.id),
                    "username": up.user.username,
                    "role": up.role,
                })

        # Latest analysis data
        latest = p.analyses[0] if p.analyses else None
        storage = 0
        last_analyzed = None
        total_issues = 0

        if latest:
            last_analyzed = latest.completed_at.isoformat() if latest.completed_at else (
                latest.created_at.isoformat() if latest.created_at else None
            )
            total_issues = latest.total_issues or 0
            clone_path = latest.clone_path or latest.repo_path
            if clone_path and os.path.exists(clone_path):
                try:
                    storage = _get_dir_size(clone_path)
                except Exception:
                    pass

        # Sum across all analyses for total issues
        all_issues = sum(a.total_issues or 0 for a in p.analyses)

        repo_list.append({
            "id": str(p.id),
            "repo_name": p.repo_name,
            "repo_url": p.repo_url,
            "description": p.description,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "last_analyzed": last_analyzed,
            "analysis_count": len(p.analyses),
            "total_issues": all_issues,
            "storage_bytes": storage,
            "storage_mb": round(storage / (1024 * 1024), 2) if storage else 0,
            "users": users_data,
            "status": latest.status if latest else "none",
        })

    return repo_list


async def delete_repo(db: AsyncSession, project_id: UUID, admin: User) -> dict:
    """Delete a specific project and all associated data."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
        .options(
            selectinload(Project.users).selectinload(UserProject.user),
            selectinload(Project.analyses),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ValueError("Repository not found")

    # Cleanup filesystem
    for analysis in project.analyses:
        await _cleanup_repo_files(analysis)

    details = {
        "repo_name": project.repo_name,
        "repo_url": project.repo_url,
        "affected_users": [up.user.username for up in project.users if up.user],
        "analysis_count": len(project.analyses),
    }

    # Delete project (cascades analyses + user_projects via ORM)
    await db.delete(project)
    await db.flush()

    await _log_action(db, admin, "repo_deleted", "project", str(project_id), details)

    logger.info(f"Admin {admin.username} deleted repo {project.repo_name} (id={project_id})")
    return details


async def delete_all_repos(db: AsyncSession, admin: User) -> dict:
    """Nuclear option: delete ALL repositories, analyses, and filesystem data."""
    # Fetch all projects with analyses
    result = await db.execute(
        select(Project).options(selectinload(Project.analyses))
    )
    projects = result.scalars().unique().all()

    total_deleted = 0
    total_analyses = 0

    for project in projects:
        for analysis in project.analyses:
            await _cleanup_repo_files(analysis)
            total_analyses += 1
        await db.delete(project)
        total_deleted += 1

    await db.flush()

    # Also try to clean up the entire repos directory
    settings = get_settings()
    repos_dir = settings.REPOS_DIR
    try:
        if os.path.exists(repos_dir):
            for item in os.listdir(repos_dir):
                item_path = os.path.join(repos_dir, item)
                if os.path.isdir(item_path):
                    await asyncio.to_thread(shutil.rmtree, item_path, True)
    except Exception as e:
        logger.error(f"Error cleaning repos directory: {e}")

    details = {
        "projects_deleted": total_deleted,
        "analyses_deleted": total_analyses,
    }

    await _log_action(db, admin, "all_repos_deleted", "system", None, details)

    logger.info(f"Admin {admin.username} deleted ALL repos ({total_deleted} projects, {total_analyses} analyses)")
    return details


# ─── Audit Logs ────────────────────────────────────────────────

async def get_audit_logs(db: AsyncSession, limit: int = 50) -> list[dict]:
    """Get recent audit log entries."""
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.admin))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "admin_username": log.admin.username if log.admin else "system",
            "admin_id": str(log.admin_id) if log.admin_id else None,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": json.loads(log.details) if log.details else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


# ─── Bulk Rules Import ────────────────────────────────────────

async def bulk_import_rules(
    db: AsyncSession,
    rules_data: list[dict],
    admin: User,
) -> dict:
    """
    Import analysis rules in bulk.
    Validates each rule, skips duplicates, returns summary.
    """
    from app.models.analysis_rule import AnalysisRule

    created = 0
    skipped = 0
    errors = []

    VALID_SEVERITIES = {"trace", "info", "low", "medium", "high", "critical", "blocker"}
    VALID_FAMILIES = {
        "injection", "auth", "crypto", "secrets", "xss", "path_traversal",
        "deserialization", "ssrf", "reliability", "maintainability",
        "best_practice", "supply_chain",
    }
    VALID_MATCH_TYPES = {"regex_line", "regex_multiline", "ast_semgrep"}

    for i, rule_data in enumerate(rules_data):
        try:
            rule_id = rule_data.get("rule_id", "").strip()
            if not rule_id:
                errors.append({"index": i, "error": "Missing rule_id"})
                continue

            # Check duplicate
            existing = await db.execute(
                select(AnalysisRule).where(AnalysisRule.rule_id == rule_id)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Validate required fields
            name = rule_data.get("name", "").strip()
            pattern = rule_data.get("pattern", "").strip()
            message = rule_data.get("message", "").strip()
            severity = rule_data.get("severity", "").strip().lower()
            defect_family = rule_data.get("defect_family", "").strip().lower()
            match_type = rule_data.get("match_type", "regex_line").strip().lower()
            language = rule_data.get("language", "any").strip().lower()

            if not all([name, pattern, message]):
                errors.append({"index": i, "rule_id": rule_id, "error": "Missing required fields (name, pattern, message)"})
                continue

            if severity not in VALID_SEVERITIES:
                errors.append({"index": i, "rule_id": rule_id, "error": f"Invalid severity: {severity}"})
                continue

            if defect_family not in VALID_FAMILIES:
                errors.append({"index": i, "rule_id": rule_id, "error": f"Invalid defect_family: {defect_family}"})
                continue

            if match_type not in VALID_MATCH_TYPES:
                errors.append({"index": i, "rule_id": rule_id, "error": f"Invalid match_type: {match_type}"})
                continue

            rule = AnalysisRule(
                rule_id=rule_id,
                name=name,
                description=rule_data.get("description", ""),
                language=language,
                defect_family=defect_family,
                severity=severity,
                pattern=pattern,
                match_type=match_type,
                message=message,
                fix_hint=rule_data.get("fix_hint"),
                cwe_id=rule_data.get("cwe_id"),
                owasp_ref=rule_data.get("owasp_ref"),
                is_active=rule_data.get("is_active", True),
            )
            db.add(rule)
            created += 1

        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    await db.flush()

    details = {"created": created, "skipped": skipped, "errors_count": len(errors)}
    await _log_action(db, admin, "rules_bulk_import", "rule", None, details)

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],  # Limit error output
        "total_processed": len(rules_data),
    }


# ─── Helpers ───────────────────────────────────────────────────

def _get_dir_size(path: str) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        pass
    return total


async def _cleanup_repo_files(analysis: AnalysisResult) -> None:
    """Delete cloned repository files for an analysis."""
    repo_path = analysis.clone_path or analysis.repo_path
    if repo_path and os.path.exists(repo_path):
        try:
            await asyncio.to_thread(shutil.rmtree, repo_path, True)
            logger.info(f"Cleaned up repo files: {repo_path}")
        except Exception as e:
            logger.error(f"Failed to clean repo files {repo_path}: {e}")
