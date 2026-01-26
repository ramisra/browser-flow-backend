from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.contexts import router as contexts_router
from app.api.tasks import router as tasks_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup: Initialize database connection
    # The engine is already created, we just need to verify connection
    async with engine.begin() as conn:
        # Test connection
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: Close database connections
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic URL Context Service",
        description=(
            "FastAPI service exposing agentic tasks for URL context collection and "
            "action planning with PostgreSQL database integration."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # Task endpoints
    app.include_router(tasks_router, prefix="/api")
    
    # Context endpoints
    app.include_router(contexts_router, prefix="/api")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()

