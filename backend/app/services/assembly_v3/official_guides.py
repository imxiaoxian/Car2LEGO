"""Auditable official build references, independent of synthetic vehicle images.

An instruction page is a design precedent, not an accepted assembly for a new
scale. Local files are optional; sources stay useful when downloads are absent.
"""

import base64
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

GUIDES = [
    {"set_num": "10248", "name": "Ferrari F40", "make": "Ferrari", "model": "F40",
     "product_url": "https://www.lego.com/en-us/product/ferrari-f40-10248",
     "instructions_url": "https://www.lego.com/en-us/service/building-instructions/10248",
     "pdf_url": "https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6205518.pdf",
     "modules": {"cockpit": [47, 48, 49, 50], "doors": [55, 56, 57, 58, 61, 62, 63, 64],
                 "engine": [66, 67, 68, 69, 70, 71, 72, 73, 74, 75],
                 "engine_cover": [80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 101]},
     "learning_goals": ["independent subassemblies", "bucket seats on a Technic frame", "door hinge and inner panel",
                        "brick-built V8 and intake detail", "rear hatch and axle mounting"],
     "scope": "Same vehicle design precedent; adapt independently to each scale. No steering/suspension acceptance inferred."},
    {"set_num": "10295", "name": "Porsche 911", "make": "Porsche", "model": "911",
     "product_url": "https://www.lego.com/en-us/product/porsche-911-10295",
     "instructions_url": "https://www.lego.com/en-us/service/building-instructions/10295",
     "pdf_url": "https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6590143.pdf",
     "modules": {}, "learning_goals": ["steering", "tilting seats", "engine and cabin packaging"],
     "scope": "Cross-vehicle mechanism precedent; page ranges and local assemblies not yet reviewed."},
    {"set_num": "42143", "name": "Ferrari Daytona SP3", "make": "Ferrari", "model": "Daytona SP3",
     "product_url": "https://www.lego.com/en-us/product/ferrari-daytona-sp3-42143",
     "instructions_url": "https://www.lego.com/en-us/service/building-instructions/42143",
     "pdf_url": "https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6590123.pdf",
     "modules": {}, "learning_goals": ["Technic steering", "shock absorber packaging", "engine and structural frame"],
     "scope": "Cross-vehicle mechanism precedent. Butterfly doors differ from F40 conventional doors; do not substitute them."},
]


def guide_records(storage: Path | str, request: dict) -> list[dict]:
    root = Path(storage) / "official_references"
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    records = []
    for guide in GUIDES:
        same = (request.get("make", "").casefold(), request.get("model", "").casefold()) == (guide["make"].casefold(), guide["model"].casefold())
        if not same and request.get("scale") not in ("1:16", "1:12"):
            continue
        local = manifest.get(guide["set_num"], {})
        records.append(guide | {"same_vehicle": same, "source_kind": "official_lego_instructions",
            "synthetic": False, "local_pdf": bool(local.get("pdf") and (root / local["pdf"]).is_file()), "local_pages": local.get("pages", []),
            "accepted_for_target_scale": False})
    return records


def guide_content(storage: Path | str, request: dict, max_pages: int = 4) -> list[dict]:
    """Include selected genuine instruction pages with provenance and bounded payload."""
    root = (Path(storage) / "official_references").resolve()
    records = guide_records(storage, request)
    content = [{"type": "text", "text": "Official LEGO build precedents (separate from generated real-car references). "
        "Use connection techniques and subassembly design; never scale parts or assume the source assembly is verified at the target ratio. "
        "These sources do not prove target model connectivity, clearance or physical durability.\n" + json.dumps(records)}]
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    count = 0
    for record in records:
        if not record["same_vehicle"]:
            continue
        local = manifest.get(record["set_num"], {})
        for image in local.get("representative_pages", []):
            if count >= max_pages:
                break
            path = (root / image["path"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Invalid official reference path")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != image["sha256"]:
                continue
            with Image.open(path) as source:
                source = source.convert("RGB"); source.thumbnail((1024, 1024))
                buffer = io.BytesIO(); source.save(buffer, "JPEG", quality=88)
            content.extend([{"type": "text", "text": f"Official LEGO {record['set_num']} PDF page {image['page']}, module {image['module']}. Source: {record['pdf_url']}"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode(), "detail": "high"}}])
            count += 1
    return content
