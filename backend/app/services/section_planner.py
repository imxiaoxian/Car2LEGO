# backend/app/services/section_planner.py
"""Compute physical boundaries for the 5 body sections.

The plan_design LLM node uses these bounds as hard constraints; build_section
must place every part within its section's z_range/y_range.

Layout (1:38 scale, right-half X=0-80, full car Z=0-360):
    chassis: Z=0-360,  Y=0-24   — structural base
    front:   Z=240-360, Y=24-96 — hood, headlights, grille, bumper
    body:    Z=80-240,  Y=24-144— body_side, roof, cabin, windshield
    rear:    Z=0-80,    Y=24-96 — taillights, diffuser, spoiler, exhaust
    wheels:  axles at Z=60 (front) and Z=200 (rear), Y=0-72
"""
from app.agents.section_schemas import SectionBounds


SECTIONS_ORDER = ["chassis", "front", "body", "rear", "wheels"]


def compute_section_bounds(scale: str, body_style: str) -> list[SectionBounds]:
    """Return the 5 section boundaries for a given scale + body style.

    Currently only 1:38 is supported (AI generation path). Other scales
    go through Rebrickable import and never reach this function.
    """
    if scale != "1:38":
        raise ValueError(f"unsupported scale for AI generation: {scale!r}")

    # body_style influences y_range (e.g., SUV taller roof) — keep simple for v1
    roof_y_max = 144.0
    if body_style == "suv":
        roof_y_max = 168.0
    elif body_style == "f1_race":
        roof_y_max = 72.0  # open cockpit

    return [
        SectionBounds(
            section="chassis",
            z_range=(0.0, 360.0),
            y_range=(0.0, 24.0),
            connection_points=[(0.0, 24.0, 0.0), (0.0, 24.0, 360.0)],
        ),
        SectionBounds(
            section="front",
            z_range=(240.0, 360.0),
            y_range=(24.0, 96.0),
            connection_points=[(0.0, 24.0, 240.0)],  # joins chassis at Z=240
        ),
        SectionBounds(
            section="body",
            z_range=(80.0, 240.0),
            y_range=(24.0, roof_y_max),
            connection_points=[(0.0, 24.0, 80.0), (0.0, 24.0, 240.0)],
        ),
        SectionBounds(
            section="rear",
            z_range=(0.0, 80.0),
            y_range=(24.0, 96.0),
            connection_points=[(0.0, 24.0, 80.0)],
        ),
        SectionBounds(
            section="wheels",
            z_range=(0.0, 360.0),
            y_range=(0.0, 72.0),
            connection_points=[(40.0, 0.0, 60.0), (40.0, 0.0, 200.0)],  # axles
        ),
    ]
