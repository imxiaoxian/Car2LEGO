"""User entity for saved designs and authentication."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy import Uuid as UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    auth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    saved_designs: Mapped[dict | None] = mapped_column(
        JSON, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
