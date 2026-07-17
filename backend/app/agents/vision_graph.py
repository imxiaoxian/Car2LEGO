"""LangGraph vision-analysis graph (Phase 3).

Replaces the single-shot `VisionAnalyzer.analyze_image()` call with a small
StateGraph:

    START → encode_image → analyze_agent → parse_features → END

Nodes:
- `encode_image`: deterministic — reads the image file → base64 + media_type
- `analyze_agent`: LLM node — `create_vision_llm().with_structured_output(CarFeaturesOutput)`
  produces a structured classification of the car in the image
- `parse_features`: deterministic — converts the Pydantic output to a
  CarFeatures-shaped dict, applies "other → custom_*" fallbacks, and collects
  taxonomy suggestions (reuses `VisionAnalyzer._parse_response` logic)

The graph is async; call via `await graph.ainvoke(initial_state)`.
"""

import base64
import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents.models import create_vision_llm
from app.agents.security import mask_api_key
from app.agents.state import VisionState
from app.services.vision_analyzer import VisionAnalyzer


# ── Pydantic output model (mirrors the legacy output_car_features schema) ──
# All fields optional except those the system prompt marks required.


class TaxonomySuggestion(BaseModel):
    """A proposed new taxonomy entry for a vehicle that didn't fit existing categories."""

    category: Literal["body_style", "sub_style", "wheel_type", "region", "feature", "era"] = Field(
        ..., description="Which taxonomy category this suggestion applies to"
    )
    suggested_id: str = Field(..., description="Proposed machine-readable ID (snake_case)")
    suggested_label: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Why this should be added to the taxonomy")
    similar_existing: str = Field("", description="Closest existing taxonomy entry")


class CarFeaturesOutput(BaseModel):
    """Structured output schema for car image analysis.

    Every enum field accepts "other" — when chosen, fill the corresponding
    custom_* field with a detailed description.
    """

    # ── Identity ──
    make: str = Field("", description="Vehicle manufacturer")
    model: str = Field("", description="Vehicle model name")
    year: int = Field(2024, description="Model year")
    confidence: str = Field(
        "likely",
        description="How confident are you in this classification?",
    )

    # ── Body classification ──
    body_style: str = Field(
        ...,
        description="Main body style. Use 'other' for vehicles not fitting any category.",
    )
    body_sub_style: str = Field("")
    custom_body_style: str = Field(
        "", description="REQUIRED if body_style='other'. Describe this vehicle's body type."
    )

    # ── Era / Region / Performance / Modification ──
    era: str = Field(...)
    custom_era: str = Field("", description="REQUIRED if era='other'")
    region: str = Field("")
    custom_region: str = Field("", description="REQUIRED if region='other'")
    performance_tier: str = Field(...)
    custom_performance_tier: str = Field("")
    modification_level: str = Field("stock")
    custom_modification_level: str = Field("")

    # ── Color ──
    primary_color_name: str = Field(...)
    primary_color_hex: str = Field("")
    closest_lego_color: int = Field(4, ge=0, le=511)
    closest_lego_color_name: str = Field("")
    secondary_colors: list[str] = Field(default_factory=list)
    has_two_tone: bool = False
    has_racing_stripes: bool = False
    has_carbon_accent: bool = False
    custom_color_note: str = Field("")

    # ── Dimensions ──
    estimated_length_studs: int = Field(16, ge=6, le=40)
    estimated_width_studs: int = Field(6, ge=3, le=16)
    estimated_height_bricks: int = Field(5, ge=2, le=15)

    # ── Wheels ──
    wheel_type: str = Field(...)
    custom_wheel_type: str = Field("", description="REQUIRED if wheel_type='other'")
    wheel_size_note: str = Field("")
    aftermarket_wheels: bool = False
    brake_caliper_color: str = Field("")
    wheel_count: int = Field(4, ge=0, le=12)

    # ── Features by category ──
    front_features: list[str] = Field(default_factory=list)
    rear_features: list[str] = Field(default_factory=list)
    side_features: list[str] = Field(default_factory=list)
    aero_features: list[str] = Field(default_factory=list)
    roof_features: list[str] = Field(default_factory=list)
    lighting_features: list[str] = Field(default_factory=list)
    ev_features: list[str] = Field(default_factory=list)
    custom_features: list[str] = Field(default_factory=list)

    # ── Unusual vehicle attributes ──
    unusual_attributes: list[str] = Field(default_factory=list)
    is_concept_vehicle: bool = False
    is_one_off_custom: bool = False
    is_racing_specific: bool = False
    is_amphibious: bool = False
    is_military_derived: bool = False

    # ── LEGO guidance ──
    grille_style: str = Field(...)
    headlight_style: str = Field(...)
    taillight_style: str = Field("")
    detected_mods: list[str] = Field(default_factory=list)
    design_guidance: str = Field(...)

    # ── Taxonomy expansion suggestions ──
    taxonomy_suggestions: list[TaxonomySuggestion] = Field(default_factory=list)


