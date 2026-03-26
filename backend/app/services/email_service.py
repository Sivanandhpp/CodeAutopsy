"""
CodeAutopsy Email Service
Sends OTPs and other notifications via Gmail SMTP.
"""

import aiosmtplib
from email.message import EmailMessage
from app.config import get_settings

async def send_otp_email(to_email: str, otp_code: str):
    """Sends an OTP to the given email address."""
    settings = get_settings()
    
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # Fallback for development if credentials are not provided
        print(f"⚠️ [DEV MODE] OTP for {to_email}: {otp_code}")
        return
    
    msg = EmailMessage()
    msg.set_content(f"Your CodeAutopsy verification code is: {otp_code}\n\nThis code will expire in 10 minutes.")
    msg["Subject"] = "CodeAutopsy Verification Code"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )
        print(f"✅ OTP sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send OTP to {to_email}: {e}")
        # Log to terminal for debugging
        print(f"⚠️ [DEV FALLBACK] OTP for {to_email}: {otp_code}")
