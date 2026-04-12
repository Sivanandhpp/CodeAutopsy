"""
Repo Storage Service — Single Source of Truth for Clone Paths
==============================================================
Every part of the app that needs to know WHERE repos are stored
must go through this module. No exceptions.

Resolution priority (first match wins):
  1. REPOS_DIR env var    → explicit override (cloud, custom setups)
  2. /repos_data          → Docker volume (auto-detected)
  3. ./repos              → relative to CWD (bare-metal Linux/macOS/Windows)
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache so we only resolve + log once per process
_resolved_base: Path | None = None


class RepoStorageService:
    """Resolves where to clone repos. Works on every platform."""

    @staticmethod
    def get_base_path() -> Path:
        """
        Return the root directory for all cloned repos.
        Creates the directory if it doesn't exist.
        Result is cached for the lifetime of the process.
        """
        global _resolved_base
        if _resolved_base is not None:
            return _resolved_base

        # 1. Explicit env var — highest priority
        env_path = os.environ.get("REPOS_DIR", "").strip()
        if env_path:
            base = Path(env_path).resolve()
            base.mkdir(parents=True, exist_ok=True)
            _resolved_base = base
            logger.info(f"📂 Repos dir (env REPOS_DIR): {base}")
            return base

        # 2. Docker volume at /repos_data — auto-detected
        docker_mount = Path("/repos_data")
        if docker_mount.exists():
            docker_mount.mkdir(parents=True, exist_ok=True)
            _resolved_base = docker_mount
            logger.info(f"📂 Repos dir (Docker volume): {docker_mount}")
            return docker_mount

        # 3. ./repos relative to working directory — cross-platform fallback
        local = Path.cwd() / "repos"
        local.mkdir(parents=True, exist_ok=True)
        _resolved_base = local
        logger.info(f"📂 Repos dir (local): {local}")
        return local

    @staticmethod
    def get_clone_path(repo_name: str, analysis_id: str) -> Path:
        """
        Returns deterministic clone path:
        <base>/<analysis_id>/<repo_name>
        Using analysis_id as a namespace prevents collisions on
        concurrent analysis of the same repo.
        """
        base = RepoStorageService.get_base_path()
        path = base / analysis_id / repo_name
        path.mkdir(parents=True, exist_ok=True)
        return path
