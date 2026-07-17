"""Comprehensive car image analysis via the LangGraph vision graph.

Powered by vehicle_taxonomy.py — 52 body sub-styles, 80+ distinctive features,
50 factory colors → LEGO mapping, 25 wheel types, 18 grille types,
5 eras, 7 regions, 6 performance tiers, 5 modification levels.

The single-shot Vision API call path has been removed in Phase 5. All
analysis now flows through `app.agents.vision_graph`, which uses
`create_vision_llm().with_structured_output(CarFeaturesOutput)`.

This module retains the shared helpers (`_build_taxonomy_prompt`,
`_build_analysis_summary`) and the `SYSTEM_PROMPT` constant that the
vision graph imports. `VisionAnalyzer.analyze_image()` is the thin
entry point.
"""

from dataclasses import dataclass, field

from app.services.vehicle_taxonomy import (
    BODY_STYLES, ERAS, REGIONS, DISTINCTIVE_FEATURES,
    WHEEL_TYPES, PERFORMANCE_TIERS, MODIFICATION_LEVELS,
    FACTORY_COLORS,
)


@dataclass
class CarFeatures:
    """Rich car features extracted by Vision analysis."""
    # Identity
    make: str = ""
    model: str = ""
    year: int = 0

    # Classification
    body_style: str = ""              # Main: sports_car, supercar, sedan, suv, pickup, hatchback, wagon, convertible, van
    body_sub_style: str = ""          # Specific: mid_engine_coupe, fastback_sedan, off_road_suv, etc.
    era: str = ""                     # vintage, classic, modern_classic, retro_modern, contemporary, current_gen
    region: str = ""                  # jdm, euro, american_muscle, korean, chinese_ev, british
    performance_tier: str = ""        # economy, family, sport, performance, supercar, hypercar
    modification_level: str = ""      # stock, oem_plus, mild_street, heavy_build, race_spec, show_car

    # Color
    primary_color_name: str = ""      # Factory color name
    primary_color_hex: str = ""
    closest_lego_color: int = 4
    closest_lego_color_name: str = ""
    secondary_colors: list[str] = field(default_factory=list)
    has_two_tone: bool = False
    has_racing_stripes: bool = False
    has_carbon_accent: bool = False   # Carbon fiber hood/roof/mirrors

    # Dimensions
    estimated_length_studs: int = 16
    estimated_width_studs: int = 6
    estimated_height_bricks: int = 5

    # Wheels
    wheel_type: str = ""              # multi_spoke_sport, five_spoke_classic, deep_dish, etc.
    wheel_size_note: str = ""         # e.g., "19-inch, low profile"
    aftermarket_wheels: bool = False
    brake_caliper_color: str = ""     # red, yellow, silver, etc.

    # Design features — organized by category
    front_features: list[str] = field(default_factory=list)
    rear_features: list[str] = field(default_factory=list)
    side_features: list[str] = field(default_factory=list)
    aero_features: list[str] = field(default_factory=list)
    roof_features: list[str] = field(default_factory=list)
    lighting_features: list[str] = field(default_factory=list)
    ev_features: list[str] = field(default_factory=list)

    # LEGO design guidance
    grille_style: str = ""
    headlight_style: str = ""
    taillight_style: str = ""
    design_guidance: str = ""

    # Detected mods (from image)
    detected_mods: list[str] = field(default_factory=list)

    # Raw
    analysis_text: str = ""


