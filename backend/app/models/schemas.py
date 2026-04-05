"""
CodeAutopsy Pydantic Schemas
==============================
Request/Response models for all API endpoints.
Covers: Auth, Users, Projects, Analysis, Archaeology, AI, Reports.
"""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, EmailStr


# ═════════════════════════════════════════════════════════════
# AUTH SCHEMAS
# ═════════════════════════════════════════════════════════════


class EmailCheckRequest(BaseModel):
    """Check if an email is already registered."""
    email: EmailStr


class EmailCheckResponse(BaseModel):
    exists: bool
    message: str = ""


class OTPSendRequest(BaseModel):
    """Request to send a 6-digit OTP to an email."""
    email: EmailStr


class OTPSendResponse(BaseModel):
    message: str
    expires_in_minutes: int = 10


class OTPVerifyRequest(BaseModel):
    """Verify the 6-digit OTP code."""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)


class OTPVerifyResponse(BaseModel):
    """Returns a temporary token used for registration."""
    verified: bool
    temp_token: str = ""
    message: str = ""


class RegisterRequest(BaseModel):
    """Create account after OTP verification."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    temp_token: str  # From OTP verification

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    """Email + password login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT access token response."""
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


# ═════════════════════════════════════════════════════════════
# USER SCHEMAS
# ═════════════════════════════════════════════════════════════


class UserResponse(BaseModel):
    """Public user information."""
    id: UUID
    username: str
    email: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserSearchResult(BaseModel):
    id: UUID
    username: str
    email: str

    class Config:
        from_attributes = True


class UserSearchResponse(BaseModel):
    users: list[UserSearchResult] = []
    total: int = 0


# ═════════════════════════════════════════════════════════════
# PROJECT SCHEMAS
# ═════════════════════════════════════════════════════════════


class ProjectCreateRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    description: Optional[str] = None

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r'^https?://github\.com/[\w.-]+/[\w.-]+/?$'
        if not re.match(pattern, v.strip().rstrip('.git')):
            raise ValueError("Invalid GitHub URL. Format: https://github.com/owner/repo")
        return v.strip().rstrip('/')


class CollaboratorAddRequest(BaseModel):
    username: str
    role: str = Field(default="viewer", pattern=r"^(editor|viewer)$")


class CollaboratorResponse(BaseModel):
    user_id: UUID
    username: str
    email: str
    role: str
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: UUID
    repo_url: str
    repo_name: Optional[str] = None
    description: Optional[str] = None
    last_commit_sha: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    role: Optional[str] = None                      # Current user's role
    collaborators: list[CollaboratorResponse] = []
    latest_analysis: Optional["AnalysisResultResponse"] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse] = []
    total: int = 0


# ═════════════════════════════════════════════════════════════
# ANALYSIS SCHEMAS
# ═════════════════════════════════════════════════════════════


class AnalyzeRequest(BaseModel):
    """Request to analyze a GitHub repository."""
    repo_url: str = Field(..., description="GitHub repository URL")
    project_id: Optional[UUID] = None  # Optional: link to existing project

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r'^https?://github\.com/[\w.-]+/[\w.-]+/?$'
        if not re.match(pattern, v.strip().rstrip('.git')):
            raise ValueError("Invalid GitHub URL. Format: https://github.com/owner/repo")
        return v.strip().rstrip('/')


class AnalyzeResponse(BaseModel):
    """Response after starting an analysis."""
    analysis_id: str
    project_id: Optional[UUID] = None
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


class OllamaFinding(BaseModel):
    """A single finding from local AI analysis."""
    file_path: str
    type: str                     # bug, vulnerability, performance, code_smell
    severity: str                 # critical, high, medium, low
    line: Optional[int] = None
    description: str
    fix: str = ""
    category: str = ""


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
    project_id: Optional[UUID] = None
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
    ollama_findings: list[OllamaFinding] = []
    ai_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True


# ═════════════════════════════════════════════════════════════
# ARCHAEOLOGY SCHEMAS
# ═════════════════════════════════════════════════════════════


class TraceRequest(BaseModel):
    analysis_id: str
    file_path: str
    line_number: int


class CommitInfo(BaseModel):
    hash: str
    author: str
    date: str
    message: str
    change_type: str = "modification"
    insertions: int = 0
    deletions: int = 0
    diff_snippet: str = ""


class TraceResponse(BaseModel):
    origin_commit: CommitInfo
    evolution_chain: list[CommitInfo] = []
    total_commits: int = 0
    file_path: str
    line_number: int


class TimelineRequest(BaseModel):
    analysis_id: str
    file_path: str
    max_commits: int = 50


class TimelineResponse(BaseModel):
    commits: list[CommitInfo] = []
    total_commits: int = 0
    total_authors: int = 0
    first_commit_date: Optional[str] = None
    last_commit_date: Optional[str] = None
    file_path: str


class BlameRequest(BaseModel):
    analysis_id: str
    file_path: str


class BlameLineInfo(BaseModel):
    line_number: int
    author: str
    commit_hash: str
    date: str
    content: str = ""


class AuthorContribution(BaseModel):
    author: str
    total_lines: int
    commit_count: int
    percentage: float


class BlameResponse(BaseModel):
    lines: list[BlameLineInfo] = []
    authors: list[AuthorContribution] = []
    total_lines: int = 0
    file_path: str


# ═════════════════════════════════════════════════════════════
# AI SCHEMAS
# ═════════════════════════════════════════════════════════════


class AIAnalyzeRequest(BaseModel):
    code_snippet: str
    issue_type: str
    language: str = "python"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context_before: str = ""
    context_after: str = ""


class AIAnalyzeResponse(BaseModel):
    root_cause: str
    fix_strategy: str
    code_patch: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: list[str] = []
    cached: bool = False


# ═════════════════════════════════════════════════════════════
# HEALTH & SSE SCHEMAS
# ═════════════════════════════════════════════════════════════


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.0.0"
    database: str = "connected"
    ollama: str = "unknown"


class ProgressUpdate(BaseModel):
    analysis_id: str
    status: str
    progress: int = 0
    message: str = ""
    current_step: str = ""
