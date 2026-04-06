from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import List

from app.schemas.analysis import AnalysisFinding
from app.services.analysis_engines.base import BaseAnalysisEngine

logger = logging.getLogger(__name__)


class RegexEngine(BaseAnalysisEngine):
    name = "regex"

    def __init__(self, repo_path: str, rules: list[dict]):
        self._repo_path = Path(repo_path)
        self._line_rules: list[dict] = []
        self._multiline_rules: list[dict] = []
        for rule in rules:
            try:
                compiled = re.compile(rule.get("pattern", ""))
            except re.error as exc:
                logger.warning("Invalid regex pattern for %s: %s", rule.get("rule_id"), exc)
                continue
            entry = {**rule, "_regex": compiled}
            if rule.get("match_type") == "regex_multiline":
                self._multiline_rules.append(entry)
            else:
                self._line_rules.append(entry)

    async def is_available(self) -> bool:
        return True

    async def analyze(self, file_path: str, language: str) -> List[AnalysisFinding]:
        try:
            full_path = self._repo_path / file_path
            content = await asyncio.to_thread(self._read_file, full_path)
            if content is None:
                return []
            lines = content.splitlines()

            findings: list[AnalysisFinding] = []
            findings.extend(self._scan_line_rules(lines, file_path, language))
            findings.extend(self._scan_multiline_rules(content, lines, file_path, language))
            return findings
        except Exception as exc:
            logger.debug("Regex engine failed for %s: %s", file_path, exc)
            return []

    @staticmethod
    def _read_file(path: Path) -> str | None:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except OSError:
            return None

    @staticmethod
    def _language_matches(rule_language: str, file_language: str) -> bool:
        if not rule_language:
            return True
        if rule_language == "any":
            return True
        return rule_language.lower() == (file_language or "").lower()

    @staticmethod
    def _issue_type(rule_id: str) -> str:
        if rule_id.startswith("REGEX-"):
            return rule_id[len("REGEX-"):]
        return rule_id

    @staticmethod
    def _build_snippet(lines: list[str], start_line: int, end_line: int | None = None) -> str:
        if end_line is None:
            end_line = start_line
        start = max(0, start_line - 2)
        end = min(len(lines), end_line + 1)
        return "\n".join(lines[start:end])

    def _scan_line_rules(
        self, lines: list[str], file_path: str, language: str
    ) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        for rule in self._line_rules:
            if not self._language_matches(rule.get("language", "any"), language):
                continue
            pattern = rule.get("_regex")
            if pattern is None:
                continue

            for line_num, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue
                snippet = self._build_snippet(lines, line_num)
                findings.append(
                    AnalysisFinding(
                        rule_id=rule.get("rule_id", ""),
                        engine_source=self.name,
                        file_path=file_path,
                        line_number=line_num,
                        end_line=line_num,
                        column=1,
                        severity=rule.get("severity", "low"),
                        defect_family=rule.get("defect_family", "best_practice"),
                        message=rule.get("message", "Issue detected"),
                        fix_hint=rule.get("fix_hint"),
                        cwe_id=rule.get("cwe_id"),
                        owasp_ref=rule.get("owasp_ref"),
                        code_snippet=snippet,
                        issue_type=self._issue_type(rule.get("rule_id", "")),
                    )
                )
        return findings

    def _scan_multiline_rules(
        self, content: str, lines: list[str], file_path: str, language: str
    ) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        for rule in self._multiline_rules:
            if not self._language_matches(rule.get("language", "any"), language):
                continue
            pattern = rule.get("_regex")
            if pattern is None:
                continue

            for match in pattern.finditer(content):
                line_num = content.count("\n", 0, match.start()) + 1
                end_line = line_num + match.group(0).count("\n")
                snippet = self._build_snippet(lines, line_num, end_line)
                findings.append(
                    AnalysisFinding(
                        rule_id=rule.get("rule_id", ""),
                        engine_source=self.name,
                        file_path=file_path,
                        line_number=line_num,
                        end_line=end_line,
                        column=1,
                        severity=rule.get("severity", "low"),
                        defect_family=rule.get("defect_family", "best_practice"),
                        message=rule.get("message", "Issue detected"),
                        fix_hint=rule.get("fix_hint"),
                        cwe_id=rule.get("cwe_id"),
                        owasp_ref=rule.get("owasp_ref"),
                        code_snippet=snippet,
                        issue_type=self._issue_type(rule.get("rule_id", "")),
                    )
                )
        return findings
