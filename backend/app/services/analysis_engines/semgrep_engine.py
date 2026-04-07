from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List

from app.schemas.analysis import AnalysisFinding
from app.services.analysis_engines.base import BaseAnalysisEngine

logger = logging.getLogger(__name__)


class SemgrepEngine(BaseAnalysisEngine):
    name = "semgrep"

    def __init__(self, repo_path: str, rules_by_id: dict[str, dict]):
        self._repo_path = Path(repo_path)
        self._rules_by_id = rules_by_id
        self._available: bool | None = None
        self._results_by_file: dict[str, list[AnalysisFinding]] | None = None
        self._lock = asyncio.Lock()

    async def is_available(self) -> bool:
        if self._available is None:
            self._available = await asyncio.to_thread(self._check_semgrep)
        return self._available

    async def analyze(self, file_path: str, language: str) -> List[AnalysisFinding]:
        if not await self.is_available():
            return []
        await self._ensure_results_loaded()
        return list(self._results_by_file.get(file_path, [])) if self._results_by_file else []

    @staticmethod
    def _check_semgrep() -> bool:
        try:
            result = subprocess.run(
                ["semgrep", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def _ensure_results_loaded(self) -> None:
        if self._results_by_file is not None:
            return
        async with self._lock:
            if self._results_by_file is not None:
                return
            self._results_by_file = await asyncio.to_thread(self._run_semgrep_scan)

    def _run_semgrep_scan(self) -> dict[str, list[AnalysisFinding]]:
        try:
            result = subprocess.run(
                [
                    "semgrep", "scan",
                    "--config=p/security-audit",
                    "--config=p/secrets",
                    "--json",
                    "--timeout=30",
                    "--timeout-threshold=3",
                    "--max-target-bytes=500000",
                    "--exclude=node_modules",
                    "--exclude=vendor",
                    "--exclude=dist",
                    "--exclude=build",
                    "--exclude=.git",
                    "--exclude=__pycache__",
                    "--exclude=*.min.js",
                    "--exclude=*.min.css",
                    "--exclude=*.lock",
                    "--exclude=*.map",
                    str(self._repo_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self._repo_path),
            )
        except subprocess.TimeoutExpired:
            logger.warning("Semgrep analysis timed out")
            return {}
        except Exception as exc:
            logger.warning("Semgrep error: %s", exc)
            return {}

        if not result.stdout:
            return {}

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

        findings_by_file: dict[str, list[AnalysisFinding]] = {}
        for finding in self._parse_results(payload):
            findings_by_file.setdefault(finding.file_path, []).append(finding)
        return findings_by_file

    def _parse_results(self, payload: dict) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        for result in payload.get("results", []):
            file_path = result.get("path", "")
            if file_path.startswith(str(self._repo_path)):
                file_path = os.path.relpath(file_path, str(self._repo_path))
            file_path = file_path.replace("\\", "/")

            rule_id = result.get("check_id", "unknown")
            metadata = result.get("extra", {}).get("metadata", {})
            rule_meta = self._rules_by_id.get(rule_id)

            severity = self._map_severity(result.get("extra", {}).get("severity"), rule_meta)
            defect_family = self._map_defect_family(rule_id, metadata, rule_meta)
            message = rule_meta.get("message") if rule_meta else result.get("extra", {}).get("message", "Issue detected")

            start = result.get("start", {})
            end = result.get("end", {})
            line_number = start.get("line", 0) or 0
            end_line = end.get("line", line_number) or line_number
            column = start.get("col", 0) or 0
            code_snippet = result.get("extra", {}).get("lines", "")

            findings.append(
                AnalysisFinding(
                    rule_id=rule_id,
                    engine_source=self.name,
                    file_path=file_path,
                    line_number=line_number,
                    end_line=end_line,
                    column=column,
                    severity=severity,
                    defect_family=defect_family,
                    message=message,
                    fix_hint=rule_meta.get("fix_hint") if rule_meta else None,
                    cwe_id=self._metadata_first(metadata, "cwe") if rule_meta is None else rule_meta.get("cwe_id"),
                    owasp_ref=self._metadata_first(metadata, "owasp") if rule_meta is None else rule_meta.get("owasp_ref"),
                    code_snippet=code_snippet,
                    issue_type=self._issue_type_from_rule_id(rule_id),
                )
            )

        return findings

    @staticmethod
    def _metadata_first(metadata: dict, key: str) -> str | None:
        value = metadata.get(key)
        if isinstance(value, list):
            return str(value[0]) if value else None
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _map_severity(semgrep_severity: str | None, rule_meta: dict | None) -> str:
        if rule_meta and rule_meta.get("severity"):
            return rule_meta["severity"]
        mapping = {
            "ERROR": "high",
            "WARNING": "medium",
            "INFO": "info",
        }
        if not semgrep_severity:
            return "medium"
        return mapping.get(semgrep_severity.upper(), "medium")

    @staticmethod
    def _map_defect_family(rule_id: str, metadata: dict, rule_meta: dict | None) -> str:
        if rule_meta and rule_meta.get("defect_family"):
            return rule_meta["defect_family"]

        text = f"{rule_id} {metadata.get('category', '')}".lower()
        if "xss" in text:
            return "xss"
        if "ssrf" in text:
            return "ssrf"
        if "path" in text and "travers" in text:
            return "path_traversal"
        if "deserialize" in text or "pickle" in text:
            return "deserialization"
        if "sql" in text or "injection" in text or "command" in text or "ldap" in text or "xpath" in text:
            return "injection"
        if "secret" in text or "token" in text or "credential" in text:
            return "secrets"
        if "crypto" in text or "hash" in text or "tls" in text or "ssl" in text:
            return "crypto"
        if "auth" in text or "jwt" in text or "csrf" in text or "session" in text:
            return "auth"
        if "dependency" in text or "supply" in text or "package" in text:
            return "supply_chain"
        if "maintain" in text or "style" in text:
            return "maintainability"
        if "best" in text or "practice" in text:
            return "best_practice"
        return "reliability"

    @staticmethod
    def _issue_type_from_rule_id(rule_id: str) -> str:
        parts = rule_id.split(".")
        if parts:
            return parts[-1].replace("_", "-")
        return rule_id
