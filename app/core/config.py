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

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


# Global settings instance
settings = Settings()
