"""
CodeAutopsy Configuration
Loads settings from .env file using Pydantic Settings.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    GROQ_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/codeautopsy.db"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # Analysis limits
    MAX_REPO_SIZE_MB: int = 100
    MAX_ANALYSIS_PER_HOUR: int = 5
    MAX_AI_CALLS_PER_HOUR: int = 10
    
    # Paths
    REPOS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "repos")
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