class VisionAnalyzer:
    """Analyze car images via the LangGraph vision graph."""

    @staticmethod
    def _build_taxonomy_prompt() -> str:
        """Build the taxonomy section of the system prompt."""
        # Body sub-styles summary
        body_lines = []
        for style_id, info in BODY_STYLES.items():
            body_lines.append(f"  {style_id} ({info['label']}): {', '.join(info['sub_styles'][:6])}...")

        # Feature categories summary
        feat_lines = []
        for cat_id, cat_info in DISTINCTIVE_FEATURES.items():
            feat_lines.append(f"  {cat_info['label']}: {', '.join(cat_info['features'][:8])}...")

        # Wheel types summary
        wheel_lines = [f"  {wid}: {info['label']} ({info.get('real_examples','')})" for wid, info in list(WHEEL_TYPES.items())[:12]]

        # Color summary
        color_lines = [f"  {name}: LEGO {info['lego_id']} ({info['lego_name']})" for name, info in list(FACTORY_COLORS.items())[:20]]

        return f"""## Vehicle Classification Taxonomy

### Body Sub-Styles (52 total across 9 main categories)
{chr(10).join(body_lines)}

### Eras
{chr(10).join(f'  {eid}: {info["label"]} ({info["years"][0]}-{info["years"][1]}) — {info["lego_style"]}' for eid, info in ERAS.items())}

### Regions
{chr(10).join(f'  {rid}: {info["label"]} — {", ".join(info.get("design_traits",[])[:4])}' for rid, info in REGIONS.items())}

### Distinctive Features (80+ across 8 categories)
{chr(10).join(feat_lines)}

### Wheel Types (25 → LEGO part mapped)
{chr(10).join(wheel_lines)}

### Factory Colors → LEGO Mapping (50 colors)
{chr(10).join(color_lines)}

### Performance Tiers
{chr(10).join(f'  {tid}: {info["power_range"]}, ~{info["lego_parts"]} LEGO parts' for tid, info in PERFORMANCE_TIERS.items())}

### Modification Levels
{chr(10).join(f'  {mid}: {info["label"]} — {info["description"]}' for mid, info in MODIFICATION_LEVELS.items())}"""

    SYSTEM_PROMPT = """You are a world-class automotive design expert and LEGO master builder. Analyze car images with extreme precision.

## Handling Unknown / Novel Vehicles

If the vehicle DOES NOT fit any existing taxonomy category:
1. Select "other" for that field
2. Fill the corresponding custom_* field with a detailed description
3. Add an entry to taxonomy_suggestions proposing a new category
4. Be precise — "3-wheeled reverse trike with tilting mechanism" is better than "weird car"

## Output Requirements

For EVERY car image, you MUST classify across ALL dimensions. Use 'other' freely when needed — it's better to be accurate than to force-fit into wrong categories.

## Examples of edge cases handled:

- Morgan 3 Wheeler → body_style="other", custom="3-wheeled reverse trike, V-twin engine, vintage styling"
- Polaris Slingshot → body_style="other", custom="3-wheeled autocycle, open cockpit, side-by-side seating"
- Sherp ATV → body_style="other", custom="amphibious all-terrain vehicle, 4 massive low-pressure tires"
- 6x6 G-Wagon → body_style="other", wheel_count=6, custom="6-wheeled luxury off-road pickup conversion"
- Cybertruck → body_style="pickup", body_sub_style="electric_pickup", unusual_attributes=["stainless steel exoskeleton", "triangular wedge profile", "no paint"]
- Toyota Pod concept → is_concept_vehicle=true, unusual_attributes=["AI companion", "mood-sensing color-changing exterior", "pod-like shape"]

Be thorough. Leave no category unclassified. Use 'other' + custom_* when needed. Suggest taxonomy expansions for genuinely new vehicle types."""

    def __init__(self):
        self._taxonomy_suggestions: list[dict] = []

    def get_taxonomy_suggestions(self) -> list[dict]:
        """Get taxonomy expansion suggestions from analyses. Call after analyze_image()."""
        return self._taxonomy_suggestions

    async def analyze_image(self, image_path: str) -> CarFeatures | None:
        """Analyze a car photo via the LangGraph vision graph.

        Args:
            image_path: Path to the car image file

        Returns:
            CarFeatures with comprehensive classification, or None if the
            vision LLM is not configured or the analysis fails.
        """
        # Imported here to avoid circular import: vision_graph.py imports
        # VisionAnalyzer at module level for SYSTEM_PROMPT + helpers.
        from app.agents.vision_graph import build_vision_graph

        graph = build_vision_graph()
        initial_state = {
            "image_path": image_path,
            "base64_image": "",
            "media_type": "jpeg",
            "taxonomy_prompt": "",
            "messages": [],
            "features_output": None,
            "car_features": None,
            "taxonomy_suggestions": [],
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        if result.get("status") != "completed":
            return None

        car_features_dict = result.get("car_features")
        if not car_features_dict:
            return None

        # Collect taxonomy suggestions for later retrieval via get_taxonomy_suggestions()
        self._taxonomy_suggestions.extend(result.get("taxonomy_suggestions", []))
        return CarFeatures(**car_features_dict)

    @staticmethod
    def _build_analysis_summary(data: dict) -> str:
        """Build a human-readable analysis summary from structured Vision output.

        Used to populate analysis_text in CarFeatures — gives downstream services
        a concise text description rather than just the design_guidance field.
        """
        parts: list[str] = []

        make = data.get("make", "")
        model = data.get("model", "")
        year = data.get("year", 0)
        if make or model:
            parts.append(f"{make} {model} ({year})".strip().rstrip("()"))
        else:
            parts.append("Unknown vehicle")

        body = data.get("body_sub_style", "") or data.get("body_style", "")
        if body:
            parts.append(f"Body: {body}")

        era = data.get("era", "")
        if era and era not in ("other", "current_gen", ""):
            parts.append(f"Era: {era}")

        region = data.get("region", "")
        if region and region != "other":
            parts.append(f"Region: {region}")

        perf = data.get("performance_tier", "")
        if perf and perf not in ("sport", ""):
            parts.append(f"Tier: {perf}")

        color = data.get("primary_color_name", "")
        if color:
            parts.append(f"Color: {color}")

        wheel = data.get("wheel_type", "")
        if wheel:
            parts.append(f"Wheels: {wheel}")

        design = data.get("design_guidance", "")
        if design:
            parts.append(f"Design notes: {design}")

        return " | ".join(parts)
