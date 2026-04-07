"""
Analysis Result Model
=====================
Stores analysis results for GitHub repositories, linked to projects.
Extracted from the old database.py and converted to async-compatible model.
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AnalysisResult(Base):
    """Stores analysis results for a GitHub repository scan."""
    __tablename__ = "analysis_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    repo_url = Column(String(500), nullable=False)
    repo_name = Column(String(200), nullable=True)
    status = Column(
        String(20), default="queued", nullable=False
    )  # queued, cloning, analyzing, complete, failed, cancelled
    health_score = Column(Integer, nullable=True)
    total_issues = Column(Integer, default=0)
    file_count = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    languages = Column(Text, default="{}")        # JSON string
    issues = Column(Text, default="[]")           # JSON string
    file_tree = Column(Text, default="[]")        # JSON string
    ollama_findings = Column(Text, default="[]")  # JSON: local AI analysis results
    contributor_stats = Column(Text, default="{}") # JSON: summarized stats per author
    ai_summary = Column(Text, nullable=True)      # Live summary of static issues
    error_message = Column(String(2000), nullable=True)
    commit_sha = Column(String(64), nullable=True)  # HEAD SHA at analysis time
    repo_path = Column(String(500), nullable=True)   # Legacy clone path
    clone_path = Column(String(500), nullable=True)  # Canonical clone path

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    project = relationship("Project", back_populates="analyses")

    __table_args__ = (
        Index("ix_analysis_status", "status"),
        Index("ix_analysis_project", "project_id"),
        Index("ix_analysis_created", "created_at"),
        Index("ix_analysis_repo_url", "repo_url"),
    )

    # ─── JSON helpers ────────────────────────────────────────
    def get_issues(self) -> list:
        try:
            return json.loads(self.issues) if self.issues else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_issues(self, issues_list: list) -> None:
        self.issues = json.dumps(issues_list, default=str)

    def get_languages(self) -> dict:
        try:
            return json.loads(self.languages) if self.languages else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_languages(self, lang_dict: dict) -> None:
        self.languages = json.dumps(lang_dict, default=str)

    def get_file_tree(self) -> list:
        try:
            return json.loads(self.file_tree) if self.file_tree else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_file_tree(self, tree_list: list) -> None:
        self.file_tree = json.dumps(tree_list, default=str)

    def get_ollama_findings(self) -> list:
        try:
            return json.loads(self.ollama_findings) if self.ollama_findings else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_ollama_findings(self, findings: list) -> None:
        self.ollama_findings = json.dumps(findings, default=str)

    def get_contributor_stats(self) -> dict:
        try:
            return json.loads(self.contributor_stats) if self.contributor_stats else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_contributor_stats(self, stats: dict) -> None:
        self.contributor_stats = json.dumps(stats, default=str)
        
    def get_ai_summary(self) -> str:
        return self.ai_summary or ""
        
    def set_ai_summary(self, summary: str) -> None:
        self.ai_summary = summary

    def __repr__(self) -> str:
        return f"<AnalysisResult {self.id[:8]} status={self.status}>"
