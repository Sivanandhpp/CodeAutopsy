"""
AI Gateway
==========
Central orchestrator that selects the best available AI provider and
falls back automatically when the primary fails.

Priority order:  GROQ → OLLAMA → graceful error

Usage
-----
    from app.services.ai import get_ai_gateway

    gateway = get_ai_gateway()
    result  = await gateway.generate_fix(code, issue_type, language)
    summary = await gateway.stream_summary(issues, send_event)
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from app.config import get_settings
from app.services.ai.providers.base import AIProvider, SendEvent
from app.services.ai.providers.groq_provider import GroqProvider
from app.services.ai.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class AIGateway:
    """
    Facade that routes AI requests to the best available provider.

    Initialises both providers eagerly but only calls the ones that are
    enabled.  On every request it:

    1. Picks the primary provider based on env toggles.
    2. Checks availability.
    3. Attempts the task.
    4. On failure, falls back to the secondary provider.
    5. If both fail, returns a structured error (never raises).
    """

    def __init__(self):
        self._groq = GroqProvider()
        self._ollama = OllamaProvider()

    # ─── Provider resolution ─────────────────────────────────

    def _ordered_providers(self) -> list[AIProvider]:
        """
        Return providers in priority order based on config toggles.
        Groq is preferred when both are enabled (faster, cloud-based).
        """
        settings = get_settings()
        providers: list[AIProvider] = []

        if settings.GROQ_ENABLED and settings.GROQ_API_KEY:
            providers.append(self._groq)
        if settings.OLLAMA_ENABLED:
            providers.append(self._ollama)

        return providers

    async def get_status(self) -> dict:
        """
        Return the current availability status of all providers.
        Used by the /health endpoint.
        """
        settings = get_settings()
        status: dict = {}

        if settings.GROQ_ENABLED:
            try:
                status["groq"] = "connected" if await self._groq.is_available() else "unavailable"
            except Exception:
                status["groq"] = "error"
        else:
            status["groq"] = "disabled"

        if settings.OLLAMA_ENABLED:
            try:
                status["ollama"] = "connected" if await self._ollama.is_available() else "unavailable"
            except Exception:
                status["ollama"] = "error"
        else:
            status["ollama"] = "disabled"

        return status

    # ─── Task: Issue Fix ─────────────────────────────────────

    async def generate_fix(
        self,
        code_snippet: str,
        issue_type: str,
        language: str = "python",
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        context_before: str = "",
        context_after: str = "",
    ) -> dict:
        """
        Analyse a code issue using the best available provider.
        Falls back through all providers; returns a structured error
        dict if none succeed.
        """
        providers = self._ordered_providers()

        if not providers:
            return self._no_provider_error(code_snippet)

        last_error: Exception | None = None

        for provider in providers:
            try:
                available = await provider.is_available()
                if not available:
                    logger.info(
                        "AI Fix: skipping %s (unavailable)", provider.name,
                    )
                    continue

                logger.info("AI Fix: attempting with %s", provider.name)
                result = await provider.generate_fix(
                    code_snippet=code_snippet,
                    issue_type=issue_type,
                    language=language,
                    file_path=file_path,
                    line_number=line_number,
                    context_before=context_before,
                    context_after=context_after,
                )
                logger.info(
                    "AI Fix: success via %s (confidence=%.2f)",
                    provider.name,
                    result.get("confidence", 0),
                )
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "AI Fix: %s failed (%s: %s), trying next provider...",
                    provider.name,
                    exc.__class__.__name__,
                    str(exc)[:200],
                )
                continue

        # All providers failed
        return self._fix_error(code_snippet, last_error)

    # ─── Task: Executive Summary (Streaming) ─────────────────

    async def stream_summary(
        self,
        issues: list[dict],
        send_event: SendEvent,
    ) -> str:
        """
        Stream an executive summary using the best available provider.
        Falls back; emits SSE error events if all providers fail.
        """
        providers = self._ordered_providers()

        if not providers:
            return await self._no_provider_summary(send_event)

        last_error: Exception | None = None

        for provider in providers:
            try:
                available = await provider.is_available()
                if not available:
                    logger.info(
                        "AI Summary: skipping %s (unavailable)", provider.name,
                    )
                    continue

                logger.info("AI Summary: attempting with %s", provider.name)
                result = await provider.stream_summary(issues, send_event)
                logger.info(
                    "AI Summary: success via %s (%d chars)",
                    provider.name,
                    len(result),
                )
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "AI Summary: %s failed (%s: %s), trying next provider...",
                    provider.name,
                    exc.__class__.__name__,
                    str(exc)[:200],
                )
                continue

        # All providers failed — emit error events
        return await self._summary_error(send_event, last_error)

    # ─── Error responses ─────────────────────────────────────

    @staticmethod
    def _no_provider_error(code_snippet: str) -> dict:
        return {
            "root_cause": "No AI provider is available.",
            "fix_strategy": (
                "Enable at least one AI provider in your .env file:\n"
                "• Set GROQ_ENABLED=True and provide a GROQ_API_KEY (free at https://console.groq.com)\n"
                "• Set OLLAMA_ENABLED=True and run 'ollama pull qwen2.5-coder:3b'"
            ),
            "code_patch": code_snippet,
            "confidence": 0.0,
            "reasoning": ["No AI providers configured or available"],
            "cached": False,
            "provider": "none",
        }

    @staticmethod
    def _fix_error(code_snippet: str, last_error: Exception | None) -> dict:
        detail = str(last_error)[:200] if last_error else "Unknown error"

        # Friendly messages for common Groq errors
        if last_error:
            msg = str(last_error).lower()
            if "rate_limit" in msg or "429" in msg:
                strategy = "AI rate limit reached. Wait a minute and try again."
            elif "authentication" in msg or "401" in msg:
                strategy = "Your GROQ_API_KEY is invalid. Check at https://console.groq.com/keys"
            else:
                strategy = f"All AI providers failed. Last error: {detail}"
        else:
            strategy = "All AI providers are unavailable. Check your configuration."

        return {
            "root_cause": "AI analysis failed.",
            "fix_strategy": strategy,
            "code_patch": code_snippet,
            "confidence": 0.0,
            "reasoning": [detail],
            "cached": False,
            "provider": "none",
        }

    @staticmethod
    async def _no_provider_summary(send_event: SendEvent) -> str:
        await send_event("ollama_unavailable", {
            "message": "No AI providers available. Static analysis results are still available.",
        })
        await send_event("ai_summary_complete", {
            "summary": "",
            "message": "AI summary unavailable — no providers configured.",
            "status": "failed",
        })
        return ""

    @staticmethod
    async def _summary_error(send_event: SendEvent, last_error: Exception | None) -> str:
        detail = str(last_error)[:200] if last_error else "Unknown error"
        await send_event("ai_summary_error", {
            "message": "AI summary unavailable. Static analysis results are still available.",
            "detail": detail,
        })
        await send_event("ai_summary_complete", {
            "summary": "",
            "message": "AI summary unavailable.",
            "status": "failed",
        })
        return ""


# ─── Singleton ───────────────────────────────────────────────

@lru_cache()
def get_ai_gateway() -> AIGateway:
    """Return the singleton AIGateway instance."""
    return AIGateway()
