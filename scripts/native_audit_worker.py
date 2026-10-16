"""Read-only bridge to the original project's native Studio geometry checks."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sys
from types import SimpleNamespace

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("D:/lego"))
    parser.add_argument("--assembly", type=Path)
    parser.add_argument("--parts", nargs="*")
    parser.add_argument("--query")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.source.resolve()):
        raise ValueError("The original project is read-only.")
    sys.dont_write_bytecode = True
    os.environ["STUDIO_LDRAW_PATH"] = str(args.source / "Studio 2.0/ldraw")
    os.environ["STORAGE_PATH"] = str(args.output.resolve().parent)
    sys.path.insert(0, str(args.source / "backend"))
    from app.services.assembly_preview import part_triangles
    from app.services.assembly_v3.catalog import ports, part_validity
    from app.services.assembly_v3.connections import infer_connections
    from app.services.assembly_v3.validation import collisions
    from app.services.assembly_v3.scene import PartInstance, Transform
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from car2lego3d.part_library import PartLibrary, assembly_library

    root = args.source / "Studio 2.0/ldraw"
    with (root / "Bricksmith Parts.plist").open("rb") as stream:
        names = plistlib.load(stream)["Part List"]
    if args.assembly:
        assembly = json.loads(args.assembly.read_text(encoding="utf-8"))
        rows = assembly["parts"]
        selected = sorted({p["part"].removesuffix('.dat') + '.dat' for p in rows})
        library = assembly_library(args.assembly, root)
    else:
        library = PartLibrary(root)
        selected = [p if p.endswith(".dat") else p+".dat" for p in args.parts or []]
        if args.query:
            selected += [p for p, item in names.items() if item["Part Name"].startswith(args.query)]
    catalog = {}
    for name in sorted(set(selected)):
        try:
            triangles, _ = library.triangles(name)
            low, high = triangles.min(axis=(0, 1)), triangles.max(axis=(0, 1))
            entry = {"description": names.get(name, {}).get("Part Name", ""),
                     "low_ldu": low.tolist(), "high_ldu": high.tolist(),
                     "size_mm": ((high-low)*.4).tolist(), "validity": part_validity(name) if not name.startswith('c2l-')
                        else dict(status='unverified', geometry=True, connections='unverified', collider='unverified')}
            entry["connectors"] = [dict(kind=p.kind, subtype=p.subtype, tag=p.tag,
                position=p.position, direction=p.direction, semantic=p.semantic,
                length=p.length, altitude=p.altitude, area=p.area) for p in ports(name)] if not name.startswith('c2l-') else []
            if args.parts and any(kind in entry["description"] for kind in ("Slope", "Tile", "Windscreen", "Wedge")):
                sys.path.append(str(Path(__file__).resolve().parents[1] / ".venv/Lib/site-packages"))
                import trimesh
                geometry = trimesh.Trimesh(vertices=triangles.reshape(-1,3),
                    faces=np.arange(len(triangles)*3).reshape(-1,3), process=False)
                stations = np.arange(low[2]+10, high[2], 20)
                origins = np.column_stack([np.zeros(len(stations)), np.full(len(stations), low[1]-20), stations])
                hits, rays, _ = geometry.ray.intersects_location(origins, np.tile([0,1,0], (len(stations),1)))
                entry["surface_profile"] = [[float(z), float(hits[rays==i,1].min())]
                    for i,z in enumerate(stations) if np.any(rays==i)]
            catalog[name] = entry
        except (ValueError, OSError) as error:
            catalog[name] = {"error": str(error)}
    result = {"catalog": catalog, "physical_verified": False, "studio_gui_verified": False}
    if args.assembly:
        result["assembly_sha256"] = hashlib.sha256(args.assembly.read_bytes()).hexdigest()
        features = {"tyres": "tyre", "wheel rims": "rim"}
        instances = [PartInstance(id=f"p{i}", part_num=row["part"].removesuffix('.dat') + '.dat', color_id=row["color"],
                     module=row["module"], feature=features.get(row["module"], ""),
                     transform=Transform(position=row["position"], rotation=row["rotation"])) for i,row in enumerate(rows)]
        scene = SimpleNamespace(parts=instances, modules=[SimpleNamespace(id=name, structural=True)
                                for name in {p.module for p in instances}], connections=[])
        scene.connections, connectivity = infer_connections(scene)
        issues = collisions(scene, limit=10000)
        bounds, missing = [], []
        for row in rows:
            try:
                geometry, _ = library.instance(row)
                bounds.append([geometry.min(axis=(0,1)), geometry.max(axis=(0,1))])
            except (ValueError, OSError) as error:
                missing.append(dict(part=row['part'], error=str(error)))
        bounds = np.array(bounds)
        custom = [name for name in selected if name.startswith('c2l-')]
        incomplete_colliders = [name for name, item in catalog.items() if item.get('error') or
            item.get('validity', {}).get('collider') is not True]
        result.update(connectivity=connectivity, collisions=issues, collision_count=len(issues),
                      collision_status='failed' if issues else 'unverified' if custom or missing or incomplete_colliders else 'passed',
                      collision_coverage=dict(status='partial' if custom or missing or incomplete_colliders else 'complete',
                          custom_parts=custom, missing_geometry=missing, unchecked_colliders=incomplete_colliders),
                      connections=[c.model_dump() for c in scene.connections],
                      part_count=len(rows), bounds_coverage='partial' if missing else 'complete',
                      disconnected_modules=dict(Counter(instances[int(p[1:])].module for p in connectivity["disconnected_parts"])),
                      per_part_bounds_ldu=bounds.tolist())
        if len(bounds):
            result['bounds_ldu'] = [bounds[:,0].min(axis=0).tolist(), bounds[:,1].max(axis=0).tolist()]
    result['part_dependencies'] = library.dependency_record()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "parts": len(catalog),
                      "collisions": result.get("collision_count"), "connectivity": result.get("connectivity")}))


if __name__ == "__main__":
    main()
