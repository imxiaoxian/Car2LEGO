"""Render and independently count one exported assembly through ldraw-mcp."""

import argparse
import asyncio
import base64
from collections import Counter
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from PIL import Image


def _structured(result):
    data = getattr(result, "structured_content", None)
    if data is not None:
        return data
    for block in result.content:
        if block.type == "text":
            try:
                return json.loads(block.text)
            except (TypeError, json.JSONDecodeError):
                return {"result": block.text}
    return {}


def _write_images(result, output: Path, stem: str, azimuths: list[int] | None = None) -> list[str]:
    paths = []
    image_blocks = [block for block in result.content if block.type == "image"]
    for block_index, block in enumerate(image_blocks):
        image_bytes = base64.b64decode(block.data)
        with Image.open(BytesIO(image_bytes)) as source:
            angles = azimuths if len(image_blocks) == 1 and azimuths else None
            frame_count = len(angles) if angles else 1
            for frame_index in range(frame_count):
                left = source.width * frame_index // frame_count
                right = source.width * (frame_index + 1) // frame_count
                frame = source.crop((left, 0, right, source.height)) if frame_count > 1 else source.copy()
                if angles:
                    angle = angles[frame_index]
                    suffix = f"azimuth-{'m' if angle < 0 else 'p'}{abs(angle)}"
                else:
                    suffix = f"{block_index:02d}"
                path = output / f"{stem}-{suffix}.png"
                frame.save(path, format="PNG", optimize=True)
                paths.append(path.name)
    return paths


def _part_line(part: dict) -> str:
    transform = part["transform"]
    values = [*transform["position"], *transform["rotation"]]
    return f"1 {part['color_id']} " + " ".join(f"{value:.9g}" for value in values) + f" {part['part_num']}"


def _detail_groups(scene: dict) -> list[tuple[str, list[dict]]]:
    parts = scene.get("parts", [])
    preferred = ("engine", "cockpit", "seats", "doors", "front_hood", "engine_cover", "details")
    groups = []
    for module in preferred:
        module_parts = [part for part in parts if part["module"] == module]
        if module == "seats" and not module_parts:
            module_parts = [part for part in parts if part["module"] == "cockpit"
                            and part.get("feature") in {"seat", "seat_mount", "bucket_seat"}]
        if module_parts:
            groups.append((module, module_parts))
    return groups


def _compare_bom(scene: dict, bom: dict) -> dict:
    actual = Counter({(str(row["part"]).lower(), int(row["color_code"])): int(row["quantity"])
                      for row in bom.get("rows", [])})
    expected = Counter((part["part_num"].lower(), int(part["color_id"])) for part in scene["parts"])
    matched = actual == expected and int(bom.get("total_parts", -1)) == len(scene["parts"])
    missing_parts = list(bom.get("parts_not_in_library", []))
    unknown_colors = list(bom.get("unknown_color_codes", []))
    return {"status": "passed" if matched and not missing_parts and not unknown_colors else "failed",
            "quantities_and_colors_match": matched, "expected_total": len(scene["parts"]),
            "actual_total": bom.get("total_parts"), "missing_parts": missing_parts,
            "unknown_colors": unknown_colors, "distinct_part_color_rows": len(bom.get("rows", []))}


def _mcp_env() -> dict[str, str]:
    return {"PYTHONUTF8": "1", "LDRAW_LIBRARY_PATH": os.environ["ASSEMBLY_LDRAW_LIBRARY"],
            "LDRAW_MCP_BLENDER": os.environ.get("ASSEMBLY_LDRAW_MCP_BLENDER", ""),
            "BLENDER_USER_SCRIPTS": os.environ.get("ASSEMBLY_LDRAW_BLENDER_SCRIPTS", "")}


async def run(model: Path, scene_path: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    report = {"status": "indeterminate", "renderer": "indeterminate", "bom": {"status": "indeterminate"},
              "renders": [], "detail_renders": [], "scene_hash": None}
    try:
        server = os.environ["ASSEMBLY_LDRAW_MCP_COMMAND"]
        params = StdioServerParameters(command=server, args=[], env=_mcp_env())
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=240) as client:
                initialized = await client.initialize()
                report["server"] = initialized.server_info.model_dump()
                available = {tool.name for tool in (await client.list_tools()).tools}
                if "bill_of_materials" not in available or "render_ldraw_file" not in available:
                    raise RuntimeError("Required LDraw MCP tools are unavailable")

                bom_result = await client.call_tool("bill_of_materials", {"path": str(model)})
                if bom_result.is_error:
                    raise RuntimeError(f"BOM request failed: {bom_result.content}")
                bom = _structured(bom_result)
                report["bom"] = _compare_bom(scene, bom)
                (output / "bom.json").write_text(json.dumps(bom, indent=2, ensure_ascii=False), encoding="utf-8")

                exterior_azimuths = [-90, -45, 0, 45, 90, 180]
                render_result = await client.call_tool("render_ldraw_file", {
                    "path": str(model), "azimuths": ",".join(map(str, exterior_azimuths)), "resolution": 768, "samples": 8})
                if render_result.is_error:
                    raise RuntimeError(f"Exterior rendering failed: {render_result.content}")
                render_artifacts = _write_images(render_result, output, "exterior", exterior_azimuths)
                report["renders"] = render_artifacts
                report["render_views"] = [
                    {"view": f"azimuth_{'m' if angle < 0 else 'p'}{abs(angle)}", "azimuth": angle,
                     "artifact": artifact}
                    for angle, artifact in zip(exterior_azimuths, render_artifacts)
                ]
                report["renderer"] = "passed" if len(report["renders"]) == len(exterior_azimuths) else "failed"

                for module, parts in _detail_groups(scene):
                    ldr = f"0 {scene.get('vehicle', {}).get('model', 'Vehicle')} {module} detail\n"
                    ldr += "\n".join(_part_line(part) for part in parts) + "\n"
                    detail_azimuths = [-45, 135]
                    detail = await client.call_tool("render_ldraw_text", {
                        "ldr": ldr, "azimuths": ",".join(map(str, detail_azimuths)), "resolution": 512, "samples": 8})
                    images = _write_images(detail, output, f"detail-{module}", detail_azimuths) if not detail.is_error else []
                    report["detail_renders"].append({"module": module, "parts": len(parts),
                                                     "status": "passed" if len(images) == len(detail_azimuths) else "failed", "artifacts": images,
                                                     "views": [{"azimuth": angle, "artifact": artifact}
                                                               for angle, artifact in zip(detail_azimuths, images)]})
                report["scene_hash"] = hashlib.sha256(json.dumps(scene, sort_keys=True).encode("utf-8")).hexdigest()
                details_passed = all(item["status"] == "passed" for item in report["detail_renders"])
                report["status"] = "passed" if report["bom"]["status"] == "passed" and report["renderer"] == "passed" and details_passed else "failed"
    except Exception as exc:
        report["error"] = str(exc)[:2000]
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--scene", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = asyncio.run(run(args.model.resolve(), args.scene.resolve(), args.output.resolve()))
    print(json.dumps({"status": result["status"], "renderer": result["renderer"], "bom": result["bom"]}, ensure_ascii=False))
