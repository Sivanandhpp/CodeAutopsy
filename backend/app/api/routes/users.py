"""
Users API Routes
================
User search for collaboration features.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.schemas import UserSearchResponse, UserSearchResult
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query(..., min_length=2, max_length=50, description="Search by username"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search users by username for adding collaborators to projects.
    Protected: requires authentication.
    Does not return the searching user themselves.
    """
    search_term = f"%{q.strip()}%"

    result = await db.execute(
        select(User)
        .where(
            User.username.ilike(search_term),
            User.id != current_user.id,  # Exclude self
        )
        .order_by(User.username)
        .limit(limit)
    )
    users = result.scalars().all()

    return UserSearchResponse(
        users=[
            UserSearchResult(
                id=u.id,
                username=u.username,
                email=u.email,
            )
            for u in users
        ],
        total=len(users),
    )
