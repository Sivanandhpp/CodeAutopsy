"""
CodeAutopsy — Main FastAPI Application
AI-Powered Code Archaeology & Security Analysis Platform
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes.health import router as health_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.archaeology import router as archaeology_router
from app.api.routes.ai import router as ai_router
from app.api.routes.report import router as report_router
from app.api.routes.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    
    # Create data directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/repos", exist_ok=True)
    
    # Initialize async database
    from app.database import init_db
    await init_db()
    
    print("🔬 CodeAutopsy API is running!")
    print(f"📊 Database: {settings.DATABASE_URL.replace('secretpassword', '***')}")
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
    app.include_router(auth_router, prefix="/api", tags=["Authentication"])
    app.include_router(health_router, prefix="/api", tags=["Health"])
    app.include_router(analysis_router, prefix="/api", tags=["Analysis"])
    app.include_router(archaeology_router, prefix="/api", tags=["Archaeology"])
    app.include_router(ai_router, prefix="/api", tags=["AI"])
    app.include_router(report_router, prefix="/api", tags=["Report"])
    
    return app


app = create_app()
