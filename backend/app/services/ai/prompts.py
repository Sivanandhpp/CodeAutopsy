"""
AI Prompt Templates
===================
Centralised, expert-level prompts shared by every provider.
Each prompt is tuned for both large cloud models (Groq/LLaMA 3.1) and
smaller local models (Ollama/Qwen 2.5-coder) — clear structure, explicit
JSON schema, chain-of-thought guidance.

Usage
-----
    from app.services.ai.prompts import build_fix_messages, build_summary_prompt
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Optional


# ═════════════════════════════════════════════════════════════════
# ISSUE FIX — System + User
# ═════════════════════════════════════════════════════════════════

FIX_SYSTEM_PROMPT = """\
You are a principal-level security engineer performing a code review.
Your task is to analyze a flagged code issue and produce an actionable fix.

INSTRUCTIONS
────────────
1. Read the issue type, language, and flagged code carefully.
2. Think step-by-step:
   a. Confirm whether this is a real vulnerability or a false positive.
   b. Identify the root cause — *why* is this code dangerous?
   c. Decide on the minimal, correct fix that preserves functionality.
   d. Write the patched code — it must compile/run and be a drop-in replacement.
3. Rate your confidence from 0.0 (likely false positive) to 1.0 (certain real issue).

RESPONSE FORMAT — strict JSON, nothing else
────────────────────────────────────────────
{
  "root_cause": "1-2 sentences explaining WHY this is a problem",
  "fix_strategy": "2-3 sentences explaining HOW to fix it",
  "code_patch": "The corrected code snippet, ready to paste (NOT a diff)",
  "confidence": 0.85,
  "reasoning": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ..."
  ]
}

RULES
─────
• confidence < 0.3 if the code is NOT actually vulnerable — explain why.
• code_patch must be syntactically valid in the target language.
• reasoning must contain 2-4 short steps showing your chain of thought.
• Keep all text concise, specific, and actionable — no filler.
• Do NOT wrap the JSON in markdown code fences.
"""


def build_fix_user_prompt(
    code_snippet: str,
    defect_family: str,
    language: str,
    file_path: Optional[str] = None,
    context_before: str = "",
    context_after: str = "",
) -> str:
    """Build the user message for an issue-fix request."""
    sections = [
        f"**Defect Family:** {defect_family}",
        f"**Language:** {language}",
    ]

    if file_path:
        sections.append(f"**File:** {file_path}")

    if context_before:
        sections.append(f"\n**Context before:**\n```{language}\n{context_before}\n```")

    sections.append(f"\n**Flagged code:**\n```{language}\n{code_snippet}\n```")

    if context_after:
        sections.append(f"\n**Context after:**\n```{language}\n{context_after}\n```")

    sections.append(
        "\nAnalyze this issue step-by-step and respond with your fix recommendation "
        "as a single JSON object."
    )
    return "\n".join(sections)


def build_fix_messages(
    code_snippet: str,
    defect_family: str,
    language: str,
    file_path: Optional[str] = None,
    context_before: str = "",
    context_after: str = "",
) -> list[dict]:
    """Return the [system, user] message list for a fix request."""
    return [
        {"role": "system", "content": FIX_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_fix_user_prompt(
                code_snippet, defect_family, language,
                file_path, context_before, context_after,
            ),
        },
    ]


# ═════════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY — System + User
# ═════════════════════════════════════════════════════════════════

SUMMARY_SYSTEM_PROMPT = """\
You are an expert security and code-quality analyst writing an executive summary
for a development team lead. Be direct, practical, and concise.
"""

SUMMARY_USER_TEMPLATE = """\
Below is a condensed summary of issues found during a static-analysis scan of a
code repository. Write a markdown executive summary with EXACTLY these sections:

## Critical Risks
Describe the most severe findings that need immediate attention.
If none exist, say "No critical risks identified."

## Repeating Patterns
Group repeated findings into themes (e.g. "Hardcoded secrets across 12 files").
Mention approximate counts.

## Recommended Actions
A prioritised, numbered list of concrete next steps (max 5 items).

GUIDELINES
──────────
• Prioritise highest-severity risks first.
• Group similar findings — do NOT list every issue individually.
• If the repository is clean, say so plainly in 1-2 sentences.
• Keep the entire response under 400 words.

SCAN DATA:
{scan_summary}
"""


# ─── Helpers for building the summary payload ────────────────

SEVERITY_ORDER = {
    "blocker": 0,
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "info": 5,
    "trace": 6,
}
MAX_REPRESENTATIVE_ISSUES = 18
MAX_TOP_TYPES = 8


def _top_counts(items: list[dict], key: str, limit: int) -> dict[str, int]:
    counter = Counter()
    for item in items:
        value = str(item.get(key, "") or "").strip()
        if value:
            counter[value] += 1
    return dict(counter.most_common(limit))


def _representative_issues(issues: list[dict]) -> list[dict]:
    """Select a diverse, severity-sorted sample of issues for the prompt."""
    sampled: list[dict] = []
    seen: set[tuple[str, str, int, str]] = set()

    for issue in sorted(
        issues,
        key=lambda i: (
            SEVERITY_ORDER.get(i.get("severity", "info"), 4),
            str(i.get("defect_family", "")),
            str(i.get("file_path", "")),
            int(i.get("line_number", 0) or 0),
        ),
    ):
        dedup_key = (
            str(issue.get("defect_family", "")),
            str(issue.get("file_path", "")),
            int(issue.get("line_number", 0) or 0),
            str(issue.get("message", "")),
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        sampled.append({
            "file": issue.get("file_path", ""),
            "line": int(issue.get("line_number", 0) or 0),
            "severity": issue.get("severity", "low"),
            "family": issue.get("defect_family", "unknown"),
            "rule_id": issue.get("rule_id", ""),
            "message": str(issue.get("message", ""))[:180],
        })
        if len(sampled) >= MAX_REPRESENTATIVE_ISSUES:
            break
    return sampled


def build_summary_prompt(issues: list[dict]) -> str:
    """
    Build the full user prompt for an executive-summary request.
    Returns a single string (not a message list) because Ollama's
    ``/api/generate`` endpoint takes a flat ``prompt`` field.
    """
    severity_counts = {s: 0 for s in (
        "blocker", "critical", "high", "medium", "low", "info", "trace"
    )}
    for issue in issues:
        sev = str(issue.get("severity", "info")).lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    payload = {
        "total_issues": len(issues),
        "severity_counts": severity_counts,
        "top_defect_families": _top_counts(issues, "defect_family", MAX_TOP_TYPES),
        "top_rule_ids": _top_counts(issues, "rule_id", MAX_TOP_TYPES),
        "representative_issues": _representative_issues(issues),
    }

    return SUMMARY_USER_TEMPLATE.format(scan_summary=json.dumps(payload, indent=2))


def build_summary_messages(issues: list[dict]) -> list[dict]:
    """Return the [system, user] message list for a summary request."""
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": build_summary_prompt(issues)},
    ]
