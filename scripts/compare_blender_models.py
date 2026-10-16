"""Compare actual Blender renders and seam measurements from two audited scenes."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from car2lego3d.common import digest, write_json
from car2lego3d.model_quality import new_failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    views = ("three-quarter", "rear-quarter", "left")
    sheet = Image.new("RGB", (1600, 1770), "#eeeeef")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=24)
    reports = {}
    qualities = []
    for col, (label, root) in enumerate((("Before", args.before), ("After", args.after))):
        metrics = json.loads((root / "scene-metrics.json").read_text(encoding="utf-8"))
        quality = json.loads((root / "model-quality.json").read_text(encoding="utf-8"))
        qualities.append(quality)
        if quality["metrics_sha256"] != digest(root / "scene-metrics.json"):
            raise ValueError(f"Stale quality report: {root}")
        seams = [c for c in quality["checks"] if ".connection." in c["name"]]
        reports[label.lower()] = dict(directory=str(root.resolve()), triangles=metrics["triangles"],
            dimensions_mm=metrics["dimensions_mm"], failed_checks=quality["failed_checks"],
            seam_checks=len(seams), failed_seams=[c["name"] for c in seams if not c["passed"]],
            regions=sorted({c["region"] for c in seams}),
            max_measured_seam_gap_m=max((c["max_gap_m"] for c in seams if c["max_gap_m"] is not None), default=None),
            metrics_sha256=digest(root / "scene-metrics.json"),
            renders={v: digest(root / f"render-{v}.png") for v in views})
        draw.text((col * 800 + 24, 15), f"{label} | {quality['failed_checks']} diagnostic failures", fill="#222222", font=font)
        for row, view in enumerate(views):
            picture = Image.open(root / f"render-{view}.png").convert("RGBA")
            background = Image.new("RGBA", picture.size, "#eeeeef")
            picture = Image.alpha_composite(background, picture).convert("RGB")
            picture.thumbnail((800, 550))
            y = 60 + row * 570
            sheet.paste(picture, (col * 800 + (800 - picture.width) // 2, y))
            draw.text((col * 800 + 24, y + 520), view, fill="#333333", font=font)
    sheet.save(args.output / "connection-comparison.png")
    write_json(args.output / "connection-comparison.json", dict(**reports, appearance_accepted=False,
        new_geometry_failures=new_failures(*qualities),
        scope="Smooth full-size reconstruction; LEGO conversion and physical build not tested by this report"))
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
