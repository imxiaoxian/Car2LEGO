# backend/app/agents/section_schemas.py
"""Pydantic schemas for the section-by-section design workflow.

See docs/specs/2026-07-17-section-workflow-design.md for full design.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


SectionName = Literal["chassis", "front", "body", "rear", "wheels"]


class SectionBounds(BaseModel):
    """Physical boundary of a body section, locked by plan_design node."""
    section: SectionName
    z_range: tuple[float, float]
    y_range: tuple[float, float]
    connection_points: list[tuple[float, float, float]] = Field(default_factory=list)


class DesignPlan(BaseModel):
    """Output of plan_design node — global plan, hard constraint for 5 steps."""
    body_color_id: int
    accent_color_id: int
    overall_dimensions: dict  # {length, width, height} LDU
    section_bounds: list[SectionBounds]
    section_highlights: dict[str, str]
    brand_features_to_render: list[str] = Field(default_factory=list)
    plan_notes: str = ""

    @field_validator("section_bounds")
    @classmethod
    def must_have_5_sections(cls, v: list[SectionBounds]) -> list[SectionBounds]:
        if len(v) != 5:
            raise ValueError(f"section_bounds must have 5 entries, got {len(v)}")
        return v


class SectionPartPlacement(BaseModel):
    """Single LEGO part placement."""
    part_num: str
    color_id: int
    x: float
    y: float
    z: float
    rotation: str = "1 0 0 0 1 0 0 0 1"
    quantity: int = 1
    semantic_label: str = "detail"

    @field_validator("x")
    @classmethod
    def x_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"x must be >= 0 (right-half only), got {v}")
        return v


class SectionParts(BaseModel):
    """Output of build_section node."""
    section: SectionName
    parts: list[SectionPartPlacement]
    section_notes: str = ""


class DeterministicCheckResult(BaseModel):
    """Output of deterministic_check node."""
    passed: bool
    issues: list[str] = Field(default_factory=list)
    failed_part_indices: list[int] = Field(default_factory=list)


class SectionInspection(BaseModel):
    """Output of inspect_ldr node — LDR roundtrip snapshot."""
    section: str
    parts_snapshot: list[dict]
    boundary_occupancy: dict
    connection_integrity: dict
    distribution_stats: dict


class SectionEvaluation(BaseModel):
    """Output of llm_evaluate node."""
    quality_score: int = Field(ge=0, le=100)
    semantic_issues: list[str] = Field(default_factory=list)
    needs_retry: bool
    retry_guidance: str = ""
