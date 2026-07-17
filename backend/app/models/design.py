"""Design entity — the core output: a LEGO design for a specific car."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, SmallInteger, Text, Integer, ForeignKey, UniqueConstraint, func
from sqlalchemy import JSON; from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4
    )
    car_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("cars.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("users.id"), nullable=True, comment="Owner (Phase 2)"
    )
    match_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="1=official set, 2=MOC, 3=template, 4=AI"
    )
    matched_set_num: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("lego_sets.set_num"), nullable=True
    )
    matched_moc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("mocs.id"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("design_templates.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="pending / processing / completed / failed"
    )
    scale: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="minifig-scale",
        comment="minifig-scale / speed-champions / technic / creator-expert"
    )
    visibility: Mapped[str] = mapped_column(
        String(20), default="private",
        comment="private / public / unlisted"
    )
    parts_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_io_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_ldr_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_job_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("designs.id"), nullable=True,
        comment="If this is a customization, references the base design"
    )
    customization_request: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="The user's customization instructions"
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    car = relationship("Car", back_populates="designs")
    matched_set = relationship("LegoSet")
    matched_moc = relationship("Moc")
    template = relationship("DesignTemplate")
    parent_design = relationship("Design", remote_side="Design.id", backref="customizations")
    parts = relationship("DesignPart", back_populates="design", cascade="all, delete-orphan")


class DesignPart(Base):
    __tablename__ = "design_parts"
    __table_args__ = (
        UniqueConstraint("design_id", "part_num", "ldraw_color_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    design_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )
    part_num: Mapped[str] = mapped_column(
        String(25), ForeignKey("parts.part_num"), nullable=False
    )
    ldraw_color_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bricklink_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bricklink_color_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    price_guide: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    design = relationship("Design", back_populates="parts")
