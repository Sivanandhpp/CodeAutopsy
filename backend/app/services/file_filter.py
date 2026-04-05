"""
File Filter — Smart Stack Detection & User-Authored File Selection
===================================================================
Solves the core performance problem: Ollama was scanning entire repos including
node_modules, dist, vendor, lockfiles, and generated code. This module:

1. Reads manifest files (package.json, pyproject.toml, etc.) to detect the
   project's tech stack in O(1) — no tree-walking needed.
2. Builds a whitelist of user-authored source files only, respecting the
   detected stack's conventions (src dirs, extensions).
3. Sorts files smallest-first so Ollama produces results quickly for small
   files, giving the user early feedback.

Usage:
    ff = FileFilter(repo_path="/app/data/repos/example_abc123")
    stack = ff.detect_stack()          # -> ProjectStack
    files = ff.user_authored_files()   # -> list[Path], sorted by size
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Directories that are NEVER user-authored code ───────────
IGNORE_DIRS: set[str] = {
    # Package managers / dependencies
    "node_modules", ".pnpm", "bower_components", "jspm_packages",
    # Python virtual environments
    ".venv", "venv", "env", ".env", "virtualenv", ".virtualenv",
    # Python caches & build artifacts
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "htmlcov", "eggs", ".eggs", ".tox", ".nox",
    # Build outputs
    "dist", "build", "out", "_build", ".build",
    # Framework-specific build dirs
    ".next", ".nuxt", ".svelte-kit", ".output", ".vercel", ".netlify",
    # Coverage & test artifacts
    "coverage", ".coverage", ".nyc_output",
    # Version control
    ".git", ".hg", ".svn",
    # IDE / editor
    ".idea", ".vscode", ".vs",
    # Compiled languages
    "target",             # Rust / Java / Maven
    ".cargo",             # Rust registry cache
    "bin", "obj",         # C# / .NET
    "vendor",             # Go / PHP / Ruby
    # Docker
    ".docker",
    # Misc
    ".cache", ".tmp", "tmp", "temp",
}

# ─── File extensions that are never worth analyzing ──────────
IGNORE_EXTENSIONS: set[str] = {
    # Lock files
    ".lock",
    # Logs
    ".log",
    # Minified bundles
    ".min.js", ".min.css", ".min.mjs",
    # Source maps
    ".map",
    # Images & fonts (binary)
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    # Compiled / bytecode
    ".pyc", ".pyo", ".class", ".jar", ".dll", ".so", ".dylib", ".exe",
    # Database
    ".sqlite", ".sqlite3", ".db",
}

# ─── Filenames that are never worth analyzing ────────────────
IGNORE_FILENAMES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "Cargo.lock",
    "composer.lock", "Gemfile.lock", "go.sum",
    ".DS_Store", "Thumbs.db",
    ".gitignore", ".dockerignore", ".editorconfig",
    ".prettierrc", ".eslintrc", ".eslintignore",
}


# ─── Stack detection configuration ──────────────────────────

@dataclass
class ProjectStack:
    """Detected project technology stack."""
    language: str                           # Primary language: "python", "javascript", etc.
    frameworks: list[str] = field(default_factory=list)   # e.g. ["fastapi", "react"]
    src_dirs: list[str] = field(default_factory=list)     # Preferred source directories
    extensions: list[str] = field(default_factory=list)   # File extensions to include
    manifest: Optional[str] = None                        # Which manifest was detected


# Maps: manifest filename → (primary language, default extensions, default src_dirs)
_MANIFEST_MAP: dict[str, tuple[str, list[str], list[str]]] = {
    "package.json":      ("javascript", [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"],
                          ["src", "app", "pages", "components", "lib", "utils", "hooks", "services", "api", "server", "client"]),
    "pyproject.toml":    ("python", [".py"],
                          ["src", "app", "api", "services", "models", "utils", "core", "lib", "tests"]),
    "setup.py":          ("python", [".py"],
                          ["src", "app", "api", "services", "models", "utils", "core", "lib"]),
    "setup.cfg":         ("python", [".py"],
                          ["src", "app", "api", "services", "models", "utils", "core", "lib"]),
    "requirements.txt":  ("python", [".py"],
                          ["src", "app", "api", "services", "models", "utils", "core", "lib"]),
    "Pipfile":           ("python", [".py"],
                          ["src", "app", "api", "services", "models", "utils", "core", "lib"]),
    "go.mod":            ("go", [".go"],
                          ["cmd", "internal", "pkg", "api", "server", "handler", "service", "model"]),
    "Cargo.toml":        ("rust", [".rs"],
                          ["src", "lib", "bin", "examples"]),
    "pom.xml":           ("java", [".java", ".kt", ".scala"],
                          ["src/main/java", "src/main/kotlin", "src/main/scala"]),
    "build.gradle":      ("java", [".java", ".kt", ".groovy"],
                          ["src/main/java", "src/main/kotlin"]),
    "build.gradle.kts":  ("java", [".java", ".kt"],
                          ["src/main/java", "src/main/kotlin"]),
    "mix.exs":           ("elixir", [".ex", ".exs"],
                          ["lib", "config"]),
    "Gemfile":           ("ruby", [".rb", ".erb"],
                          ["app", "lib", "config"]),
    "composer.json":     ("php", [".php"],
                          ["src", "app", "lib"]),
}

# Framework detection patterns for package.json dependencies
_JS_FRAMEWORK_PATTERNS: dict[str, str] = {
    "react": "react",
    "next": "nextjs",
    "vue": "vue",
    "nuxt": "nuxt",
    "svelte": "svelte",
    "angular": "angular",
    "express": "express",
    "fastify": "fastify",
    "nestjs": "@nestjs/core",
    "hono": "hono",
}

# Framework detection patterns for pyproject.toml / requirements.txt
_PY_FRAMEWORK_PATTERNS: dict[str, str] = {
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "starlette": "starlette",
    "tornado": "tornado",
    "sanic": "sanic",
}


class FileFilter:
    """
    Smart file filter that detects the project stack and returns only
    user-authored source files suitable for AI analysis.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self._stack: Optional[ProjectStack] = None

    # ─── Stack Detection ─────────────────────────────────────

    def detect_stack(self) -> ProjectStack:
        """
        Detect the project's tech stack by reading manifest files.
        This is O(1) — it only reads a few small files, never walks the tree.
        Results are cached on the instance.
        """
        if self._stack is not None:
            return self._stack

        # Check each manifest in priority order
        for manifest_name, (language, extensions, src_dirs) in _MANIFEST_MAP.items():
            manifest_path = self.repo_path / manifest_name
            if manifest_path.exists():
                frameworks = self._detect_frameworks(manifest_path, manifest_name, language)

                # Refine src_dirs based on what actually exists
                existing_src_dirs = [
                    d for d in src_dirs
                    if (self.repo_path / d).is_dir()
                ]

                self._stack = ProjectStack(
                    language=language,
                    frameworks=frameworks,
                    src_dirs=existing_src_dirs if existing_src_dirs else src_dirs,
                    extensions=extensions,
                    manifest=manifest_name,
                )
                logger.info(
                    f"Stack detected: {language} "
                    f"({', '.join(frameworks) if frameworks else 'no framework'}) "
                    f"via {manifest_name}"
                )
                return self._stack

        # Fallback: multi-language repo — scan by extension frequency
        self._stack = self._fallback_detect()
        return self._stack

    def _detect_frameworks(
        self, manifest_path: Path, manifest_name: str, language: str
    ) -> list[str]:
        """Extract framework names from a manifest file."""
        frameworks: list[str] = []

        try:
            content = manifest_path.read_text(encoding="utf-8", errors="ignore")

            if manifest_name == "package.json":
                try:
                    pkg = json.loads(content)
                    all_deps = {
                        **pkg.get("dependencies", {}),
                        **pkg.get("devDependencies", {}),
                    }
                    for framework, dep_name in _JS_FRAMEWORK_PATTERNS.items():
                        if dep_name in all_deps:
                            frameworks.append(framework)
                except json.JSONDecodeError:
                    pass

            elif language == "python":
                # Simple substring match against the raw file content
                content_lower = content.lower()
                for framework, pattern in _PY_FRAMEWORK_PATTERNS.items():
                    if pattern in content_lower:
                        frameworks.append(framework)

            elif manifest_name == "Cargo.toml":
                content_lower = content.lower()
                if "actix" in content_lower:
                    frameworks.append("actix")
                if "rocket" in content_lower:
                    frameworks.append("rocket")
                if "axum" in content_lower:
                    frameworks.append("axum")
                if "tokio" in content_lower:
                    frameworks.append("tokio")

            elif manifest_name == "go.mod":
                content_lower = content.lower()
                if "gin-gonic" in content_lower:
                    frameworks.append("gin")
                if "echo" in content_lower:
                    frameworks.append("echo")
                if "fiber" in content_lower:
                    frameworks.append("fiber")

        except Exception as e:
            logger.debug(f"Framework detection failed for {manifest_name}: {e}")

        return frameworks

    def _fallback_detect(self) -> ProjectStack:
        """
        Fallback when no manifest file is found.
        Counts file extensions in the top 2 directory levels to guess the stack.
        """
        ext_count: dict[str, int] = {}

        for item in self.repo_path.rglob("*"):
            # Only check top 2 levels to keep it fast
            try:
                relative = item.relative_to(self.repo_path)
                if len(relative.parts) > 3:
                    continue
            except ValueError:
                continue

            if item.is_file() and item.suffix:
                ext = item.suffix.lower()
                if ext not in IGNORE_EXTENSIONS:
                    ext_count[ext] = ext_count.get(ext, 0) + 1

        if not ext_count:
            return ProjectStack(
                language="unknown",
                extensions=[".py", ".js", ".ts", ".go", ".rs", ".java"],
                src_dirs=["src", "app", "lib"],
            )

        # Find dominant extension
        dominant_ext = max(ext_count, key=ext_count.get)

        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".rs": "rust", ".java": "java",
            ".rb": "ruby", ".php": "php", ".ex": "elixir",
        }

        language = ext_to_lang.get(dominant_ext, "unknown")

        # Find default extensions for this language from any manifest config
        for _, (lang, exts, src_dirs) in _MANIFEST_MAP.items():
            if lang == language:
                return ProjectStack(
                    language=language,
                    extensions=exts,
                    src_dirs=[d for d in src_dirs if (self.repo_path / d).is_dir()] or src_dirs,
                )

        return ProjectStack(
            language=language,
            extensions=[dominant_ext],
            src_dirs=["src", "app", "lib"],
        )

    # ─── User-Authored File Selection ────────────────────────

    def user_authored_files(self, max_files: int = 80) -> list[Path]:
        """
        Walk the repo and return only user-authored source files.

        Strategy:
        1. If src_dirs exist in the repo, ONLY walk those directories.
           This dramatically reduces noise for monorepos.
        2. If no src_dirs exist, walk the entire repo but aggressively
           filter out IGNORE_DIRS and IGNORE_EXTENSIONS.
        3. Sort by file size ascending — small files get analyzed first
           so the user sees quick wins early.
        4. Cap at max_files to prevent Ollama from running for hours.
        """
        stack = self.detect_stack()
        candidates: list[tuple[Path, int]] = []  # (path, size_bytes)

        # Determine walk roots
        walk_roots: list[Path] = []

        if stack.src_dirs:
            for src_dir in stack.src_dirs:
                src_path = self.repo_path / src_dir
                if src_path.is_dir():
                    walk_roots.append(src_path)

        # Also include root-level source files (e.g. main.py, app.py, manage.py)
        walk_roots.append(self.repo_path)

        seen: set[Path] = set()

        for root in walk_roots:
            if root == self.repo_path:
                # For repo root, only consider top-level files (not subdirs
                # unless they're in src_dirs which we already handle above)
                iterator = self._walk_directory(root, max_depth=1 if walk_roots[:-1] else None)
            else:
                iterator = self._walk_directory(root, max_depth=None)

            for file_path in iterator:
                if file_path in seen:
                    continue
                seen.add(file_path)

                # Extension filter
                ext = file_path.suffix.lower()
                if ext in IGNORE_EXTENSIONS:
                    continue

                # Must match stack extensions (if we know the stack)
                if stack.extensions and ext not in stack.extensions:
                    continue

                # Filename filter
                if file_path.name in IGNORE_FILENAMES:
                    continue

                # Skip hidden files (except config that might matter)
                if file_path.name.startswith("."):
                    continue

                # Skip empty or massive files
                try:
                    size = file_path.stat().st_size
                    if size == 0 or size > 500_000:  # 500KB max
                        continue
                except OSError:
                    continue

                # Skip binary files (quick check: read first 512 bytes)
                if self._is_binary(file_path):
                    continue

                candidates.append((file_path, size))

        # Sort by size ascending — smallest files first for fast early results
        candidates.sort(key=lambda x: x[1])

        # Cap at max_files
        selected = [path for path, _ in candidates[:max_files]]

        logger.info(
            f"FileFilter: {len(selected)} files selected for AI analysis "
            f"(from {len(candidates)} candidates, stack={stack.language})"
        )
        return selected

    def _walk_directory(self, root: Path, max_depth: Optional[int] = None):
        """
        Generator that yields file Paths, skipping IGNORE_DIRS.
        Optional max_depth limits recursion (1 = only direct children).
        """
        try:
            for entry in root.iterdir():
                if entry.is_dir():
                    if entry.name in IGNORE_DIRS:
                        continue
                    if max_depth is not None and max_depth <= 0:
                        continue
                    next_depth = max_depth - 1 if max_depth is not None else None
                    yield from self._walk_directory(entry, next_depth)
                elif entry.is_file():
                    yield entry
        except PermissionError:
            pass

    @staticmethod
    def _is_binary(file_path: Path) -> bool:
        """Quick binary detection: check for null bytes in the first 512 bytes."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(512)
                return b"\x00" in chunk
        except (OSError, IOError):
            return True
