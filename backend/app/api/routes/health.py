"""
Health Check Route (Async + AI Provider Status)
=================================================
Reports database health and status of all configured AI providers.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ai import get_ai_gateway

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check if the API, database, and AI providers are healthy."""
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"

    # AI provider checks via the gateway
    try:
        gateway = get_ai_gateway()
        ai_status = await gateway.get_status()
    except Exception:
        ai_status = {"groq": "error", "ollama": "error"}

    # Backward-compatible: keep "ollama" key at top level
    ollama_status = ai_status.get("ollama", "unknown")

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "2.0.0",
        "database": db_status,
        "ollama": ollama_status,
        "ai_providers": ai_status,
    }
