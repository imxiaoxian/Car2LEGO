"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.router import api_router
from app.database import engine, Base
from app.models import *  # noqa: ensure all models are loaded


async def _run_alembic_upgrade() -> None:
    """Run alembic migrations programmatically.

    Uses create_all as a fallback when no migrations exist (e.g., first setup).
    In production, always prefer alembic upgrade head.
    """
    import asyncio
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config()
        # Point alembic at our migrations directory
        script_location = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "alembic"
        )
        alembic_cfg.set_main_option("script_location", script_location)
        # Let env.py read DATABASE_URL from the environment
        alembic_cfg.set_main_option(
            "sqlalchemy.url", os.getenv("DATABASE_URL", settings.database_url)
        )
        # Run sync alembic command in a thread to avoid event-loop conflicts
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    except Exception:
        # Fallback: create_all (works for fresh dev setups)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — run migrations
    await _run_alembic_upgrade()
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
