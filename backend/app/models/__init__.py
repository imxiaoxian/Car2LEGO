"""Import all models for Alembic auto-detection."""

from app.models.car import Car
from app.models.car_spec import CarSpec
from app.models.design import Design, DesignPart
from app.models.lego_set import LegoSet
from app.models.moc import Moc
from app.models.part import Part, PartColor
from app.models.template import DesignTemplate
from app.models.user import User

__all__ = [
    "Car",
    "CarSpec",
    "Design",
    "DesignPart",
    "DesignTemplate",
    "LegoSet",
    "Moc",
    "Part",
    "PartColor",
    "User",
]
