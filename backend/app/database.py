"""
CodeAutopsy Database
SQLAlchemy models and database initialization for PostgreSQL via asyncpg.
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, ForeignKey, Index
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .config import get_settings

Base = declarative_base()

# ─── Auth & User Models ─────────────────────────────────────────

class User(Base):
    """User account spanning login and preferences."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class OTPCode(Base):
    """Stores generated OTPs (hashed) for email verification and password reset."""
    __tablename__ = "otp_codes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)  # bcrypt hash of the 6-digit code
    purpose = Column(String, nullable=False)  # "email_verification" or "password_reset"
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)

class Project(Base):
    """Links a user to a previously analysed repo."""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_url = Column(String, nullable=False)
    repo_name = Column(String, nullable=True) # e.g. "torvalds/linux"
    last_analysed_at = Column(DateTime(timezone=True), nullable=True)
    analysis_score = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserProject(Base):
    """Many-to-many relationship between Users and Projects."""
    __tablename__ = "user_projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, default="owner")  # owner/viewer/editor
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ─── Analysis Models ───────────────────────────────────────────────

class AnalysisResult(Base):
    """Stores analysis results for a GitHub repository."""
    __tablename__ = "analysis_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_url = Column(String, nullable=False)
    repo_name = Column(String, nullable=True)
    status = Column(String, default="queued")  # queued, cloning, analyzing, complete, failed
    health_score = Column(Integer, nullable=True)
    total_issues = Column(Integer, default=0)
    file_count = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    languages = Column(Text, default="{}")  # JSON string
    issues = Column(Text, default="[]")  # JSON string
    file_tree = Column(Text, default="[]")  # JSON string
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    repo_path = Column(String, nullable=True)  # temp path to cloned repo
    
    __table_args__ = (
        Index("idx_analysis_status", "status"),
        Index("idx_analysis_created", "created_at"),
    )
    
    def get_issues(self):
        return json.loads(self.issues) if self.issues else []
    
    def set_issues(self, issues_list):
        self.issues = json.dumps(issues_list)
    
    def get_languages(self):
        return json.loads(self.languages) if self.languages else {}
    
    def set_languages(self, lang_dict):
        self.languages = json.dumps(lang_dict)
    
    def get_file_tree(self):
        return json.loads(self.file_tree) if self.file_tree else []
    
    def set_file_tree(self, tree_list):
        self.file_tree = json.dumps(tree_list)


class GitArchaeology(Base):
    """Caches git archaeology data (blame, trace, timeline) for files."""
    __tablename__ = "git_archaeology"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String, ForeignKey("analysis_results.id"), nullable=False)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=True)
    data_type = Column(String, nullable=False)  # blame, trace, timeline, heatmap
    origin_commit = Column(String, nullable=True)
    author_hash = Column(String, nullable=True)
    data = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_arch_analysis", "analysis_id"),
        Index("idx_arch_file", "analysis_id", "file_path"),
        Index("idx_arch_type", "data_type"),
    )
    
    def get_data(self):
        return json.loads(self.data) if self.data else {}
    
    def set_data(self, data_dict):
        self.data = json.dumps(data_dict)


class AICache(Base):
    """Caches AI analysis responses to avoid redundant API calls."""
    __tablename__ = "ai_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code_hash = Column(String, unique=True, nullable=False)
    issue_type = Column(String, nullable=True)
    ai_response = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_cache_hash", "code_hash"),
    )
    
    def get_response(self):
        return json.loads(self.ai_response) if self.ai_response else {}
    
    def set_response(self, response_dict):
        self.ai_response = json.dumps(response_dict)


# ─── Database Engine & Session ────────────────────────────────

_engine = None
_async_session_maker = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL
        
        _engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yields an async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all database tables asynchronously."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Async PostgreSQL database tables created successfully")
