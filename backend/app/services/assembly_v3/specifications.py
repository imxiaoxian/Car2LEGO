"""Scale capability registry. Validation is evidence-based and never inferred from size."""

import math

from app.services.vehicle_physics import OVERALL
from .requirements import SCALES, requirements_for_scale

CAPABILITIES = {s: [m["id"] for m in requirements_for_scale(s)["mechanisms"]] for s in SCALES}
F40_SPEC = {
    "length": 4358., "width": 1970., "height": 1124., "wheelbase": 2450.,
    "units": "mm", "estimated": False, "confidence": 1.,
    "source": "https://www.ferrari.com/en-EN/auto/f40",
    "source_type": "manufacturer_specification", "verification": "source_access_blocked_403",
}


def target_dimensions(spec: dict, scale: str) -> dict[str, float]:
    if scale not in SCALES:
        raise ValueError("Scale is not available for assembly_v3")
    denominator = int(scale.split(":")[1])
    return {key: float(spec[key]) / denominator / .4 for key in ("length", "width", "height", "wheelbase")}


def specifications_from_profile(profile: dict, fallback: dict | None = None, estimates: dict | None = None) -> dict:
    """Keep fallback/estimated dimensions explicitly distinct from sourced values."""
    result = dict(fallback or {})
    measurements = profile.get("measurements", {})
    origins = {}
    for name in OVERALL:
        record = measurements.get(name, {})
        if record.get("grounded"):
            result[name] = record["value"]
            origins[name] = "sourced"
        elif result.get(name, 0) > 0:
            origins[name] = "unverified_baseline"
        elif (estimates or {}).get(name, 0) > 0:
            result[name] = estimates[name]
            origins[name] = "model_estimate"
        elif record.get("value", 0) > 0 and not record.get("conflicted"):
            result[name] = record["value"]
            origins[name] = "unverified_document"
    if not all(math.isfinite(float(result.get(n, 0))) and float(result.get(n, 0)) > 0 for n in OVERALL):
        raise ValueError("Vehicle dimensions unavailable; provide sourced measurements or explicitly estimated dimensions")
    if result["wheelbase"] >= result["length"]:
        raise ValueError("Vehicle wheelbase must be shorter than overall length")
    result.update(units="mm", estimated=not profile.get("overall_grounded", False),
                  confidence=min(measurements[n]["confidence"] if origins[n] == "sourced" else .3 for n in OVERALL),
                  physical_data=profile, dimension_origins=origins)
    return result


def physical_layout_constraints(profile: dict) -> dict:
    measurements = profile.get("measurements", {})
    targets = {name: {"value": m["target_ldu"] if m["unit"] == "mm" else m["value"],
                      "unit": "LDU" if m["unit"] == "mm" else "deg", "source_url": m["source_url"]}
               for name, m in measurements.items() if m.get("grounded")}
    glass, rake = targets.get("windshield_height"), targets.get("windshield_rake")
    if glass and rake:
        angle = math.radians(rake["value"])
        targets["windshield_vertical_rise"] = {"value": glass["value"] * math.sin(angle), "unit": "LDU"}
        targets["windshield_horizontal_run"] = {"value": glass["value"] * math.cos(angle), "unit": "LDU"}
    return {"targets": targets, "unknown": profile.get("missing", []),
            "conflicts": profile.get("conflicts", []),
            "policy": "Native LEGO geometry only; record incompatible component targets for local redesign"}


def scale_capabilities(make: str = "Ferrari", model: str = "F40") -> list[dict]:
    f40 = make.lower() == "ferrari" and model.lower().replace(" ", "") == "f40"
    return [dict(ratio=s, ai_generation=True, official_sets=False, vehicle=f"{make} {model}",
                 status="experimental", precision_supported=False, mechanisms=CAPABILITIES[s],
                 requirements=requirements_for_scale(s),
                 recipe_available=f40, note="Experimental assembly; digital, Studio and physical acceptance required")
            for s in SCALES]
