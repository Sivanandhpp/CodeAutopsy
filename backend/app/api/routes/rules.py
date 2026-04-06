"""Rules API Routes
Manage database-driven analysis rules.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis_rule import AnalysisRule
from app.models.schemas import RuleCreate, RuleUpdate, RuleResponse
from app.models.user import User
from app.api.deps import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules", tags=["Rules"])


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    language: Optional[str] = Query(None),
    defect_family: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """List rules with optional filtering."""
    query = select(AnalysisRule)

    if language:
        query = query.where(AnalysisRule.language == language)
    if defect_family:
        query = query.where(AnalysisRule.defect_family == defect_family)
    if severity:
        query = query.where(AnalysisRule.severity == severity)
    if is_active is not None:
        query = query.where(AnalysisRule.is_active == is_active)

    result = await db.execute(query.order_by(AnalysisRule.rule_id))
    return result.scalars().all()


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    req: RuleCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new analysis rule (admin only)."""
    existing = await db.execute(
        select(AnalysisRule).where(AnalysisRule.rule_id == req.rule_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rule with this rule_id already exists",
        )

    rule = AnalysisRule(**req.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    logger.info("Rule created: %s", rule.rule_id)
    return rule


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    req: RuleUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing rule (admin only)."""
    result = await db.execute(
        select(AnalysisRule).where(AnalysisRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a rule by setting is_active = false (admin only)."""
    result = await db.execute(
        select(AnalysisRule).where(AnalysisRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = False
    await db.flush()

    logger.info("Rule deactivated: %s", rule.rule_id)
    return {"message": "Rule deactivated"}
