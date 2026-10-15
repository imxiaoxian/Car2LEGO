"""Publish a completed local run to the desktop UI and a portable draft bundle."""
import argparse
import json
from pathlib import Path
import shutil
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from car2lego3d.common import ROOT, write_json
from car2lego3d.studio import verify_archive
from car2lego3d.web import catalog_brands


def publish(artifacts, output, brand, model, scale, color, port):
    artifacts, output = Path(artifacts).resolve(), Path(output).resolve()
    pipeline = json.loads((artifacts / "pipeline.json").read_text(encoding="utf-8"))
    if pipeline["status"] != "completed":
        raise ValueError("Only completed pipelines can be published as drafts.")
    verified = verify_archive(artifacts / "04-studio/model.io", artifacts / "03-lego/model.ldr")
    output.mkdir(parents=True, exist_ok=False)
    job_id = uuid4().hex
    job = ROOT / "runs/web" / job_id
    shutil.copytree(artifacts, job / "artifacts")
    shutil.copyfile(artifacts / "00-vehicle/spec.json", job / "vehicle-specs.json")
    brand_zh = next((item["name_zh"] for item in catalog_brands() if item["name"] == brand), brand)
    write_json(job / "request.json", {"brand": brand, "model": model, "variant": "", "scale": scale,
               "brand_zh": brand_zh,
               "color": color, "seed": pipeline["inputs"]["seed"], "resolved_model": f"{brand} {model}",
               "origin": "CLI multiview run imported for draft review"})
    write_json(job / "status.json", {"status": "completed", "error": None})
    shutil.copyfile(artifacts / "04-studio/model.io", output / "model.io")
    shutil.copyfile(artifacts / "03-lego/native-ldraw.png", output / "preview.png")
    record = {"job_id": job_id, "url": f"http://127.0.0.1:{port}/?job={job_id}",
              "source_run": str(artifacts), "archive_verification": verified,
              "appearance_accepted": False, "physical_verified": False, "studio_gui_verified": False}
    write_json(output / "delivery-record.json", record)
    with ZipFile(output / "draft-bundle.zip", "w", ZIP_DEFLATED) as archive:
        for file in artifacts.rglob("*"):
            if file.is_file():
                archive.write(file, "artifacts/" + file.relative_to(artifacts).as_posix())
        archive.write(output / "delivery-record.json", "delivery-record.json")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--scale", required=True)
    parser.add_argument("--color", type=int, required=True)
    parser.add_argument("--port", type=int, default=8766)
    print(json.dumps(publish(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
