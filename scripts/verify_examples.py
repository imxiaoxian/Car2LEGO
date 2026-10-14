"""Check published artifacts against their measured stage records, without model downloads."""
import csv
import json
from car2lego3d.common import ROOT, digest


def verify():
    base = ROOT / "examples"
    count = 0
    for name in ("image.json", "reconstruction.json", "lego.json"):
        for record_path in base.rglob(name):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            assert record["status"] == "completed", record_path
            for filename, sha256 in record.get("outputs", {}).items():
                assert digest(record_path.parent / filename) == sha256, filename
                count += 1
            if name == "image.json":
                assert digest(record_path.parent / record["output"]) == record["sha256"]
                count += 1
    for path in base.rglob("model.ldr"):
        folder = path.parent
        parts = [line.split() for line in path.read_text().splitlines() if line.startswith("1 ")]
        report = json.loads((folder / "validation.json").read_text())
        assembly = json.loads((folder / "assembly.json").read_text())
        with (folder / "inventory.csv").open(newline="") as stream:
            total = sum(int(row["quantity"]) for row in csv.DictReader(stream))
        assert len(parts) == total == report["part_count"] == len(assembly["plates"])
        assert all(len(p) == 15 and p[-1].endswith(".dat") for p in parts)
        assert report["coverage_exact"] and report["physical_verified"] is False
        native = folder / "native-render.json"
        if native.exists():
            assert digest(path) == json.loads(native.read_text())["model_sha256"]
    print(f"Verified {count} recorded file hashes and all LDraw/BOM part totals.")


if __name__ == "__main__":
    verify()
