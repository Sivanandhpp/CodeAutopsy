"""
Project & UserProject Models
==============================
Supports collaborative workflows where multiple users can be linked to a
single project with roles (owner, editor, viewer).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """A code analysis project tied to a GitHub repository."""
    __tablename__ = "projects"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    repo_url = Column(String(500), nullable=False)
    repo_name = Column(String(200), nullable=True)
    description = Column(String(1000), nullable=True)
    last_commit_sha = Column(String(64), nullable=True)  # For smart re-analysis

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    users = relationship(
        "UserProject",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    analyses = relationship(
        "AnalysisResult",
        back_populates="project",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AnalysisResult.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_projects_repo_url", "repo_url"),
        Index("ix_projects_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Project {self.repo_name}>"


class UserProject(Base):
    """Association table linking users to projects with roles."""
    __tablename__ = "user_projects"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role = Column(
        String(20),
        nullable=False,
        default="viewer",
    )  # owner, editor, viewer

    added_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="projects")
    project = relationship("Project", back_populates="users")

    __table_args__ = (
        Index("ix_user_projects_user", "user_id"),
        Index("ix_user_projects_project", "project_id"),
        Index("ix_user_projects_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<UserProject user={self.user_id} project={self.project_id} role={self.role}>"
