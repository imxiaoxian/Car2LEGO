"""Read-only subprocess bridge to Car2LEGO's actual reference image service."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dotenv import dotenv_values
from PIL import Image

from .common import ROOT, digest, stage, write_json
from .vehicle import load_spec, spec_record


def configuration():
    local = dotenv_values(ROOT / ".env")
    def value(name, default=""):
        return os.environ.get(name) or local.get(name) or default
    source = Path(value("CAR2LEGO_SOURCE_ROOT", "D:/lego")).resolve()
    python = value("CAR2LEGO_SOURCE_PYTHON", sys.executable)
    return source, python


def generate(prompt, directory, vehicle_spec=None, reference_image=None):
    directory = Path(directory).resolve()
    source, python = configuration()
    upstream = source / "backend/app/services/reference_images.py"
    if not upstream.is_file():
        raise RuntimeError("Car2LEGO reference service missing. Configure CAR2LEGO_SOURCE_ROOT in .env.")
    if directory.is_relative_to(source):
        raise ValueError("Reference outputs must be outside the original Car2LEGO project.")
    spec = load_spec(vehicle_spec) if vehicle_spec else None
    make, _, model = (spec["model"] if spec else prompt).partition(" ")
    state = {"design_id": "car2lego", "storage_path": str(directory),
             "make": make, "model": model or make, "year": None,
             "vehicle_features": {"variant": spec["variant"]} if spec else {},
             "custom_request": prompt, "mod_ids": [], "physical_specifications": spec or {}}
    if reference_image:
        anchor = Path(reference_image).resolve()
        with Image.open(anchor) as image:
            image.verify()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "identity-anchor.png"
        with Image.open(anchor) as image:
            image.save(target, format="PNG")
        state["source_image_path"] = str(target)
    inputs = {"prompt": prompt, "provider": "Car2LEGO ReferenceImageService", "source_sha256": digest(upstream),
              "views": ["front", "back", "left", "right"], "source_root": str(source)}
    with stage(directory, "image", inputs) as record:
        if spec:
            record.update(vehicle_spec=spec_record(vehicle_spec), specifications=spec)
        if reference_image:
            record["reference_image"] = {"file": "identity-anchor.png", "sha256": digest(target)}
        request = directory / "reference-request.json"
        write_json(request, state)
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([python, "-B", str(ROOT / "scripts/car2lego_reference_worker.py"),
                                 "--source-root", str(source), "--request", str(request)],
                                env=environment, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (directory / "reference-service.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError("Car2LEGO GPT reference generation failed; inspect reference-service.log. No local-model fallback.")
        manifest = json.loads((directory / "car2lego/references/manifest.json").read_text(encoding="utf-8"))
        overview = next(item for item in manifest["images"] if item["view"] == "overview")
        if not overview["model"].startswith("gpt-image-"):
            raise RuntimeError("The reused service did not report a GPT Image model.")
        generated = directory / "car2lego" / overview["path"]
        if digest(generated) != overview["sha256"]:
            raise ValueError("Generated reference hash mismatch.")
        output = directory / "reference.png"
        shutil.copyfile(generated, output)
        views = {}
        for slot, view in {"front": "front", "rear": "back", "body": "left", "wheels": "right"}.items():
            item = next(item for item in manifest["images"] if item["view"] == slot)
            origin = directory / "car2lego" / item["path"]
            if not item["model"].startswith("gpt-image-") or digest(origin) != item["sha256"]:
                raise ValueError(f"Invalid GPT multiview provenance for {view}.")
            destination = directory / f"{view}.png"
            shutil.copyfile(origin, destination)
            views[view] = {"file": destination.name, "sha256": digest(destination), "model": item["model"]}
        view_manifest = directory / "views.json"
        write_json(view_manifest, {"schema_version": 1, "views": views,
                   "camera_contract": "orthographic elevations at wheel hub height; front/back/left/right",
                   "identity_anchor": "reference.png", "brief": manifest["brief"],
                   "synthetic": True, "cross_view_consistency_verified": False})
        with Image.open(output) as image:
            size = list(image.size)
        record.update(model=overview["model"], output=output.name, sha256=digest(output), size=size,
                      synthetic=True, physical_proportions_guaranteed=False,
                      generation_logic="Direct call to unmodified Car2LEGO ReferenceImageService.generate",
                      appearance_accepted=False, seed_supported=False,
                      reconstruction_input="four labelled views", views=views,
                      outputs={"reference.png": digest(output), "views.json": digest(view_manifest),
                               "car2lego/references/manifest.json": digest(directory / "car2lego/references/manifest.json")})
    return view_manifest
