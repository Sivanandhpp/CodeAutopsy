"""
Email Service
=============
Sends OTP verification emails via SMTP or prints to console in dev mode.
"""

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Send a 6-digit OTP verification email.
    Falls back to console output if SMTP is not configured (dev mode).
    Returns True if sent successfully.
    """
    settings = get_settings()

    if settings.EMAIL_DEV_MODE or not settings.is_email_configured:
        # ─── Dev Mode: Print to console ──────────────────────
        logger.info(f"📧 [DEV MODE] OTP for {email}: {otp_code}")
        print(f"\n{'='*50}")
        print(f"📧  OTP VERIFICATION CODE")
        print(f"{'='*50}")
        print(f"  Email: {email}")
        print(f"  Code:  {otp_code}")
        print(f"  Expires in: {settings.OTP_EXPIRE_MINUTES} minutes")
        print(f"{'='*50}\n")
        return True

    # ─── Production: Send via SMTP ───────────────────────────
    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"CodeAutopsy — Your Verification Code: {otp_code}"
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = email

        # Plain text version
        text_body = (
            f"Your CodeAutopsy verification code is: {otp_code}\n\n"
            f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
            f"If you didn't request this, you can safely ignore this email."
        )

        # HTML version
        html_body = f"""
        <div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 24px;">
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="color: #6366f1; font-size: 24px; margin: 0;">CodeAutopsy</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">AI-Powered Code Analysis</p>
            </div>
            <div style="background: #0f172a; border-radius: 16px; padding: 32px; text-align: center;">
                <p style="color: #94a3b8; font-size: 14px; margin: 0 0 16px 0;">Your verification code is:</p>
                <div style="background: #1e293b; border-radius: 12px; padding: 20px; display: inline-block;">
                    <span style="color: #e2e8f0; font-size: 36px; font-weight: 700; letter-spacing: 8px; font-family: 'JetBrains Mono', monospace;">{otp_code}</span>
                </div>
                <p style="color: #64748b; font-size: 12px; margin-top: 20px;">
                    This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
                </p>
            </div>
            <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 24px;">
                If you didn't request this code, you can safely ignore this email.
            </p>
        </div>
        """

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        )

        logger.info(f"OTP email sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        return False


async def send_password_reset_email(email: str, otp_code: str) -> bool:
    """Send a password reset OTP email. Same as send_otp_email with different subject."""
    settings = get_settings()

    if settings.EMAIL_DEV_MODE or not settings.is_email_configured:
        logger.info(f"📧 [DEV MODE] Password Reset OTP for {email}: {otp_code}")
        print(f"\n{'='*50}")
        print(f"🔑  PASSWORD RESET CODE")
        print(f"{'='*50}")
        print(f"  Email: {email}")
        print(f"  Code:  {otp_code}")
        print(f"  Expires in: {settings.OTP_EXPIRE_MINUTES} minutes")
        print(f"{'='*50}\n")
        return True

    # For production, reuse OTP email with different messaging
    return await send_otp_email(email, otp_code)
