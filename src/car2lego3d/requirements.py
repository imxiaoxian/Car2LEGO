"""Versioned design requirements and draft checks for each vehicle scale."""
from copy import deepcopy
import hashlib
import json
import math

from .vehicle import measurement, tyre_diameter, validate_spec


POLICY_VERSION = "car2lego3d-scale-v1"
SCALES = ("1:38", "1:24", "1:16", "1:12")
RECIPE_LENGTH_RANGE = (23, 32)
RECIPE_WIDTHS = (8, 10, 12)
SCALE_MODES = ("exact", "appearance", "auto")
PREFERRED_SCALE_DENOMINATOR = 12
APPEARANCE_SIZE_MARGIN = .15
OVERALL = ["length", "width", "height", "wheelbase"]
TYRES = ["front_tyre_diameter", "rear_tyre_diameter"]
GLASS = ["windscreen_bottom_width", "windscreen_slant_height", "windscreen_angle_to_horizontal"]
EXTERIOR = ["front_three_quarter", "rear_three_quarter", "front", "rear", "side", "top"]
EVIDENCE = ["native_dimensions", "native_collision", "connectivity", "appearance_comparison",
            "studio_open", "physical_build"]


def _policy(scale, label, detail, fields, mechanisms, views, tyre_error, tyre_width_error, step_parts):
    compact = scale == "1:38"
    tolerances = {"length": 5 if compact else 3, "width": 10 if compact else 5,
                  "height": 8 if compact else 5, "wheelbase": 5 if compact else 3,
                  "front_track": 10 if compact else 5, "rear_track": 10 if compact else 5,
                  "door_length": 5, "door_panel_height": 5, "seat_width": 5,
                  "windscreen_bottom_width": 8 if compact else 5, "windscreen_slant_height": 8 if compact else 5,
                  "engine_length": 5, "engine_width": 5, "engine_height": 5}
    for axle in ("front", "rear"):
        tolerances.update({f"{axle}_tyre_diameter": tyre_error, f"{axle}_tyre_width": tyre_width_error,
                           f"{axle}_rim_diameter": 3})
    return {"version": POLICY_VERSION, "scale": scale, "label": label,
            "visual_requirements": detail, "required_measurements": fields,
            "required_mechanisms": mechanisms, "reference_views": EXTERIOR + views,
            "dimension_tolerances_percent": tolerances,
            "angle_tolerances_degrees": {"windscreen_angle_to_horizontal": 8 if compact else
                                          {"1:24": 5, "1:16": 3, "1:12": 2}[scale],
                                          "door_opening_angle": 5},
            "max_parts_per_step": step_parts, "motion_sample_count": 9,
            "required_evidence": list(EVIDENCE), "standard_part_scaling_allowed": False,
            "applicability": "Engine, intakes and wing follow the exact vehicle variant; exceptions require evidence.",
            "excluded_mechanisms": ["gearbox", "powered_drivetrain"]}


_compact = OVERALL + TYRES
_standard = _compact + ["front_tyre_width", "rear_tyre_width"] + GLASS
_detailed = _standard + ["front_track", "rear_track", "door_length", "door_panel_height",
                         "door_opening_angle", "seat_width"]
_precision = _detailed + ["engine_length", "engine_width", "engine_height",
                         "front_rim_diameter", "rear_rim_diameter"]
_rolling = {"rolling_wheels": 4}
_covers = {**_rolling, "front_hood": 1, "engine_cover": 1}
_doors = {**_covers, "opening_doors": 2, "steering": 1}
_exterior = ["recognizable silhouette and stance", "wheel arches", "front and rear lights",
             "transparent glazing", "vehicle-specific intakes and rear treatment"]
_interior = ["continuous body surfaces", "dimensioned windscreen", "simplified seats and dashboard",
             "simplified engine bay"]
_detail = ["separate seats and headrests", "dashboard and console", "door panels and opening clearances"]
_views = ["cockpit", "engine_bay", "hood_open", "engine_cover_open", "hinges", "intakes", "lights", "seats"]
_POLICIES = {
    "1:38": _policy("1:38", "compact", _exterior, _compact, _rolling, [], 15, 20, 12),
    "1:24": _policy("1:24", "exterior", _exterior + _interior, _standard, _covers, _views, 5, 10, 12),
    "1:16": _policy("1:16", "interior", _exterior + _interior + _detail, _detailed, _doors,
                      _views + ["doors_open", "door_hinges", "dashboard", "steering"], 5, 7.5, 10),
    "1:12": _policy("1:12", "structure", _exterior + _interior + _detail +
                      ["engine plumbing", "layered body panels", "underbody load paths", "suspension clearances"],
                      _precision, {**_doors, "independent_suspension": 4},
                      _views + ["doors_open", "door_hinges", "dashboard", "steering", "suspension", "underbody"],
                      3, 5, 8),
}


