"""
AI Service — Groq-powered code analysis
========================================

How this works:
---------------
1. We use Groq's API (https://groq.com) — a blazing-fast LLM inference provider.
   Groq runs models like Meta's LLaMA on custom hardware called LPUs (Language
   Processing Units), which makes it 10-50x faster than typical GPU inference.

2. We use the `llama-3.1-8b-instant` model which is:
   - FREE on Groq's free tier (30 req/min, 14,400 req/day)
   - Fast (~500 tokens/sec)
   - Good enough for code analysis tasks

3. The flow:
   User clicks "AI Fix" on an issue
   → Frontend sends code_snippet + issue_type + language to POST /api/ai/analyze
   → This service calls Groq's chat completion API with a carefully crafted prompt
   → Groq returns a JSON response with root_cause, fix_strategy, code_patch, etc.
   → We parse and return it to the frontend

4. We cache results in-memory to avoid hitting the API for duplicate requests.

Free tier limits (as of 2024):
- llama-3.1-8b-instant: 30 req/min, 14,400 req/day, 131,072 token context
- No credit card required
"""

import json
import hashlib
import logging
from typing import Optional

from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)

# ─── In-memory cache ──────────────────────────────────────────
_cache: dict[str, dict] = {}
MAX_CACHE_SIZE = 200


def _cache_key(code_snippet: str, issue_type: str, language: str) -> str:
    """Create a deterministic cache key from the input."""
    raw = f"{code_snippet}|{issue_type}|{language}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── System Prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior security engineer and code reviewer.
You analyze code issues and provide actionable fix suggestions.

You MUST respond with ONLY valid JSON (no markdown, no explanation outside JSON). 
Use this exact schema:

{
  "root_cause": "A clear 1-2 sentence explanation of WHY this is a problem",
  "fix_strategy": "A concise explanation of HOW to fix it (2-3 sentences max)",
  "code_patch": "The corrected code snippet (just the fixed version, not a diff)",
  "confidence": 0.85,
  "reasoning": [
    "Step 1 of your analysis",
    "Step 2 of your analysis",
    "Step 3 of your analysis"
  ]
}

Rules:
- confidence is a float 0.0-1.0 (1.0 = certain this is a real issue with a clear fix)
- code_patch should be the FIXED version of the code, ready to paste
- reasoning should be 2-4 short steps showing your thought process
- Keep all text concise and actionable
- If the code is not actually vulnerable, set confidence < 0.3 and explain why
"""


def _build_user_prompt(code_snippet: str, issue_type: str, language: str,
                       file_path: Optional[str] = None,
                       context_before: str = "", context_after: str = "") -> str:
    """Build the user message with all relevant context."""
    parts = [f"**Issue Type:** {issue_type}", f"**Language:** {language}"]

    if file_path:
        parts.append(f"**File:** {file_path}")

    if context_before:
        parts.append(f"\n**Context before:**\n```{language}\n{context_before}\n```")

    parts.append(f"\n**Flagged code:**\n```{language}\n{code_snippet}\n```")

    if context_after:
        parts.append(f"\n**Context after:**\n```{language}\n{context_after}\n```")

    parts.append("\nAnalyze this issue and provide your fix recommendation as JSON.")
    return "\n".join(parts)


# ─── Main Analysis Function ──────────────────────────────────

def analyze_issue(
    code_snippet: str,
    issue_type: str,
    language: str = "python",
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    context_before: str = "",
    context_after: str = "",
) -> dict:
    """
    Send a code issue to Groq for AI analysis.
    
    Returns a dict with: root_cause, fix_strategy, code_patch, confidence, reasoning, cached
    """
    settings = get_settings()

    # Check if API key is configured
    if not settings.GROQ_API_KEY:
        return {
            "root_cause": "AI analysis is not available — no GROQ_API_KEY configured.",
            "fix_strategy": "Set GROQ_API_KEY in your backend/.env file. Get a free key at https://console.groq.com",
            "code_patch": code_snippet,
            "confidence": 0.0,
            "reasoning": ["No API key found in environment variables"],
            "cached": False,
        }

    # Check cache
    key = _cache_key(code_snippet, issue_type, language)
    if key in _cache:
        result = _cache[key].copy()
        result["cached"] = True
        return result

    # Build the prompt
    user_prompt = _build_user_prompt(
        code_snippet, issue_type, language, file_path,
        context_before, context_after
    )

    try:
        # Create Groq client
        client = Groq(api_key=settings.GROQ_API_KEY)

        # Call Groq API
        # We use llama-3.1-8b-instant because:
        # - It's the fastest model on Groq's free tier
        # - 30 requests/minute, 14,400/day on free plan
        # - 131K token context window
        # - Great for structured JSON tasks like this
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3,        # Low temp = more deterministic/focused
            max_tokens=1024,         # Enough for code patch + explanation
            top_p=0.9,
            response_format={"type": "json_object"},  # Force JSON output
        )

        # Extract the response text
        response_text = chat_completion.choices[0].message.content

        # Parse the JSON response
        result = json.loads(response_text)

        # Validate and normalize
        result = {
            "root_cause": result.get("root_cause", "Unable to determine root cause"),
            "fix_strategy": result.get("fix_strategy", "No fix strategy available"),
            "code_patch": result.get("code_patch", code_snippet),
            "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.5)))),
            "reasoning": result.get("reasoning", []),
            "cached": False,
        }

        # Store in cache (evict oldest if full)
        if len(_cache) >= MAX_CACHE_SIZE:
            oldest_key = next(iter(_cache))
            del _cache[oldest_key]
        _cache[key] = result

        logger.info(
            f"AI analysis complete: issue={issue_type}, lang={language}, "
            f"confidence={result['confidence']}, "
            f"tokens={chat_completion.usage.total_tokens}"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Groq response as JSON: {e}")
        return {
            "root_cause": "AI returned an invalid response format.",
            "fix_strategy": "Try again — the AI occasionally produces malformed output.",
            "code_patch": code_snippet,
            "confidence": 0.0,
            "reasoning": [f"JSON parse error: {str(e)}"],
            "cached": False,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Groq API error: {error_msg}")

        # Friendly error messages
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            fix = "You've hit Groq's free tier rate limit (30 req/min). Wait a minute and try again."
        elif "authentication" in error_msg.lower() or "401" in error_msg:
            fix = "Your GROQ_API_KEY is invalid. Check it at https://console.groq.com/keys"
        else:
            fix = f"Groq API error: {error_msg}"

        return {
            "root_cause": "AI analysis failed.",
            "fix_strategy": fix,
            "code_patch": code_snippet,
            "confidence": 0.0,
            "reasoning": [error_msg],
            "cached": False,
        }
