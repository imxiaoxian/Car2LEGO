"""Validated recursive LDraw documents shared by exporters and package readers."""
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import PurePosixPath

import numpy as np


def parse_color(value):
    return int(value, 16) if value.lower().startswith('0x') else int(value)


def color_token(value):
    return f'0x{value:07X}' if value >= 0x2000000 else str(value)


def safe_name(name):
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ":" in name or any(p in {"", "..", "."} for p in name.split("/")):
        raise ValueError(f"Unsafe LDraw dependency: {name}")
    return name.lower()


@dataclass(frozen=True)
class Reference:
    color: int
    position: tuple
    rotation: tuple
    name: str

    def matrix(self):
        matrix = np.eye(4)
        matrix[:3, :3] = np.array(self.rotation).reshape(3, 3)
        matrix[:3, 3] = self.position
        return matrix


class Document:
    def __init__(self, text):
        self.text = text
        self.sections = {}
        self.root = None
        current, outside, ended = None, [], False
        for line in text.splitlines():
            tokens = line.split()
            if tokens[:2] == ["0", "FILE"]:
                current = safe_name(" ".join(tokens[2:]))
                if current in self.sections:
                    raise ValueError("Duplicate MPD section")
                self.root = self.root or current
                self.sections[current] = []
                ended = False
            elif tokens[:2] == ["0", "NOFILE"]:
                current, ended = None, True
            elif current is not None:
                self.sections[current].append(line)
            elif not self.sections:
                outside.append(line)
            elif tokens and (tokens[0] != "0" or not ended):
                raise ValueError("LDraw geometry outside an MPD section")
        if self.root is None:
            self.root = "main.ldr"
            self.sections[self.root] = outside
        elif any(line.split() and line.split()[0] != "0" for line in outside):
            raise ValueError("Geometry before the MPD root")
        for name, lines in self.sections.items():
            for line in lines:
                self.parse_line(line, geometry=name.endswith(".dat"))
        visited, active = set(), set()

        def dependencies(name):
            if name in active:
                raise ValueError('Cyclic MPD reference')
            if name in visited:
                return
            active.add(name)
            for line in self.sections[name]:
                ref = self.parse_line(line, geometry=name.endswith('.dat'))
                if ref and ref.name in self.sections:
                    dependencies(ref.name)
            active.remove(name)
            visited.add(name)

        for name in self.sections:
            dependencies(name)
        # Expand now to reject recursion, missing submodels and empty roots.
        if not self.instances():
            raise ValueError("LDraw assembly has no parts")

    @staticmethod
    def parse_line(line, geometry=False):
        tokens = line.split()
        if not tokens or tokens[0] == "0":
            return None
        if tokens[0] == "1":
            if len(tokens) < 15:
                raise ValueError("Expected a full LDraw transform")
            color = parse_color(tokens[1])
            values = tuple(float(x) for x in tokens[2:14])
            if not all(math.isfinite(x) for x in values):
                raise ValueError("Non-finite LDraw transform")
            ref = Reference(color, values[:3], values[3:], safe_name(" ".join(tokens[14:])))
            if not geometry:
                rotation = np.array(ref.rotation).reshape(3, 3)
                if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5):
                    raise ValueError("Assembly instances cannot stretch standard parts")
            return ref
        if geometry and tokens[0] in {"2", "3", "4", "5"}:
            expected = {"2": 8, "3": 11, "4": 14, "5": 14}[tokens[0]]
            if len(tokens) != expected or not all(math.isfinite(float(x)) for x in tokens[2:]):
                raise ValueError("Malformed custom-part geometry")
            parse_color(tokens[1])
            return None
        raise ValueError("Unexpected geometry in an assembly")

    def instances(self):
        result = []

        def visit(name, transform, color, stack):
            if name in stack:
                raise ValueError("Cyclic MPD reference")
            for line in self.sections[name]:
                ref = self.parse_line(line, geometry=name.endswith(".dat"))
                if ref is None:
                    continue
                matrix = transform @ ref.matrix()
                actual_color = color if ref.color == 16 else ref.color
                if ref.name in self.sections and not ref.name.endswith(".dat"):
                    visit(ref.name, matrix, actual_color, (*stack, name))
                else:
                    if not ref.name.endswith(".dat"):
                        raise ValueError(f"Missing MPD submodel: {ref.name}")
                    result.append(dict(part=ref.name, color=actual_color,
                        position=matrix[:3, 3].tolist(), rotation=matrix[:3, :3].ravel().tolist(),
                        modules=list(stack) + [name], custom=ref.name in self.sections or ref.name.startswith('c2l-')))
                    if len(result) > 200000:
                        raise ValueError("Assembly exceeds 200000 expanded parts")
        visit(self.root, np.eye(4), 16, ())
        return result

    def signature(self):
        return [(name, tuple(line.strip() for line in lines if line.strip()))
                for name, lines in self.sections.items()]

    def flatten(self):
        lines = ["0 Car2LEGO_3D flattened assembly; custom dependencies require the parts package"]
        for item in self.instances():
            values = " ".join(f"{v:.10g}" for v in item["position"] + item["rotation"])
            lines.append(f"1 {color_token(item['color'])} {values} {item['part']}")
        return "\n".join(lines) + "\n"

    def inventory(self):
        counts = Counter((i["part"], i["color"], i["custom"]) for i in self.instances())
        return [dict(part=p, color=c, custom=custom, quantity=n)
                for (p, c, custom), n in sorted(counts.items())]
