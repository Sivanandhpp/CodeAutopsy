"""
CodeAutopsy Async Database Engine
==================================
Production-grade async SQLAlchemy setup with PostgreSQL via asyncpg.
Handles connection pooling, session lifecycle, and table creation.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Base Model ──────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ─── Engine & Session Factory (Module-level singletons) ──────
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine with connection pooling."""
    global _engine
    if _engine is None:
        settings = get_settings()

        # Determine pool class — NullPool for testing, QueuePool for production
        engine_kwargs = {
            "echo": False,
            "future": True,
            "pool_pre_ping": True,          # Verify connections before use
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }

        _engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
        logger.info(
            f"Database engine created: pool_size={settings.DB_POOL_SIZE}, "
            f"max_overflow={settings.DB_MAX_OVERFLOW}"
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,       # Avoid lazy-load issues after commit
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


# ─── Session Dependency for FastAPI ──────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    Automatically commits on success, rolls back on error, and always closes.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_standalone_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Standalone session for background tasks (not tied to a request).
    Use this in background analysis tasks, scheduled jobs, etc.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Table Creation (Startup) ────────────────────────────────
async def create_tables() -> None:
    """Create all database tables. Called once during application startup."""
    # Import all models so they are registered with Base.metadata
    import app.models.user       # noqa: F401
    import app.models.project    # noqa: F401
    import app.models.otp        # noqa: F401
    import app.models.analysis   # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Database tables created/verified successfully")


async def dispose_engine() -> None:
    """Dispose of the engine on shutdown. Closes all pooled connections."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database engine disposed")
