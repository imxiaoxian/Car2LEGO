"""Studio, MPD, flat LDR, inventory and actual scene step documents."""

from collections import Counter
import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from reportlab.pdfgen import canvas

from app.services.studio_service import StudioService, StudioFile
from .jobs import atomic_json, replace_file
from .scene import AssemblyScene, Transform


def part_line(part) -> str:
    values = [*part.transform.position, *part.transform.rotation]
    return f"1 {part.color_id} " + " ".join(f"{v:.9g}" for v in values) + f" {part.part_num}"


def ldraw(scene: AssemblyScene, submodels: bool = False) -> str:
    by_id = {p.id: p for p in scene.parts}
    title = f"{scene.vehicle['make']} {scene.vehicle['model']} {scene.scale}"
    header = [f"0 {title}", "0 Author: Car2LEGO assembly_v3", f"0 // Scene SHA256 {scene.digest()}"]
    if not submodels:
        lines = list(header)
        for step in scene.steps:
            lines.append(f"0 // Step {step.index} {step.module}")
            lines.extend(part_line(by_id[p]) for p in step.parts)
            lines.append("0 STEP")
        return "\n".join(lines) + "\n"
    lines = ["0 FILE main.ldr", *header]
    by_module={m.id:m for m in scene.modules}
    ordered=[by_module[name] for name in dict.fromkeys(s.module for s in scene.steps)]
    for module in ordered:
        if any(p.module == module.id for p in scene.parts):
            lines += [f"1 16 0 0 0 1 0 0 0 1 0 0 0 1 {module.id}.ldr", "0 STEP"]
    lines += ["0 NOFILE"]
    for module in ordered:
        lines += [f"0 FILE {module.id}.ldr", f"0 {module.id}"]
        for step in scene.steps:
            if step.module == module.id:
                lines += [f"0 // Step {step.index}", *(part_line(by_id[p]) for p in step.parts), "0 STEP"]
        lines += ["0 NOFILE"]
    return "\n".join(lines) + "\n"


def read_ldraw(content: str) -> list[tuple]:
    files, current, root = {}, None, None
    for line in content.splitlines():
        if line.startswith("0 FILE "):
            current = line[7:].strip()
            if current in files:
                raise ValueError("Duplicate MPD submodel")
            root = root or current; files[current] = []
        elif line == "0 NOFILE":
            current = None
        else:
            files.setdefault(current or "flat", []).append(line)
    root = root or "flat"
    def expand(name, origin, matrix, inherited, stack):
        if name in stack:
            raise ValueError("Recursive MPD submodel")
        result = []
        for line in files[name]:
            tokens = line.split()
            if not tokens or tokens[0] != "1":
                continue
            if len(tokens) < 15:
                raise ValueError("Invalid LDraw part line")
            c = int(tokens[1]); c = inherited if c == 16 else c
            pos = origin + matrix @ np.array(tokens[2:5], dtype=float)
            rotation = matrix @ np.array(tokens[5:14], dtype=float).reshape(3, 3)
            number = " ".join(tokens[14:])
            if number in files:
                result.extend(expand(number, pos, rotation, c, stack | {name}))
            elif number.endswith(".dat"):
                Transform(position=tuple(pos), rotation=tuple(rotation.ravel()))
                result.append((number, c, *np.round(pos, 5), *np.round(rotation.ravel(), 5)))
            else:
                raise ValueError(f"Missing submodel {number}")
        return result
    return expand(root, np.zeros(3), np.eye(3), 16, set())


def read_step_blocks(content: str) -> dict[int,tuple[str,list[tuple]]]:
    """Read leaf submodel STEP blocks rather than reporting an assumed count."""
    result={};module=None;index=None;lines=[]
    for line in content.splitlines():
        if line.startswith("0 FILE "):module=line[7:].strip().removesuffix(".ldr")
        elif line.startswith("0 // Step "):
            if index is not None:raise ValueError("Unterminated STEP block")
            fields=line.split()
            if len(fields)<4 or not fields[3].isdigit():
                raise ValueError("Invalid exported STEP index")
            index=int(fields[3]);lines=[]
            if len(fields)>4:
                module=fields[4]
        elif line=="0 STEP" and index is not None:
            if index in result:raise ValueError("Duplicate exported STEP index")
            result[index]=(module,read_ldraw("\n".join(lines)))
            index=None
        elif line.startswith("1 ") and index is not None:lines.append(line)
    if index is not None:raise ValueError("Unterminated STEP block")
    return result


