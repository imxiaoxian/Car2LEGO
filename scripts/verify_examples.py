"""Check published artifacts against their measured stage records, without model downloads."""
import csv
import json
from car2lego3d.common import ROOT, digest
from car2lego3d.studio import verify_archive
from car2lego3d.vehicle import load_spec


def verify():
    base = ROOT / "examples"
    count = 0
    for name in ("image.json", "reconstruction.json", "lego.json", "studio.json", "measurement.json"):
        for record_path in base.rglob(name):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            assert record["status"] == "completed", record_path
            for filename, sha256 in record.get("outputs", {}).items():
                assert digest(record_path.parent / filename) == sha256, filename
                count += 1
            if name == "image.json":
                assert digest(record_path.parent / record["output"]) == record["sha256"]
                count += 1
            if name == "studio.json":
                source = record_path.parent.parent / "03-lego" / record["inputs"]["ldraw"]
                assert verify_archive(record_path.parent / "model.io", source)["part_count"] == record["part_count"]
    for path in base.rglob("model.ldr"):
        folder = path.parent
        parts = [line.split() for line in path.read_text().splitlines() if line.startswith("1 ")]
        report = json.loads((folder / "validation.json").read_text())
        assembly = json.loads((folder / "assembly.json").read_text())
        with (folder / "inventory.csv").open(newline="") as stream:
            total = sum(int(row["quantity"]) for row in csv.DictReader(stream))
        assert len(parts) == total == report["part_count"] == len(assembly.get("parts", assembly.get("plates", [])))
        assert all(len(p) == 15 and p[-1].endswith(".dat") for p in parts)
        assert report["physical_verified"] is False
        if report.get("strategy") == "car":
            assert report["body_cells_exact"] and report["appearance_accepted"] is False
        else:
            assert report["coverage_exact"]
        native = folder / "native-render.json"
        if native.exists():
            assert digest(path) == json.loads(native.read_text())["model_sha256"]
        native = folder / "native-ldraw.json"
        if native.exists():
            record = json.loads(native.read_text())
            assert digest(path) == record["model_sha256"]
            assert digest(native.with_suffix(".png")) == record["image_sha256"]
            assert not record["missing_parts"] and not record["appearance_accepted"]
            count += 2
    for path in base.rglob("pipeline.json"):
        record = json.loads(path.read_text())
        assert record["status"] == "completed"
        folder = path.parent
        reconstruction = json.loads((folder / "02-mesh/reconstruction.json").read_text())
        lego = json.loads((folder / "03-lego/lego.json").read_text())
        if record["inputs"]["mode"] == "prompt":
            source = folder / "01-image" / reconstruction["inputs"]["image"]
            assert digest(source) == reconstruction["inputs"]["sha256"]
            count += 1
        mesh = folder / "02-mesh" / lego["inputs"]["mesh"]
        assert digest(mesh) == lego["inputs"]["sha256"]
        count += 1
        if "vehicle_spec" in record:
            snapshot = folder / "00-vehicle" / record["vehicle_spec"]["file"]
            load_spec(snapshot)
            assert digest(snapshot) == record["vehicle_spec"]["sha256"]
            for stage in (folder / "01-image/image.json", folder / "02-mesh/reconstruction.json",
                          folder / "03-lego/lego.json"):
                if stage.exists():
                    assert json.loads(stage.read_text())["vehicle_spec"]["sha256"] == digest(snapshot)
            count += 1
        if "studio_file" in record:
            archive = folder / record["studio_file"]
            studio = json.loads((archive.parent / "studio.json").read_text())
            source = folder / "03-lego" / studio["inputs"]["ldraw"]
            assert digest(source) == studio["inputs"]["sha256"]
            assert digest(archive) == studio["outputs"][archive.name]
            count += 2
    print(f"Verified {count} recorded file hashes and all LDraw/BOM part totals.")


if __name__ == "__main__":
    verify()
