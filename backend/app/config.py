"""
CodeAutopsy Configuration
=========================
Centralized settings loaded from environment variables via Pydantic Settings.
Supports PostgreSQL, JWT auth, email, Ollama, and all service configuration.
"""

import os
import logging
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — all configurable via environment variables."""

    # ─── Environment ─────────────────────────────────────────
    ENV: str = "development"  # "development" or "production"

    # ─── Database ────────────────────────────────────────────
    # Value is injected from .env. We don't hardcode connection strings here.
    DATABASE_URL: str = ""

    # Connection pool tuning — conservative defaults for budget VMs.
    # Override in .env for larger deployments.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # Recycle connections every 30 min

    # ─── JWT Authentication ──────────────────────────────────
    # Secret must be injected via .env
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_OTP_TOKEN_EXPIRE_MINUTES: int = 15       # Temporary token after OTP verification

    # ─── Email / OTP ─────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@codeautopsy.dev"
    SMTP_USE_TLS: bool = True
    OTP_EXPIRE_MINUTES: int = 10
    # If no SMTP configured, OTP is printed to console (dev mode)
    EMAIL_DEV_MODE: bool = True

    # ─── API Keys ────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_ENABLED: bool = True
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GITHUB_TOKEN: str = ""

    # ─── Ollama (Local AI) ───────────────────────────────────
    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = ""
    OLLAMA_TIMEOUT: int = 120                # Per-file analysis timeout
    OLLAMA_MAX_CONCURRENT: int = 4           # Max concurrent Ollama requests
    OLLAMA_ENABLED: bool = True

    # ─── CORS ────────────────────────────────────────────────
    CORS_ORIGINS: str = ""

    # ─── Analysis Limits ─────────────────────────────────────
    MAX_REPO_SIZE_MB: int = 100
    MAX_ANALYSIS_PER_HOUR: int = 10
    MAX_AI_CALLS_PER_HOUR: int = 20
    MAX_CONCURRENT_ANALYSES: int = 10        # System-wide concurrent limit

    # ─── Paths ───────────────────────────────────────────────
    # Repo storage is resolved by RepoStorageService (single source of truth).
    # Set REPOS_DIR env var to override. Leave empty for auto-detection.
    REPOS_DIR: str = ""

    # ─── Derived Properties ──────────────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_email_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    settings = Settings()

    # ── Production guard: reject weak JWT secrets ──
    _logger = logging.getLogger(__name__)
    secret = settings.JWT_SECRET_KEY
    if settings.ENV == "production":
        if not secret or len(secret) < 32 or "change-me" in secret:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY is too weak for production. "
                "Generate a secure key with: openssl rand -hex 32"
            )
    elif not secret:
        _logger.warning(
            "⚠ JWT_SECRET_KEY is empty — using an insecure default for development only."
        )

    return settings
