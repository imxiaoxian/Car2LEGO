"""BrickLink Studio file manipulation service.

Studio (.io) files are ZIP archives containing:
  model.ldr     — Main LDraw model with 0 FILE sub-model structure
  model2.ldr    — Self-contained model with all part geometry inlined
  model.lxfml   — LDD-compatible XML format
  model.ins     — Instruction step data
  thumbnail.png — 256x256 preview image
  .info         — Metadata (version, author, etc.)

Studio is Unity-based, version 2.26.6. No public API exists.
Integration is file-based: we generate valid .io files that Studio opens directly.

This service:
  - Creates valid .io packages from LDraw data
  - Merges multiple .io files (base car + mod parts)
  - Extracts and modifies existing .io files
  - Generates proper Studio metadata
"""

import io as std_io
import json
import zipfile
import uuid
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class StudioFile:
    """Represents a BrickLink Studio .io file in memory."""
    model_ldr: str           # Main LDraw content
    model2_ldr: str          # Self-contained model
    thumbnail: bytes | None  # PNG thumbnail
    info: dict               # Metadata
    lxfml: str | None = None # LDD XML (optional)

    @classmethod
    def from_path(cls, path: Path | str) -> "StudioFile":
        """Load a .io file from disk."""
        sf = cls(model_ldr="", model2_ldr="", thumbnail=None, info={})
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name == "model.ldr":
                    sf.model_ldr = zf.read(name).decode("utf-8", errors="replace")
                elif name == "model2.ldr":
                    sf.model2_ldr = zf.read(name).decode("utf-8", errors="replace")
                elif name == "thumbnail.png":
                    sf.thumbnail = zf.read(name)
                elif name == ".info":
                    sf.info = json.loads(zf.read(name).decode("utf-8", errors="replace"))
                elif name == "model.lxfml":
                    sf.lxfml = zf.read(name).decode("utf-8", errors="replace")
        return sf

    def to_bytes(self) -> bytes:
        """Serialize to .io file bytes (ZIP format)."""
        buf = std_io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("model.ldr", self.model_ldr)
            zf.writestr("model2.ldr", self.model2_ldr)
            if self.lxfml:
                zf.writestr("model.lxfml", self.lxfml)
            if self.thumbnail:
                zf.writestr("thumbnail.png", self.thumbnail)
            # Generate simple instruction placeholder
            zf.writestr("model.ins", self._generate_ins())
            # Metadata
            zf.writestr(".info", json.dumps(self.info, indent=2))
        return buf.getvalue()

    def save(self, path: Path | str):
        """Write to a .io file on disk."""
        Path(path).write_bytes(self.to_bytes())

    def _generate_ins(self) -> str:
        """Generate minimal instruction data."""
        return json.dumps({"application": "Car2LEGO", "version": "1.0"})


