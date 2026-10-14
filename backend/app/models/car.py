"""Car model entity — stores vehicle specifications from NHTSA API."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, SmallInteger, Text, UniqueConstraint, func, text
from sqlalchemy import JSON
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Car(Base):
    __tablename__ = "cars"
    __table_args__ = (UniqueConstraint("make", "model", "year"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4
    )
    make: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, index=True)
    trim: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    nhtsa_vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    designs = relationship("Design", back_populates="car")


Index("uq_cars_without_year", func.lower(Car.make), func.lower(Car.model), unique=True,
      sqlite_where=text("year IS NULL"), postgresql_where=text("year IS NULL"))
