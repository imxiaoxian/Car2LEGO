"""TypedDict state definitions for each LangGraph graph.

State flows through graph nodes as a single dict. Each state schema documents
which keys a node may read and which it may write. `messages` uses LangGraph's
`add_messages` reducer so the ReAct loop can append without overwriting.
"""

from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class DesignState(TypedDict, total=False):
    """State for the design-generation graph (Path B: AI generation, 1:38 only).

    Phase 2 will wire nodes to read/write these keys.
    """

    # ── Input (set by StudioDesignGenerator.generate) ──
    design_id: str
    make: str
    model: str
    year: int
    scale: str
    mod_ids: list[str]
    custom_request: str
    flagship_metadata: dict | None

    # ── Intermediate state (populated by deterministic nodes) ──
    template_ldr: str
    template_info: dict
    template_parts: list[dict]          # Right-half parsed parts
    template_parts_json: str            # JSON string for prompt
    template_part_count: int            # Number of right-half parts
    parts_catalog_text: str
    colors_text: str
    mod_instructions: str
    scale_guidance: str
    prompt: str
    messages: Annotated[list, add_messages]  # ReAct conversation history
    customization_output: dict | None   # DesignCustomization dumped to dict
    design_output: dict | None  # Pydantic model dumped to dict
    retry_count: int

    # ── Output (written by finalize/build_ldraw/create_io nodes) ──
    ldr_content: str
    io_path: str
    ldr_path: str
    parts_data: list[dict]
    parts_count: int
    difficulty: str
    design_notes: str
    body_color_id: int
    metadata: dict
    status: str            # "completed" | "failed"
    error_message: str


class CustomizationState(TypedDict, total=False):
    """State for the customization graph.

    Phase 4 will replace the broken legacy path with this graph.
    """

    # ── Input ──
    design_id: str
    base_ldr_content: str
    base_parts_summary: str
    car_info: str
    customization_request: str

    # ── Intermediate (shared shape with DesignState) ──
    parts_catalog_text: str
    colors_text: str
    prompt: str
    messages: Annotated[list, add_messages]
    design_output: dict | None  # CustomizedDesign dumped to dict
    retry_count: int

    # ── Output ──
    ldr_content: str
    io_path: str
    ldr_path: str
    parts_data: list[dict]
    parts_count: int
    difficulty: str
    modification_summary: str
    added_parts: int
    removed_parts: int
    metadata: dict
    status: str
    error_message: str


class VisionState(TypedDict, total=False):
    """State for the vision-analysis graph.

    Phase 3 will replace the single LLM call with a tiny graph so the
    "other → custom_*" parsing can be a separate, testable node.
    """

    # ── Input ──
    image_path: str
    base64_image: str
    media_type: str
    taxonomy_prompt: str

    # ── Intermediate ──
    messages: Annotated[list, add_messages]
    features_output: dict | None  # Raw structured output from LLM

    # ── Output (parsed CarFeatures as dict + taxonomy suggestions) ──
    car_features: dict | None
    taxonomy_suggestions: list[dict]
    status: str
    error_message: str
