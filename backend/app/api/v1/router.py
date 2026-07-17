"""Aggregate all v1 API routers."""

from fastapi import APIRouter

from app.api.v1 import cars, designs, sets, parts, export, mods, templates, community, research

api_router = APIRouter()

api_router.include_router(cars.router, prefix="/cars", tags=["cars"])
api_router.include_router(designs.router, prefix="/designs", tags=["designs"])
api_router.include_router(sets.router, prefix="/sets", tags=["sets"])
api_router.include_router(parts.router, prefix="/parts", tags=["parts"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(mods.router, prefix="/mods", tags=["mods"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(community.router, prefix="/community", tags=["community"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
