"""Publish a completed CLI candidate as a new draft without changing older jobs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from uuid import uuid4

from car2lego3d.common import ROOT, digest, write_json
from car2lego3d.multiview import load_views
from car2lego3d.studio import export_studio, verify_archive
from car2lego3d.vehicle import load_spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--views", type=Path, required=True)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--research-audit", type=Path)
    parser.add_argument("--frontend-port", type=int, default=8768)
    args = parser.parse_args()
    load_views(args.views / "views.json")
    spec = load_spec(args.spec)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if not (args.candidate / "03-lego/model.ldr").is_file() or not (args.mesh / "calibrated.glb").is_file():
        raise ValueError("Candidate assembly and calibrated reconstruction are required")
    id = uuid4().hex
    directory = ROOT / "runs/web" / id
    artifacts = directory / "artifacts"
    shutil.copytree(args.candidate / "03-lego", artifacts / "03-lego")
    shutil.copytree(args.views, artifacts / "01-image")
    shutil.copytree(args.mesh, artifacts / "02-mesh")
    if (args.candidate / "05-presentation").exists():
        shutil.copytree(args.candidate / "05-presentation", artifacts / "05-presentation")
    preview = artifacts / "05-presentation/render_front.png"
    studio = export_studio(artifacts / "03-lego/model.ldr", artifacts / "04-studio", preview if preview.exists() else None)
    verify_archive(studio, artifacts / "03-lego/model.ldr")
    write_json(directory / "vehicle-specs.json", spec)
    if args.research_audit:
        audit = json.loads(args.research_audit.read_text(encoding="utf-8"))
        write_json(directory / "research-audit.json", audit.get("audit", audit))
    write_json(directory / "request.json", request | dict(created_at=datetime.now(timezone.utc).isoformat(),
               origin="Imported CLI candidate; appearance and physical build not accepted"))
    write_json(directory / "desktop.json", dict(artifacts="artifacts", workflow="multiview_v1"))
    write_json(directory / "checkpoints.json", {stage: digest(artifacts / file) for stage,file in {
        "reference_images":"01-image/views.json", "reconstruction":"02-mesh/calibrated.glb",
        "assembly":"03-lego/model.ldr", "exporting":"04-studio/model.io"}.items()})
    write_json(directory / "status.json", dict(status="draft", stage="draft", progress=100, error=None))
    print(json.dumps(dict(id=id, url=f"http://127.0.0.1:{args.frontend_port}/designs/{id}", studio=str(studio))))


if __name__ == "__main__":
    main()
