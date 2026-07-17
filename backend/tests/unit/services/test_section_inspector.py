# backend/tests/unit/services/test_section_inspector.py
"""Section inspector tests — LDR roundtrip + distribution stats."""
from app.services.section_inspector import inspect_current_state


def _sample_parts():
    return [
        {"part_num": "3020.dat", "color_id": 7, "x": 40.0, "y": 8.0, "z": 100.0,
         "rotation": "1 0 0 0 1 0 0 0 1", "quantity": 1, "semantic_label": "chassis"},
        {"part_num": "3020.dat", "color_id": 7, "x": 40.0, "y": 8.0, "z": 200.0,
         "rotation": "1 0 0 0 1 0 0 0 1", "quantity": 1, "semantic_label": "chassis"},
        {"part_num": "3004.dat", "color_id": 4, "x": 40.0, "y": 48.0, "z": 150.0,
         "rotation": "1 0 0 0 1 0 0 0 1", "quantity": 1, "semantic_label": "body_side"},
    ]


def test_inspect_returns_section_inspection_shape():
    result = inspect_current_state(
        committed_parts=[],
        pending_parts=_sample_parts(),
        section="chassis",
        make="Ferrari", model="F40", year=1990,
    )
    assert result.section == "chassis"
    assert isinstance(result.parts_snapshot, list)
    assert isinstance(result.boundary_occupancy, dict)
    assert isinstance(result.connection_integrity, dict)
    assert isinstance(result.distribution_stats, dict)


def test_inspect_ldr_roundtrip_preserves_part_count():
    parts = _sample_parts()
    result = inspect_current_state(
        committed_parts=[], pending_parts=parts,
        section="chassis",
        make="Ferrari", model="F40", year=1990,
    )
    # LDR roundtrip should preserve parts (each part with X>0 gets mirrored,
    # so 3 right-half parts → 6 in LDR → but parts_snapshot stores right-half only)
    assert len(result.parts_snapshot) >= len(parts)


def test_distribution_stats_has_y_histogram():
    result = inspect_current_state(
        committed_parts=[], pending_parts=_sample_parts(),
        section="chassis",
        make="Ferrari", model="F40", year=1990,
    )
    assert "y_histogram" in result.distribution_stats
    assert "z_histogram" in result.distribution_stats
    assert "color_dist" in result.distribution_stats
    assert "type_dist" in result.distribution_stats
