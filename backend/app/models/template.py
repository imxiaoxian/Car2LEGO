"""Design template entity for L3 category matching."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Integer, func
from sqlalchemy import JSON
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DesignTemplate(Base):
    __tablename__ = "design_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    body_style: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scale: Mapped[str] = mapped_column(String(20), nullable=False)
    parts_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_ldr: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjustable_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
