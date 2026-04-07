"""
Audit Log Model
================
Records all admin actions for accountability and debugging.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """Tracks admin actions for audit trail."""
    __tablename__ = "audit_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(100), nullable=False)  # user_deleted, repo_deleted, all_repos_deleted, rule_created, etc.
    target_type = Column(String(50), nullable=True)  # user, project, rule, system
    target_id = Column(String(255), nullable=True)  # UUID or identifier of target
    details = Column(Text, nullable=True)  # JSON string with extra context
    ip_address = Column(String(45), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    admin = relationship("User", foreign_keys=[admin_id], lazy="selectin")

    __table_args__ = (
        Index("ix_audit_logs_admin_id", "admin_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.admin_id}>"
