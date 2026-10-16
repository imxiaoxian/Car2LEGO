"""One recursive geometry resolver for native and packaged LDraw parts."""
from pathlib import Path
import json

import numpy as np

from .common import digest
from .ldraw_document import Document, safe_name, parse_color


class PartLibrary:
    def __init__(self, root, packages=()):
        self.root = Path(root).resolve()
        self.packages = tuple(Path(p).resolve() for p in packages)
        self.used = {}
        self._cache = {}

    def resolve(self, name):
        name = safe_name(name)
        roots = [*self.packages, self.root, self.root / 'UnOfficial']
        for root in roots:
            for folder in ('parts', 'p'):
                path = (root / folder / name).resolve()
                if path.is_relative_to(root) and path.is_file():
                    self.used[str(path)] = digest(path)
                    return path
        raise FileNotFoundError('Missing LDraw geometry: ' + name)

    def triangles(self, name, stack=()):
        name = safe_name(name)
        if name in stack:
            raise ValueError('Cyclic LDraw part dependency: ' + name)
        cached = self._cache.get(name)
        if cached and all(Path(path).is_file() and digest(path) == sha for path, sha in cached[2].items()):
            self.used.update(cached[2])
            return cached[:2]
        path = self.resolve(name)
        dependencies = {str(path): digest(path)}
        triangles, colors = [], []
        for line in path.read_text(encoding='utf-8-sig', errors='strict').splitlines():
            tokens = line.split()
            if not tokens or tokens[0] == '0':
                continue
            ref = Document.parse_line(line, geometry=True)
            if tokens[0] in {'2', '5'}:
                continue
            if tokens[0] == '1':
                child, color = self.triangles(ref.name, (*stack, name))
                dependencies.update(self._cache[ref.name][2])
                transform = ref.matrix()
                triangles.extend(child @ transform[:3, :3].T + transform[:3, 3])
                colors.extend(np.where(color == 16, ref.color, color).tolist())
            elif tokens[0] in {'3', '4'}:
                vertices = np.asarray(tokens[2:], dtype=float).reshape(-1, 3)
                for indices in ((0, 1, 2),) if tokens[0] == '3' else ((0, 1, 2), (0, 2, 3)):
                    triangles.append(vertices[list(indices)])
                    colors.append(parse_color(tokens[1]))
            else:
                raise ValueError('Unexpected LDraw record in ' + name)
        result = np.asarray(triangles, dtype=float).reshape(-1, 3, 3), np.asarray(colors, dtype=int)
        self._cache[name] = (*result, dependencies)
        self.used.update(dependencies)
        return result

    def instance(self, row):
        triangles, colors = self.triangles(row['part'] if row['part'].endswith('.dat') else row['part'] + '.dat')
        rotation = np.asarray(row['rotation']).reshape(3, 3)
        position = np.asarray(row['position'])
        if (not np.isfinite(rotation).all() or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5)
                or position.shape != (3,) or not np.isfinite(position).all()):
            raise ValueError('An assembly instance stretches a native part')
        return triangles @ rotation.T + position, np.where(colors == 16, row['color'], colors)

    def geometry(self, rows):
        result = {}
        for row in rows:
            name = row['part'].removesuffix('.dat') + '.dat'
            if name in result:
                continue
            triangles, colors = self.triangles(name)
            # Existing desktop viewer consumes native LDU positions and face color groups.
            result[name] = [dict(color_id=int(color), positions=triangles[colors == color].reshape(-1).tolist())
                            for color in np.unique(colors)]
        return result

    def dependency_record(self):
        return dict(schema='car2lego3d.part-dependencies.v1', files=[
            dict(file=path, sha256=sha) for path, sha in sorted(self.used.items())],
            missing_geometry=[], physical_verified=False)


def assembly_library(assembly_path, root):
    from .part_package import validate_package
    assembly_path = Path(assembly_path).resolve()
    assembly = json.loads(assembly_path.read_text(encoding='utf-8'))
    packages = []
    for relative in assembly.get('part_packages', []):
        package = (assembly_path.parent / relative).resolve()
        if not package.is_relative_to(assembly_path.parent):
            raise ValueError('Part package escaped assembly directory')
        validate_package(package)
        packages.append(package)
    return PartLibrary(root, packages)
