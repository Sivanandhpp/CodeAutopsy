"""
OTP Model
=========
Stores hashed one-time passwords for email verification during registration.
OTPs expire after a configurable time (default 10 minutes).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

# Maximum failed verification attempts before the OTP is locked
MAX_VERIFY_ATTEMPTS = 5


class OTP(Base):
    """One-time password for email verification."""
    __tablename__ = "otps"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email = Column(String(255), nullable=False)
    otp_hash = Column(String(255), nullable=False)  # bcrypt hash of the 6-digit code
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    verify_attempts = Column(Integer, default=0, nullable=False, server_default="0")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_otps_email", "email"),
        Index("ix_otps_expires", "expires_at"),
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_locked(self) -> bool:
        """True when too many failed verify attempts have been made."""
        return (self.verify_attempts or 0) >= MAX_VERIFY_ATTEMPTS

    def __repr__(self) -> str:
        return f"<OTP email={self.email} expired={self.is_expired}>"
