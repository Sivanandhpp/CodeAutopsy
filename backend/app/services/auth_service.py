"""
CodeAutopsy Auth Utility Service
Handles password hashing, OTP generation, and JWT encoding/decoding.
"""

import random
import string
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
otp_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def generate_otp() -> str:
    """Generates a 6-digit OTP."""
    return ''.join(random.choices(string.digits, k=6))

def hash_otp(otp: str) -> str:
    return otp_context.hash(otp)

def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    return otp_context.verify(plain_otp, hashed_otp)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
