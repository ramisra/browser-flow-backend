"""Configuration management using environment variables."""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Database configuration
    DATABASE_URL: str = os.environ["DATABASE_URL"]
    # Set to "require" (default) for cloud PostgreSQL; use "disable" for local dev without SSL
    DATABASE_SSL: str = os.getenv("DATABASE_SSL", "require").lower()

    # OpenAI configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Application configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Opik configuration
    OPIK_ENABLED: bool = os.getenv("OPIK_ENABLED", "false").lower() == "true"
    OPIK_BASE_URL: Optional[str] = os.getenv("OPIK_BASE_URL")
    OPIK_URL_OVERRIDE: Optional[str] = os.getenv("OPIK_URL_OVERRIDE") or OPIK_BASE_URL
    OPIK_PROJECT_NAME: Optional[str] = os.getenv("OPIK_PROJECT_NAME")
    OPIK_WORKSPACE: Optional[str] = os.getenv("OPIK_WORKSPACE")
    OPIK_API_KEY: Optional[str] = os.getenv("OPIK_API_KEY")

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


# Global settings instance
settings = Settings()
