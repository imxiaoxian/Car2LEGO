"""Canonical scene in LDraw coordinates: X right, Y down, Z rearward."""

import hashlib
import json
from typing import Literal

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field, model_validator

IDENTITY = (1., 0., 0., 0., 1., 0., 0., 0., 1.)


class Transform(BaseModel):
    position: tuple[float, float, float] = (0., 0., 0.)
    rotation: tuple[float, float, float, float, float, float, float, float, float] = IDENTITY

    @model_validator(mode="after")
    def rigid(self):
        matrix = np.asarray(self.rotation).reshape(3, 3)
        if not np.isfinite([*self.position, *self.rotation]).all():
            raise ValueError("Nonfinite transform")
        if not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(matrix), 1, atol=1e-5):
            raise ValueError("Only proper rigid rotations are allowed; scaled/reflected LEGO parts are invalid")
        return self


class PartInstance(BaseModel):
    id: str
    part_num: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.dat$")
    color_id: int = Field(ge=0)
    module: str
    transform: Transform
    feature: str = ""


class Module(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    depends_on: list[str] = Field(default_factory=list)
    structural: bool = False
    recipe_version: str = "f40-1"


class Connection(BaseModel):
    a: str
    b: str
    port_a: str
    port_b: str
    kind: str
    evidence: str


class Joint(BaseModel):
    id: str
    kind: Literal["revolute", "prismatic"] = "revolute"
    parent: str
    child: str
    pivot: tuple[float, float, float]
    axis: tuple[float, float, float]
    limits: tuple[float, float]
    capability: str
    mounting_parts: tuple[str, str] | None = None
    implemented: bool = False

    @model_validator(mode="after")
    def valid_axis(self):
        if not np.isfinite([*self.pivot, *self.axis, *self.limits]).all() or not np.isclose(np.linalg.norm(self.axis), 1):
            raise ValueError("Joint requires a finite unit axis")
        if self.limits[0] > self.limits[1]:
            raise ValueError("Invalid joint limits")
        return self


class BuildStep(BaseModel):
    index: int = Field(ge=1)
    module: str
    parts: list[str]
    insertion_axis: tuple[float, float, float] = (0., 1., 0.)


class AssemblyScene(BaseModel):
    version: Literal["assembly_v3"] = "assembly_v3"
    design_id: str
    vehicle: dict
    scale: str = Field(pattern=r"^1:(38|24|16|12)$")
    specifications: dict
    target_ldu: dict[str, float]
    parts: list[PartInstance]
    modules: list[Module]
    connections: list[Connection] = Field(default_factory=list)
    joints: list[Joint] = Field(default_factory=list)
    steps: list[BuildStep] = Field(default_factory=list)
    planning: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def references(self):
        ids = [p.id for p in self.parts]
        module_ids = [m.id for m in self.modules]
        if len(set(ids)) != len(ids) or len(set(module_ids)) != len(module_ids):
            raise ValueError("Duplicate scene identifiers")
        graph = nx.DiGraph()
        graph.add_nodes_from(module_ids)
        for module in self.modules:
            for dependency in module.depends_on:
                if dependency not in module_ids:
                    raise ValueError("Missing dependency")
                graph.add_edge(dependency, module.id)
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("Cyclic module dependencies")
        if any(p.module not in module_ids for p in self.parts):
            raise ValueError("Part refers to missing module")
        if any(c.a not in ids or c.b not in ids or c.a == c.b for c in self.connections):
            raise ValueError("Invalid connection edge")
        if any(j.parent not in module_ids or j.child not in module_ids for j in self.joints):
            raise ValueError("Invalid joint module")
        step_ids = [p for step in self.steps for p in step.parts]
        if len(step_ids) != len(set(step_ids)) or set(step_ids) != set(ids):
            raise ValueError("Each part must occur in exactly one build step")
        if [s.index for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("Build steps must be sequential")
        owners = {p.id: p.module for p in self.parts}
        if any(s.module not in module_ids or any(owners.get(pid) != s.module for pid in s.parts) for s in self.steps):
            raise ValueError("Step/module mismatch")
        return self

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()

    def placements(self) -> list[dict]:
        return [dict(part_num=p.part_num, color_id=p.color_id, x=p.transform.position[0],
                     y=-p.transform.position[1], z=p.transform.position[2], mirror=False,
                     rotation=" ".join(f"{n:.8g}" for n in p.transform.rotation)) for p in self.parts]

    def dependency_closure(self, module: str) -> set[str]:
        """Modules invalidated by a local repair, including downstream dependents."""
        graph = nx.DiGraph()
        graph.add_nodes_from(m.id for m in self.modules)
        for m in self.modules:
            graph.add_edges_from((dep, m.id) for dep in m.depends_on)
        if module not in graph:
            raise ValueError("Unknown module")
        return {module, *nx.descendants(graph, module)}

    def module_hashes(self) -> dict[str, str]:
        return {m.id: hashlib.sha256(json.dumps([p.model_dump() for p in self.parts if p.module == m.id],
                                               sort_keys=True).encode()).hexdigest() for m in self.modules}
