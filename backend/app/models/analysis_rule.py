"""Analysis Rule Model
======================
Database-driven static analysis rules.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Boolean, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AnalysisRule(Base):
    """Rule definition for static analysis engines."""
    __tablename__ = "analysis_rules"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    rule_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(50), nullable=False)
    defect_family = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    pattern = Column(Text, nullable=False)
    match_type = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    fix_hint = Column(Text, nullable=True)
    cwe_id = Column(String(20), nullable=True)
    owasp_ref = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_analysis_rules_rule_id", "rule_id"),
        Index("ix_analysis_rules_language", "language"),
        Index("ix_analysis_rules_family", "defect_family"),
        Index("ix_analysis_rules_severity", "severity"),
        Index("ix_analysis_rules_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AnalysisRule {self.rule_id}>"
