"""
Authentication API Routes
==========================
Handles email check, OTP send/verify, registration, login, and password reset.
All endpoints are public (no JWT required) except /me.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.otp import OTP
from app.models.schemas import (
    EmailCheckRequest, EmailCheckResponse,
    OTPSendRequest, OTPSendResponse,
    OTPVerifyRequest, OTPVerifyResponse,
    RegisterRequest, LoginRequest, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import (
    hash_password, verify_password,
    generate_otp, verify_otp,
    create_access_token, create_otp_temp_token, verify_otp_temp_token,
)
from app.services.email_service import send_otp_email, send_password_reset_email
from app.api.deps import get_current_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ─── Check Email ─────────────────────────────────────────────

@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email(
    req: EmailCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check if an email is already registered."""
    result = await db.execute(
        select(User).where(User.email == req.email.lower())
    )
    user = result.scalar_one_or_none()
    return EmailCheckResponse(
        exists=user is not None,
        message="Account exists" if user else "New email",
    )


# ─── Send OTP ───────────────────────────────────────────────

@router.post("/send-otp", response_model=OTPSendResponse)
async def send_otp(
    req: OTPSendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate and send a 6-digit OTP to the given email."""
    settings = get_settings()
    email = req.email.lower()

    # Rate limit: max 5 OTPs per email per hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        select(OTP).where(
            and_(
                OTP.email == email,
                OTP.created_at > one_hour_ago,
            )
        )
    )
    recent_otps = result.scalars().all()
    if len(recent_otps) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait before trying again.",
        )

    # Generate OTP
    otp_code, otp_hash = generate_otp()

    # Store hashed OTP
    otp_record = OTP(
        email=email,
        otp_hash=otp_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp_record)
    await db.flush()

    # Send email (or print to console in dev mode)
    sent = await send_otp_email(email, otp_code)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email. Please try again.",
        )

    return OTPSendResponse(
        message="Verification code sent to your email",
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
    )


# ─── Verify OTP ─────────────────────────────────────────────

@router.post("/verify-otp", response_model=OTPVerifyResponse)
async def verify_otp_code(
    req: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify a 6-digit OTP code and return a temporary registration token."""
    email = req.email.lower()

    # Find the most recent unused, non-expired OTP for this email
    result = await db.execute(
        select(OTP)
        .where(
            and_(
                OTP.email == email,
                OTP.used == False,  # noqa: E712
                OTP.expires_at > datetime.now(timezone.utc),
            )
        )
        .order_by(OTP.created_at.desc())
        .limit(1)
    )
    otp_record = result.scalar_one_or_none()

    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new code.",
        )

    # Verify the OTP
    if not verify_otp(req.otp_code, otp_record.otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect verification code. Please try again.",
        )

    # Mark OTP as used
    otp_record.used = True
    await db.flush()

    # Generate temporary token for registration
    temp_token = create_otp_temp_token(email)

    return OTPVerifyResponse(
        verified=True,
        temp_token=temp_token,
        message="Email verified successfully",
    )


# ─── Register ───────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account after OTP verification."""
    # Verify the temporary token
    verified_email = verify_otp_temp_token(req.temp_token)
    if verified_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification. Please verify your email again.",
        )

    if verified_email.lower() != req.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email mismatch. The verification was for a different email.",
        )

    # Check if email already taken
    result = await db.execute(
        select(User).where(User.email == req.email.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Check if username already taken
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken. Please choose another.",
        )

    # Create user
    user = User(
        email=req.email.lower(),
        username=req.username,
        password_hash=hash_password(req.password),
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Generate access token
    access_token = create_access_token(user.id, user.email)

    logger.info(f"New user registered: {user.username} ({user.email})")

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        ),
    )


# ─── Login ───────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password and receive a JWT."""
    result = await db.execute(
        select(User).where(User.email == req.email.lower())
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id, user.email)

    logger.info(f"User logged in: {user.username}")

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        ),
    )


# ─── Forgot Password ────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset OTP to the user's email."""
    email = req.email.lower()

    # Always return success (don't reveal if email exists)
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user:
        settings = get_settings()
        otp_code, otp_hash = generate_otp()
        otp_record = OTP(
            email=email,
            otp_hash=otp_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
        db.add(otp_record)
        await db.flush()
        await send_password_reset_email(email, otp_code)

    return {"message": "If an account exists with this email, a reset code has been sent."}


# ─── Reset Password ─────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using OTP code."""
    email = req.email.lower()

    # Verify OTP
    result = await db.execute(
        select(OTP)
        .where(
            and_(
                OTP.email == email,
                OTP.used == False,  # noqa: E712
                OTP.expires_at > datetime.now(timezone.utc),
            )
        )
        .order_by(OTP.created_at.desc())
        .limit(1)
    )
    otp_record = result.scalar_one_or_none()

    if otp_record is None or not verify_otp(req.otp_code, otp_record.otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    otp_record.used = True

    # Update password
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(req.new_password)
    await db.flush()

    logger.info(f"Password reset for: {user.username}")
    return {"message": "Password has been reset successfully. You can now log in."}


# ─── Get Current User ───────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
    )
