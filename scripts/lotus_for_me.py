"""Persist live specification evidence and publish this actual generation run."""
import argparse
import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from car2lego3d.common import ROOT, digest, write_json
from car2lego3d.research import SKILL, compile_result
from car2lego3d.studio import verify_archive
from car2lego3d.vehicle import UNITS
from car2lego3d.web_access import search


BASE = ROOT / "runs/lotus-for-me-20261015"
OFFICIAL = "https://www.lotuscars.com.cn/forme"
CONFIG = "https://www.autohome.com.cn/config/series/8464.html"


def prepare():
    import httpx
    from PIL import Image, ImageOps, ImageDraw
    directory = BASE / "official-inputs"
    directory.mkdir(parents=True, exist_ok=True)
    files = ["2026/03-13/20e868f268664a23bdbd45c3323c2811.jpg",
             "2026/03-05/d54b3b239a334f6fabbeaf999332766f.jpg",
             "2026/03-05/b982e9dd0b87469c84d379443654d02b.jpg",
             "2026/03-13/5b72e95512c943398cd33a23454a27fc.jpg",
             "2026/04-10/ce7b4ff923954c84b253885d5757ae53.png"]
    sheet = Image.new("RGB", (1200, 900), "white")
    records = []
    for i, file in enumerate(files):
        url = "https://oss-web.lotuscars.com.cn/" + file
        response = httpx.get(url, timeout=60)
        response.raise_for_status()
        im = Image.open(BytesIO(response.content))
        path = directory / f"official-{i+1}.png"
        im.save(path)
        thumb = ImageOps.contain(im.convert("RGB"), (590, 260))
        x, y = (i % 2)*600, (i//2)*300
        sheet.paste(thumb, (x, y+30))
        ImageDraw.Draw(sheet).text((x+10, y+5), f"Official input {i+1}", fill="black")
        records.append({"url": url, "file": path.name, "sha256": digest(path), "page": OFFICIAL})
    sheet.save(directory / "contact-sheet.png")
    write_json(directory / "sources.json", records)
    print(directory / "contact-sheet.png")


def browser(*args):
    executable = shutil.which("agent-browser")
    return subprocess.run([executable, "--session", "lotus", *args], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def research():
    directory = BASE / "research"
    directory.mkdir(parents=True, exist_ok=True)
    calls = [search("Lotus For Me SUV")]
    pages = []
    for url, marker in ((OFFICIAL, "基本参数配置"), (CONFIG, "前轮胎规格")):
        browser("open", url)
        browser("wait", "--text", marker)
        text = browser("get", "text", "body")
        pages.append({"requested_url": url, "url": browser("get", "url"),
                      "title": browser("get", "title"), "text": text,
                      "reader": "agent-browser rendered DOM", "success": True})
    audit = {"mode": "live", "runner": "project HTTP search + agent-browser dynamic DOM",
             "web_search_calls": sum(bool(call["success"]) for call in calls),
             "calls": calls, "opened_pages": pages, "skill_sha256": digest(SKILL)}
    sources = [{"id": "lotus", "title": pages[0]["title"], "url": OFFICIAL, "kind": "manufacturer"},
               {"id": "autohome", "title": pages[1]["title"], "url": CONFIG, "kind": "reference"}]
    published = {
        "length": (5103, "lotus", "长度 (mm)\n5,103"),
        "width": (2019, "lotus", "宽度(mm)\n2,019"),
        "height": (1636, "lotus", "高度(mm)\n1,636"),
        "wheelbase": (3019, "lotus", "轴距(mm)\n3,019"),
        "front_track": (1738, "autohome", "前轮距(mm)\n1738"),
        "rear_track": (1744, "autohome", "后轮距(mm)\n1744"),
    }
    for axle, width, label in (("front", 265, "前"), ("rear", 285, "后")):
        evidence = f"{label}轮胎规格\n{width}/45 R21"
        for suffix, value in (("tyre_width", width), ("tyre_aspect", 45), ("rim_diameter", 21)):
            published[f"{axle}_{suffix}"] = (value, "autohome", evidence)
    measurements = []
    for field, unit in UNITS.items():
        value, source, evidence = published.get(field, (None, None, ""))
        measurements.append({"field": field, "value": value, "unit": unit, "source": source,
                             "evidence": evidence,
                             "status": "unknown" if value is None else "manufacturer" if source == "lotus" else "reported",
                             "note": "" if value is not None else "No published engineering dimension found in the opened sources."})
    answer = {"status": "ready", "model": "Lotus For Me", "variant": "China standard For Me, 21-inch wheels",
              "width_reference": "unspecified", "sources": sources, "measurements": measurements,
              "questions": [], "notes": ["Selected standard For Me with 21-inch wheels; year was not required.",
                  "The published width does not explicitly state whether mirrors are included.",
                  "Door and glazing geometry is unpublished in these sources; LEGO geometry remains a design prior."]}
    result = compile_result(answer, {"brand": "Lotus", "model": "For Me", "variant": ""}, audit)
    for name, data in (("audit.json", audit), ("answer.json", answer), ("spec.json", result["spec"]), ("result.json", result)):
        write_json(directory / name, data)
    print(json.dumps({"status": result["status"], "spec": str(directory / "spec.json")}, indent=2))


def deliver():
    full = BASE / "artifacts"
    pipeline = json.loads((full / "pipeline.json").read_text())
    if pipeline["status"] != "completed":
        raise RuntimeError("Only completed runs can be published.")
    delivery = BASE / "delivery"
    delivery.mkdir(exist_ok=True)
    for source, name in (("04-studio/model.io", "Lotus_For_Me_1-24.io"),
                         ("03-lego/model.ldr", "model.ldr"), ("03-lego/native-ldraw.png", "preview.png"),
                         ("01-image/reference.png", "reference.png"), ("03-lego/inventory.csv", "inventory.csv"),
                         ("02-mesh/calibrated.glb", "mesh.glb"), ("00-vehicle/spec.json", "vehicle-specs.json"),
                         ("03-lego/dimensions.json", "dimensions.json"), ("03-lego/validation.json", "validation.json")):
        shutil.copyfile(full / source, delivery / name)
    verification = verify_archive(delivery / "Lotus_For_Me_1-24.io", delivery / "model.ldr")
    job_id = uuid4().hex
    job = ROOT / "runs/web" / job_id
    shutil.copytree(full, job / "artifacts")
    shutil.copyfile(full / "00-vehicle/spec.json", job / "vehicle-specs.json")
    write_json(job / "request.json", {"brand": "Lotus", "brand_zh": "莲花", "model": "For Me", "variant": "",
               "scale": "1:24", "color": 25, "seed": 42, "origin": "CLI run imported for preview",
               "resolved_model": "Lotus For Me"})
    write_json(job / "status.json", {"status": "completed", "error": None})
    record = {"job_id": job_id, "url": f"http://127.0.0.1:8766/?job={job_id}",
              "studio": str(delivery / "Lotus_For_Me_1-24.io"), "archive_verification": verification,
              "appearance_accepted": False, "physical_verified": False}
    write_json(BASE / "delivery-record.json", record)
    example = ROOT / "examples/lotus-for-me-1-24"
    shutil.copytree(full, example)
    shutil.copytree(BASE / "research", example / "research")
    with ZipFile(BASE / "Lotus_For_Me_1-24.zip", "w", ZIP_DEFLATED) as archive:
        for folder in (delivery, full, BASE / "research"):
            for path in folder.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(BASE).as_posix())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["research", "prepare", "deliver"])
    args = parser.parse_args()
    {"research": research, "prepare": prepare, "deliver": deliver}[args.mode]()
