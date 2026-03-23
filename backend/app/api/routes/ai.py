"""
AI API Route
=============
POST /api/ai/analyze — Send a code issue to Groq for AI-powered analysis.

This endpoint:
1. Receives the code snippet + issue type + language
2. Calls the Groq AI service
3. Returns structured analysis: root cause, fix, code patch, confidence
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import AIAnalyzeRequest, AIAnalyzeResponse
from app.services.ai_service import analyze_issue
from app.config import get_settings

router = APIRouter(prefix="/api/ai")

# ─── Simple rate limiter for AI calls ────────────────────────
_ai_rate_limit: dict[str, list[float]] = {}


def check_ai_rate_limit(request: Request):
    """Prevent abuse of the AI endpoint (uses config MAX_AI_CALLS_PER_HOUR)."""
    settings = get_settings()
    max_calls = settings.MAX_AI_CALLS_PER_HOUR

    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).timestamp()

    if client_ip not in _ai_rate_limit:
        _ai_rate_limit[client_ip] = []

    # Remove entries older than 1 hour
    _ai_rate_limit[client_ip] = [
        t for t in _ai_rate_limit[client_ip] if now - t < 3600
    ]

    if len(_ai_rate_limit[client_ip]) >= max_calls:
        raise HTTPException(
            status_code=429,
            detail=f"AI rate limit exceeded. Maximum {max_calls} AI calls per hour on free tier."
        )

    _ai_rate_limit[client_ip].append(now)


@router.post("/analyze", response_model=AIAnalyzeResponse)
async def ai_analyze(req: AIAnalyzeRequest, request: Request):
    """
    Analyze a code issue using Groq AI.

    Send a code snippet and issue type, get back:
    - root_cause: why this is a problem
    - fix_strategy: how to fix it
    - code_patch: the corrected code
    - confidence: 0.0-1.0 score
    - reasoning: step-by-step analysis
    """
    # Rate limit check
    check_ai_rate_limit(request)

    # Validate input
    if not req.code_snippet.strip():
        raise HTTPException(status_code=400, detail="code_snippet cannot be empty")

    if len(req.code_snippet) > 5000:
        raise HTTPException(
            status_code=400,
            detail="code_snippet too long (max 5000 chars). Send only the relevant code."
        )

    # Call the AI service
    result = analyze_issue(
        code_snippet=req.code_snippet,
        issue_type=req.issue_type,
        language=req.language,
        file_path=req.file_path,
        line_number=req.line_number,
        context_before=req.context_before,
        context_after=req.context_after,
    )

    return AIAnalyzeResponse(**result)
