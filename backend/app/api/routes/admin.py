"""
Admin API Routes
================
Protected endpoints for admin panel operations.
All routes require admin privileges via the require_admin dependency.
"""

import csv
import io
import json
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.analysis_rule import AnalysisRule
from app.api.deps import require_admin
from app.services import admin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ─── System Stats ──────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get system-wide statistics."""
    return await admin_service.get_system_stats(db)


# ─── User Management ──────────────────────────────────────────

@router.get("/users")
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with enriched metadata."""
    users = await admin_service.get_all_users(db)
    return {"users": users, "total": len(users)}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user and cascade-delete all associated data."""
    try:
        details = await admin_service.delete_user(db, user_id, admin)
        return {"message": "User deleted successfully", "details": details}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ─── Repository Management ────────────────────────────────────

@router.get("/repos")
async def list_repos(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all repositories with enriched metadata."""
    repos = await admin_service.get_all_repos(db)
    return {"repos": repos, "total": len(repos)}


@router.delete("/repos/{project_id}")
async def delete_repo(
    project_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific repository and all associated data."""
    try:
        details = await admin_service.delete_repo(db, project_id, admin)
        return {"message": "Repository deleted successfully", "details": details}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/repos-all")
async def delete_all_repos(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete ALL repositories and associated data. Irreversible."""
    details = await admin_service.delete_all_repos(db, admin)
    return {"message": "All repositories deleted successfully", "details": details}


# ─── Audit Logs ────────────────────────────────────────────────

@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get recent audit log entries."""
    logs = await admin_service.get_audit_logs(db, limit)
    return {"logs": logs, "total": len(logs)}


# ─── Rules Management (Enhanced for Admin) ────────────────────

@router.get("/rules")
async def list_all_rules(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    language: Optional[str] = Query(None),
    defect_family: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """List all analysis rules with optional filtering (admin view)."""
    query = select(AnalysisRule)

    if language:
        query = query.where(AnalysisRule.language == language)
    if defect_family:
        query = query.where(AnalysisRule.defect_family == defect_family)
    if severity:
        query = query.where(AnalysisRule.severity == severity)
    if is_active is not None:
        query = query.where(AnalysisRule.is_active == is_active)

    result = await db.execute(query.order_by(AnalysisRule.created_at.desc()))
    rules = result.scalars().all()

    rules_data = []
    for r in rules:
        rules_data.append({
            "id": str(r.id),
            "rule_id": r.rule_id,
            "name": r.name,
            "description": r.description,
            "language": r.language,
            "defect_family": r.defect_family,
            "severity": r.severity,
            "pattern": r.pattern,
            "match_type": r.match_type,
            "message": r.message,
            "fix_hint": r.fix_hint,
            "cwe_id": r.cwe_id,
            "owasp_ref": r.owasp_ref,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })

    return {"rules": rules_data, "total": len(rules_data)}


@router.post("/rules/bulk-json")
async def bulk_import_rules_json(
    rules: list[dict],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Import analysis rules in bulk from JSON array."""
    if not rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rules provided",
        )

    if len(rules) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 500 rules per import",
        )

    result = await admin_service.bulk_import_rules(db, rules, admin)
    return result


@router.post("/rules/bulk-csv")
async def bulk_import_rules_csv(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Import analysis rules from a CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV",
        )

    try:
        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rules_data = []
        for row in reader:
            # Convert 'is_active' string to bool
            if "is_active" in row:
                row["is_active"] = row["is_active"].lower() in ("true", "1", "yes")
            rules_data.append(dict(row))

        if len(rules_data) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 500 rules per import",
            )

        result = await admin_service.bulk_import_rules(db, rules_data, admin)
        return result

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV encoding. Please use UTF-8.",
        )
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}",
        )


@router.patch("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a rule's active status."""
    result = await db.execute(
        select(AnalysisRule).where(AnalysisRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    await db.flush()

    await admin_service._log_action(
        db, admin,
        "rule_toggled",
        "rule",
        rule_id,
        {"is_active": rule.is_active, "name": rule.name},
    )

    return {
        "message": f"Rule {'activated' if rule.is_active else 'deactivated'}",
        "is_active": rule.is_active,
    }


@router.delete("/rules/{rule_id}")
async def hard_delete_rule(
    rule_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete an analysis rule."""
    result = await db.execute(
        select(AnalysisRule).where(AnalysisRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_name = rule.name
    await db.delete(rule)
    await db.flush()

    await admin_service._log_action(
        db, admin,
        "rule_deleted",
        "rule",
        rule_id,
        {"name": rule_name},
    )

    return {"message": "Rule permanently deleted"}
