"""
CodeAutopsy — Main FastAPI Application
AI-Powered Code Archaeology & Security Analysis Platform
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.api.routes.health import router as health_router
from app.api.routes.analysis import router as analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    
    # Create data directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/repos", exist_ok=True)
    
    # Initialize database
    create_tables(settings.DATABASE_URL)
    
    print("🔬 CodeAutopsy API is running!")
    print(f"📊 Database: {settings.DATABASE_URL}")
    print(f"🌐 CORS Origins: {settings.cors_origins_list}")
    
    yield
    
    # Cleanup on shutdown
    print("🛑 CodeAutopsy API shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="CodeAutopsy API",
        description="AI-Powered Code Archaeology & Security Analysis Platform",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(analysis_router, tags=["Analysis"])
    
    return app


app = create_app()
