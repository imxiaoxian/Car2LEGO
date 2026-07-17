"""Parts catalog endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.part import Part

router = APIRouter()


@router.get("")
async def search_parts(
    query: str = Query(default="", description="Search by part number or name"),
    category: str | None = Query(default=None, description="Filter by category"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search the parts catalog."""
    stmt = select(Part)
    if query:
        stmt = stmt.where(
            Part.name.ilike(f"%{query}%") | Part.part_num.ilike(f"%{query}%")
        )
    if category:
        stmt = stmt.where(Part.category == category)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    parts = result.scalars().all()
    return [
        {
            "part_num": p.part_num,
            "name": p.name,
            "category": p.category,
            "brick_type": p.brick_type,
            "image_url": p.image_url,
        }
        for p in parts
    ]
