import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from car2lego3d.common import ROOT, write_json
from car2lego3d.reference_plan import Shot, reference_plan
from car2lego3d.references import load_references

spec = importlib.util.spec_from_file_location('rich_reference_worker', ROOT / 'scripts/car2lego_reference_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class Service:
    def __init__(self):
        self.calls = Counter()
        self.active = self.peak = 0
        self.fail = set()
        self.ReferenceImageService = lambda: SimpleNamespace(generate=self.generate)

    def design_directory(self, state):
        directory = Path(state['storage_path']) / 'car2lego'
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def transient_model_error(self, error):
        return False

    def failure_details(self, error, stage, attempt):
        return dict(error=str(error), attempt=attempt)

    def write_progress(self, *args):
        pass

    async def generate(self, state, only):
        name, = only
        directory = self.design_directory(state)
        path = directory / 'references/manifest.json'
        path.parent.mkdir(exist_ok=True)
        manifest = json.loads(path.read_text()) if path.exists() else dict(brief={}, images=[])
        request = state['requested_reference_shots'][0]
        cached = next((r for r in manifest['images'] if r['view'] == name), None)
        if cached and (directory / cached['path']).is_file():
            actual = hashlib.sha256((directory / cached['path']).read_bytes()).hexdigest()
            if cached['sha256'] == actual and cached['request'] == request:
                return dict(reference_images=manifest['images'])
        self.calls[name] += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(.005)
            if name in self.fail:
                raise ValueError('test failure')
            image = path.parent / (name + '.png')
            image.write_bytes(f'{name}-{self.calls[name]}'.encode())
            ref = dict(view=name, path='references/' + image.name,
                       sha256=hashlib.sha256(image.read_bytes()).hexdigest(), request=request)
            manifest['images'] = [r for r in manifest['images'] if r['view'] != name] + [ref]
            write_json(path, manifest)
            return dict(reference_images=manifest['images'])
        finally:
            self.active -= 1


def run(service, directory, shots):
    return asyncio.run(worker.generate_reference_set(service,
        dict(storage_path=str(directory), design_id='car2lego'), write_json, shots, attempts=1))


def test_dependency_cache_and_bounded_concurrency(tmp_path):
    service = Service()
    shots = reference_plan('Countach')
    run(service, tmp_path, shots)
    assert len(shots) == 29 and service.peak == 5
    initial = service.calls.copy()
    run(service, tmp_path, shots)
    assert service.calls == initial
    (tmp_path / 'car2lego/references/left.png').unlink()
    run(service, tmp_path, shots)
    assert service.calls['left'] == 2
    assert service.calls['door_left_open'] == 2
    assert service.calls['scissor_hinge'] == 2
    assert service.calls['right'] == 1 and service.calls['overview'] == 1


def test_provider_concurrency_limit_cannot_be_exceeded(tmp_path):
    with pytest.raises(ValueError, match='between 1 and 5'):
        asyncio.run(worker.generate_reference_set(Service(),
            dict(storage_path=str(tmp_path), design_id='car2lego'), write_json,
            reference_plan(), concurrency=6))


@pytest.mark.parametrize('retry', [False, True])
def test_next_batch_waits_for_slowest_request_including_retries(tmp_path, retry):
    class TemporaryFailure(Exception):
        pass

    class GatedService(Service):
        def __init__(self):
            super().__init__()
            self.started = set()
            self.completed = set()
            self.release_slow = asyncio.Event()
            self.slow_started = asyncio.Event()
            self.fast_completed = asyncio.Event()
            self.slow_attempts = 0

        def transient_model_error(self, error):
            return isinstance(error, TemporaryFailure)

        async def generate(self, state, only):
            name, = only
            self.started.add(name)
            if name == 'top':
                self.slow_attempts += 1
                if retry and self.slow_attempts == 1:
                    raise TemporaryFailure('retry this image')
                self.slow_started.set()
                await self.release_slow.wait()
            result = await super().generate(state, only)
            self.completed.add(name)
            if {'front', 'back', 'left', 'right'} <= self.completed:
                self.fast_completed.set()
            return result

    async def exercise():
        service = GatedService()
        task = asyncio.create_task(worker.generate_reference_set(service,
            dict(storage_path=str(tmp_path), design_id='car2lego'), write_json,
            reference_plan(), attempts=2, retry_delay=0))
        try:
            await service.slow_started.wait()
            await service.fast_completed.wait()
            # Give freed semaphore slots time to admit another request if the
            # scheduler lacks a batch barrier. The fifth image is still held.
            await asyncio.sleep(.03)
            assert service.started == {'overview', 'front', 'back', 'left', 'right', 'top'}
            assert service.slow_attempts == (2 if retry else 1)
            dispatch = json.loads((tmp_path / 'car2lego/reference-dispatch.json').read_text())
            assert dispatch['status'] == 'running' and dispatch['batch_index'] == 2
            assert dispatch['views'] == ['front', 'back', 'left', 'right', 'top']
            assert set(dispatch['completed_views']) == {'overview', 'front', 'back', 'left', 'right'}
            assert dispatch['batches'][-1]['completed_views'] == ['front', 'back', 'left', 'right']
            assert len(dispatch['batches']) == 2
            service.release_slow.set()
            result = await task
            assert len(result['reference_images']) == len(reference_plan())
            dispatch = json.loads((tmp_path / 'car2lego/reference-dispatch.json').read_text())
            assert dispatch['status'] == 'completed'
            assert len(dispatch['completed_views']) == len(reference_plan())
            batches = dispatch['batches']
            assert all(b['status'] == 'completed' and len(b['views']) <= 5 for b in batches)
            assert all(set(b['views']) == set(b['completed_views']) for b in batches)
            assert all(datetime.fromisoformat(previous['finished_at']) <= datetime.fromisoformat(next_['started_at'])
                       for previous, next_ in zip(batches, batches[1:]))
        finally:
            service.release_slow.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(asyncio.wait_for(exercise(), timeout=5))


def test_completed_siblings_survive_failure(tmp_path):
    service = Service()
    service.fail.add('left')
    shots = reference_plan()
    with pytest.raises(ValueError, match='test failure'):
        run(service, tmp_path, shots)
    assert service.calls['right'] == 1
    assert service.calls['top'] == 1
    assert service.calls['front_left'] == 0
    dispatch = json.loads((tmp_path / 'car2lego/reference-dispatch.json').read_text())
    assert dispatch['status'] == 'failed' and dispatch['failed_views'] == ['left']
    assert len(dispatch['batches']) == 2
    assert dispatch['batches'][-1]['status'] == 'failed'
    assert set(dispatch['batches'][-1]['completed_views']) == {'front', 'back', 'right', 'top'}
    service.fail.clear()
    run(service, tmp_path, shots)
    assert service.calls['right'] == 1 and service.calls['left'] == 2


def test_rich_manifest_rejects_stale_parent_and_keeps_module_details(tmp_path):
    records = {}
    for i, shot in enumerate(reference_plan()):
        file = tmp_path / f'{shot.id}.png'
        Image.new('RGB', (20, 20), (i, 30, 40)).save(file)
        records[shot.id] = {**shot.record(), 'file': file.name,
                            'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    for record in records.values():
        record['parents'] = {p: records[p]['sha256'] for p in record['parents']}
    path = tmp_path / 'views.json'
    manifest = dict(schema_version=2, shots=records, expected_shots=[s.record() for s in reference_plan()],
                    views={v: records[v] for v in ('front', 'back', 'left', 'right')})
    write_json(path, manifest)
    _, images = load_references(path, ['doors'])
    assert {'overview', 'door_left_open', 'door_right_closed'} <= images.keys()
    records['door_left_open']['parents']['left'] = 'bad'
    write_json(path, manifest)
    with pytest.raises(ValueError, match='Stale parent'):
        load_references(path)
