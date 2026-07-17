"""CarSpec model — real-world car specifications knowledge base.

Stores accurate vehicle dimensions, engine specs, and distinctive features
so the LLM design generator can produce models that match real car
proportions instead of guessing.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CarSpec(Base):
    __tablename__ = "car_specs"
    __table_args__ = (UniqueConstraint("make", "model", "year"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    make: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    body_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Real-world dimensions (millimeters)
    length_mm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    width_mm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    height_mm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    wheelbase_mm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Engine and drivetrain
    engine_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drive_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    horsepower: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    top_speed_kmh: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Exterior features (JSON lists)
    distinctive_features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    colors_available: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Body proportions description (natural language, for LLM reference)
    body_proportions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Metadata
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
