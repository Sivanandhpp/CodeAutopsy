"""
Authentication Endpoints
Handles login, signup, OTP verification, and JWT issuance.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone, timedelta
import uuid

from app.database import get_db, User, OTPCode
from app.services.auth_service import (
    get_password_hash, verify_password,
    generate_otp, hash_otp, verify_otp,
    create_access_token
)
from app.services.email_service import send_otp_email

router = APIRouter(prefix="/auth", tags=["Authentication"])

class EmailRequest(BaseModel):
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class SetPasswordRequest(BaseModel):
    email: EmailStr
    nickname: str
    password: str

class LoginPasswordRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login-init")
async def login_init(req: EmailRequest, db: AsyncSession = Depends(get_db)):
    """Initial step: check if user exists. Returns 'password' or 'otp'."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if user and user.is_verified:
        return {"status": "password"}
    
    if not user:
        # Create unverified placeholder user
        user = User(
            email=req.email,
            name="Pending User",
            hashed_password="",
            is_verified=False
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # Generate OTP
    otp_code = generate_otp()
    hashed = hash_otp(otp_code)
    
    # Save OTP to DB
    otp_record = OTPCode(
        user_id=user.id,
        code=hashed,
        purpose="email_verification",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    db.add(otp_record)
    await db.commit()
    
    # Send email
    await send_otp_email(req.email, otp_code)
    
    return {"status": "otp"}

@router.post("/verify-otp")
async def verify_otp_endpoint(req: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Verifies the standard 6 digit OTP sent to the user email."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    result = await db.execute(
        select(OTPCode)
        .where(OTPCode.user_id == user.id)
        .where(OTPCode.used == False)
        .where(OTPCode.expires_at > datetime.now(timezone.utc))
        .order_by(OTPCode.expires_at.desc())
    )
    otp_record = result.scalars().first()
    
    if not otp_record:
        print(f"❌ DEBUG OTP: No valid OTP record found for {user.email}")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")
        
    clean_otp = req.otp.strip()
    if not verify_otp(clean_otp, otp_record.code):
        print(f"❌ DEBUG OTP: Verification failed for {user.email}. Provided: '{clean_otp}'")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP.")    
    # Mark as used
    otp_record.used = True
    user.is_verified = True
    await db.commit()
    
    return {"status": "set_password"}

@router.post("/set-password")
async def set_password(req: SetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Sets nickname and password for newly verified users."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified or found.")
        
    user.name = req.nickname
    user.hashed_password = get_password_hash(req.password)
    await db.commit()
    
    # Generate JWT
    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name}
    }

@router.post("/login-password")
async def login_password(req: LoginPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Standard password login."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user or not user.is_verified:
        raise HTTPException(status_code=401, detail="Invalid credentials or unverified user.")
        
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
        
    # Generate JWT
    access_token = create_access_token(data={"sub": user.id, "email": user.email})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name}
    }
