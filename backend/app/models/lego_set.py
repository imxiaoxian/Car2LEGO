"""LEGO set entity — official LEGO sets mapped to real car models."""

from datetime import datetime

from sqlalchemy import DateTime, String, SmallInteger, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LegoSet(Base):
    __tablename__ = "lego_sets"

    set_num: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    theme_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brick_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    car_make: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    car_model: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    minifigs: Mapped[int | None] = mapped_column(Integer, default=0)
    rebrickable_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