def parts_data(scene: AssemblyScene) -> list[dict]:
    counts = Counter((p.part_num, p.color_id) for p in scene.parts)
    return [dict(part_num=n, ldraw_color_id=c, quantity=q, bricklink_id=n.removesuffix(".dat")) for (n, c), q in sorted(counts.items())]


def verify_export_bundle(scene: AssemblyScene, directory: Path) -> dict:
    """Read final saved artifacts against the canonical scene, including model2."""
    expected = Counter((p.part_num, p.color_id, *np.round(p.transform.position, 5),
                        *np.round(p.transform.rotation, 5)) for p in scene.parts)
    by_id = {p.id: p for p in scene.parts}
    expected_steps = {s.index: (s.module, Counter((by_id[pid].part_num, by_id[pid].color_id,
                      *np.round(by_id[pid].transform.position, 5), *np.round(by_id[pid].transform.rotation, 5))
                      for pid in s.parts)) for s in scene.steps}
    studio = StudioFile.from_path(directory / "model.io")
    contents = {"model.ldr": (directory / "model.ldr").read_text(encoding="utf-8"),
                "model.mpd": (directory / "model.mpd").read_text(encoding="utf-8"),
                "model.io/model.ldr": studio.model_ldr, "model.io/model2.ldr": studio.model2_ldr}
    expected_models = {"main.ldr", *(f"{p.module}.ldr" for p in scene.parts)}
    for name, content in contents.items():
        if Counter(read_ldraw(content)) != expected:
            raise ValueError(f"{name} parts, colors or transforms differ from canonical scene")
        blocks = {index: (module, Counter(parts)) for index, (module, parts) in read_step_blocks(content).items()}
        if blocks != expected_steps:
            raise ValueError(f"{name} STEP membership differs from canonical scene")
        if name != "model.ldr":
            models = [line[7:].strip() for line in content.splitlines() if line.startswith("0 FILE ")]
            if len(models) != len(expected_models) or set(models) != expected_models:
                raise ValueError(f"{name} submodels differ from canonical scene")
    inventory = Counter()
    with (directory / "parts.csv").open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            key = (row["part_num"], int(row["ldraw_color_id"]))
            quantity = int(row["quantity"])
            if quantity <= 0 or key in inventory or row["bricklink_id"] != key[0].removesuffix(".dat"):
                raise ValueError("Invalid or duplicate inventory row")
            inventory[key] = quantity
    if inventory != Counter((p.part_num, p.color_id) for p in scene.parts):
        raise ValueError("Exported inventory differs from canonical scene")
    saved = AssemblyScene.model_validate_json((directory / "scene.json").read_text(encoding="utf-8"))
    if saved.digest() != scene.digest():
        raise ValueError("Saved scene differs from canonical scene")
    return {"status": "passed", "method": "final_saved_artifacts_v2", "scene_hash": scene.digest(),
            "parts": len(scene.parts), "steps": len(scene.steps), "step_membership": "passed",
            "submodels": len(expected_models) - 1, "inventory_quantity": sum(inventory.values()),
            "checked_files": list(contents) + ["parts.csv", "scene.json"]}


@lru_cache(maxsize=256)
def colored_geometry(name: str, inherited: int = 16) -> tuple:
    """Expand native subpart colours, preserving transparent materials in the web viewer."""
    from app.services.io_validator import STUDIO_LDRAW_PARTS
    root = STUDIO_LDRAW_PARTS.parent
    relative = Path(name.replace("\\", "/"))
    path = next((p for p in (root / "parts" / relative, root / "p" / relative,
                             root / "UnOfficial" / "parts" / relative, root / "UnOfficial" / "p" / relative) if p.is_file()), None)
    if not path:
        raise ValueError(f"Missing geometry {name}")
    groups = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if not fields or fields[0] not in ("1", "3", "4"):
            continue
        color = int(fields[1]); color = inherited if color == 16 else color
        if fields[0] == "1":
            pos, rot = np.array(fields[2:5], dtype=float), np.array(fields[5:14], dtype=float).reshape(3, 3)
            for c, mesh in colored_geometry(" ".join(fields[14:]), color):
                groups.setdefault(c, []).append(mesh @ rot.T + pos)
        else:
            count = int(fields[0]); vertices = np.array(fields[2:2 + count * 3], dtype=float).reshape(count, 3)
            groups.setdefault(color, []).append(vertices[:3][None])
            if count == 4:
                groups[color].append(vertices[[0, 2, 3]][None])
    return tuple((c, np.concatenate(mesh)) for c, mesh in groups.items())


