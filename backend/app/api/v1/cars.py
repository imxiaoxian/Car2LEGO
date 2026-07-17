"""Car endpoints — lookup and validation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.integrations.nhtsa import nhtsa_client
from app.models.car import Car
from app.schemas.car import CarCreate, CarResponse

router = APIRouter()


@router.get("", response_model=list[CarResponse])
async def search_cars(
    make: str = Query(default="", description="Car make (brand)"),
    model: str = Query(default="", description="Car model"),
    year: int | None = Query(default=None, description="Model year"),
    db: AsyncSession = Depends(get_db),
):
    """Search for cars in the local database."""
    stmt = select(Car)
    if make:
        stmt = stmt.where(func.lower(Car.make).contains(make.lower()))
    if model:
        stmt = stmt.where(func.lower(Car.model).contains(model.lower()))
    if year:
        stmt = stmt.where(Car.year == year)
    stmt = stmt.order_by(Car.make, Car.model).limit(50)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/lookup", response_model=CarResponse)
async def lookup_car(
    car_in: CarCreate,
    db: AsyncSession = Depends(get_db),
):
    """Look up a car by make/model/year, validating against NHTSA.

    Creates the car record in the database if it doesn't exist.
    """
    # Check if already in DB
    stmt = select(Car).where(
        func.lower(Car.make) == car_in.make.lower(),
        func.lower(Car.model) == car_in.model.lower(),
        Car.year == car_in.year,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Validate via NHTSA
    nhtsa_data = await nhtsa_client.get_vehicle_details(
        car_in.make, car_in.model, car_in.year
    )

    car = Car(
        make=nhtsa_data["make"],
        model=nhtsa_data["model"],
        year=nhtsa_data["year"],
        trim=car_in.trim,
        body_style=nhtsa_data.get("body_style"),
        image_url=car_in.image_url,
        metadata_=nhtsa_data,
    )
    db.add(car)
    await db.flush()
    await db.refresh(car)
    return car


@router.get("/{car_id}", response_model=CarResponse)
async def get_car(
    car_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific car by ID."""
    result = await db.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    return car
