"""
CodeAutopsy Pydantic Schemas
Request/Response models for all API endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re


# ─── Analysis Schemas ─────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Request to analyze a GitHub repository."""
    repo_url: str = Field(..., description="GitHub repository URL")
    
    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v):
        pattern = r'^https?://github\.com/[\w.-]+/[\w.-]+/?$'
        if not re.match(pattern, v.strip().rstrip('.git')):
            raise ValueError("Invalid GitHub URL. Format: https://github.com/owner/repo")
        return v.strip().rstrip('/')


class AnalyzeResponse(BaseModel):
    """Response after starting an analysis."""
    analysis_id: str
    status: str
    message: str


class IssueDetail(BaseModel):
    """A single code issue found during analysis."""
    id: str
    file_path: str
    line_number: int
    end_line: Optional[int] = None
    column: Optional[int] = None
    issue_type: str
    severity: str  # critical, high, medium, low
    message: str
    code_snippet: str = ""
    rule_id: Optional[str] = None
    category: Optional[str] = None


class FileInfo(BaseModel):
    """File information in the analyzed repo."""
    path: str
    language: str
    lines: int = 0
    issue_count: int = 0
    is_directory: bool = False
    children: Optional[list] = None


class AnalysisResultResponse(BaseModel):
    """Full analysis results."""
    id: str
    repo_url: str
    repo_name: Optional[str] = None
    status: str
    health_score: Optional[int] = None
    total_issues: int = 0
    file_count: int = 0
    total_lines: int = 0
    languages: dict = {}
    issues: list[IssueDetail] = []
    file_tree: list = []
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ─── Archaeology Schemas ──────────────────────────────────────

class TraceRequest(BaseModel):
    """Request to trace bug origin."""
    analysis_id: str
    file_path: str
    line_number: int


class CommitInfo(BaseModel):
    """Git commit metadata."""
    hash: str
    author: str  # anonymized
    date: str
    message: str
    change_type: str = "modification"  # introduction, modification, refactor
    insertions: int = 0
    deletions: int = 0
    diff_snippet: str = ""


class TraceResponse(BaseModel):
    """Bug origin trace result."""
    origin_commit: CommitInfo
    evolution_chain: list[CommitInfo] = []
    total_commits: int = 0
    file_path: str
    line_number: int


class TimelineRequest(BaseModel):
    """Request for file commit timeline."""
    analysis_id: str
    file_path: str
    max_commits: int = 50


class TimelineResponse(BaseModel):
    """Commit timeline for a file."""
    commits: list[CommitInfo] = []
    total_commits: int = 0
    total_authors: int = 0
    first_commit_date: Optional[str] = None
    last_commit_date: Optional[str] = None
    file_path: str


class BlameRequest(BaseModel):
    """Request for file blame data."""
    analysis_id: str
    file_path: str


class BlameLineInfo(BaseModel):
    """Blame data for a single line."""
    line_number: int
    author: str
    commit_hash: str
    date: str
    content: str = ""


class AuthorContribution(BaseModel):
    """Author contribution stats."""
    author: str
    total_lines: int
    commit_count: int
    percentage: float


class BlameResponse(BaseModel):
    """Blame data for a file."""
    lines: list[BlameLineInfo] = []
    authors: list[AuthorContribution] = []
    total_lines: int = 0
    file_path: str


# ─── AI Analysis Schemas ──────────────────────────────────────

class AIAnalyzeRequest(BaseModel):
    """Request for AI analysis of a code issue."""
    code_snippet: str
    issue_type: str
    language: str = "python"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context_before: str = ""
    context_after: str = ""


class AIAnalyzeResponse(BaseModel):
    """AI analysis result."""
    root_cause: str
    fix_strategy: str
    code_patch: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = []
    cached: bool = False


# ─── Health Check ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "connected"


# ─── SSE Progress ─────────────────────────────────────────────

class ProgressUpdate(BaseModel):
    """Server-Sent Event progress update."""
    analysis_id: str
    status: str
    progress: int = 0  # 0-100
    message: str = ""
    current_step: str = ""
