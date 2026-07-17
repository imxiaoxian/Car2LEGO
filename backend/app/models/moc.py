"""Community MOC (My Own Creation) entity."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Integer, Numeric, func
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Moc(Base):
    __tablename__ = "mocs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4
    )
    rebrickable_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    car_make: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    car_model: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    parts_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ldraw_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