def viewer_geometry(scene: AssemblyScene) -> dict:
    result = {}
    for name in sorted({p.part_num for p in scene.parts}):
        result[name] = [{"color_id": c, "positions": mesh.astype(np.float32).ravel().tolist()} for c, mesh in colored_geometry(name)]
    return result


def instructions_pdf(scene: AssemblyScene, output: Path, report: dict, progress=None):
    from .render import render_scene
    pdf = canvas.Canvas(str(output), pagesize=(842, 595))
    by_id = {p.id: p for p in scene.parts}
    visible = []
    for step in scene.steps:
        if progress:
            progress("instructions", 94 + round(step.index / len(scene.steps) * 4))
        visible.extend(step.parts)
        image = output.parent / f"step_{step.index:03d}.png"
        render_scene(scene, image, size=(640, 400), ids=set(visible), highlight=set(step.parts))
        pdf.setFont("Helvetica", 16)
        pdf.drawString(32, 563, f"{scene.vehicle['make']} {scene.vehicle['model']} {scene.scale} / {step.index} of {len(scene.steps)}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(32, 542, f"Module: {step.module} | {len(step.parts)} new parts | DIGITAL DRAFT")
        pdf.drawImage(str(image), 24, 110, width=640, height=400, preserveAspectRatio=True)
        pdf.setFont("Helvetica", 9)
        for i, ((number, color), quantity) in enumerate(Counter((by_id[p].part_num, by_id[p].color_id) for p in step.parts).items()):
            pdf.drawString(670, 505 - i * 16, f"{quantity} x {number} / {color}")
        pdf.drawString(32, 66, "New parts: " + ", ".join(step.parts)[:150])
        pdf.drawString(32, 45, "Assembly and insertion paths require acceptance. Studio and physical verification are independent.")
        pdf.showPage()
    pdf.save()


def export_scene(scene: AssemblyScene, directory: Path, report: dict, progress=None) -> dict:
    from .render import render_scene
    directory.mkdir(parents=True, exist_ok=True)
    report["export_roundtrip"] = {"status": "unverified"}
    report["artifact_hashes"] = {}
    report.setdefault("gates", {})["export_integrity"] = "unverified"
    atomic_json(directory / "quality_report.json", report)
    flat, mpd = ldraw(scene), ldraw(scene, True)
    (directory / "model.ldr").write_text(flat, encoding="utf-8")
    (directory / "model.mpd").write_text(mpd, encoding="utf-8")
    sf = StudioService.create_studio_file(mpd, f"{scene.vehicle['make']} {scene.vehicle['model']} {scene.scale}", description="assembly_v3 digital draft")
    sf.save(directory / "model.io")
    rows = parts_data(scene)
    with (directory / "parts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    atomic_json(directory / "scene.json", scene.model_dump())
    atomic_json(directory / "geometry.json", viewer_geometry(scene))
    for view in ("front", "rear", "left", "right", "top", "bottom"):
        if progress:
            progress("rendering:" + view, 88)
        render_scene(scene, directory / f"render_{view}.png", view)
    sf.thumbnail = (directory / "render_front.png").read_bytes()
    io_temp = directory / "model.partial.io"
    sf.save(io_temp)
    replace_file(io_temp, directory / "model.io")
    if progress:
        progress("instructions", 94)
    # Never expose a truncated PDF after pause/cancel or a render failure.
    pdf_temp = directory / "instructions.partial.pdf"
    instructions_pdf(scene, pdf_temp, report, progress)
    replace_file(pdf_temp,directory / "instructions.pdf")
    if progress:
        progress("export_validation", 98)
    try:
        report["export_roundtrip"] = verify_export_bundle(scene, directory)
    except Exception:
        report["export_roundtrip"] = {"status": "failed"}
        report["gates"]["export_integrity"] = "failed"
        report["digital_status"] = "failed"
        report["precision_verified"] = False
        atomic_json(directory / "quality_report.json", report)
        raise
    report["gates"]["export_integrity"] = "passed"
    report["digital_status"] = "passed" if all(v == "passed" for v in report["gates"].values()) else "failed"
    for filename in ("scene.json", "model.io", "model.ldr", "model.mpd", "parts.csv", "instructions.pdf"):
        report.setdefault("artifact_hashes", {})[filename] = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
    atomic_json(directory / "quality_report.json", report)
    return {"parts_data": rows, "parts_count": len(scene.parts), "steps_count": len(scene.steps)}
