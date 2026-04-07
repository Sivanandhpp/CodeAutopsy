from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.schemas.analysis import AnalysisFinding


class BaseAnalysisEngine(ABC):
    name: str

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if engine can run (binary present, API reachable, etc.)."""

    @abstractmethod
    async def analyze(self, file_path: str, language: str) -> List[AnalysisFinding]:
        """Analyse one file. Return findings. Never raise — return [] on error."""
