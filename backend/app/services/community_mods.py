"""Community Mod System — like Steam Workshop for LEGO car modifications.

Users can:
  - Submit mod packs (LDraw parts + metadata + preview images)
  - Browse/search mods by category, car compatibility, rating
  - Rate and review mods
  - Install mods into their designs
  - Fork/remix existing mods

Mod Specification (MOD_SPEC v1.0):
  Each mod is a directory containing:
    mod.json        — Required: metadata manifest
    model.ldr       — Required: LDraw parts for this mod
    preview.png     — Required: 256x256 preview render
    decals/         — Optional: PNG decal files
    instructions.txt — Optional: installation notes
    changelog.md    — Optional: version history
"""

import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════
# MOD SPECIFICATION v1.0
# ═══════════════════════════════════════════════════════════════

MOD_SPEC_SCHEMA = {
    "$schema": "https://car2lego.dev/mod-spec/v1.0/schema.json",
    "title": "Car2LEGO Mod Specification v1.0",
    "description": "Standard format for community-contributed LEGO car modification packs.",
    "type": "object",
    "required": ["mod_id", "name", "version", "author", "category", "description"],
    "properties": {
        "mod_id": {
            "type": "string",
            "pattern": "^[a-z0-9_]+$",
            "description": "Unique mod identifier (lowercase, underscores). e.g., 'gt_wing_v2'"
        },
        "name": {"type": "string", "description": "Human-readable mod name"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "author": {"type": "string"},
        "author_email": {"type": "string", "format": "email"},
        "category": {
            "type": "string",
            "enum": [
                "aerodynamics", "wheels_stance", "exhaust", "body_kits",
                "interior", "lighting", "paint_finish", "performance",
                "engine_bay", "audio", "suspension", "custom"
            ]
        },
        "description": {"type": "string", "maxLength": 500},
        "long_description": {"type": "string", "maxLength": 5000},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "difficulty": {"type": "string", "enum": ["beginner", "easy", "medium", "hard", "expert"]},
        "estimated_parts": {"type": "integer", "minimum": 1},
        "estimated_cost_usd": {"type": "number", "minimum": 0},
        "compatible_body_styles": {
            "type": "array",
            "items": {"type": "string", "enum": ["sports_car", "suv", "sedan", "pickup", "hatchback", "wagon", "coupe", "convertible", "all"]}
        },
        "compatible_makes": {"type": "array", "items": {"type": "string"}},
        "preview_image": {"type": "string", "description": "Relative path to preview PNG"},
        "ldraw_file": {"type": "string", "description": "Relative path to model.ldr"},
        "decals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "target_part": {"type": "string"},
                    "description": {"type": "string"},
                }
            }
        },
        "dependencies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of mod_ids this mod depends on"
        },
        "incompatible_with": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of mod_ids this mod conflicts with"
        },
        "changelog": {"type": "string"},
        "license": {"type": "string", "default": "CC-BY-4.0"},
        "homepage": {"type": "string", "format": "uri"},
        "repository": {"type": "string", "format": "uri"},
    }
}