# Reuse the existing taxonomy prompt builder + system prompt
TAXONOMY_PROMPT = VisionAnalyzer._build_taxonomy_prompt()
SYSTEM_PROMPT = VisionAnalyzer.SYSTEM_PROMPT


# ── Graph nodes ──


async def encode_image_node(state: VisionState) -> dict:
    """Read the image file from disk and encode as base64."""
    image_path = state["image_path"]
    if not os.path.exists(image_path):
        return {
            "status": "failed",
            "error_message": f"Image file not found: {image_path}",
        }
    with open(image_path, "rb") as f:
        image_data = f.read()
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    media_type = {
        "jpg": "jpeg", "jpeg": "jpeg", "png": "png",
        "webp": "webp", "gif": "gif",
    }.get(ext, "jpeg")
    base64_image = base64.b64encode(image_data).decode("utf-8")
    return {
        "base64_image": base64_image,
        "media_type": media_type,
        "taxonomy_prompt": TAXONOMY_PROMPT,
    }


async def analyze_agent_node(state: VisionState) -> dict:
    """Call the vision LLM with the image + taxonomy prompt, getting structured output."""
    if state.get("status") == "failed":
        return {}

    llm = create_vision_llm()
    structured_llm = llm.with_structured_output(CarFeaturesOutput)

    base64_image = state["base64_image"]
    media_type = state["media_type"]
    taxonomy_prompt = state["taxonomy_prompt"]
    system_prompt = f"{SYSTEM_PROMPT}\n\n{taxonomy_prompt}"

    user_message = HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{media_type};base64,{base64_image}"},
            },
            {
                "type": "text",
                "text": (
                    "Analyze this car comprehensively. Classify across ALL taxonomy "
                    "dimensions. Be specific and thorough. Use 'other' + custom_* "
                    "fields for vehicles that don't fit existing categories."
                ),
            },
        ]
    )

    try:
        result = await structured_llm.ainvoke([SystemMessage(content=system_prompt), user_message])
        return {"features_output": result.model_dump()}
    except Exception as exc:
        return {
            "status": "failed",
            "error_message": mask_api_key(f"Vision LLM call failed: {exc}"),
        }


