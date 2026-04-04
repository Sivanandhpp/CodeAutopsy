"""
Ollama Service — Local AI Code Analysis
=========================================
Integrates with Ollama (qwen2.5-coder:3b) for deep code analysis.
Analyzes files for bugs, vulnerabilities, performance issues, and code smells.
Returns structured JSON findings with severity levels and actionable fixes.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# ─── Semaphore for concurrency control ───────────────────────
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        settings = get_settings()
        _semaphore = asyncio.Semaphore(settings.OLLAMA_MAX_CONCURRENT)
    return _semaphore


# ─── System Prompt ───────────────────────────────────────────
ANALYSIS_SYSTEM_PROMPT = """You are an expert code reviewer and security auditor.
Analyze the provided code and identify issues in these categories:

1. **Critical Bugs** — Logic errors, null pointer dereferences, race conditions, data corruption
2. **Security Vulnerabilities** — Injection flaws, auth bypasses, data exposure, unsafe deserialization
3. **Performance Issues** — N+1 queries, memory leaks, blocking I/O, unnecessary allocations
4. **Code Smells** — God functions, tight coupling, magic numbers, code duplication, poor naming

For each finding, provide:
- `type`: one of "bug", "vulnerability", "performance", "code_smell"
- `severity`: one of "critical", "high", "medium", "low"
- `line`: the line number (integer or null if general)
- `description`: clear explanation of the issue (1-2 sentences)
- `fix`: concise actionable fix suggestion (1-2 sentences)
- `category`: specific subcategory (e.g. "sql-injection", "memory-leak", "god-function")

You MUST respond with ONLY valid JSON. No markdown, no explanation outside JSON.
Use this exact format:
{
  "findings": [
    {
      "type": "vulnerability",
      "severity": "critical",
      "line": 42,
      "description": "SQL query built with string concatenation allows injection",
      "fix": "Use parameterized queries with bound parameters instead",
      "category": "sql-injection"
    }
  ]
}

If no issues are found, return: {"findings": []}
Be conservative — only report genuine issues, not style preferences.
Focus on actionable findings that developers should fix."""


def _build_analysis_prompt(content: str, language: str, file_path: str) -> str:
    """Build the user prompt for file analysis."""
    # Truncate very large files to avoid overwhelming the model
    max_chars = 6000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n... [truncated for analysis]"

    return (
        f"Analyze this {language} file for bugs, security vulnerabilities, "
        f"performance issues, and code smells.\n\n"
        f"**File:** `{file_path}`\n"
        f"**Language:** {language}\n\n"
        f"```{language}\n{content}\n```\n\n"
        f"Return your findings as JSON."
    )


# ─── Core Analysis Function ─────────────────────────────────

async def analyze_file(
    content: str,
    language: str,
    file_path: str,
) -> list[dict]:
    """
    Analyze a single file using the local Ollama model.
    Returns a list of finding dicts.
    Thread-safe with semaphore-based concurrency control.
    """
    settings = get_settings()

    if not settings.OLLAMA_ENABLED:
        return []

    semaphore = _get_semaphore()

    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": _build_analysis_prompt(
                                    content, language, file_path
                                ),
                            },
                        ],
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0.2,
                            "num_predict": 2048,
                        },
                    },
                )
                response.raise_for_status()

            data = response.json()
            message_content = data.get("message", {}).get("content", "")

            # Parse JSON response
            parsed = json.loads(message_content)
            findings = parsed.get("findings", [])

            # Validate and normalize findings
            valid_findings = []
            for f in findings:
                if not isinstance(f, dict):
                    continue
                valid_findings.append({
                    "file_path": file_path,
                    "type": f.get("type", "code_smell"),
                    "severity": f.get("severity", "low"),
                    "line": f.get("line"),
                    "description": f.get("description", ""),
                    "fix": f.get("fix", ""),
                    "category": f.get("category", ""),
                })

            logger.info(
                f"Ollama analyzed {file_path}: {len(valid_findings)} findings"
            )
            return valid_findings

        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout for {file_path}")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Ollama returned invalid JSON for {file_path}: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(f"Ollama HTTP error for {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Ollama analysis failed for {file_path}: {e}")
            return []


async def analyze_files_batch(
    files: list[dict],
    repo_path: str,
    progress_callback=None,
) -> list[dict]:
    """
    Analyze multiple files concurrently with Ollama.
    
    Args:
        files: List of dicts with 'path' and 'language' keys
        repo_path: Root path of the cloned repository
        progress_callback: Optional async callback(files_done, total_files)
    
    Returns:
        Combined list of all findings from all files
    """
    settings = get_settings()

    if not settings.OLLAMA_ENABLED:
        return []

    # Filter to analyzable languages
    analyzable_langs = {
        "python", "javascript", "typescript", "java", "go", "ruby",
        "php", "c", "c++", "c#", "rust", "kotlin", "swift", "shell",
    }

    target_files = [
        f for f in files
        if f.get("language", "").lower() in analyzable_langs
        and f.get("lines", 0) > 5      # Skip trivially small files
        and f.get("lines", 0) < 2000    # Skip very large files
    ]

    if not target_files:
        return []

    # Check if Ollama is available
    if not await is_ollama_available():
        logger.warning("Ollama is not available — skipping AI analysis")
        return []

    all_findings = []
    total = len(target_files)
    done = 0

    # Process in batches using gather with semaphore-controlled concurrency
    async def _process_file(file_info: dict) -> list[dict]:
        nonlocal done
        try:
            full_path = Path(repo_path) / file_info["path"]
            if not full_path.exists():
                return []

            content = full_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                return []

            findings = await analyze_file(
                content=content,
                language=file_info["language"],
                file_path=file_info["path"],
            )
            return findings
        except Exception as e:
            logger.error(f"Failed to process {file_info.get('path')}: {e}")
            return []
        finally:
            done += 1
            if progress_callback:
                try:
                    await progress_callback(done, total)
                except Exception:
                    pass

    # Run all analyses concurrently (semaphore controls actual parallelism)
    tasks = [_process_file(f) for f in target_files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_findings.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"File analysis task failed: {result}")

    logger.info(
        f"Ollama batch analysis complete: "
        f"{total} files → {len(all_findings)} findings"
    )
    return all_findings


async def is_ollama_available() -> bool:
    """Check if Ollama service is reachable and the model is loaded."""
    settings = get_settings()
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
