"""Reproducible, API-free inspection of the native F40 surface recipe."""
import json
from collections import Counter
from pathlib import Path

from app.services.assembly_v3.recipes import build_f40
from app.services.assembly_v3.connections import infer_connections
from app.services.assembly_v3.validation import collisions
from app.services.assembly_v3.exports import ldraw
from app.services.assembly_v3.jobs import atomic_json
from app.services.assembly_preview import geometry_bounds


def main():
    root = Path("storage/tool_research/surface-work")
    root.mkdir(parents=True, exist_ok=True)
    scene = build_f40("surface-work", "1:24")
    scene.connections, connectivity = infer_connections(scene)
    overlap = collisions(scene, 1000)
    by_id = {p.id: p for p in scene.parts}
    details = [{**i, "pieces": [by_id[k].model_dump() for k in i["parts"]]} for i in overlap]
    missing = [by_id[k].model_dump() for k in connectivity["disconnected_parts"]]
    bounds = geometry_bounds(scene.placements())
    actual = {k: max(b[axis][1] for b in bounds)-min(b[axis][0] for b in bounds)
              for k, axis in (("length", "z"), ("width", "x"), ("height", "height"))}
    atomic_json(root/"scene.json", scene.model_dump())
    atomic_json(root/"inspection.json", dict(connectivity=connectivity, collisions=details, disconnected=missing, actual_ldu=actual))
    (root/"model.mpd").write_text(ldraw(scene, True), encoding="utf-8")
    print(json.dumps(dict(parts=len(scene.parts), dimensions=actual, components=connectivity["components"],
        collisions=len(overlap), collision_features=Counter(tuple(sorted(p["feature"] for p in i["pieces"])) for i in details).__repr__(),
        disconnected=len(missing), disconnected_features=dict(Counter(p["feature"] for p in missing))), indent=2))


if __name__ == "__main__":
    main()
