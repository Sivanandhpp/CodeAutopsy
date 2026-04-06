"""Repo storage service for resolving clone paths across environments."""

import os
from pathlib import Path


class RepoStorageService:
    """
    Resolves where to clone a repo based on runtime environment.
    Priority order:
      1. REPOS_DATA_PATH env var (explicit override, highest priority)
      2. Docker volume mount at /repos_data (detected by os.path.ismount)
      3. Linux home directory ~/repos (WSL2 native fallback)
      4. /tmp/codeautopsy_repos (last resort)
    """

    @staticmethod
    def get_base_path() -> Path:
        env_path = os.environ.get("REPOS_DATA_PATH")
        if env_path:
            base = Path(env_path).expanduser()
            base.mkdir(parents=True, exist_ok=True)
            return base

        docker_mount = Path("/repos_data")
        if docker_mount.exists() and os.path.ismount(docker_mount):
            docker_mount.mkdir(parents=True, exist_ok=True)
            return docker_mount

        home_repos = Path.home() / "repos"
        try:
            home_repos.mkdir(parents=True, exist_ok=True)
            return home_repos
        except OSError:
            tmp_repos = Path("/tmp/codeautopsy_repos")
            tmp_repos.mkdir(parents=True, exist_ok=True)
            return tmp_repos

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
