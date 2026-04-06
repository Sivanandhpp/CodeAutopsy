"""
AI API Route (Async + Auth + Provider Fallback)
=================================================
POST /api/ai/analyze — Send a code issue through the AI gateway.
Automatically uses the best available provider (Groq → Ollama).
Protected with JWT auth and per-user rate limiting.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import AIAnalyzeRequest, AIAnalyzeResponse
from app.models.user import User
from app.services.ai import get_ai_gateway
from app.api.deps import get_current_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])

# ─── Per-user rate limiter ───────────────────────────────────
_ai_rate_limit: dict[str, list[float]] = {}


def check_ai_rate_limit(user_id: str):
    """Per-user rate limiting for AI calls."""
    settings = get_settings()
    max_calls = settings.MAX_AI_CALLS_PER_HOUR
    now = datetime.now(timezone.utc).timestamp()

    if user_id not in _ai_rate_limit:
        _ai_rate_limit[user_id] = []

    _ai_rate_limit[user_id] = [
        t for t in _ai_rate_limit[user_id] if now - t < 3600
    ]

    if len(_ai_rate_limit[user_id]) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI rate limit exceeded. Maximum {max_calls} AI calls per hour.",
        )

    _ai_rate_limit[user_id].append(now)


@router.post("/analyze", response_model=AIAnalyzeResponse)
async def ai_analyze(
    req: AIAnalyzeRequest,
    user: User = Depends(get_current_user),
):
    """
    Analyze a code issue using the best available AI provider.
    Tries Groq first, falls back to Ollama, returns structured error if both fail.
    """
    check_ai_rate_limit(str(user.id))

    if not req.code_snippet.strip():
        raise HTTPException(status_code=400, detail="code_snippet cannot be empty")

    if len(req.code_snippet) > 5000:
        raise HTTPException(
            status_code=400,
            detail="code_snippet too long (max 5000 chars).",
        )

    gateway = get_ai_gateway()
    result = await gateway.generate_fix(
        code_snippet=req.code_snippet,
        defect_family=req.defect_family,
        language=req.language,
        file_path=req.file_path,
        line_number=req.line_number,
        context_before=req.context_before,
        context_after=req.context_after,
    )

    return AIAnalyzeResponse(**result)
