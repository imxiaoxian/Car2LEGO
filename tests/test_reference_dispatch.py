import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from car2lego3d.common import ROOT, write_json


spec = importlib.util.spec_from_file_location("reference_worker", ROOT / "scripts/car2lego_reference_worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class GatewayError(Exception):
    pass


class FakeService:
    """Exercise scheduling and manifest writes without making paid API calls."""

    def __init__(self):
        self.calls = Counter()
        self.started = set()
        self.all_started = asyncio.Event()
        self.failures = Counter()
        self.fatal = set()
        self.states = {}
        self.ReferenceImageService = lambda: SimpleNamespace(generate=self.generate)

    def design_directory(self, state):
        directory = Path(state["storage_path"]) / state["design_id"]
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def write_progress(self, state, stage, percent):
        write_json(self.design_directory(state) / "generation_status.json", dict(stage=stage, progress=percent))

    def transient_model_error(self, error):
        return isinstance(error, GatewayError)

    def failure_details(self, error, stage, attempt):
        return dict(message=str(error), attempt=attempt)

    async def generate(self, state, only):
        view, = only
        self.states[view] = state
        directory = self.design_directory(state)
        refs = directory / "references"
        refs.mkdir(exist_ok=True)
        manifest_path = refs / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(brief={"paint": "orange"}, images=[])
        cached = next((ref for ref in manifest["images"] if ref["view"] == view), None)
        if cached and (directory / cached["path"]).is_file():
            if hashlib.sha256((directory / cached["path"]).read_bytes()).hexdigest() == cached["sha256"]:
                return dict(reference_images=manifest["images"])
        self.calls[view] += 1
        if view != "overview":
            assert (refs / "overview.png").read_bytes() == b"overview"
            assert manifest["brief"] == {"paint": "orange"}
            self.started.add(view)
            if self.started == set(worker.VIEW_SHOTS):
                self.all_started.set()
            await self.all_started.wait()
        if view in self.fatal:
            raise ValueError("invalid request")
        if self.failures[view]:
            self.failures[view] -= 1
            raise GatewayError("502")
        path = refs / f"{view}.png"
        path.write_bytes(view.encode())
        ref = dict(view=view, path=f"references/{view}.png", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest["images"] = [ref_ for ref_ in manifest["images"] if ref_["view"] != view] + [ref]
        write_json(manifest_path, manifest)
        return dict(reference_images=manifest["images"])


def run(service, state, attempts=3):
    # The deadline is a test deadlock guard, never a production request timeout.
    return asyncio.run(asyncio.wait_for(worker.generate_references(
        service, state, write_json, attempts=attempts, retry_delay=0), timeout=5))


def test_four_views_overlap_and_share_anchor_with_independent_manifests(tmp_path):
    service = FakeService()
    state = dict(storage_path=str(tmp_path), design_id="car2lego")
    result = run(service, state)
    assert {ref["view"] for ref in result["reference_images"]} == {"overview", *worker.VIEW_SHOTS}
    assert service.calls == Counter({view: 1 for view in ("overview", *worker.VIEW_SHOTS)})
    assert len({service.states[view]["storage_path"] for view in worker.VIEW_SHOTS}) == 4
    for ref in result["reference_images"]:
        assert (tmp_path / "car2lego" / ref["path"]).read_bytes() == ref["view"].encode()
    run(service, state)
    assert all(count == 1 for count in service.calls.values())


def test_only_failed_view_retries_and_completed_siblings_survive_restart(tmp_path):
    service = FakeService()
    service.failures["body"] = 3
    state = dict(storage_path=str(tmp_path), design_id="car2lego")
    with pytest.raises(GatewayError):
        run(service, state)
    manifest_path = tmp_path / "car2lego/references/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert {ref["view"] for ref in manifest["images"]} == {"overview", "front", "rear", "wheels"}
    assert service.calls["body"] == 3
    result = run(service, state)
    assert len(result["reference_images"]) == 5
    assert service.calls["body"] == 4
    assert all(service.calls[view] == 1 for view in ("overview", "front", "rear", "wheels"))


def test_nontransient_error_does_not_retry_or_cancel_siblings(tmp_path):
    service = FakeService()
    service.fatal.add("front")
    with pytest.raises(ValueError, match="invalid request"):
        run(service, dict(storage_path=str(tmp_path), design_id="car2lego"))
    assert service.calls["front"] == 1
    manifest = json.loads((tmp_path / "car2lego/references/manifest.json").read_text())
    assert {ref["view"] for ref in manifest["images"]} == {"overview", "rear", "body", "wheels"}


def test_corrupt_cached_view_is_regenerated(tmp_path):
    service = FakeService()
    state = dict(storage_path=str(tmp_path), design_id="car2lego")
    run(service, state)
    (tmp_path / "car2lego/references/front.png").write_bytes(b"corrupt")
    run(service, state)
    assert service.calls["front"] == 2
    assert all(service.calls[view] == 1 for view in ("overview", "body", "rear", "wheels"))
    assert list((tmp_path / "car2lego/references/history").glob("front-*.png"))