@dataclass
class CommunityMod:
    """A community-contributed modification pack."""
    mod_id: str
    name: str
    version: str
    author: str
    category: str
    description: str
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    estimated_parts: int = 10
    estimated_cost_usd: float = 0.0
    compatible_body_styles: list[str] = field(default_factory=lambda: ["all"])
    compatible_makes: list[str] = field(default_factory=list)
    long_description: str = ""
    preview_image: str = ""
    ldraw_file: str = ""
    decals: list[dict] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    incompatible_with: list[str] = field(default_factory=list)
    license: str = "CC-BY-4.0"

    # Runtime stats
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    # File paths (not serialized)
    _base_path: str = ""

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "CommunityMod":
        """Load a mod from its mod.json manifest."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        mod = cls(
            mod_id=data["mod_id"],
            name=data["name"],
            version=data["version"],
            author=data["author"],
            category=data["category"],
            description=data["description"],
            tags=data.get("tags", []),
            difficulty=data.get("difficulty", "medium"),
            estimated_parts=data.get("estimated_parts", 10),
            estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
            compatible_body_styles=data.get("compatible_body_styles", ["all"]),
            compatible_makes=data.get("compatible_makes", []),
            long_description=data.get("long_description", ""),
            preview_image=data.get("preview_image", ""),
            ldraw_file=data.get("ldraw_file", ""),
            decals=data.get("decals", []),
            dependencies=data.get("dependencies", []),
            incompatible_with=data.get("incompatible_with", []),
            license=data.get("license", "CC-BY-4.0"),
        )
        mod._base_path = str(Path(manifest_path).parent)
        return mod

    def to_manifest(self) -> dict:
        """Serialize to mod.json format."""
        return {
            "mod_id": self.mod_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "description": self.description,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "estimated_parts": self.estimated_parts,
            "estimated_cost_usd": self.estimated_cost_usd,
            "compatible_body_styles": self.compatible_body_styles,
            "compatible_makes": self.compatible_makes,
            "long_description": self.long_description,
            "preview_image": self.preview_image,
            "ldraw_file": self.ldraw_file,
            "decals": self.decals,
            "dependencies": self.dependencies,
            "incompatible_with": self.incompatible_with,
            "license": self.license,
        }

    def get_ldraw_content(self) -> str | None:
        """Read the mod's LDraw file content."""
        if not self.ldraw_file:
            return None
        path = Path(self._base_path) / self.ldraw_file
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def validate(self) -> list[str]:
        """Validate mod completeness. Returns list of issues (empty = valid)."""
        issues = []
        base = Path(self._base_path)

        if not (base / "mod.json").exists():
            issues.append("Missing mod.json")
        if not self.ldraw_file:
            issues.append("Missing ldraw_file reference")
        elif not (base / self.ldraw_file).exists():
            issues.append(f"LDraw file not found: {self.ldraw_file}")
        if not self.preview_image:
            issues.append("Missing preview_image")
        elif not (base / self.preview_image).exists():
            issues.append(f"Preview image not found: {self.preview_image}")
        if not self.mod_id or not self.mod_id.strip():
            issues.append("mod_id is empty")
        if not self.name.strip():
            issues.append("name is empty")
        if self.estimated_parts < 1:
            issues.append("estimated_parts must be >= 1")

        return issues


