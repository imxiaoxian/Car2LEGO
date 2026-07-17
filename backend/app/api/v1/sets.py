"""LEGO set endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.lego_set import LegoSet
from app.schemas.car import LegoSetResponse

router = APIRouter()


@router.get("", response_model=list[LegoSetResponse])
async def list_sets(
    make: str | None = Query(default=None, description="Filter by car make"),
    model: str | None = Query(default=None, description="Filter by car model"),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List LEGO sets, optionally filtered by associated car."""
    stmt = select(LegoSet)
    if make:
        stmt = stmt.where(func.lower(LegoSet.car_make) == make.lower())
    if model:
        stmt = stmt.where(func.lower(LegoSet.car_model).contains(model.lower()))
    stmt = stmt.order_by(LegoSet.year.desc()).limit(limit)
    result = await db.execute(stmt)
    sets = result.scalars().all()
    return sets


@router.get("/known-cars", response_model=list[LegoSetResponse])
async def known_cars(
    db: AsyncSession = Depends(get_db),
):
    """Get all cars that have matching LEGO sets (for the explore page)."""
    stmt = (
        select(LegoSet)
        .where(LegoSet.car_make.isnot(None), LegoSet.car_model.isnot(None))
        .order_by(LegoSet.car_make, LegoSet.car_model)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{set_num}", response_model=LegoSetResponse)
async def get_set(
    set_num: str,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific LEGO set."""
    result = await db.execute(
        select(LegoSet).where(LegoSet.set_num == set_num)
    )
    lego_set = result.scalar_one_or_none()
    if not lego_set:
        raise HTTPException(status_code=404, detail="LEGO set not found")
    return lego_set
