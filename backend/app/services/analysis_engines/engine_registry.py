from __future__ import annotations

from typing import List

from app.schemas.analysis import AnalysisFinding
from app.services.analysis_engines.base import BaseAnalysisEngine


class EngineRegistry:
    def __init__(self):
        self._engines: List[BaseAnalysisEngine] = []

    def register(self, engine: BaseAnalysisEngine) -> None:
        self._engines.append(engine)

    async def run_all(self, file_path: str, language: str) -> List[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        for engine in self._engines:
            if await engine.is_available():
                findings.extend(await engine.analyze(file_path, language))
        return self._deduplicate(findings)

    def _deduplicate(self, findings: List[AnalysisFinding]) -> List[AnalysisFinding]:
        severity_order = [
            "trace", "info", "low", "medium", "high", "critical", "blocker"
        ]
        seen: dict[tuple, AnalysisFinding] = {}
        for finding in findings:
            key = (finding.rule_id, finding.line_number)
            if key not in seen:
                seen[key] = finding
                continue
            try:
                current_idx = severity_order.index(finding.severity)
            except ValueError:
                current_idx = 0
            try:
                existing_idx = severity_order.index(seen[key].severity)
            except ValueError:
                existing_idx = 0
            if current_idx > existing_idx:
                seen[key] = finding

        return sorted(
            seen.values(),
            key=lambda f: severity_order.index(f.severity)
            if f.severity in severity_order else 0,
            reverse=True,
        )