class ModRepository:
    """Manages the community mod collection — storage, search, rating."""

    def __init__(self, storage_path: str):
        self.root = Path(storage_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, CommunityMod] = {}
        self._load_index()

    def _load_index(self):
        """Load all mods from disk into memory index."""
        self._index.clear()
        for mod_dir in self.root.iterdir():
            if not mod_dir.is_dir():
                continue
            manifest = mod_dir / "mod.json"
            if manifest.exists():
                try:
                    mod = CommunityMod.from_manifest(manifest)
                    mod._base_path = str(mod_dir)
                    self._index[mod.mod_id] = mod
                except Exception as e:
                    print(f"[ModRepo] Failed to load {mod_dir.name}: {e}")

    def install_mod(self, mod_dir: str | Path, replace: bool = False) -> tuple[bool, str]:
        """Install a mod from a directory into the repository.

        Args:
            mod_dir: Path to the mod directory containing mod.json
            replace: If True, overwrite existing mod with same mod_id

        Returns:
            (success, message)
        """
        mod_dir = Path(mod_dir)
        manifest_path = mod_dir / "mod.json"

        if not manifest_path.exists():
            return False, "mod.json not found in directory"

        try:
            mod = CommunityMod.from_manifest(manifest_path)
        except Exception as e:
            return False, f"Invalid mod.json: {e}"

        # Validate
        mod._base_path = str(mod_dir)
        issues = mod.validate()
        if issues:
            return False, f"Validation failed: {'; '.join(issues)}"

        # Check for conflicts
        existing = self._index.get(mod.mod_id)
        if existing and not replace:
            return False, f"Mod '{mod.mod_id}' already exists. Use replace=true to overwrite."

        # Copy to repository
        dest_dir = self.root / mod.mod_id
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(mod_dir, dest_dir, dirs_exist_ok=True)

        # Update index
        mod._base_path = str(dest_dir)
        mod.created_at = datetime.now(timezone.utc).isoformat()
        self._index[mod.mod_id] = mod

        # Save manifest copy
        with open(dest_dir / "mod.json", "w", encoding="utf-8") as f:
            json.dump(mod.to_manifest(), f, indent=2, ensure_ascii=False)

        return True, f"Mod '{mod.mod_id}' installed successfully"

    def remove_mod(self, mod_id: str) -> bool:
        """Remove a mod from the repository."""
        if mod_id not in self._index:
            return False
        mod_dir = self.root / mod_id
        if mod_dir.exists():
            shutil.rmtree(mod_dir)
        del self._index[mod_id]
        return True

    def get_mod(self, mod_id: str) -> CommunityMod | None:
        """Get a specific mod by ID."""
        return self._index.get(mod_id)

    def list_mods(
        self,
        category: str | None = None,
        body_style: str | None = None,
        make: str | None = None,
        difficulty: str | None = None,
        search: str | None = None,
        sort_by: str = "rating",
        limit: int = 50,
        offset: int = 0,
    ) -> list[CommunityMod]:
        """Search and filter mods."""
        results = list(self._index.values())

        if category:
            results = [m for m in results if m.category == category]
        if body_style:
            results = [m for m in results if "all" in m.compatible_body_styles or body_style in m.compatible_body_styles]
        if make:
            make_lower = make.lower()
            results = [m for m in results if not m.compatible_makes or any(make_lower in c.lower() for c in m.compatible_makes)]
        if difficulty:
            results = [m for m in results if m.difficulty == difficulty]
        if search:
            query = search.lower()
            results = [m for m in results if query in m.name.lower() or query in m.description.lower() or any(query in t.lower() for t in m.tags)]

        # Sort
        if sort_by == "rating":
            results.sort(key=lambda m: (m.rating, m.downloads), reverse=True)
        elif sort_by == "downloads":
            results.sort(key=lambda m: m.downloads, reverse=True)
        elif sort_by == "newest":
            results.sort(key=lambda m: m.created_at, reverse=True)
        elif sort_by == "name":
            results.sort(key=lambda m: m.name.lower())

        return results[offset:offset + limit]

    def get_categories(self) -> list[dict]:
        """Get all categories with mod counts."""
        counts: dict[str, int] = {}
        for mod in self._index.values():
            counts[mod.category] = counts.get(mod.category, 0) + 1
        return [
            {"id": cat, "name": cat.replace("_", " ").title(), "count": count}
            for cat, count in sorted(counts.items())
        ]

    def to_api_dict(self, mod: CommunityMod) -> dict:
        """Convert a mod to API-friendly dict."""
        return {
            "mod_id": mod.mod_id,
            "name": mod.name,
            "version": mod.version,
            "author": mod.author,
            "category": mod.category,
            "description": mod.description,
            "tags": mod.tags,
            "difficulty": mod.difficulty,
            "estimated_parts": mod.estimated_parts,
            "estimated_cost_usd": mod.estimated_cost_usd,
            "compatible_body_styles": mod.compatible_body_styles,
            "compatible_makes": mod.compatible_makes,
            "long_description": mod.long_description,
            "dependencies": mod.dependencies,
            "incompatible_with": mod.incompatible_with,
            "license": mod.license,
            "downloads": mod.downloads,
            "rating": mod.rating,
            "rating_count": mod.rating_count,
        }
