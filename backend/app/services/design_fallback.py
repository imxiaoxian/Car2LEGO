# backend/app/services/design_fallback.py
"""Fallback path — when final_validate fails after section retries.

Invokes the legacy single-shot customize_design logic (now in
design_graph_legacy.py) and tags the result so callers can track
which designs used fallback.
"""
from app.agents.design_graph_legacy import build_design_graph as build_legacy_graph


async def fallback_single_shot(state: dict) -> dict:
    """Run legacy graph as fallback. Returns dict matching v2 output shape."""
    # Adapt v2 state → legacy state shape (legacy expects its own keys)
    legacy_state = {
        "design_id": state["design_id"],
        "make": state["make"],
        "model": state["model"],
        "year": state["year"],
        "scale": state.get("scale", "1:38"),
        "mod_ids": state.get("mod_ids", []),
        "custom_request": state.get("custom_request", ""),
        "flagship_metadata": state.get("flagship_metadata"),
        "messages": [],
        "design_output": None,
        "retry_count": 0,
        "status": "",
        "error_message": "",
        "reference_images": state.get("reference_images", []),
        "reference_brief": state.get("reference_brief", {}),
        "vehicle_features": state.get("vehicle_features", {}),
        "storage_path": state.get("storage_path", ""),
    }

    graph = build_legacy_graph()
    result = await graph.ainvoke(legacy_state)

    # Tag metadata so we can track fallback usage
    metadata = result.get("metadata", {}) or {}
    metadata["workflow"] = "fallback_legacy"
    metadata["fallback_reason"] = "final_validate failed after section retries"
    result["metadata"] = metadata
    result["fallback_used"] = True
    return result
