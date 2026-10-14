"""Convert manually annotated orthographic side-view segments to sourced priors."""
import copy
import math
from pathlib import Path

import numpy as np
from PIL import Image

from .common import digest
from .vehicle import measurement, validate_spec


METHODS = {"door_length": "horizontal", "door_panel_height": "vertical",
           "door_front_x": "horizontal", "windscreen_bottom_x": "horizontal",
           "front_overhang": "horizontal", "rear_overhang": "horizontal",
           "windscreen_slant_height": "distance", "windscreen_angle_to_horizontal": "angle"}


def measure_side_view(spec, annotations, image_path):
    validate_spec(spec)
    if annotations.get("view") != "orthographic_side":
        raise ValueError("Only an explicitly declared orthographic_side reference is supported.")
    reference = annotations.get("reference_measurement")
    if reference not in ("wheelbase", "length"):
        raise ValueError("Reference measurement must be wheelbase or length.")
    uncertainty = annotations.get("endpoint_uncertainty_px")
    if (isinstance(uncertainty, bool) or not isinstance(uncertainty, (int, float))
            or not math.isfinite(uncertainty) or uncertainty <= 0):
        raise ValueError("Declare a positive endpoint_uncertainty_px.")
    image_path = Path(image_path)
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        image_width, image_height = image.size

    def segment(value):
        points = np.asarray(value, dtype=float)
        if (points.shape != (2, 2) or not np.isfinite(points).all() or np.any(points < 0)
                or np.any(points[:, 0] >= image_width) or np.any(points[:, 1] >= image_height)):
            raise ValueError("Every segment requires two finite pixel points inside the image.")
        vector = points[1] - points[0]
        if np.linalg.norm(vector) < 1:
            raise ValueError("Measurement segment is too short.")
        return vector

    reference_vector = segment(annotations.get("reference_points"))
    pixels = float(np.linalg.norm(reference_vector))
    horizontal = reference_vector / pixels
    vertical = np.array([-horizontal[1], horizontal[0]])
    mm_per_pixel = measurement(spec, reference) / pixels
    result = copy.deepcopy(spec)
    source_id = "annotated_side_view"
    if source_id in result["sources"]:
        raise ValueError("This spec already contains annotated_side_view; use a fresh input spec.")
    result["sources"][source_id] = {"title": annotations.get("title") or "Manually annotated side-view reference",
            "file": image_path.name, "sha256": digest(image_path),
            "view": "orthographic_side", "reference_measurement": reference,
            "annotations": annotations, "mm_per_pixel": mm_per_pixel,
            "notes": "Orthographic declaration is supplied by the annotator; camera projection is not verified."}
    segments = annotations.get("segments", {})
    if not segments or set(segments) - set(METHODS):
        raise ValueError("Provide supported side-view segments.")
    for name, points in segments.items():
        vector = segment(points)
        dx, dz = abs(float(vector @ horizontal)), abs(float(vector @ vertical))
        method = METHODS[name]
        if method == "angle":
            value = math.degrees(math.atan2(dz, dx))
            tolerance = math.degrees(math.atan2(2 * uncertainty, np.linalg.norm(vector)))
            unit = "deg"
        else:
            extent = {"horizontal": dx, "vertical": dz, "distance": float(np.linalg.norm(vector))}[method]
            value, unit = extent * mm_per_pixel, "mm"
            tolerance = 2 * uncertainty * mm_per_pixel * (1 + extent / pixels)
        result["measurements"][name] = {"value": value, "unit": unit, "status": "estimated",
                "source": source_id, "estimated_annotation_error": tolerance,
                "notes": "Annotation error estimate excludes drawing/projection error and source-dimension uncertainty."}
    return validate_spec(result)
