"""
Health Check Route (Async + Ollama Status)
===========================================
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import HealthResponse
from app.services.ollama_service import is_ollama_available

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check if the API, database, and Ollama are healthy."""
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "disconnected"

    # Ollama check
    try:
        ollama_ok = await is_ollama_available()
        ollama_status = "connected" if ollama_ok else "unavailable"
    except Exception:
        ollama_status = "unavailable"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="2.0.0",
        database=db_status,
        ollama=ollama_status,
    )
