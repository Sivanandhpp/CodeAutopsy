"""
Re-analysis Service
===================
Smart re-analysis that checks GitHub for updates and only reprocesses
new or modified files, reusing cached results otherwise.
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def get_latest_commit_sha(repo_url: str) -> Optional[str]:
    """
    Fetch the latest commit SHA from GitHub API.
    Returns None if the API call fails (rate limited, private repo, etc.)
    """
    settings = get_settings()

    # Extract owner/repo from URL
    parts = repo_url.rstrip("/").split("github.com/")
    if len(parts) < 2:
        return None
    repo_path = parts[1].rstrip(".git")

    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"https://api.github.com/repos/{repo_path}/commits",
                headers=headers,
                params={"per_page": 1},
            )
            response.raise_for_status()
            commits = response.json()
            if commits and isinstance(commits, list):
                return commits[0].get("sha")
    except Exception as e:
        logger.warning(f"Failed to fetch latest commit for {repo_url}: {e}")

    return None


async def should_reanalyze(repo_url: str, last_known_sha: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Check if a repository needs re-analysis.
    
    Returns:
        (needs_reanalysis: bool, latest_sha: Optional[str])
    """
    if not last_known_sha:
        return True, None

    latest_sha = await get_latest_commit_sha(repo_url)

    if latest_sha is None:
        # Can't determine — don't re-analyze
        logger.info(f"Could not fetch latest SHA for {repo_url}, skipping re-analysis check")
        return False, None

    needs_update = latest_sha != last_known_sha
    if needs_update:
        logger.info(f"Repository {repo_url} has new commits: {last_known_sha[:8]} → {latest_sha[:8]}")
    else:
        logger.info(f"Repository {repo_url} is up to date: {latest_sha[:8]}")

    return needs_update, latest_sha


def get_changed_files(repo_path: str, old_sha: str, new_sha: str) -> list[str]:
    """
    Get list of files changed between two commits using git diff.
    Returns relative file paths.
    """
    try:
        from git import Repo

        repo = Repo(repo_path)
        diff = repo.git.diff("--name-only", old_sha, new_sha)
        if diff:
            return [f.strip() for f in diff.split("\n") if f.strip()]
        return []
    except Exception as e:
        logger.error(f"Failed to get changed files: {e}")
        return []


def merge_analysis_results(
    old_issues: list[dict],
    new_issues: list[dict],
    changed_files: list[str],
) -> list[dict]:
    """
    Merge old cached results with new analysis results.
    Keeps old results for unchanged files, replaces with new for changed files.
    """
    # Remove old issues from changed files
    unchanged_issues = [
        issue for issue in old_issues
        if issue.get("file_path") not in changed_files
    ]

    # Add new issues from changed files
    merged = unchanged_issues + new_issues
    return merged
