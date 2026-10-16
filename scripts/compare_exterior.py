"""Compare native-part exterior candidates without claiming visual acceptance."""
import argparse
from collections import Counter
import json
from pathlib import Path

from PIL import Image, ImageDraw

from car2lego3d.common import digest, write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def metrics(root):
    assembly = root / "03-lego/assembly.json"
    rows = read(assembly)["parts"]
    audit = read(root / "03-lego/native-audit.json")
    stage = read(root / "03-lego/lego.json")
    assembly_hash = digest(assembly)
    if audit["assembly_sha256"] != assembly_hash:
        raise ValueError(f"Stale native audit for {root}")
    module_counts = Counter(p["module"] for p in rows)
    roof_modules = {"curved roof shoulders", "roof center", "modular roof shoulders",
                    "modular roof center", "raked roof modules"}
    hood_modules = {"fitted bonnet", "modular bonnet"}
    return dict(assembly_sha256=assembly_hash, part_count=len(rows),
                mesh_sha256=stage["inputs"]["sha256"],
                views_sha256=stage.get("reference_views_sha256"),
                module_counts=dict(module_counts),
                roof_parts=sum(module_counts[m] for m in roof_modules),
                bonnet_parts=sum(module_counts[m] for m in hood_modules),
                native_collisions=audit["collision_count"],
                disconnected_parts=len(audit["connectivity"]["disconnected_parts"]),
                connectivity=audit["connectivity"]["status"],
                door_panels=dict(Counter(p["part"] for p in rows if p["module"] == "door skin")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    before, after = metrics(args.baseline), metrics(args.candidate)
    same_inputs=all(before.get(key) and before[key] == after.get(key) for key in ("mesh_sha256","views_sha256"))
    report = dict(baseline=before, candidate=after,
                  same_images_and_reconstruction=same_inputs,
                  comparison_scope="LEGO conversion only; reference and mesh stages were reused",
                  appearance_accepted=False, physical_build_verified=False, studio_gui_verified=False,
                  limitations=["Module counts do not measure visual likeness or exposed-stud coverage.",
                               "Native checks are geometric diagnostics, not physical clutch or build certification."])
    write_json(args.candidate / "exterior-comparison.json", report)
    sheet = Image.new("RGB", (1600, 1100), "#f4f4f6")
    draw = ImageDraw.Draw(sheet)
    for col, (name, root, data) in enumerate((("Before", args.baseline, before), ("Modular exterior", args.candidate, after))):
        draw.text((col*800+24, 18), f"{name}: {data['part_count']} parts; roof {data['roof_parts']}; bonnet {data['bonnet_parts']}", fill="#222222")
        for row, view in enumerate(("rear", "front")):
            picture = Image.open(root / f"05-presentation/render_{view}.png").convert("RGB")
            picture.thumbnail((800, 500))
            sheet.paste(picture, (col*800, 55+row*510))
    sheet.save(args.candidate / "exterior-comparison.png")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
