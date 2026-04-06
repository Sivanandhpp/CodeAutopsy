"""
Abstract AI Provider
====================
Every AI backend (Groq, Ollama, future providers) must implement this
interface so the gateway can treat them interchangeably.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional


# Type alias for the SSE event emitter used during streaming.
SendEvent = Callable[[str, dict], Awaitable[None]]


class AIProvider(ABC):
    """Base interface that every AI backend must implement."""

    # ─── Identity ────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging (e.g. 'Groq', 'Ollama')."""

    # ─── Availability ────────────────────────────────────────

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Return True if the provider is reachable, configured, and the
        model is loaded/ready.  Called before every task attempt.
        """

    # ─── Task: Issue Fix ─────────────────────────────────────

    @abstractmethod
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
        Analyze a code issue and return a fix recommendation.

        Must return a dict with at least:
            root_cause   : str
            fix_strategy : str
            code_patch   : str
            confidence   : float  (0.0 – 1.0)
            reasoning    : list[str]
            cached       : bool
            provider     : str    (self.name)
        """

    # ─── Task: Executive Summary (Streaming) ─────────────────

    @abstractmethod
    async def stream_summary(
        self,
        issues: list[dict],
        send_event: SendEvent,
    ) -> str:
        """
        Generate and stream an executive summary of static analysis findings.

        Emit SSE events via *send_event* as chunks become available:
            ai_summary_start    → { message }
            ai_summary_chunk    → { text }
            ai_summary_complete → { summary, message, status }

        Returns the full collected summary text.
        """
