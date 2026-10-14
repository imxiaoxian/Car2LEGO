"""Vehicle measurements with units, provenance and conservative conflict handling."""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from app.config import settings


FIELDS = {
    "length": ("mm", "overall length", "车身长度"),
    "width": ("mm", "body width excluding mirrors", "车身宽度（不含后视镜）"),
    "height": ("mm", "overall height", "车身高度"),
    "wheelbase": ("mm", "distance between axle centres", "轴距"),
    "front_track": ("mm", "front wheel centre to centre", "前轮距"),
    "rear_track": ("mm", "rear wheel centre to centre", "后轮距"),
    "front_tyre_diameter": ("mm", "nominal unloaded outside diameter", "前轮胎外径"),
    "rear_tyre_diameter": ("mm", "nominal unloaded outside diameter", "后轮胎外径"),
    "front_tyre_width": ("mm", "nominal tyre section width", "前轮胎宽度"),
    "rear_tyre_width": ("mm", "nominal tyre section width", "后轮胎宽度"),
    "front_rim_diameter": ("mm", "rim bead seat diameter", "前轮毂直径"),
    "rear_rim_diameter": ("mm", "rim bead seat diameter", "后轮毂直径"),
    "door_length": ("mm", "closed front door longitudinal extent", "车门长度"),
    "door_height": ("mm", "closed front door overall height including glass", "车门高度"),
    "door_opening_angle": ("deg", "angle from fully closed door", "车门开启角"),
    "windshield_width": ("mm", "front glass maximum straight line width", "前风挡宽度"),
    "windshield_height": ("mm", "front glass straight line slant height", "前风挡斜高"),
    "windshield_rake": ("deg", "front glass inclination above horizontal", "前风挡倾角（相对水平面）"),
    "seat_width": ("mm", "front seat maximum width", "座椅宽度"),
    "engine_length": ("mm", "engine envelope longitudinal extent", "发动机长度"),
    "engine_width": ("mm", "engine envelope transverse extent", "发动机宽度"),
    "engine_height": ("mm", "engine envelope vertical extent", "发动机高度"),
}
OVERALL = ("length", "width", "height", "wheelbase")
SOURCE_RANK = {"manufacturer": 5, "repair_manual": 4, "homologation": 4,
               "measurement": 4, "database": 3, "user": 2, "model_estimate": 0}


def vehicle_key(make: str, model: str, year: int | None) -> str:
    identity = [re.sub(r"[^\w]", "", value.casefold()) for value in (make, model)]
    return hashlib.sha256(json.dumps([*identity, year]).encode()).hexdigest()


