"""
Git Service
Handles GitHub repository cloning, file tree extraction, and language detection.
"""

import os
import re
import uuid
import shutil
from pathlib import Path

from git import Repo, GitCommandError
from app.utils.languages import LANGUAGE_MAP

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
    
    def __init__(self, repos_dir: str = None):
        if repos_dir:
            self.repos_dir = repos_dir
        else:
            self.repos_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "repos"
            )
        os.makedirs(self.repos_dir, exist_ok=True)
    
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
    
    def sync_repository(self, repo_url: str) -> tuple[str, str, bool, list[str]]:
        """
        Clones or updates a GitHub repository in a production-level sandbox (deterministic DB persistence).
        Returns (repo_path, repo_name, has_updates, changed_files).
        """
        valid, result = self.validate_github_url(repo_url)
        if not valid:
            raise ValueError(result)
        
        repo_name = self.extract_repo_name(repo_url)
        # Sandbox path is deterministic and mapped to Docker volume
        repo_path = os.path.join(self.repos_dir, repo_name.replace('/', '_'))
        
        has_updates = False
        changed_files = []
        
        try:
            if os.path.exists(repo_path) and os.path.exists(os.path.join(repo_path, '.git')):
                # Repository exists, check for updates
                repo = Repo(repo_path)
                origin = repo.remotes.origin
                
                # Get current commit hash before fetch
                head_commit_before = repo.head.commit.hexsha
                
                origin.fetch()
                
                # Check if the fetch brought in a new commit on the default branch
                # For simplicity, we compare local HEAD to origin/HEAD
                if 'origin/HEAD' in repo.refs:
                    remote_ref = repo.refs['origin/HEAD']
                else:
                    # Fallback to checking master/main
                    remote_ref = None
                    for ref in origin.refs:
                        if ref.name in ['origin/main', 'origin/master']:
                            remote_ref = ref
                            break
                
                if remote_ref and remote_ref.commit.hexsha != head_commit_before:
                    has_updates = True
                    # Get diff between old head and new remote head
                    diffs = repo.head.commit.diff(remote_ref.commit)
                    changed_files = [d.b_path for d in diffs if d.b_path]
                    
                    # Pull changes (reset to match remote)
                    repo.head.reset(remote_ref, index=True, working_tree=True)
            else:
                # Need to clone fresh
                has_updates = True 
                os.makedirs(repo_path, exist_ok=True)
                Repo.clone_from(
                    repo_url,
                    repo_path,
                    depth=200, 
                    no_single_branch=True,
                )
            
            return repo_path, repo_name, has_updates, changed_files
            
        except GitCommandError as e:
            raise RuntimeError(f"Failed to sync repository: {str(e)}")
    
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
    
    def cleanup_repo(self, repo_path: str):
        """Delete the cloned repository directory."""
        if repo_path and os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)


# Singleton instance
git_service = GitService()
