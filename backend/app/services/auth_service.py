"""
Authentication Service
======================
Handles JWT token creation/verification, password hashing, and OTP generation.
Production-grade with proper error handling and security best practices.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
import bcrypt

from app.config import get_settings

logger = logging.getLogger(__name__)

# ─── Password Hashing ───────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    pwd_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    try:
        # bcrypt.checkpw requires bytes
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


# ─── OTP Generation ─────────────────────────────────────────

def generate_otp() -> tuple[str, str]:
    """
    Generate a cryptographically secure 6-digit OTP.
    Returns: (plaintext_otp, bcrypt_hash_of_otp)
    """
    otp = "".join(secrets.choice("0123456789") for _ in range(6))
    otp_bytes = otp.encode('utf-8')
    otp_hash = bcrypt.hashpw(otp_bytes, bcrypt.gensalt(rounds=12)).decode('utf-8')
    return otp, otp_hash


def verify_otp(plain_otp: str, otp_hash: str) -> bool:
    """Verify a plaintext OTP against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_otp.encode('utf-8'), 
            otp_hash.encode('utf-8')
        )
    except Exception:
        return False


# ─── JWT Tokens ──────────────────────────────────────────────

def create_access_token(
    user_id: UUID,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    Payload contains user_id (sub), email, and expiration time.
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_otp_temp_token(email: str) -> str:
    """
    Create a short-lived temporary token after OTP verification.
    This token is required for the registration step.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_OTP_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": email,
        "exp": expire,
        "type": "otp_verified",
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    Returns the payload dict or None if invalid/expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.debug(f"JWT verification failed: {e}")
        return None


def verify_otp_temp_token(token: str) -> Optional[str]:
    """
    Verify an OTP temporary token and return the email if valid.
    Returns None if invalid or expired.
    """
    payload = verify_token(token)
    if payload is None:
        return None
    if payload.get("type") != "otp_verified":
        return None
    return payload.get("sub")