async def parse_features_node(state: VisionState) -> dict:
    """Convert the structured output dict to a CarFeatures-shaped dict.

    Applies the "other → custom_*" fallbacks and collects taxonomy suggestions.
    Reuses `VisionAnalyzer._build_analysis_summary` for the analysis_text field.
    """
    if state.get("status") == "failed":
        return {}

    data = state.get("features_output") or {}
    if not data:
        return {
            "status": "failed",
            "error_message": "No structured output from vision LLM.",
        }

    # Collect taxonomy suggestions (the LLM may emit them directly)
    suggestions = [s if isinstance(s, dict) else dict(s) for s in data.get("taxonomy_suggestions", [])]

    # Handle "other" values by substituting the custom_* field
    body_style = data.get("body_style", "sports_car")
    if body_style == "other":
        body_style = data.get("custom_body_style", "unknown_custom")
        # Auto-suggest this as a new taxonomy entry if not already suggested
        if not any(s.get("suggested_id") == body_style for s in suggestions):
            suggestions.append({
                "category": "body_style",
                "suggested_id": body_style.lower().replace(" ", "_").replace("-", "_")[:40],
                "suggested_label": body_style,
                "description": "Custom body style detected from image analysis",
                "similar_existing": "sports_car",
            })

    era = data.get("era", "current_gen")
    if era == "other":
        era = data.get("custom_era", "current_gen")

    region = data.get("region", "")
    if region == "other":
        region = data.get("custom_region", "")

    performance_tier = data.get("performance_tier", "sport")
    if performance_tier == "other":
        performance_tier = data.get("custom_performance_tier", "sport")

    modification_level = data.get("modification_level", "stock")
    if modification_level == "other":
        modification_level = data.get("custom_modification_level", "stock")

    wheel_type = data.get("wheel_type", "")
    if wheel_type == "other":
        wheel_type = data.get("custom_wheel_type", "five_spoke_classic")

    car_features = {
        "make": data.get("make", ""),
        "model": data.get("model", ""),
        "year": data.get("year", 2024),
        "body_style": body_style,
        "body_sub_style": data.get("body_sub_style", ""),
        "era": era,
        "region": region,
        "performance_tier": performance_tier,
        "modification_level": modification_level,
        "primary_color_name": data.get("primary_color_name", ""),
        "primary_color_hex": data.get("primary_color_hex", ""),
        "closest_lego_color": data.get("closest_lego_color", 4),
        "closest_lego_color_name": data.get("closest_lego_color_name", ""),
        "secondary_colors": data.get("secondary_colors", []),
        "has_two_tone": data.get("has_two_tone", False),
        "has_racing_stripes": data.get("has_racing_stripes", False),
        "has_carbon_accent": data.get("has_carbon_accent", False),
        "estimated_length_studs": data.get("estimated_length_studs", 16),
        "estimated_width_studs": data.get("estimated_width_studs", 6),
        "estimated_height_bricks": data.get("estimated_height_bricks", 5),
        "wheel_type": wheel_type,
        "wheel_size_note": data.get("wheel_size_note", ""),
        "aftermarket_wheels": data.get("aftermarket_wheels", False),
        "brake_caliper_color": data.get("brake_caliper_color", ""),
        "front_features": data.get("front_features", []) + [
            f"CUSTOM: {f}" for f in data.get("custom_features", [])
        ],
        "rear_features": data.get("rear_features", []),
        "side_features": data.get("side_features", []),
        "aero_features": data.get("aero_features", []),
        "roof_features": data.get("roof_features", []),
        "lighting_features": data.get("lighting_features", []),
        "ev_features": data.get("ev_features", []),
        "grille_style": data.get("grille_style", ""),
        "headlight_style": data.get("headlight_style", ""),
        "taillight_style": data.get("taillight_style", ""),
        "detected_mods": data.get("detected_mods", []),
        "design_guidance": data.get("design_guidance", ""),
        "analysis_text": VisionAnalyzer._build_analysis_summary(data),
    }

    return {
        "car_features": car_features,
        "taxonomy_suggestions": suggestions,
        "status": "completed",
    }


# ── Graph builder ──


def build_vision_graph():
    """Compile and return the vision-analysis StateGraph.

    The graph is async; call via `await graph.ainvoke(initial_state)`.
    """
    graph = StateGraph(VisionState)

    graph.add_node("encode_image", encode_image_node)
    graph.add_node("analyze_agent", analyze_agent_node)
    graph.add_node("parse_features", parse_features_node)

    graph.add_edge(START, "encode_image")
    graph.add_edge("encode_image", "analyze_agent")
    graph.add_edge("analyze_agent", "parse_features")
    graph.add_edge("parse_features", END)

    return graph.compile()
