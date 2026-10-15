"""Run the original Car2LEGO GPT service with isolated output and no source writes."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from dotenv import dotenv_values


SINGLE_VEHICLE_VIEW = (
    "ONE single complete car in a front-left three-quarter view, seen from slightly above, "
    "camera elevation about 15 degrees, long focal length to limit perspective distortion. "
    "The front points toward the left of the image; show its front fascia and left side. "
    "All four wheel positions, roof, bumpers and mirrors must remain within frame. "
    "Use a seamless white background with a minimal contact shadow. The car occupies "
    "about 80 percent of the image width. This is the identity anchor for four-view generation: "
    "output exactly one car, no contact sheet, panels, alternate angles or duplicated cars. "
    "If a source photo is present, preserve its exact vehicle identity, door count, lamp shapes, "
    "wheel style, roofline and paint. Reconstruct only the requested camera view."
)

VIEW_SHOTS = {"front": "front", "rear": "back", "body": "left", "wheels": "right"}


def shot_instructions(view):
    directions = {
        "front": "exact straight front elevation, looking at the front bumper",
        "back": "exact straight rear elevation, looking at the rear bumper",
        "left": "exact left side elevation, front of the car toward image LEFT",
        "right": "exact right side elevation, front of the car toward image RIGHT",
    }
    return (
        f"ONE complete car in {directions[view]}. Orthographic camera at wheel hub height, "
        "zero elevation, no perspective or three-quarter view. Keep wheels straight, doors and "
        "all panels closed. Include the whole car, roof, tyres, mirrors and bumpers, with a "
        "15 percent clean margin. Plain white background, uniform studio light, minimal shadow. "
        "This image is one labelled input of a four-view 3D reconstruction. Preserve EXACTLY "
        "the same vehicle identity, paint, door count, wheel style and body proportions as the "
        "overview and source photo. Output one view only; no panels, contact sheet, close-ups, "
        "captions or measurement annotations. Do not mirror the left image to create the right side."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    source = args.source_root.resolve()
    state = json.loads(args.request.read_text(encoding="utf-8"))
    storage = Path(state["storage_path"]).resolve()
    if storage.is_relative_to(source) or state["design_id"] != "car2lego":
        raise ValueError("All generated files must stay outside the source project.")
    inherited = dotenv_values(source / "backend/.env")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_IMAGE_MODEL",
                "IMAGE_QUALITY", "IMAGE_SIZE", "IMAGE_TIMEOUT"):
        if inherited.get(key) and not os.environ.get(key):
            os.environ[key] = inherited[key]
    os.environ["STORAGE_PATH"] = str(storage)
    sys.path.insert(0, str(source / "backend"))
    from app.services import reference_images as service
    from app.services.assembly_v3.jobs import atomic_json
    if not service.settings.openai_image_model.startswith("gpt-image-"):
        raise ValueError("The source configuration must select a GPT Image model.")
    # Change only the shot instructions in this process; source files remain read-only.
    service.REFERENCE_VIEWS["overview"] = SINGLE_VEHICLE_VIEW
    service.ALL_REFERENCE_VIEWS["overview"] = SINGLE_VEHICLE_VIEW
    for slot, view in VIEW_SHOTS.items():
        instructions = shot_instructions(view)
        service.REFERENCE_VIEWS[slot] = instructions
        service.ALL_REFERENCE_VIEWS[slot] = instructions
    state["requested_reference_shots"] = [
        {"view": slot, "focus": f"A single complete orthographic {view} elevation of the same car. Four-view reconstruction contract v1.", "angles": [view],
         "reason": "Labelled multiview reconstruction input"}
        for slot, view in VIEW_SHOTS.items()
    ]
    calls = []
    state["consume_call"] = lambda kind: calls.append(kind)
    state["checkpoint_progress"] = lambda stage, percent: print(json.dumps({"stage": stage, "progress": percent}), flush=True)
    try:
        result = asyncio.run(service.ReferenceImageService().generate(state, only={"overview", *VIEW_SHOTS}))
    except Exception as error:
        print(json.dumps(service.failure_details(error, "reference", attempt=1)), flush=True)
        return 1
    atomic_json(storage / "car2lego/service-record.json", {
        "model": service.settings.openai_image_model, "quality": service.settings.image_quality,
        "size": service.settings.image_size, "calls": calls, "reference_images": result["reference_images"],
        "source_modified": False, "reconstruction_views": VIEW_SHOTS,
        "view_overrides": {view: shot_instructions(view) for view in VIEW_SHOTS.values()}})
    print(json.dumps({"model": service.settings.openai_image_model, "calls": calls, "status": "completed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