class PhysicalMeasurement(BaseModel):
    name: str
    value: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal["mm", "cm", "m", "in", "deg", "rad"] = "mm"
    method: Literal["documented", "measured", "derived", "estimated"] = "documented"
    source_url: str | None = None
    source_kind: Literal["manufacturer", "repair_manual", "homologation", "measurement", "database", "user", "model_estimate"] = "user"
    source_status: Literal["fetched", "provided", "unverified"] = "unverified"
    vehicle_match: Literal["exact", "generation", "unconfirmed", "mismatch"] = "unconfirmed"
    year_start: int | None = Field(default=None, ge=1886, le=2100)
    year_end: int | None = Field(default=None, ge=1886, le=2100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: str = Field(default="", max_length=1200)
    definition: str = ""
    width_reference: Literal["body", "including_mirrors", "unspecified"] = "unspecified"
    angle_reference: Literal["horizontal", "vertical", "closed"] | None = None
    derivation: str | None = None

    @model_validator(mode="after")
    def canonical(self):
        if self.name not in FIELDS:
            raise ValueError("Unsupported vehicle measurement: " + self.name)
        canonical_unit, definition, _ = FIELDS[self.name]
        if self.source_url:
            parsed = urlparse(self.source_url)
            if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Measurement source must be a public HTTP(S) document URL")
        if self.year_start and self.year_end and self.year_start > self.year_end:
            raise ValueError("Invalid model year interval")
        if canonical_unit == "deg":
            if self.unit not in ("deg", "rad"):
                raise ValueError("An angle requires degrees or radians")
            if self.unit == "rad":
                self.value = math.degrees(self.value)
            if self.name == "windshield_rake":
                if self.angle_reference not in ("horizontal", "vertical") or self.value > 90:
                    raise ValueError("Windshield rake requires a horizontal/vertical datum and an angle <=90")
                if self.angle_reference == "vertical":
                    self.value = 90 - self.value
                self.angle_reference = "horizontal"
            elif self.angle_reference != "closed" or self.value > 180:
                raise ValueError("Door opening angle requires the closed-door datum and an angle <=180")
        else:
            factors = {"mm": 1, "cm": 10, "m": 1000, "in": 25.4}
            if self.unit not in factors:
                raise ValueError("A length requires a length unit")
            self.value *= factors[self.unit]
        self.unit = canonical_unit
        if self.value <= 0:
            raise ValueError("Canonical measurement must be positive")
        self.value = round(self.value, 5)
        if self.name == "width" and self.width_reference != "body":
            definition = "overall width including mirrors" if self.width_reference == "including_mirrors" else "width; mirror inclusion not specified"
        self.definition = self.definition or definition
        return self

    def grounded(self, year: int | None) -> bool:
        return bool(self.method != "estimated" and self.source_kind != "model_estimate"
                    and (self.name != "width" or self.width_reference == "body")
                    and self.source_url and self.evidence and self.source_status == "fetched"
                    and self.vehicle_match in ("exact", "generation") and self.confidence >= .7
                    and self.year_start is not None and self.year_end is not None
                    and (year is None or self.year_start <= year <= self.year_end))


class VehiclePhysicalProfile(BaseModel):
    version: Literal["vehicle_physics_v1"] = "vehicle_physics_v1"
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    year: int | None = Field(default=None, ge=1886, le=2100)
    measurements: list[PhysicalMeasurement] = Field(default_factory=list, max_length=500)
    sources: list[dict] = Field(default_factory=list)
    research: dict = Field(default_factory=dict)

    def resolved(self, scale: str = "1:38") -> dict:
        from .assembly_v3.requirements import requirements_for_scale
        denominator = int(scale.split(":")[1])
        if denominator <= 0:
            raise ValueError("Invalid scale")
        selected, conflicts = {}, []
        scopes = sorted({(m.year_start, m.year_end) for m in self.measurements
                         if m.grounded(self.year)})
        # With no requested year, incompatible source generations must not be mixed.
        ambiguous_generation = self.year is None and bool(scopes) and max(s[0] for s in scopes) > min(s[1] for s in scopes)
        for name in FIELDS:
            candidates = [m for m in self.measurements if m.name == name and m.vehicle_match != "mismatch"
                          and (self.year is None or m.year_start is None or m.year_start <= self.year)
                          and (self.year is None or m.year_end is None or m.year_end >= self.year)]
            if not candidates:
                continue
            candidates.sort(key=lambda m: (m.grounded(self.year), SOURCE_RANK[m.source_kind], m.confidence), reverse=True)
            winner = candidates[0]
            grounded = [m for m in candidates if m.grounded(self.year)]
            conflict = any(abs(m.value - winner.value) > (0.5 if winner.unit == "deg" else max(1., winner.value * .01))
                           for m in grounded)
            if conflict:
                conflicts.append({"name": name, "values": [m.model_dump() for m in grounded]})
            selected[name] = winner.model_dump() | {"grounded": winner.grounded(self.year) and not conflict and not ambiguous_generation,
                "conflicted": conflict, "target_ldu": round(winner.value / denominator / .4, 4) if winner.unit == "mm" else None,
                "target_model_mm": round(winner.value / denominator, 4) if winner.unit == "mm" else None}
        # Research can query reserved ratios, which have no assembly policy yet.
        try:
            policy = requirements_for_scale(scale)
        except ValueError:
            policy = None
        required = policy["required_measurements"] if policy else list(OVERALL)
        recommended = policy["recommended_measurements"] if policy else []
        return {"version": self.version, "vehicle": {"make": self.make, "model": self.model, "year": self.year},
                "scale": scale, "measurements": selected, "conflicts": conflicts,
                "requirements_version": policy["version"] if policy else None,
                "required_measurements": required, "recommended_measurements": recommended,
                "missing_required": [n for n in required if not selected.get(n, {}).get("grounded")],
                "missing_recommended": [n for n in recommended if not selected.get(n, {}).get("grounded")],
                "missing": [name for name in FIELDS if name not in selected], "sources": self.sources,
                "overall_grounded": all(selected.get(n, {}).get("grounded", False) for n in OVERALL),
                "research": self.research,
                "generation_status": "ambiguous" if ambiguous_generation else "source_scoped" if scopes and self.year is None else "requested_year" if self.year is not None else "unknown",
                "source_year_ranges": [{"start": start, "end": end} for start, end in scopes]}


def profile_path(make: str, model: str, year: int | None, storage: str | Path | None = None) -> Path:
    return Path(storage or settings.storage_path) / "vehicle_specs" / (vehicle_key(make, model, year) + ".json")


def load_profile(make: str, model: str, year: int | None = None, storage=None) -> VehiclePhysicalProfile:
    path = profile_path(make, model, year, storage)
    profile = VehiclePhysicalProfile.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else VehiclePhysicalProfile(make=make, model=model, year=year)
    if vehicle_key(profile.make, profile.model, profile.year) != vehicle_key(make, model, year):
        raise ValueError("Vehicle specification identity mismatch")
    return profile


def save_profile(profile: VehiclePhysicalProfile, storage=None) -> None:
    from .assembly_v3.jobs import atomic_json
    atomic_json(profile_path(profile.make, profile.model, profile.year, storage), profile.model_dump())


def physical_prompt(resolved: dict) -> str:
    return json.dumps({"measurements": resolved.get("measurements", {}), "missing": resolved.get("missing", []),
        "required_measurements": resolved.get("required_measurements", []), "missing_required": resolved.get("missing_required", []),
        "conflicts": resolved.get("conflicts", []),
        "rules": "Only grounded, non-conflicting values constrain geometry. Angles retain degrees at every scale. Missing details stay unknown. Synthetic images cannot supply measured facts."}, ensure_ascii=True)
