"""Validate rich reference sets while retaining legacy reconstruction manifests."""
import json
from pathlib import Path

from PIL import Image

from .common import digest


def load_references(path, modules=None):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding='utf-8'))
    version = manifest.get('schema_version')
    if version not in {1, 2}:
        raise ValueError('Unsupported reference schema')
    records = manifest.get('shots') if version == 2 else manifest.get('views')
    if not isinstance(records, dict) or not records:
        raise ValueError('Reference set is empty')
    if not {'front', 'back', 'left', 'right'} <= set(records):
        raise ValueError('Reference set requires all four elevations')
    if version == 2:
        expected = {s['id'] for s in manifest.get('expected_shots', [])}
        if not expected or set(records) != expected:
            raise ValueError('Reference set does not match its expected camera plan')
        if any(manifest.get('views', {}).get(v) != records.get(v) for v in ('front', 'back', 'left', 'right')):
            raise ValueError('Legacy view projection differs from rich reference set')
    paths, hashes = {}, set()
    for name, item in records.items():
        source = (path.parent / item['file']).resolve()
        if not source.is_relative_to(path.parent):
            raise ValueError('Reference file escaped manifest directory')
        if not source.is_file() or digest(source) != item['sha256']:
            raise ValueError(f'Reference checksum mismatch: {name}')
        if item['sha256'] in hashes:
            raise ValueError('Duplicate reference images cannot represent different cameras')
        hashes.add(item['sha256'])
        with Image.open(source) as image:
            image.verify()
        if version == 2:
            for parent, expected_hash in item.get('parents', {}).items():
                if parent not in records or records[parent]['sha256'] != expected_hash:
                    raise ValueError(f'Stale parent reference: {name}/{parent}')
        if modules is None or name == 'overview' or set(item.get('modules', [])) & set(modules):
            paths[name] = source
    return manifest, paths