def requirements_for_scale(scale):
    if scale not in SCALES:
        raise ValueError(f"Available scale policies: {', '.join(SCALES)}; 1:8 and 1:10 are reserved.")
    return deepcopy(_POLICIES[scale])


def automatic_requirements():
    return {"version": "car2lego3d-auto-size-v2", "scale": None, "label": "appearance",
            "size_reference": {"ratio": "1:12", "denominator": PREFERRED_SCALE_DENOMINATOR,
                               "binding": False},
            "visual_requirements": _exterior + _detail + ["continuous modular body surfaces",
                "native glazing integrated with door assemblies", "layered lamp housings and lenses",
                "complete cockpit and vehicle-specific front and rear transitions",
                "engine bay plumbing", "layered body panels", "underbody load paths",
                "suspension and wheel clearances",
                "preserve reference detail without scale-based simplification"],
            "required_measurements": list(_precision),
            "required_mechanisms": {**_doors, "independent_suspension": 4},
            "reference_views": EXTERIOR + _views + ["doors_open", "door_hinges", "dashboard", "steering",
                                                      "suspension", "underbody"],
            "dimension_tolerances_percent": {}, "angle_tolerances_degrees": {},
            "max_parts_per_step": 8, "motion_sample_count": 9,
            "required_evidence": list(EVIDENCE), "standard_part_scaling_allowed": False,
            "excluded_mechanisms": ["gearbox", "powered_drivetrain"]}


def _automatic_plan(spec, scale, length, width):
    if scale is not None or length is not None or width is not None:
        raise ValueError("Automatic sizing does not accept a scale or fixed grid dimensions.")
    policy = automatic_requirements()
    reference_denominator = policy["size_reference"]["denominator"]
    reference_mm = {field: measurement(spec, field) / reference_denominator
                    for field in OVERALL}
    # This is a starting footprint, not a bound on later native-module fitting.
    length = max(1, math.floor(reference_mm["length"] / 8 + .5))
    width = max(2, 2 * math.floor(reference_mm["width"] / 16 + .5))
    denominator = measurement(spec, "length") / (length*8)
    blockers = []
    if not RECIPE_LENGTH_RANGE[0] <= length <= RECIPE_LENGTH_RANGE[1]:
        blockers.append(f"Approximate 1:12 footprint needs {length} studs in length; "
                        f"current compact chassis supports {RECIPE_LENGTH_RANGE[0]}..{RECIPE_LENGTH_RANGE[1]}.")
    if width not in RECIPE_WIDTHS:
        blockers.append(f"Approximate 1:12 footprint needs {width} studs in width; "
                        "matching native wheel, glazing and chassis modules are not implemented (compact widths: 8/10/12).")
    fields = [measurement_source(spec, field) for field in policy["required_measurements"]]
    return {"policy": policy, "selection": "automatic_approximate_size_reference",
            "requested_scale": None, "target_scale_denominator": denominator,
            "vehicle_spec_fingerprint": spec_fingerprint(spec),
            "grid": {"length_studs": length, "width_studs": width,
                     "target_length_mm": None, "target_width_mm": None,
                     "effective_core_length_scale_denominator": denominator},
            "scale_intent": {"mode": "auto", "requested_grid": {"length_studs": None, "width_studs": None},
                "size_margin_percent": None, "standard_part_scaling_allowed": False,
                "size_reference": {**policy["size_reference"], "dimensions_mm": reference_mm},
                "fitting_scale_denominator": denominator,
                "priorities": ["rendered appearance", "complete native modules and detail",
                               "vehicle proportions", "approximate 1:12 size"],
                "ranking": "Initial stud footprint from a soft size reference; native module fitting may change it."},
            "physical_data": fields,
            "missing_measurements": [item["field"] for item in fields if item["status"] == "missing"],
            "estimated_measurements": [item["field"] for item in fields if item["status"] == "estimated"],
            "generation": {"draft_recipe_available": not blockers, "blockers": blockers, "delivery_ready": False},
            "notes": ["Approximate 1:12 size and full detail are preferred; no fixed dimensions or percentage size bounds.",
                "Reference millimeters are planning estimates, not measured exterior dimensions or acceptance limits.",
                "The fitting denominator transfers vehicle proportions; it is not a delivery size requirement.",
                "Do not fall back to a compact recipe or remove details to satisfy current recipe capacity.",
                "Larger wheel, windscreen and chassis modules require matching recipes; no part stretching.",
                "Actual dimensions must be measured from exported native geometry.",
                "No visual, Studio or physical acceptance is implied by automatic sizing."]}


