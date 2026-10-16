"""Run the original Car2LEGO GPT service with isolated output and no source writes."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from contextlib import ExitStack
from contextvars import ContextVar
from datetime import datetime, timezone

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from car2lego3d.reference_plan import reference_plan, shot_fingerprint, validate_plan
from car2lego3d.image_slots import IMAGE_CONCURRENCY, image_slot


SINGLE_VEHICLE_VIEW = (
    "ONE single complete car in a front-left three-quarter view, seen from slightly above, "
    "camera elevation about 15 degrees, long focal length to limit perspective distortion. "
    "The front points toward the left of the image; show its front fascia and left side. "
    "All four wheel positions, roof, bumpers and mirrors must remain within frame. "
    "Use a seamless white background with a minimal contact shadow. The car occupies "
    "about 80 percent of the image width. This is the identity anchor for four-view generation: "
    "output exactly one car, no contact sheet, panels, alternate angles or duplicated cars. "
    "If a source photo is present, preserve its exact vehicle identity, door count, lamp shapes, "
    "wheel style, roofline and paint. Reconstruct only the requested camera view."
)

VIEW_SHOTS = {"front": "front", "rear": "back", "body": "left", "wheels": "right"}


def configure_shots(service, shots):
    """Process-local adapter; the upstream GPT image client and prompts stay in use."""
    service.ALL_REFERENCE_VIEWS.update({s.id: s.instructions() for s in shots})
    service.REFERENCE_VIEWS.update({s.id: s.instructions() for s in shots if s.category != "detail"})
    service.DETAIL_VIEWS.update({s.id: s.instructions() for s in shots if s.category == "detail"})
    known = {s.id for s in shots}

    def requested(state):
        result = {}
        for shot in state.get("requested_reference_shots", []):
            if shot["view"] not in known:
                raise ValueError("Unknown local camera request")
            result[shot["view"]] = shot
        return result

    service.requested_shots = requested
    service.reference_plan = lambda state, brief=None: {
        s.id: s.instructions() for s in shots}
    context = ContextVar("reference_parents", default=None)
    prompts, original_factory = {}, service.AsyncOpenAI

    def enforce_camera(request, info):
        if info:
            shot = next(s for s in shots if s.id == info[0])
            request['prompt'] += (
                "\nFINAL SHOT CONTRACT (takes priority over pose/opening descriptions in the appearance brief "
                "and parent images): " + shot.instructions() +
                " Copy the parents' vehicle identity, not their camera or articulation pose. "
                "For a closed whole-car view, both doors, bonnet, rear cover and pop-up headlamps are CLOSED; "
                "all glazing is seated and the wheels point straight. For an explicitly open-detail view, "
                "open ONLY the requested mechanism. Do not inherit raised doors from an anchor.")
            prompts[info[0]] = request['prompt']
        return request

    def factory(*args, **kwargs):
        client = original_factory(*args, **kwargs)
        original_edit, original_generate = client.images.edit, client.images.generate

        async def audited(call):
            try:
                async with image_slot():
                    return await call()
            except json.JSONDecodeError as error:
                info = context.get()
                directory = Path(state_storage.get()) if state_storage.get() else None
                if directory:
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / f"invalid-response-{info[0] if info else 'unknown'}.txt").write_text(error.doc, encoding="utf-8")
                raise

        async def edit(*, image, **request):
            info = context.get()
            request = enforce_camera(request, info)
            with ExitStack() as stack:
                images = list(image)
                existing = {str(Path(f.name).resolve()) for f in images}
                for path in info[1] if info else []:
                    if str(path.resolve()) not in existing:
                        images.append(stack.enter_context(path.open("rb")))
                return await audited(lambda: original_edit(image=images, **request))

        async def generate(**request):
            info = context.get()
            request = enforce_camera(request, info)
            return await audited(lambda: original_generate(**request))

        client.images.edit, client.images.generate = edit, generate
        return client

    service.AsyncOpenAI = factory
    return context, prompts


state_storage = ContextVar("reference_diagnostics", default=None)


async def generate_reference_set(service, state, atomic_json, shots, context=None, prompts=None,
                                 concurrency=IMAGE_CONCURRENCY, attempts=6, retry_delay=15):
    validate_plan(shots)
    if not 1 <= concurrency <= IMAGE_CONCURRENCY:
        raise ValueError("Reference concurrency must be between 1 and 5")
    directory = service.design_directory(state)
    semaphore = asyncio.Semaphore(concurrency)
    manifest, done = {}, set()
    prompts = prompts if prompts is not None else {}
    batch_index = 0
    batches = []

    def batch_status(status, batch, failures=()):
        now = datetime.now(timezone.utc).isoformat()
        new_batch = status == "running" and (not batches or batches[-1]["index"] != batch_index)
        if new_batch:
            batches.append(dict(index=batch_index, views=[s.id for s in batch],
                                status=status, started_at=now, completed_views=[], failed_views=[]))
        current = batches[-1]
        current.update(status=status, completed_views=[s.id for s in batch if s.id in done],
                       failed_views=list(failures))
        if status != "running":
            current["finished_at"] = now
        record = dict(schema="car2lego3d.reference-dispatch.v1", status=status,
            batch_index=batch_index, batch_size=concurrency,
            views=[s.id for s in batch], failed_views=list(failures),
            completed_views=sorted(done), expected_views=len(shots),
            wait_for_batch_completion=True, batches=batches, updated_at=now)
        atomic_json(directory / "reference-dispatch.json", record)
        if status != "running" or new_batch:
            print(json.dumps({"event": "reference_batch", **record}), flush=True)

    async def request(local, shot, parents):
        token = context.set((shot.id, parents)) if context else None
        try:
            for attempt in range(1, attempts + 1):
                try:
                    async with semaphore:
                        return await service.ReferenceImageService().generate(local, only={shot.id})
                except Exception as error:
                    print(json.dumps({**service.failure_details(error, "reference", attempt=attempt),
                                      "view": shot.id}), flush=True)
                    if not service.transient_model_error(error) or attempt == attempts:
                        raise
                    await asyncio.sleep(min(retry_delay * attempt, 90))
        finally:
            if context:
                context.reset(token)

    def shot_request(shot, parents):
        return [{"view": shot.id, "focus": shot.focus, "angles": [shot.camera],
                 "modules": list(shot.modules), "reason": "Modular reconstruction reference",
                 "dependency_fingerprint": shot_fingerprint(shot, parents)}]

    anchor = next(s for s in shots if s.id == "overview")
    state = {**state, "requested_reference_shots": shot_request(anchor, {})}
    batch_index += 1
    batch_status("running", [anchor])
    try:
        await request(state, anchor, [])
    except Exception:
        batch_status("failed", [anchor], [anchor.id])
        raise
    manifest_path = directory / "references/manifest.json"
    manifest.update(json.loads(manifest_path.read_text(encoding="utf-8")))

    def enrich(ref, shot, parents):
        return {**ref, **shot.record(), "view": shot.id, "synthetic": True,
                "inferred_hidden_geometry": shot.category == "detail",
                "parents": parents, "request_fingerprint": shot_fingerprint(shot, parents),
                "prompt": prompts.get(shot.id) or ref.get("prompt"),
                "consistency": {"status": "unverified", "issues": []}}

    ref = next(r for r in manifest["images"] if r["view"] == "overview")
    manifest["images"] = [r for r in manifest["images"] if r["view"] != "overview"] + [enrich(ref, anchor, {})]
    done.add("overview")
    atomic_json(manifest_path, manifest)
    batch_status("completed", [anchor])
    with tempfile.TemporaryDirectory(prefix="reference-set-", dir=directory.parent) as scratch:
        async def generate(shot):
            refs_by_id = {r["view"]: r for r in manifest["images"]}
            parents = {p: refs_by_id[p]["sha256"] for p in shot.parents}
            local = {**state, "storage_path": str(Path(scratch) / shot.id),
                     "requested_reference_shots": shot_request(shot, parents)}
            local_directory = service.design_directory(local)
            refs = local_directory / "references"
            refs.mkdir(exist_ok=True)
            seed = {**manifest, "images": [r for r in manifest["images"]
                                          if r["view"] in {*shot.parents, shot.id, "overview"}]}
            for item in seed["images"]:
                origin = directory / item['path']
                if origin.is_file():
                    shutil.copy2(origin, refs / Path(item["path"]).name)
            atomic_json(refs / "manifest.json", seed)
            result = await request(local, shot, [directory / refs_by_id[p]["path"] for p in shot.parents])
            item = next(r for r in result["reference_images"] if r["view"] == shot.id)
            origin, target = local_directory / item["path"], directory / item["path"]
            if not target.exists() or origin.read_bytes() != target.read_bytes():
                if target.exists():
                    history = target.parent / "history"
                    history.mkdir(exist_ok=True)
                    shutil.copy2(target, history / f"{shot.id}-{hashlib.sha256(target.read_bytes()).hexdigest()}.png")
                temporary = target.with_suffix(".publishing.tmp")
                shutil.copy2(origin, temporary)
                temporary.replace(target)
            manifest["images"] = [r for r in manifest["images"] if r["view"] != shot.id] + [enrich(item, shot, parents)]
            done.add(shot.id)
            manifest["reference_contract"] = "car2lego3d.references.v2"
            manifest["expected_shots"] = [s.record() for s in shots]
            atomic_json(manifest_path, manifest)
            service.write_progress(state, f"reference_images:{shot.id}", 5 + round(len(done) / len(shots) * 30))
            batch_status("running", batch)

        while len(done) < len(shots):
            ready = [s for s in shots if s.id not in done and set(s.parents) <= done]
            if not ready:
                raise ValueError("Reference dependency graph stalled")
            # Wait for the entire batch, including retries, before starting
            # another group. The SDK slot lock also caps other worker processes.
            for start in range(0, len(ready), concurrency):
                batch = ready[start:start + concurrency]
                batch_index += 1
                batch_status("running", batch)
                results = await asyncio.gather(*(generate(s) for s in batch), return_exceptions=True)
                failures = [shot.id for shot, result in zip(batch, results) if isinstance(result, BaseException)]
                batch_status("failed" if failures else "completed", batch, failures)
                for result in results:
                    if isinstance(result, BaseException):
                        raise result
    manifest['images'] = [r for r in manifest['images'] if r['view'] in {s.id for s in shots}]
    atomic_json(manifest_path, manifest)
    return {"reference_brief": manifest["brief"], "reference_images": manifest["images"]}


async def generate_references(service, state, atomic_json, attempts=6, retry_delay=15):
    """Keep the upstream generator unchanged and isolate concurrent manifests."""
    async def generate_one(local_state, view):
        for attempt in range(1, attempts + 1):
            try:
                return await service.ReferenceImageService().generate(local_state, only={view})
            except Exception as error:
                details = service.failure_details(error, "reference", attempt=attempt)
                print(json.dumps({**details, "view": view}), flush=True)
                if not service.transient_model_error(error) or attempt == attempts:
                    raise
                await asyncio.sleep(min(retry_delay * attempt, 90))

    # Every elevation must use the same completed overview and appearance brief.
    await generate_one(state, "overview")
    directory = service.design_directory(state)
    manifest_path = directory / "references/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    completed = 0

    def checkpoint(stage, percent):
        if state.get("checkpoint_progress"):
            state["checkpoint_progress"](stage, 5 + round(completed / len(VIEW_SHOTS) * 30))

    # Upstream generate() writes its own manifest and progress file. Give each
    # request a private directory; publish results serially in this event loop.
    with tempfile.TemporaryDirectory(prefix="reference-workers-", dir=directory.parent) as scratch:
        async def generate_view(view):
            nonlocal completed
            local_state = {**state, "storage_path": str(Path(scratch) / view),
                           "checkpoint_progress": checkpoint}
            local_directory = service.design_directory(local_state)
            refs = local_directory / "references"
            refs.mkdir(exist_ok=True)
            seed = {**manifest, "images": [ref for ref in manifest["images"]
                                          if ref["view"] in {"overview", view}]}
            for ref in seed["images"]:
                origin = directory / ref["path"]
                if origin.is_file():
                    shutil.copy2(origin, refs / Path(ref["path"]).name)
            atomic_json(refs / "manifest.json", seed)
            result = await generate_one(local_state, view)
            ref = next(item for item in result["reference_images"] if item["view"] == view)
            origin, destination = local_directory / ref["path"], directory / ref["path"]
            if not destination.is_file() or origin.read_bytes() != destination.read_bytes():
                if destination.is_file():
                    history = destination.parent / "history"
                    history.mkdir(exist_ok=True)
                    old_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
                    shutil.copy2(destination, history / f"{view}-{old_hash}.png")
                temporary = destination.with_suffix(".parallel.tmp")
                shutil.copy2(origin, temporary)
                temporary.replace(destination)
            manifest["images"] = [item for item in manifest["images"] if item["view"] != view] + [ref]
            atomic_json(manifest_path, manifest)
            completed += 1
            service.write_progress(state, "reference_images", 5 + round(completed / len(VIEW_SHOTS) * 30))
            checkpoint("reference_images", 0)

        # Wait for every request, including successes after another view fails.
        # Their checkpoints remain reusable on the next run.
        results = await asyncio.gather(*(generate_view(view) for view in VIEW_SHOTS), return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result
    return {"reference_brief": manifest["brief"], "reference_images": manifest["images"]}


def shot_instructions(view):
    directions = {
        "front": "exact straight front elevation, looking at the front bumper",
        "back": "exact straight rear elevation, looking at the rear bumper",
        "left": "exact left side elevation, front of the car toward image LEFT",
        "right": "exact right side elevation, front of the car toward image RIGHT",
    }
    return (
        f"ONE complete car in {directions[view]}. Orthographic camera at wheel hub height, "
        "zero elevation, no perspective or three-quarter view. Keep wheels straight, doors and "
        "all panels closed. Include the whole car, roof, tyres, mirrors and bumpers, with a "
        "15 percent clean margin. Plain white background, uniform studio light, minimal shadow. "
        "This image is one labelled input of a four-view 3D reconstruction. Preserve EXACTLY "
        "the same vehicle identity, paint, door count, wheel style and body proportions as the "
        "overview and source photo. Output one view only; no panels, contact sheet, close-ups, "
        "captions or measurement annotations. Do not mirror the left image to create the right side."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    source = args.source_root.resolve()
    state = json.loads(args.request.read_text(encoding="utf-8"))
    storage = Path(state["storage_path"]).resolve()
    state_storage.set(str(storage / "diagnostics"))
    if storage.is_relative_to(source) or state["design_id"] != "car2lego":
        raise ValueError("All generated files must stay outside the source project.")
    inherited = dotenv_values(source / "backend/.env")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_IMAGE_MODEL",
                "IMAGE_QUALITY", "IMAGE_SIZE", "IMAGE_TIMEOUT"):
        if inherited.get(key) and not os.environ.get(key):
            os.environ[key] = inherited[key]
    os.environ["STORAGE_PATH"] = str(storage)
    sys.path.insert(0, str(source / "backend"))
    from app.services import reference_images as service
    from app.services.assembly_v3.jobs import atomic_json
    if not service.settings.openai_image_model.startswith("gpt-image-"):
        raise ValueError("The source configuration must select a GPT Image model.")
    shots = reference_plan(state["make"] + " " + state["model"])
    context, prompts = configure_shots(service, shots)
    calls = []
    state["consume_call"] = lambda kind: calls.append(kind)
    state["checkpoint_progress"] = lambda stage, percent: print(json.dumps({"stage": stage, "progress": percent}), flush=True)
    try:
        result = asyncio.run(generate_reference_set(service, state, atomic_json, shots, context, prompts))
    except Exception as error:
        print(json.dumps(service.failure_details(error, "reference")), flush=True)
        return 1
    atomic_json(storage / "car2lego/service-record.json", {
        "model": service.settings.openai_image_model, "quality": service.settings.image_quality,
        "size": service.settings.image_size, "calls": calls, "reference_images": result["reference_images"],
        "source_modified": False, "reconstruction_views": [s.record() for s in shots],
        "dispatch": {"anchor_first": True, "view_concurrency": IMAGE_CONCURRENCY,
                     "batch_size": IMAGE_CONCURRENCY, "wait_for_batch_completion": True,
                     "global_image_concurrency": IMAGE_CONCURRENCY, "retry_attempts_per_view": 6},
        "view_overrides": {s.id: s.instructions() for s in shots}})
    print(json.dumps({"model": service.settings.openai_image_model, "calls": calls, "status": "completed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
