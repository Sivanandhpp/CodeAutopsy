"""
Groq AI Provider
================
Cloud-based LLM inference via Groq's API (LPU hardware).
Supports both synchronous fix generation and streaming summaries.

Model: llama-3.1-8b-instant (free tier: 30 req/min, 14,400 req/day)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from groq import Groq

from app.config import get_settings
from app.services.ai.providers.base import AIProvider, SendEvent
from app.services.ai.prompts import (
    FIX_SYSTEM_PROMPT,
    build_fix_user_prompt,
    build_summary_messages,
    build_summary_prompt,
    SUMMARY_SYSTEM_PROMPT,
)
from app.services.ai.cache import ai_cache

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    """Groq cloud AI provider."""

    @property
    def name(self) -> str:
        return "Groq"

    # ─── Availability ────────────────────────────────────────

    async def is_available(self) -> bool:
        """Check that the API key is set and the API responds."""
        settings = get_settings()
        if not settings.GROQ_ENABLED:
            return False
        if not settings.GROQ_API_KEY:
            return False
        try:
            # Quick model list call to verify the key
            client = Groq(api_key=settings.GROQ_API_KEY)
            await asyncio.to_thread(client.models.list)
            return True
        except Exception as exc:
            logger.debug("Groq availability check failed: %s", exc)
            return False

    # ─── Task: Issue Fix ─────────────────────────────────────

    async def generate_fix(
        self,
        code_snippet: str,
        defect_family: str,
        language: str = "python",
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        context_before: str = "",
        context_after: str = "",
    ) -> dict:
        settings = get_settings()

        # Cache lookup
        cache_key = ai_cache.make_key("fix", code_snippet, defect_family, language)
        cached = ai_cache.get(cache_key)
        if cached is not None:
            cached["cached"] = True
            cached["provider"] = self.name
            return cached

        user_prompt = build_fix_user_prompt(
            code_snippet, defect_family, language,
            file_path, context_before, context_after,
        )

        # Run the synchronous Groq SDK call in a thread
        result = await asyncio.to_thread(
            self._call_groq_chat,
            settings.GROQ_API_KEY,
            settings.GROQ_MODEL,
            user_prompt,
        )

        result["cached"] = False
        result["provider"] = self.name

        if result.get("confidence", 0) > 0:
            ai_cache.put(cache_key, result)

        return result

    def _call_groq_chat(self, api_key: str, model: str, user_prompt: str) -> dict:
        """Synchronous Groq chat completion (runs inside asyncio.to_thread)."""
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": FIX_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=model,
                temperature=0.3,
                max_tokens=1024,
                top_p=0.9,
                response_format={"type": "json_object"},
            )

            response_text = completion.choices[0].message.content
            parsed = json.loads(response_text)

            result = {
                "root_cause": parsed.get("root_cause", "Unable to determine root cause"),
                "fix_strategy": parsed.get("fix_strategy", "No fix strategy available"),
                "code_patch": parsed.get("code_patch", ""),
                "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.5)))),
                "reasoning": parsed.get("reasoning", []),
            }

            logger.info(
                "Groq fix complete: issue=%s, lang=%s, confidence=%.2f, tokens=%d",
                parsed.get("root_cause", "?")[:30],
                "?",
                result["confidence"],
                completion.usage.total_tokens if completion.usage else 0,
            )
            return result

        except json.JSONDecodeError as exc:
            logger.error("Groq returned invalid JSON: %s", exc)
            raise
        except Exception as exc:
            logger.error("Groq API call failed: %s", exc)
            raise

    # ─── Task: Executive Summary (Streaming) ─────────────────

    async def stream_summary(
        self,
        issues: list[dict],
        send_event: SendEvent,
    ) -> str:
        """Stream an executive summary via Groq chat completion."""
        settings = get_settings()

        await send_event("ai_model_active", {
            "provider": self.name,
            "model": settings.GROQ_MODEL,
        })

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

        messages = build_summary_messages(issues)

        try:
            collected = await asyncio.to_thread(
                self._call_groq_summary, settings.GROQ_API_KEY, settings.GROQ_MODEL, messages,
            )
        except Exception as exc:
            logger.error("Groq summary failed: %s", exc)
            raise

        # Send the full text as a single chunk (Groq is fast enough)
        await send_event("ai_summary_chunk", {"text": collected})
        await send_event("ai_summary_complete", {
            "summary": collected,
            "message": "AI summary complete!",
            "status": "complete",
        })
        return collected

    def _call_groq_summary(self, api_key: str, model: str, messages: list[dict]) -> str:
        """Synchronous Groq chat call for the summary (runs in thread)."""
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=0.3,
            max_tokens=1024,
            top_p=0.9,
        )
        text = completion.choices[0].message.content or ""
        logger.info(
            "Groq summary complete: %d chars, %d tokens",
            len(text),
            completion.usage.total_tokens if completion.usage else 0,
        )
        return text
