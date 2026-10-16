"""Versioned Studio custom parts with explicit connector provenance."""
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from .common import digest, write_json
from .ldraw_document import safe_name


def validate_package(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'car2lego3d.part-package.v1':
        raise ValueError('Unsupported custom-parts manifest')
    seen = set()
    for item in manifest['files']:
        relative = safe_name(item['file'])
        path = (directory / relative).resolve()
        if relative in seen or not path.is_relative_to(directory) or digest(path) != item['sha256']:
            raise ValueError('Duplicate, escaped or changed custom-part dependency')
        seen.add(relative)
    part_ids = set()
    for part in manifest['parts']:
        name = safe_name(part['id'])
        if name in part_ids or not name.startswith('c2l-') or f'parts/{name}' not in seen:
            raise ValueError('Custom parts require namespaced IDs and geometry')
        part_ids.add(name)
        if part.get('connectivity_file') not in seen:
            raise ValueError('Missing custom-part connectivity')
        connector = directory / part['connectivity_file']
        if not part.get('native_connector_base') or digest(connector) != part.get('connector_source_sha256'):
            raise ValueError('Unverified native connector provenance')
    return manifest


def package_parts(directory):
    directory = Path(directory)
    manifest = validate_package(directory)
    target = directory.parent / 'custom-parts.zip'
    with ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
        archive.write(directory / 'manifest.json', 'manifest.json')
        for item in manifest['files']:
            archive.write(directory / item['file'], item['file'])
    return target


def install_parts(directory, studio_custom_directory):
    """Install namespaced dependencies; never overwrite a different user asset."""
    directory, target = Path(directory), Path(studio_custom_directory).resolve()
    manifest = validate_package(directory)
    planned = [(directory / item['file'], target / item['file']) for item in manifest['files']]
    for source, destination in planned:
        if not destination.resolve().is_relative_to(target):
            raise ValueError('Installation path escaped custom directory')
        if destination.exists() and digest(source) != digest(destination):
            raise ValueError(f'Existing custom part differs: {destination.name}')
    for source, destination in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
    return dict(installed_files=len(planned), target=str(target), studio_reload_required=True)


def plate_glass_package(directory, library):
    """A new pane on an untouched native 1x2 plate base; native ports stay unchanged."""
    directory, library = Path(directory), Path(library)
    name = 'c2l-p0-glass-v1.dat'
    parts = directory / 'parts'
    connectors = directory / 'connectivity'
    parts.mkdir(parents=True, exist_ok=True)
    connectors.mkdir(exist_ok=True)
    # The pane rises along the plate's back edge, clear of both native studs.
    vertices = [(-20,0,8),(20,0,8),(20,-40,8),(-20,-40,8),
                (-20,0,10),(20,0,10),(20,-40,10),(-20,-40,10)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    lines = ['0 Car2LEGO P0 glass on native plate base', '0 Name: '+name,
             '0 !LDRAW_ORG Unofficial_Part', '0 BFC CERTIFY CCW',
             '1 16 0 0 0 1 0 0 0 1 0 0 0 1 3023.dat']
    for face in faces:
        lines.append('4 16 ' + ' '.join(str(v) for i in face for v in vertices[i]))
    (parts / name).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    connector = connectors / name.replace('.dat', '.conn')
    shutil.copyfile(library / 'connectivity/3023.conn', connector)
    files = [dict(file=str(p.relative_to(directory)).replace('\\','/'),sha256=digest(p))
             for p in (parts/name, connector)]
    write_json(directory/'manifest.json',dict(schema='car2lego3d.part-package.v1',version=1,
        parts=[dict(id=name,kind='custom',native_connector_base='3023.dat',
            connectivity_file='connectivity/'+connector.name,
            connector_source_sha256=digest(library/'connectivity/3023.conn'),
            native_base_transform=[1,0,0,0,1,0,0,0,1],
            collision_status='unverified',studio_open_verified=False)],files=files))
    return name
