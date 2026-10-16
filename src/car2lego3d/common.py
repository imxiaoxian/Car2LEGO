import hashlib
import importlib.metadata
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def model_lock():
    return json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            # Windows readers/scanners may briefly deny replacement of an otherwise writable file.
            if attempt == 7:
                raise
            time.sleep(.02 * 2 ** min(attempt, 3))


@contextmanager
def stage(directory, name, inputs):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    record = {"stage": name, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "inputs": inputs, "models": model_lock()}
    for package in ("torch", "trimesh", "scikit-image", "diffusers", "transformers"):
        try:
            record.setdefault("versions", {})[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    write_json(directory / f"{name}.json", record)
    started = time.perf_counter()
    try:
        yield record
        record["status"] = "completed"
    except Exception as error:
        record.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        record["seconds"] = round(time.perf_counter() - started, 3)
        write_json(directory / f"{name}.json", record)


def device_name(requested):
    import torch
    if requested == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    if requested.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable. Run car2lego3d doctor or pass --device cpu.")
    return requested