def spec_fingerprint(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def measurement_source(spec, field):
    if field in TYRES:
        axle = field.split("_")[0]
        names = [f"{axle}_{suffix}" for suffix in ("tyre_width", "tyre_aspect", "rim_diameter")]
        value = tyre_diameter(spec, axle)
    else:
        names, value = [field], measurement(spec, field)
    statuses = [spec["measurements"].get(name, {}).get("status", "unknown") for name in names]
    status = "missing" if value is None else "estimated" if "estimated" in statuses else "sourced"
    return {"field": field, "value": value, "status": status,
            "source_fields": names, "source_statuses": statuses}


def _appearance_grids(spec, denominator, wedge, width_override):
    target_length = measurement(spec, "length") / denominator
    target_width = measurement(spec, "width") / denominator
    candidates = []
    for length in range(22 if wedge else RECIPE_LENGTH_RANGE[0], RECIPE_LENGTH_RANGE[1]+1):
        for width in RECIPE_WIDTHS:
            if width_override is not None and width != width_override:
                continue
            length_error = length*8/target_length-1
            width_error = width*8/target_width-1
            if max(abs(length_error), abs(width_error)) > APPEARANCE_SIZE_MARGIN:
                continue
            aspect_error = (length/width)/(target_length/target_width)-1
            # Rank dimensional compatibility only; this is not a visual quality score.
            cost = 4*aspect_error**2 + length_error**2 + width_error**2
            candidates.append(dict(length_studs=length, width_studs=width,
                dimension_cost=cost, length_error_percent=length_error*100,
                width_error_percent=width_error*100))
    return sorted(candidates, key=lambda c: (c["dimension_cost"], c["length_studs"], c["width_studs"]))


def plan_design(spec, scale=None, length_studs=None, width_studs=None, scale_mode="exact"):
    validate_spec(spec)
    if scale_mode not in SCALE_MODES:
        raise ValueError(f"Unknown scale mode: {scale_mode}")
    if scale_mode == "auto":
        return _automatic_plan(spec, scale, length_studs, width_studs)
    requested_grid = dict(length_studs=length_studs, width_studs=width_studs)
    if scale is not None and length_studs is not None and scale_mode == "exact":
        raise ValueError("Choose --scale or --length-studs, not both.")
    explicit_length = length_studs
    if scale is not None:
        policy = requirements_for_scale(scale)
        denominator = int(scale.split(":")[1])
        length_studs = math.floor(measurement(spec, "length") / denominator / 8 + .5)
        selection = "explicit_scale"
    else:
        length_studs = 24 if length_studs is None else length_studs
        if isinstance(length_studs, bool) or not isinstance(length_studs, int) or length_studs <= 0:
            raise ValueError("length_studs must be a positive integer.")
        denominator = measurement(spec, "length") / (length_studs * 8)
        nearest = min(SCALES, key=lambda candidate: abs(math.log(denominator / int(candidate.split(":")[1]))))
        policy = requirements_for_scale(nearest)
        selection = "nearest_policy_for_custom_length"
    target_width = measurement(spec, "width") / denominator / 8
    if width_studs is None:
        width_studs = max(4, 2 * math.floor(target_width / 2 + .5))
    if isinstance(width_studs, bool) or not isinstance(width_studs, int) or width_studs <= 0:
        raise ValueError("width_studs must be a positive integer.")
    reasons = []
    from .wedge import applies
    candidates = []
    if scale_mode == "appearance" and scale is not None and policy["scale"] == "1:24":
        candidates = _appearance_grids(spec, denominator, applies(spec), requested_grid["width_studs"])
        if explicit_length is not None:
            if type(explicit_length) is not int or explicit_length <= 0:
                raise ValueError("length_studs must be a positive integer.")
            candidates = [c for c in candidates if c["length_studs"] == explicit_length]
        if candidates:
            length_studs, width_studs = (candidates[0][key] for key in ("length_studs", "width_studs"))
            selection = "appearance_grid_near_requested_scale"
        else:
            reasons.append("No supported native-part grid inside the approximate size range.")
    compact_wedge = applies(spec) and policy["scale"] == "1:24" and length_studs == 22
    if not compact_wedge and not RECIPE_LENGTH_RANGE[0] <= length_studs <= RECIPE_LENGTH_RANGE[1]:
        reasons.append(f"Current sports-car recipe supports {RECIPE_LENGTH_RANGE[0]}..{RECIPE_LENGTH_RANGE[1]} studs; needs {length_studs}.")
    if width_studs not in RECIPE_WIDTHS:
        reasons.append(f"Current sports-car recipe has 8/10/12-stud cores; planned width is {width_studs}.")
    if policy["scale"] != "1:24":
        reasons.append(f"{policy['scale']} requires a separate wheel, glazing and chassis recipe; not implemented.")
    fields = [measurement_source(spec, field) for field in policy["required_measurements"]]
    plan = {"policy": policy, "selection": selection, "requested_scale": scale,
            "target_scale_denominator": denominator, "vehicle_spec_fingerprint": spec_fingerprint(spec),
            "grid": {"length_studs": length_studs, "width_studs": width_studs,
                     "target_length_mm": measurement(spec, "length") / denominator,
                     "target_width_mm": target_width * 8,
                     "effective_core_length_scale_denominator": measurement(spec, "length") / (length_studs * 8)},
            "physical_data": fields,
            "missing_measurements": [item["field"] for item in fields if item["status"] == "missing"],
            "estimated_measurements": [item["field"] for item in fields if item["status"] == "estimated"],
            "generation": {"draft_recipe_available": not reasons, "blockers": reasons,
                           "delivery_ready": False},
            "notes": ["Grid dimensions are nominal core dimensions, not native exterior bounds.",
                      "Reference views are an evidence plan; single-image TripoSR does not consume this view set.",
                      "Sourced specifications are not independent physical verification."]}
    if scale_mode == "appearance":
        plan["scale_intent"] = dict(mode=scale_mode, requested_grid=requested_grid,
            size_margin_percent=APPEARANCE_SIZE_MARGIN*100,
            candidates=candidates, standard_part_scaling_allowed=False,
            fitting_scale_denominator=measurement(spec, "length")/(length_studs*8),
            priorities=["vehicle silhouette", "native glazing and lamp fit", "surface continuity", "approximate size"],
            ranking="Dimensional compatibility shortlist; appearance requires rendered comparison.")
    return plan


def validate_plan(plan, spec, length, width, scale):
    intent = plan.get("scale_intent")
    if intent:
        expected = plan_design(spec, scale, **intent["requested_grid"], scale_mode=intent["mode"])
    else:
        expected = plan_design(spec, scale, None if scale is not None else length, width)
    if (plan != expected or plan["grid"]["length_studs"] != length
            or plan["grid"]["width_studs"] != width):
        raise ValueError("Requirements snapshot does not match the vehicle, scale, grid or policy version.")


def assess_requirements(plan, dimensions, step_counts):
    policy = plan["policy"]
    checks = []
    for item in plan["physical_data"]:
        field = item["field"]
        result = dimensions["dimensions"].get(field) if dimensions else None
        if field in policy["angle_tolerances_degrees"]:
            error = dimensions.get("windscreen_angle_error_degrees") if dimensions and field.startswith("windscreen") else None
            tolerance = policy["angle_tolerances_degrees"][field]
            basis = "native_part_angle" if error is not None else "not_measured"
        else:
            error = result["error_percent"] if result else None
            tolerance = policy["dimension_tolerances_percent"].get(field)
            basis = "nominal_core" if field in ("length", "width") else "nominal_part_family"
        if item["status"] != "sourced":
            status = "missing_data" if item["status"] == "missing" else "estimated_data"
        elif plan.get("scale_intent", {}).get("mode") == "auto":
            status = "reference_only" if error is not None else "not_measured"
        elif error is None or tolerance is None:
            status = "not_measured"
        elif abs(error) > tolerance:
            status = "out_of_tolerance"
        else:
            status = "within_nominal_tolerance"
        checks.append({"field": field, "status": status, "error": error, "tolerance": tolerance,
                       "unit": "deg" if field in policy["angle_tolerances_degrees"] else "%",
                       "basis": basis, "native_measurement_verified": False})
    max_parts = max(step_counts, default=0)
    return {"policy_version": policy["version"], "scale": policy["scale"],
            "scale_mode": plan.get("scale_intent", {}).get("mode", "exact"),
            "dimension_checks_are_reference": bool(plan.get("scale_intent")),
            "dimension_checks": checks,
            "mechanism_checks": [{"mechanism": key, "required_instances": count,
                                  "verified_instances": 0, "status": "unverified"}
                                 for key, count in policy["required_mechanisms"].items()],
            "reference_checks": [{"view": view, "status": "unverified"} for view in policy["reference_views"]],
            "evidence_checks": [{"evidence": evidence, "status": "unverified"} for evidence in EVIDENCE],
            "step_check": {"maximum_parts": max_parts, "limit": policy["max_parts_per_step"],
                           "status": "passed" if max_parts <= policy["max_parts_per_step"] else "failed",
                           "assembly_order_verified": False},
            "status": "draft", "delivery_accepted": False,
            "limitations": ["Nominal dimensions do not certify native geometry, motion, appearance or physical assembly."]}
