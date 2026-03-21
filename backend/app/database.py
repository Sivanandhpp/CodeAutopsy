"""
CodeAutopsy Database
SQLAlchemy models and database initialization for SQLite.
"""

import os
import json
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, 
    ForeignKey, Index, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

Base = declarative_base()


# ─── ORM Models ───────────────────────────────────────────────

class AnalysisResult(Base):
    """Stores analysis results for a GitHub repository."""
    __tablename__ = "analysis_results"
    
    id = Column(String, primary_key=True)
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_cache_hash", "code_hash"),
    )
    
    def get_response(self):
        return json.loads(self.ai_response) if self.ai_response else {}
    
    def set_response(self, response_dict):
        self.ai_response = json.dumps(response_dict)


# ─── Database Engine & Session ────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine(database_url: str = None):
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        if database_url is None:
            database_url = "sqlite:///./data/codeautopsy.db"
        
        # Ensure the data directory exists
        if database_url.startswith("sqlite:///"):
            db_path = database_url.replace("sqlite:///", "")
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        
        # Enable WAL mode for better concurrent read performance
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    return _engine


def get_session_factory(database_url: str = None):
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db():
    """Dependency: yields a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables(database_url: str = None):
    """Create all database tables."""
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
