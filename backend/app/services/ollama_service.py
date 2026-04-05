"""
Ollama Service - AI Summary Streaming
=====================================
Generates a concise markdown summary of static analysis findings and streams
the response incrementally back to the frontend.
"""

import asyncio
import json
import logging
from collections import Counter
from typing import Awaitable, Callable

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SendEvent = Callable[[str, dict], Awaitable[None]]

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}
MAX_REPRESENTATIVE_ISSUES = 18
MAX_TOP_TYPES = 8
MIN_TOTAL_TIMEOUT_SECONDS = 240
RETRYABLE_EXCEPTIONS = (
    httpx.ReadTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)

SUMMARY_PROMPT = """You are an expert security and code quality analyst.
You are given a condensed summary of issues found during a static analysis scan.
Write a concise markdown executive summary with these sections:

## Critical Risks
## Repeating Patterns
## Recommended Actions

Guidelines:
- Prioritize the highest-severity risks first.
- Group repeated findings instead of listing every issue.
- Mention approximate counts when it helps.
- Keep the response practical and skimmable.
- If the repository is clean, say so plainly.

Static analysis summary:
{scan_summary}
"""


def _normalize_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _top_counts(items: list[dict], key: str, limit: int) -> dict[str, int]:
    counter = Counter()
    for item in items:
        value = str(item.get(key, "") or "").strip()
        if value:
            counter[value] += 1
    return dict(counter.most_common(limit))


def _representative_issues(issues: list[dict]) -> list[dict]:
    sampled: list[dict] = []
    seen: set[tuple[str, str, int, str]] = set()

    for issue in sorted(
        issues,
        key=lambda item: (
            SEVERITY_ORDER.get(item.get("severity", "info"), 4),
            str(item.get("issue_type", "")),
            str(item.get("file_path", "")),
            int(item.get("line_number", 0) or 0),
        ),
    ):
        key = (
            str(issue.get("issue_type", "")),
            str(issue.get("file_path", "")),
            int(issue.get("line_number", 0) or 0),
            str(issue.get("message", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        sampled.append({
            "file": issue.get("file_path", ""),
            "line": int(issue.get("line_number", 0) or 0),
            "severity": issue.get("severity", "low"),
            "type": issue.get("issue_type", "unknown"),
            "message": str(issue.get("message", ""))[:180],
        })
        if len(sampled) >= MAX_REPRESENTATIVE_ISSUES:
            break

    return sampled


def _build_summary_prompt(issues: list[dict]) -> str:
    severity_counts = {
        severity: 0 for severity in ("critical", "high", "medium", "low", "info")
    }
    for issue in issues:
        severity = str(issue.get("severity", "info")).lower()
        if severity in severity_counts:
            severity_counts[severity] += 1

    payload = {
        "total_issues": len(issues),
        "severity_counts": severity_counts,
        "top_issue_types": _top_counts(issues, "issue_type", MAX_TOP_TYPES),
        "top_categories": _top_counts(issues, "category", 6),
        "representative_issues": _representative_issues(issues),
    }

    return SUMMARY_PROMPT.format(scan_summary=json.dumps(payload, indent=2))


class OllamaAnalyzer:
    """Streaming AI analyzer that summarizes static issues over SSE."""

    def __init__(self, repo_path: str = ""):
        self.settings = get_settings()
        self._cancelled = False

    def cancel(self):
        """Signal cancellation from outside."""
        self._cancelled = True

    async def stream_summary(self, issues: list[dict], send_event: SendEvent) -> str:
        """Generate and stream an AI summary of static analysis issues."""
        if not self.settings.OLLAMA_ENABLED:
            logger.info("Ollama is disabled; skipping AI analysis")
            return ""

        if not await is_ollama_available():
            logger.warning("Ollama model not available; skipping AI analysis")
            await send_event("ollama_unavailable", {
                "message": "AI model not loaded. Static analysis results are still available.",
            })
            return ""

        await send_event("ai_summary_start", {
            "message": "Generating AI summary of findings...",
        })

        if not issues:
            msg = "No issues were found during static analysis. The codebase looks clean and healthy!"
            await send_event("ai_summary_chunk", {"text": msg})
            await send_event("ai_summary_complete", {
                "summary": msg,
                "message": "AI summary complete!",
                "status": "complete",
            })
            return msg

        prompt = _build_summary_prompt(issues)
        collected_text = ""
        last_error: Exception | None = None

        for attempt in range(2):
            if self._cancelled:
                logger.info("Summary streaming cancelled before attempt %s", attempt + 1)
                break

            if attempt > 0:
                await self._warmup_model()

            try:
                collected_text = await self._stream_generate(prompt, send_event)
                await send_event("ai_summary_complete", {
                    "summary": collected_text,
                    "message": "AI summary complete!",
                    "status": "complete",
                })
                return collected_text
            except RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                logger.warning(
                    "Ollama summary attempt %s/%s failed with %s: %s",
                    attempt + 1,
                    2,
                    exc.__class__.__name__,
                    _normalize_exception_message(exc),
                )
                if attempt == 0:
                    continue
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Ollama summary attempt %s/%s exceeded total timeout budget",
                    attempt + 1,
                    2,
                )
                if attempt == 0:
                    continue
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Ollama summary attempt %s/%s failed unexpectedly",
                    attempt + 1,
                    2,
                )
                break

        failure_detail = _normalize_exception_message(last_error) if last_error else "Unknown summary error"
        logger.error(
            "Ollama summary failed after retries: %s (%s)",
            failure_detail,
            last_error.__class__.__name__ if last_error else "UnknownError",
        )
        await send_event("ai_summary_error", {
            "message": "AI summary unavailable. Static analysis results are still available.",
            "detail": failure_detail,
        })
        await send_event("ai_summary_complete", {
            "summary": "",
            "message": "AI summary unavailable.",
            "status": "failed",
        })
        return ""

    async def _stream_generate(self, prompt: str, send_event: SendEvent) -> str:
        total_timeout = max(int(self.settings.OLLAMA_TIMEOUT), MIN_TOTAL_TIMEOUT_SECONDS)
        timeout = httpx.Timeout(connect=10.0, write=30.0, read=None, pool=10.0)
        collected_parts: list[str] = []

        async with asyncio.timeout(total_timeout):
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": self.settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "temperature": 0.2,
                            "num_predict": 640,
                        },
                    },
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if self._cancelled:
                            logger.info("Summary streaming cancelled by caller")
                            break
                        if not line.strip():
                            continue

                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        token = chunk.get("response", "")
                        if token:
                            collected_parts.append(token)
                            await send_event("ai_summary_chunk", {"text": token})

                        if chunk.get("done", False):
                            break

        return "".join(collected_parts)

    async def _warmup_model(self) -> None:
        """Prime Ollama before retrying a failed summary request."""
        timeout = httpx.Timeout(connect=10.0, write=10.0, read=None, pool=10.0)
        try:
            async with asyncio.timeout(60):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": self.settings.OLLAMA_MODEL,
                            "prompt": "hi",
                            "stream": False,
                            "options": {
                                "num_predict": 1,
                            },
                        },
                    )
                    response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Ollama warm-up request failed before retry: %s: %s",
                exc.__class__.__name__,
                _normalize_exception_message(exc),
            )


async def is_ollama_available() -> bool:
    """Check if Ollama service is reachable and the model is loaded."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_base = settings.OLLAMA_MODEL.split(":")[0]
                return any(model_base in m for m in models)
        return False
    except Exception:
        return False