class StudioService:
    """High-level operations on Studio .io files for car models."""

    # Studio metadata template
    INFO_TEMPLATE = {
        "Author": "Car2LEGO",
        "Name": "",
        "Description": "",
        "Application": "Car2LEGO",
        "Version": "1.0",
    }

    @classmethod
    def create_studio_file(
        cls,
        ldr_content: str,
        name: str,
        author: str = "Car2LEGO",
        description: str = "",
    ) -> StudioFile:
        """Create a valid Studio .io file from LDraw content.

        Properly wraps the LDraw content in Studio's expected format:
        0 FILE header → parts → 0 NOFILE for each sub-model.
        """
        # Build proper model.ldr with file wrapper
        filename = name.replace(" ", "_").lower() + ".io"
        wrapped_ldr = f"""0 FILE {filename}
0 {name}
0 Name: {name}
0 Author: {author}
0 CustomBrick
{ldr_content}
0 NOFILE
"""

        info = dict(cls.INFO_TEMPLATE)
        info["Name"] = name
        info["Description"] = description

        # Build model2.ldr with Studio-specific metadata
        model2_ldr = cls._build_model2(ldr_content, name, author)

        return StudioFile(
            model_ldr=wrapped_ldr,
            model2_ldr=model2_ldr,
            thumbnail=cls._make_thumbnail(),
            info=info,
        )

    @classmethod
    def _build_model2(cls, ldr_content: str, name: str, author: str) -> str:
        """Build Studio-specific model2.ldr with BL_Item_No metadata.

        Studio's model2.ldr adds BrickLink item references and inline
        geometry for self-contained models. This is what Studio actually
        uses for rendering and instructions.
        """
        lines = [
            f"0 FILE {name.replace(' ', '_').lower()}.io",
            f"0 {name}",
            f"0 Name: {name}",
            f"0 Author: {author}",
            "0 CustomBrick",
            "0 IsSubModel False",
            "",
        ]

        # Process each part line, adding Studio metadata
        for line in ldr_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("0"):
                # Pass through comments and meta commands
                if stripped.startswith("0 STEP"):
                    lines.append("0 STEP")
                elif not any(stripped.startswith(x) for x in ["0 FILE", "0 NOFILE", "0 Name:", "0 Author:", "0 CustomBrick"]):
                    lines.append(line)
                continue
            if stripped.startswith("1 "):
                parts = stripped.split()
                if len(parts) >= 15:
                    part_file = parts[14]
                    bl_id = part_file.replace(".dat", "").replace("c00", "").replace("c01", "")
                    # Add BL metadata before each part
                    lines.append(f"0 BL_Item_No {bl_id}")
                    lines.append(f"0 BL_Item_Key {bl_id}")
                    lines.append("0 FlexibleType None")
                    lines.append("0 IsAssembly False")
                    lines.append(line)
                else:
                    lines.append(line)
            else:
                lines.append(line)

        lines.append("0 NOFILE")
        return "\n".join(lines)

    @classmethod
    def merge_studio_files(
        cls,
        base: StudioFile,
        modifications: list[StudioFile],
        name: str = "Customized Build",
    ) -> StudioFile:
        """Merge a base car model with modification part files.

        Extracts all part lines from each file and combines them into
        a single LDraw model. Sub-model references are preserved.
        """
        all_parts: list[str] = []
        steps: list[str] = []
        sub_models: dict[str, str] = {}

        for sf in [base] + modifications:
            lines = sf.model_ldr.split("\n")
            current_sub = None
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("0 FILE ") and not stripped.startswith("0 FILE " + name.replace(" ", "_").lower()):
                    current_sub = stripped[7:].strip()
                    continue
                if stripped == "0 NOFILE":
                    current_sub = None
                    continue
                if stripped.startswith("0 STEP"):
                    steps.append(line)
                    continue
                if stripped.startswith("1 "):
                    if current_sub:
                        sub_models.setdefault(current_sub, "")
                        # Don't duplicate part lines — collect sub-model content
                    else:
                        all_parts.append(line)
                elif stripped.startswith("0 ") and not stripped.startswith("0 STEP") and not stripped.startswith("0 FILE") and not stripped.startswith("0 NOFILE"):
                    # Preserve important meta-commands
                    pass

        # Build merged output
        output_lines = [
            f"0 FILE {name.replace(' ', '_').lower()}.io",
            f"0 {name}",
            f"0 Name: {name}",
            f"0 Author: Car2LEGO",
            "0 CustomBrick",
            "",
        ]

        # Add parts with step grouping
        if steps:
            step_idx = 0
            for part in all_parts:
                if step_idx < len(steps):
                    output_lines.append(steps[step_idx])
                    step_idx += 1
                output_lines.append(part)
        else:
            output_lines.extend(all_parts)

        output_lines.append("0 NOFILE")
        output_lines.append("")

        merged_ldr = "\n".join(output_lines)

        return StudioFile(
            model_ldr=merged_ldr,
            model2_ldr=merged_ldr,
            thumbnail=base.thumbnail,
            info={
                "Author": "Car2LEGO",
                "Name": name,
                "Description": "Customized build",
                "Application": "Car2LEGO",
                "Version": "1.0",
                "BaseFiles": [b.info.get("Name", "") for b in [base]],
            },
        )

    @classmethod
    def extract_parts_from_ldr(cls, ldr_content: str) -> list[dict]:
        """Parse LDraw content and extract all part references.

        Returns list of {part_num, color, x, y, z, rotation}.
        """
        parts = []
        for line in ldr_content.split("\n"):
            stripped = line.strip()
            if not stripped.startswith("1 "):
                continue
            tokens = stripped.split()
            if len(tokens) < 15:
                continue
            parts.append({
                "color": int(tokens[1]),
                "x": float(tokens[2]),
                "y": float(tokens[3]),
                "z": float(tokens[4]),
                "rotation": " ".join(tokens[5:14]),
                "part_file": tokens[14],
            })
        return parts

    @staticmethod
    def _make_thumbnail() -> bytes:
        """Generate a minimal placeholder PNG (1x1 pixel, black)."""
        import struct, zlib
        # Minimal valid PNG: 1x1 black pixel
        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b"\x00\x00\x00\x00")  # filtered black pixel
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat)
            + chunk(b"IEND", b"")
        )
