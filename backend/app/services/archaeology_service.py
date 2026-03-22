"""
Git Archaeology Service
The centerpiece of CodeAutopsy — traces bugs to their origin, builds evolution
chains, blame heatmaps, and file commit timelines.
"""

import hashlib
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

from git import Repo


class ArchaeologyService:
    """Git forensics engine for code archaeology."""

    # ─── Author Anonymization ─────────────────────────────────

    def _anonymize_author(self, email: str) -> str:
        """Hash email → 'dev_a3f8c1b2' for privacy."""
        if not email:
            return "dev_unknown"
        h = hashlib.md5(email.encode()).hexdigest()[:8]
        return f"dev_{h}"

    def _parse_date(self, dt) -> str:
        """Convert git datetime to ISO format string."""
        if hasattr(dt, 'isoformat'):
            return dt.isoformat()
        if isinstance(dt, (int, float)):
            return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat()
        return str(dt)

    # ─── File Blame ───────────────────────────────────────────

    def get_file_blame(self, repo_path: str, file_path: str) -> dict:
        """
        Get line-by-line blame data for a file.
        Returns { lines: [...], authors: [...], total_lines }
        """
        try:
            repo = Repo(repo_path)
        except Exception as e:
            raise RuntimeError(f"Invalid repository: {e}")

        full_path = Path(repo_path) / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            blame_data = repo.blame('HEAD', file_path)
        except Exception as e:
            raise RuntimeError(f"Blame failed: {e}")

        lines = []
        author_stats = {}
        line_num = 1

        for commit, blamed_lines in blame_data:
            author_email = commit.author.email if commit.author else ""
            author_name = self._anonymize_author(author_email)
            commit_date = self._parse_date(commit.committed_date)

            if author_name not in author_stats:
                author_stats[author_name] = {
                    "name": author_name,
                    "lines": 0,
                    "commits": set(),
                }

            for text_line in blamed_lines:
                lines.append({
                    "line_number": line_num,
                    "author": author_name,
                    "commit_hash": commit.hexsha[:8],
                    "date": commit_date,
                    "content": str(text_line),
                })
                author_stats[author_name]["lines"] += 1
                author_stats[author_name]["commits"].add(commit.hexsha)
                line_num += 1

        # Convert sets to counts for JSON
        authors = []
        for info in author_stats.values():
            authors.append({
                "name": info["name"],
                "lines": info["lines"],
                "commits": len(info["commits"]),
                "percentage": round(info["lines"] / max(len(lines), 1) * 100, 1),
            })
        authors.sort(key=lambda a: a["lines"], reverse=True)

        return {
            "file_path": file_path,
            "total_lines": len(lines),
            "lines": lines,
            "authors": authors,
        }

    # ─── Bug Origin Tracing ───────────────────────────────────

    def trace_bug_origin(
        self, repo_path: str, file_path: str, line_number: int
    ) -> dict:
        """
        Trace a specific line back to its origin commit and build an
        evolution chain showing how it changed over time.
        """
        try:
            repo = Repo(repo_path)
        except Exception as e:
            raise RuntimeError(f"Invalid repository: {e}")

        # Step 1: Get blame for the specific line
        try:
            blame_data = repo.blame('HEAD', file_path)
        except Exception as e:
            raise RuntimeError(f"Blame failed: {e}")

        # Find the commit that last touched this line
        current_line = 0
        origin_commit = None
        origin_line_content = ""

        for commit, blamed_lines in blame_data:
            for text_line in blamed_lines:
                current_line += 1
                if current_line == line_number:
                    origin_commit = commit
                    origin_line_content = str(text_line)
                    break
            if origin_commit:
                break

        if not origin_commit:
            raise ValueError(f"Line {line_number} not found in {file_path}")

        # Step 2: Get origin commit details
        origin = {
            "commit_hash": origin_commit.hexsha[:8],
            "full_hash": origin_commit.hexsha,
            "author": self._anonymize_author(
                origin_commit.author.email if origin_commit.author else ""
            ),
            "date": self._parse_date(origin_commit.committed_date),
            "message": origin_commit.message.strip().split('\n')[0],
            "line_content": origin_line_content,
        }

        # Step 3: Get diff for origin commit
        try:
            diff_text = self._get_commit_diff(repo, origin_commit, file_path)
            origin["diff"] = diff_text
        except Exception:
            origin["diff"] = ""

        # Step 4: Build evolution chain using git log -L
        evolution_chain = self._build_evolution_chain(
            repo_path, file_path, line_number
        )

        return {
            "file_path": file_path,
            "line_number": line_number,
            "origin": origin,
            "evolution_chain": evolution_chain,
            "total_commits": len(evolution_chain),
        }

    def _get_commit_diff(self, repo, commit, file_path: str) -> str:
        """Extract the diff for a specific file in a commit."""
        try:
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, paths=[file_path], create_patch=True)
            else:
                # Initial commit — diff against empty tree
                diffs = commit.diff(
                    None, paths=[file_path], create_patch=True
                )

            for d in diffs:
                patch = d.diff
                if isinstance(patch, bytes):
                    patch = patch.decode('utf-8', errors='ignore')
                # Return first ~30 lines of diff to keep it manageable
                lines = patch.split('\n')
                return '\n'.join(lines[:30])
        except Exception:
            pass
        return ""

    def _build_evolution_chain(
        self, repo_path: str, file_path: str, line_number: int
    ) -> list:
        """
        Use git log -L to trace line history across commits.
        Falls back to regular git log if -L fails.
        """
        chain = []

        try:
            # git log -L traces a specific line range through history
            result = subprocess.run(
                [
                    "git", "log", "--no-walk=unsorted",
                    f"-L{line_number},{line_number}:{file_path}",
                    "--pretty=format:%H|%ae|%ad|%s",
                    "--date=iso",
                    "-n", "20",
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                chain = self._parse_git_log_L_output(result.stdout)
            else:
                # Fallback: use regular git log for the file
                chain = self._fallback_file_log(repo_path, file_path)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # git not available or timed out, use GitPython fallback
            chain = self._fallback_file_log(repo_path, file_path)

        # Classify change types
        for i, entry in enumerate(chain):
            if i == len(chain) - 1:
                entry["change_type"] = "introduction"
            elif "refactor" in entry.get("message", "").lower() or \
                 "rename" in entry.get("message", "").lower() or \
                 "move" in entry.get("message", "").lower():
                entry["change_type"] = "refactor"
            else:
                entry["change_type"] = "modification"

        return chain

    def _parse_git_log_L_output(self, output: str) -> list:
        """Parse output from git log -L command."""
        chain = []
        current_commit = None
        diff_lines = []

        for line in output.split('\n'):
            # Check for commit header line (our format: hash|email|date|subject)
            if '|' in line and len(line.split('|')) >= 4:
                parts = line.split('|')
                # Could be a header line
                if len(parts[0]) == 40:  # full SHA
                    # Save previous commit
                    if current_commit:
                        current_commit["diff"] = '\n'.join(diff_lines[-15:])
                        chain.append(current_commit)
                        diff_lines = []

                    current_commit = {
                        "commit_hash": parts[0][:8],
                        "full_hash": parts[0],
                        "author": self._anonymize_author(parts[1]),
                        "date": parts[2].strip(),
                        "message": '|'.join(parts[3:]).strip(),
                        "change_type": "modification",
                    }
                    continue

            # Collect diff lines
            if current_commit and (line.startswith('+') or line.startswith('-') or line.startswith(' ')):
                diff_lines.append(line)

        # Save last commit
        if current_commit:
            current_commit["diff"] = '\n'.join(diff_lines[-15:])
            chain.append(current_commit)

        return chain

    def _fallback_file_log(self, repo_path: str, file_path: str) -> list:
        """Fallback: get commit history for the file using GitPython."""
        chain = []
        try:
            repo = Repo(repo_path)
            commits = list(repo.iter_commits('HEAD', paths=[file_path], max_count=20))

            for commit in commits:
                author_email = commit.author.email if commit.author else ""
                diff_text = self._get_commit_diff(repo, commit, file_path)

                # Get stats
                insertions = 0
                deletions = 0
                try:
                    stats = commit.stats.files.get(file_path, {})
                    insertions = stats.get('insertions', 0)
                    deletions = stats.get('deletions', 0)
                except Exception:
                    pass

                chain.append({
                    "commit_hash": commit.hexsha[:8],
                    "full_hash": commit.hexsha,
                    "author": self._anonymize_author(author_email),
                    "date": self._parse_date(commit.committed_date),
                    "message": commit.message.strip().split('\n')[0],
                    "diff": diff_text[:500],  # Truncate long diffs
                    "insertions": insertions,
                    "deletions": deletions,
                    "change_type": "modification",
                })
        except Exception:
            pass

        return chain

    # ─── Commit Timeline ──────────────────────────────────────

    def get_commit_timeline(
        self, repo_path: str, file_path: str, max_commits: int = 50
    ) -> dict:
        """
        Get chronological commit history for a file with stats.
        Oldest first for timeline display.
        """
        try:
            repo = Repo(repo_path)
        except Exception as e:
            raise RuntimeError(f"Invalid repository: {e}")

        try:
            commits = list(
                repo.iter_commits('HEAD', paths=[file_path], max_count=max_commits)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get commits: {e}")

        timeline = []
        authors_seen = set()

        for commit in commits:
            author_email = commit.author.email if commit.author else ""
            author = self._anonymize_author(author_email)
            authors_seen.add(author)

            # Get file-level stats
            insertions = 0
            deletions = 0
            try:
                for path_key, stats in commit.stats.files.items():
                    # Handle path separators
                    normalized = path_key.replace('\\', '/')
                    if normalized == file_path.replace('\\', '/'):
                        insertions = stats.get('insertions', 0)
                        deletions = stats.get('deletions', 0)
                        break
            except Exception:
                pass

            timeline.append({
                "commit_hash": commit.hexsha[:8],
                "full_hash": commit.hexsha,
                "author": author,
                "date": self._parse_date(commit.committed_date),
                "message": commit.message.strip().split('\n')[0],
                "insertions": insertions,
                "deletions": deletions,
                "lines_changed": insertions + deletions,
            })

        # Reverse for chronological order (oldest first)
        timeline.reverse()

        meta = {
            "file_path": file_path,
            "total_commits": len(timeline),
            "total_authors": len(authors_seen),
            "first_commit": timeline[0]["date"] if timeline else None,
            "last_commit": timeline[-1]["date"] if timeline else None,
        }

        return {
            **meta,
            "timeline": timeline,
        }

    # ─── Blame Heatmap ────────────────────────────────────────

    def get_blame_heatmap(self, repo_path: str, file_path: str) -> dict:
        """
        Blame data formatted for heatmap visualization.
        Groups lines by author with color assignments.
        """
        blame = self.get_file_blame(repo_path, file_path)

        # Assign colors to top authors
        colors = [
            "#6366f1", "#f43f5e", "#10b981", "#f59e0b",
            "#06b6d4", "#8b5cf6", "#ec4899", "#14b8a6",
            "#f97316", "#64748b",
        ]
        author_colors = {}
        for i, author in enumerate(blame["authors"]):
            author_colors[author["name"]] = colors[i % len(colors)]

        # Build line-level heatmap data
        line_data = []
        for line in blame["lines"]:
            line_data.append({
                "line_number": line["line_number"],
                "author": line["author"],
                "color": author_colors.get(line["author"], "#64748b"),
                "commit_hash": line["commit_hash"],
                "date": line["date"],
            })

        return {
            "file_path": file_path,
            "total_lines": blame["total_lines"],
            "authors": [
                {**a, "color": author_colors.get(a["name"], "#64748b")}
                for a in blame["authors"]
            ],
            "line_data": line_data,
        }


# Singleton
archaeology_service = ArchaeologyService()
