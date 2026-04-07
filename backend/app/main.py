"""
CodeAutopsy — Main FastAPI Application
========================================
AI-Powered Code Archaeology & Security Analysis Platform
v2.0: Docker + PostgreSQL + JWT Auth + Ollama
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import dispose_engine

# Route imports
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.projects import router as projects_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.archaeology import router as archaeology_router
from app.api.routes.ai import router as ai_router
from app.api.routes.report import router as report_router
from app.api.routes.rules import router as rules_router
from app.api.routes.admin import router as admin_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    # Create data directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/repos", exist_ok=True)

    logger.info("🔬 CodeAutopsy API v2.0 is running!")
    logger.info(f"📊 Database: PostgreSQL (async)")
    logger.info(f"🌐 CORS Origins: {settings.cors_origins_list}")
    logger.info(f"🤖 Ollama: {'enabled' if settings.OLLAMA_ENABLED else 'disabled'}")

    yield

    # Cleanup on shutdown
    await dispose_engine()
    logger.info("🛑 CodeAutopsy API shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="CodeAutopsy API",
        description="AI-Powered Code Archaeology & Security Analysis Platform",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Register routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(projects_router)
    app.include_router(analysis_router, tags=["Analysis"])
    app.include_router(archaeology_router)
    app.include_router(ai_router)
    app.include_router(report_router)
    app.include_router(rules_router)
    app.include_router(admin_router)

    return app


app = create_app()
