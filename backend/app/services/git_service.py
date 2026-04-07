"""
Git Service
Handles GitHub repository cloning, file tree extraction, and language detection.
"""

import os
import re
import shutil
from pathlib import Path

from git import Repo, GitCommandError, Git
from app.utils.languages import LANGUAGE_MAP
from app.services.repo_storage_service import RepoStorageService

# Directories to skip during file tree scanning
SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env',
    '.env', '.idea', '.vscode', '.vs', 'dist', 'build', 'target',
    '.next', '.nuxt', '.cache', 'coverage', '.tox', '.mypy_cache',
    '.pytest_cache', 'egg-info', '.eggs', 'vendor', 'bower_components',
}

# File extensions to skip (binary / non-code)
SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.ogg',
    '.zip', '.tar', '.gz', '.bz2', '.rar', '.7z',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.exe', '.dll', '.so', '.dylib', '.o', '.a', '.lib',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.pyc', '.pyo', '.class', '.jar',
    '.lock', '.min.js', '.min.css',
    '.map',
}


class GitService:
    """Service for cloning GitHub repos and extracting file metadata."""
    
    def validate_github_url(self, url: str) -> tuple[bool, str]:
        """Validate that the URL is a valid GitHub repository URL."""
        url = url.strip().rstrip('/')
        pattern = r'^https?://github\.com/[\w.-]+/[\w.-]+/?$'
        if not re.match(pattern, url.rstrip('.git')):
            return False, "Invalid GitHub URL. Format: https://github.com/owner/repo"
        return True, url
    
    def extract_repo_name(self, url: str) -> str:
        """Extract 'owner/repo' from a GitHub URL."""
        url = url.strip().rstrip('/').rstrip('.git')
        parts = url.split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return parts[-1]
    
    def clone_repository(self, repo_url: str, analysis_id: str) -> tuple[str, str]:
        """
        Clone a GitHub repository to a persistent storage path.
        Returns (repo_path, repo_name).
        Raises GitCommandError on failure.
        """
        valid, result = self.validate_github_url(repo_url)
        if not valid:
            raise ValueError(result)
        
        repo_name = self.extract_repo_name(repo_url)
        repo_path = RepoStorageService.get_clone_path(repo_name, analysis_id)
        
        try:
            # Clone with limited depth for speed, but enough for archaeology
            Repo.clone_from(
                repo_url,
                str(repo_path),
                depth=200,  # Enough commits for archaeology
                no_single_branch=True,
            )
            return str(repo_path), repo_name
        except GitCommandError as e:
            # Cleanup on failure
            if repo_path and os.path.exists(repo_path):
                shutil.rmtree(repo_path, ignore_errors=True)
            raise RuntimeError(f"Failed to clone repository: {str(e)}")

    def get_remote_head_sha(self, repo_url: str) -> str | None:
        """Fetch the remote HEAD SHA without cloning the repo."""
        valid, result = self.validate_github_url(repo_url)
        if not valid:
            raise ValueError(result)
        try:
            output = Git().ls_remote(result, "HEAD")
            return output.split()[0] if output else None
        except GitCommandError:
            return None

    def refresh_repository(self, repo_path: str) -> str:
        """Refresh an existing clone by fetching and hard-resetting to origin/HEAD."""
        if not repo_path or not os.path.exists(repo_path):
            raise FileNotFoundError("Repository path not found")
        try:
            repo = Repo(repo_path)
            repo.git.fetch("--all", "--prune")
            try:
                repo.git.reset("--hard", "origin/HEAD")
            except GitCommandError:
                repo.git.reset("--hard", "HEAD")
            repo.git.clean("-xdf")
            try:
                repo.git.pull("--ff-only")
            except GitCommandError:
                pass
            return repo_path
        except Exception as e:
            raise RuntimeError(f"Failed to refresh repository: {str(e)}")
    
    def get_file_tree(self, repo_path: str) -> list[dict]:
        """
        Walk the repository and return a flat list of source files.
        Each entry: { path, language, lines, size, is_directory }
        """
        files = []
        repo_root = Path(repo_path)
        
        for root, dirs, filenames in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            rel_root = Path(root).relative_to(repo_root)
            
            for filename in filenames:
                filepath = Path(root) / filename
                ext = filepath.suffix.lower()
                
                # Skip binary and non-code files
                if ext in SKIP_EXTENSIONS:
                    continue
                
                # Skip hidden files (except config files)
                if filename.startswith('.') and ext not in {'.env', '.gitignore', '.dockerignore'}:
                    continue
                
                # Skip very large files
                try:
                    file_size = filepath.stat().st_size
                    if file_size > 1_000_000:  # 1MB limit
                        continue
                except OSError:
                    continue
                
                rel_path = str(filepath.relative_to(repo_root)).replace('\\', '/')
                language = self.detect_language(filename)
                
                # Count lines
                line_count = 0
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = sum(1 for _ in f)
                except Exception:
                    pass
                
                files.append({
                    'path': rel_path,
                    'language': language,
                    'lines': line_count,
                    'size': file_size,
                    'is_directory': False,
                })
        
        return sorted(files, key=lambda x: x['path'])
    
    def detect_language(self, filename: str) -> str:
        """Detect programming language from file extension."""
        # Check for Dockerfile specifically
        if filename.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
            return 'dockerfile'
        
        ext = Path(filename).suffix.lower()
        return LANGUAGE_MAP.get(ext, 'plaintext')
    
    def get_language_stats(self, file_tree: list[dict]) -> dict:
        """Count files per language."""
        stats = {}
        for f in file_tree:
            if f['language'] != 'plaintext':
                lang = f['language']
                stats[lang] = stats.get(lang, 0) + 1
        return dict(sorted(stats.items(), key=lambda x: x[1], reverse=True))
    
    def get_total_lines(self, file_tree: list[dict]) -> int:
        """Get total lines of code."""
        return sum(f.get('lines', 0) for f in file_tree)
    
    def get_file_content(self, repo_path: str, file_path: str) -> str:
        """Read file contents from the cloned repo."""
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Security: prevent path traversal
        real_repo = os.path.realpath(repo_path)
        real_file = os.path.realpath(full_path)
        if not real_file.startswith(real_repo):
            raise ValueError("Invalid file path: path traversal detected")
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {str(e)}")
            
    def put_file_content(self, repo_path: str, file_path: str, content: str) -> None:
        """Write file contents to the cloned repo."""
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Security: prevent path traversal
        real_repo = os.path.realpath(repo_path)
        real_file = os.path.realpath(full_path)
        if not real_file.startswith(real_repo):
            raise ValueError("Invalid file path: path traversal detected")
            
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            raise RuntimeError(f"Failed to write file: {str(e)}")
    
    def cleanup_repo(self, repo_path: str):
        """Delete the cloned repository directory."""
        if repo_path and os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)

    def get_issue_blame_batch(self, repo_path: str, issues: list[dict]) -> None:
        """Enrich a list of issues with origin commit, author, and date using git blame in batch."""
        import hashlib
        from datetime import datetime, timezone
        try:
            repo = Repo(repo_path)
        except Exception:
            return

        blame_cache = {}
        for issue in issues:
            file_path = issue.get('file_path')
            line_num = issue.get('line_number', 0)
            if not file_path or line_num <= 0:
                continue

            if file_path not in blame_cache:
                try:
                    blame_cache[file_path] = repo.blame('HEAD', file_path)
                except Exception:
                    blame_cache[file_path] = None
            
            blame_data = blame_cache[file_path]
            if not blame_data:
                continue

            current_line = 0
            found = False
            for commit, lines in blame_data:
                for _ in lines:
                    current_line += 1
                    if current_line == line_num:
                        a_name = commit.author.name if commit.author and commit.author.name else "Unknown"
                        a_email = commit.author.email if commit.author and commit.author.email else "unknown@example.com"
                        issue['origin_commit'] = commit.hexsha[:8]
                        issue['origin_author'] = f"{a_name} <{a_email}>"
                        
                        date_str = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc).isoformat()
                        issue['origin_date'] = date_str
                        found = True
                        break
                if found:
                    break



# Singleton instance
git_service = GitService()
