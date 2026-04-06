"""Seed analysis_rules with legacy regex rules.

Run:
    python -m app.db.seeds.rules_seed
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.database import get_session_factory
from app.models.analysis_rule import AnalysisRule
from app.services.static_analyzer import REGEX_RULES


DEFECT_FAMILY_MAP = {
    "command-injection": "injection",
    "sql-injection": "injection",
    "sql-injection-concatenation": "injection",
    "xss-innerhtml": "xss",
    "xss-document-write": "xss",
    "jwt-no-verify": "auth",
    "insecure-deserialization": "deserialization",
    "xxe-vulnerability": "injection",
    "hardcoded-secret": "secrets",
    "hardcoded-ip": "best_practice",
    "eval-usage": "injection",
    "exec-usage": "injection",
    "open-redirect": "auth",
    "path-traversal": "path_traversal",
    "ssrf": "ssrf",
    "insecure-hash": "crypto",
    "insecure-random": "crypto",
    "insecure-random-js": "crypto",
    "prototype-pollution": "injection",
    "insecure-cookie": "auth",
    "cors-wildcard": "auth",
    "missing-csrf": "auth",
    "sensitive-data-logging": "secrets",
    "null-pointer": "reliability",
    "null-dereference-pattern": "reliability",
    "division-by-zero": "reliability",
    "unchecked-division": "reliability",
    "empty-except": "reliability",
    "bare-except": "reliability",
    "empty-catch-js": "reliability",
    "debug-enabled": "best_practice",
    "http-not-https": "crypto",
    "disabled-ssl-verify": "crypto",
    "assert-in-production": "reliability",
    "mutable-default-arg": "reliability",
    "global-variable": "maintainability",
    "unsafe-regex": "reliability",
    "no-timeout-request": "reliability",
    "file-not-closed": "reliability",
    "insecure-file-permissions": "best_practice",
    "race-condition": "reliability",
    "unvalidated-redirect": "auth",
    "template-injection": "injection",
    "unsafe-yaml": "deserialization",
    "wildcard-import": "maintainability",
    "dangerously-set-html": "xss",
    "no-error-handling-promise": "reliability",
    "var-usage": "best_practice",
    "loose-equality": "reliability",
    "console-log": "best_practice",
    "python-print": "best_practice",
    "react-missing-deps": "reliability",
    "todo-fixme": "maintainability",
    "hardcoded-port": "best_practice",
    "buffer-overflow-c": "reliability",
    "format-string-c": "injection",
    "memory-leak-c": "reliability",
    "null-check-after-deref": "reliability",
    "unsafe-unwrap": "reliability",
    "go-error-ignored": "reliability",
    "shell-injection": "injection",
    "php-type-juggling": "auth",
    "php-file-include": "path_traversal",
    "nosql-injection": "injection",
    "timing-attack": "crypto",
    "deprecated-function": "maintainability",
    "logging-exception": "reliability",
}

SEVERITY_OVERRIDE = {
    "console-log": "trace",
    "python-print": "trace",
    "todo-fixme": "info",
    "var-usage": "info",
    "wildcard-import": "info",
    "hardcoded-port": "info",
}


def _rule_name(rule_id: str) -> str:
    parts = rule_id.replace("_", "-").split("-")
    return " ".join(p.capitalize() for p in parts if p)


def _derive_language(languages: list[str]) -> str:
    if not languages:
        return "any"
    if len(languages) == 1:
        return languages[0]
    return "any"


def _derive_match_type(pattern: str) -> str:
    return "regex_multiline" if "\\n" in pattern else "regex_line"


def _build_seed_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    for rule in REGEX_RULES:
        rule_key = rule.get("id")
        if not rule_key:
            raise ValueError("Rule is missing id")

        if rule_key not in DEFECT_FAMILY_MAP:
            raise ValueError(f"Missing defect family mapping for {rule_key}")

        severity = SEVERITY_OVERRIDE.get(rule_key, rule.get("severity", "low"))
        language = _derive_language(rule.get("languages", []))
        is_active = bool(rule.get("languages"))

        rows.append({
            "rule_id": f"REGEX-{rule_key}",
            "name": _rule_name(rule_key),
            "description": rule.get("message", ""),
            "language": language,
            "defect_family": DEFECT_FAMILY_MAP[rule_key],
            "severity": severity,
            "pattern": rule.get("pattern", ""),
            "match_type": _derive_match_type(rule.get("pattern", "")),
            "message": rule.get("message", ""),
            "fix_hint": None,
            "cwe_id": None,
            "owasp_ref": None,
            "is_active": is_active,
            "created_at": now,
            "updated_at": now,
        })

    return rows


async def seed_rules() -> None:
    rows = _build_seed_rows()
    session_factory = get_session_factory()

    async with session_factory() as session:
        stmt = insert(AnalysisRule).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["rule_id"])
        await session.execute(stmt)
        await session.commit()

    print(f"Seed complete: {len(rows)} rules prepared.")


def main() -> None:
    asyncio.run(seed_rules())


if __name__ == "__main__":
    main()
