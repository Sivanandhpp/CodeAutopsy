"""
Ollama AI Provider
==================
Local LLM inference via the Ollama HTTP API.
Supports both fix generation (non-streaming) and streaming summaries.

Model: qwen2.5-coder:3b (configurable via OLLAMA_MODEL)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.services.ai.providers.base import AIProvider, SendEvent
from app.services.ai.prompts import (
    FIX_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_fix_user_prompt,
    build_summary_prompt,
)
from app.services.ai.cache import ai_cache

logger = logging.getLogger(__name__)

MIN_TOTAL_TIMEOUT_SECONDS = 240
RETRYABLE_EXCEPTIONS = (
    httpx.ReadTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


def _normalize_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message if message else exc.__class__.__name__


class OllamaProvider(AIProvider):
    """Local Ollama AI provider."""

    def __init__(self):
        self._cancelled = False

    def cancel(self):
        """Signal cancellation from outside (used during analysis)."""
        self._cancelled = True

    @property
    def name(self) -> str:
        return "Ollama"

    # ─── Availability ────────────────────────────────────────

    async def is_available(self) -> bool:
        """Check if Ollama is reachable and the configured model is loaded."""
        settings = get_settings()
        if not settings.OLLAMA_ENABLED:
            return False
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
        settings = get_settings()

        # Cache lookup
        cache_key = ai_cache.make_key("fix", code_snippet, issue_type, language)
        cached = ai_cache.get(cache_key)
        if cached is not None:
            cached["cached"] = True
            cached["provider"] = self.name
            return cached

        user_prompt = build_fix_user_prompt(
            code_snippet, issue_type, language,
            file_path, context_before, context_after,
        )

        # Build the combined prompt for Ollama's /api/generate
        combined_prompt = f"{FIX_SYSTEM_PROMPT}\n\n{user_prompt}"

        try:
            result = await self._generate_json(settings, combined_prompt)
        except Exception as exc:
            logger.error("Ollama fix generation failed: %s", exc)
            raise

        result["cached"] = False
        result["provider"] = self.name

        if result.get("confidence", 0) > 0:
            ai_cache.put(cache_key, result)

        return result

    async def _generate_json(self, settings, prompt: str) -> dict:
        """Non-streaming call to Ollama that expects a JSON response."""
        timeout = httpx.Timeout(connect=10.0, write=30.0, read=120.0, pool=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1024,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("response", "")

        # Parse the JSON from the model's response
        parsed = json.loads(raw_text)

        result = {
            "root_cause": parsed.get("root_cause", "Unable to determine root cause"),
            "fix_strategy": parsed.get("fix_strategy", "No fix strategy available"),
            "code_patch": parsed.get("code_patch", ""),
            "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.5)))),
            "reasoning": parsed.get("reasoning", []),
        }

        logger.info(
            "Ollama fix complete: confidence=%.2f, model=%s",
            result["confidence"],
            settings.OLLAMA_MODEL,
        )
        return result

    # ─── Task: Executive Summary (Streaming) ─────────────────

    async def stream_summary(
        self,
        issues: list[dict],
        send_event: SendEvent,
    ) -> str:
        settings = get_settings()
        self._cancelled = False

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

        # Build prompt with system context prepended
        user_prompt = build_summary_prompt(issues)
        full_prompt = f"{SUMMARY_SYSTEM_PROMPT}\n\n{user_prompt}"

        collected_text = ""
        last_error: Exception | None = None

        for attempt in range(2):
            if self._cancelled:
                logger.info("Summary streaming cancelled before attempt %s", attempt + 1)
                break

            if attempt > 0:
                await self._warmup_model(settings)

            try:
                collected_text = await self._stream_generate(settings, full_prompt, send_event)
                await send_event("ai_summary_complete", {
                    "summary": collected_text,
                    "message": "AI summary complete!",
                    "status": "complete",
                })
                return collected_text
            except RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                logger.warning(
                    "Ollama summary attempt %s/2 failed with %s: %s",
                    attempt + 1, exc.__class__.__name__,
                    _normalize_exception_message(exc),
                )
                if attempt == 0:
                    continue
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Ollama summary attempt %s/2 exceeded timeout",
                    attempt + 1,
                )
                if attempt == 0:
                    continue
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Ollama summary attempt %s/2 failed unexpectedly",
                    attempt + 1,
                )
                break

        # All retries exhausted — raise so the gateway can try the fallback
        detail = _normalize_exception_message(last_error) if last_error else "Unknown error"
        raise RuntimeError(f"Ollama summary failed after retries: {detail}")

    async def _stream_generate(self, settings, prompt: str, send_event: SendEvent) -> str:
        total_timeout = max(int(settings.OLLAMA_TIMEOUT), MIN_TOTAL_TIMEOUT_SECONDS)
        timeout = httpx.Timeout(connect=10.0, write=30.0, read=None, pool=10.0)
        collected_parts: list[str] = []

        async with asyncio.timeout(total_timeout):
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
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

    async def _warmup_model(self, settings) -> None:
        """Prime Ollama before retrying a failed request."""
        timeout = httpx.Timeout(connect=10.0, write=10.0, read=None, pool=10.0)
        try:
            async with asyncio.timeout(60):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": settings.OLLAMA_MODEL,
                            "prompt": "hi",
                            "stream": False,
                            "options": {"num_predict": 1},
                        },
                    )
                    response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Ollama warm-up failed: %s: %s",
                exc.__class__.__name__,
                _normalize_exception_message(exc),
            )
