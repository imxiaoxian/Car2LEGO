"""LEGO part entity — catalog of individual LEGO pieces."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, SmallInteger, Boolean, func
from sqlalchemy import JSON as JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Part(Base):
    __tablename__ = "parts"

    part_num: Mapped[str] = mapped_column(String(25), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ldraw_name: Mapped[str | None] = mapped_column(String(25), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brick_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dimensions_mm: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    year_released: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PartColor(Base):
    __tablename__ = "part_colors"

    part_num: Mapped[str] = mapped_column(
        String(25), primary_key=True
    )
    ldraw_color_id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, nullable=False
    )
    lego_element_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bricklink_color_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    bricklink_part_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rebrickable_color_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    color_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hex_rgb: Mapped[str | None] = mapped_column(String(7), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
