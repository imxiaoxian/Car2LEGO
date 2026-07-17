"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# ─── Car ──────────────────────────────────────────────

class CarCreate(BaseModel):
    make: str = Field(..., max_length=100, examples=["Porsche"])
    model: str = Field(..., max_length=200, examples=["911 Turbo"])
    year: int = Field(..., ge=1900, le=2030, examples=[2020])
    trim: str | None = None
    image_url: str | None = None


class CarResponse(BaseModel):
    id: uuid.UUID
    make: str
    model: str
    year: int
    trim: str | None = None
    body_style: str | None = None
    image_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Design ───────────────────────────────────────────

class DesignCreate(BaseModel):
    make: str = Field(..., max_length=100)
    model: str = Field(..., max_length=200)
    year: int = Field(..., ge=1900, le=2030)
    image_url: str | None = None
    scale: str = Field(
        default="1:38",
        description="Scale ratio: 1:8, 1:10, 1:12, or 1:38 (default)",
    )


class MatchInfo(BaseModel):
    level: int = Field(..., ge=1, le=4)
    label: str
    confidence: float
    set_num: str | None = None
    set_name: str | None = None
    moc_name: str | None = None
    moc_author: str | None = None


class DesignPartResponse(BaseModel):
    part_num: str
    ldraw_color_id: int
    color_name: str | None = None
    quantity: int
    bricklink_id: str | None = None
    name: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class DesignResponse(BaseModel):
    id: uuid.UUID
    car_id: uuid.UUID | None = None
    match: MatchInfo | None = None
    status: str
    parts_count: int | None = None
    difficulty: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class DesignDetailResponse(DesignResponse):
    car: CarResponse | None = None
    parts: list[DesignPartResponse] = []
    file_urls: dict[str, str] = {}
    parent_design_id: uuid.UUID | None = None
    customization_request: str | None = None


class DesignStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    progress: int = 0
    stage: str | None = None
    error_message: str | None = None


# ─── Customization ──────────────────────────────────────

class CustomizationRequest(BaseModel):
    customization_text: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        examples=["Add a large rear wing and wide body kit. Change the color to matte black."],
        description="Describe what modifications to make to the base car design.",
    )


class CustomizationResponse(BaseModel):
    id: uuid.UUID
    status: str
    message: str
    parent_design_id: uuid.UUID


# ─── LEGO Set ─────────────────────────────────────────

class LegoSetResponse(BaseModel):
    set_num: str
    name: str
    year: int | None = None
    brick_count: int | None = None
    car_make: str | None = None
    car_model: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


# ─── Export ───────────────────────────────────────────

class ExportOptions(BaseModel):
    format: str = Field(..., pattern="^(ldr|io|pdf|xml|csv)$")
    include_prices: bool = False
