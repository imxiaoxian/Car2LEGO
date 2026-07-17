from app.config import settings
from app.database import async_session
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
