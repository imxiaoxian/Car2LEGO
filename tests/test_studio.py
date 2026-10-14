import json
from zipfile import ZipFile

import pytest
from PIL import Image

from car2lego3d.studio import export_studio, verify_archive


ASSEMBLY = """0 Test assembly
1 4 -10 -8 20 0 0 1 0 1 0 -1 0 0 3023.dat
0 STEP
1 0 10 -16 20 1 0 0 0 1 0 0 0 1 3024.dat
0 STEP
"""


def test_studio_preserves_transforms_colors_steps_and_thumbnail(tmp_path):
    source = tmp_path / "input.ldr"
    source.write_text(ASSEMBLY)
    thumbnail = tmp_path / "preview.png"
    Image.new("RGB", (32, 32), "red").save(thumbnail)
    output = export_studio(source, tmp_path / "studio", thumbnail)
    with ZipFile(output) as archive:
        assert set(archive.namelist()) == {"model.ldr", "model2.ldr", ".info", "thumbnail.png"}
        assert archive.read("model.ldr").decode() == ASSEMBLY
        assert archive.read("thumbnail.png") == thumbnail.read_bytes()
    report = verify_archive(output, source)
    assert report["part_count"] == report["step_count"] == 2
    assert report["archive_roundtrip_verified"]
    assert not report["studio_open_verified"]
    assert not report["physical_verified"]
    record = json.loads((output.parent / "studio.json").read_text())
    assert record["status"] == "completed"


def test_roundtrip_detects_a_changed_color_or_step(tmp_path):
    source = tmp_path / "input.ldr"
    source.write_text(ASSEMBLY)
    for changed in (ASSEMBLY.replace("1 4 ", "1 0 "), ASSEMBLY.replace("0 STEP\n", "", 1)):
        output = tmp_path / "damaged.io"
        with ZipFile(output, "w") as archive:
            archive.writestr("model.ldr", changed)
            archive.writestr("model2.ldr", ASSEMBLY)
            archive.writestr(".info", json.dumps({"total_parts": 2}))
        with pytest.raises(ValueError, match="changed the assembly"):
            verify_archive(output, source)


@pytest.mark.parametrize("content", ["0 Empty\n", "0 FILE submodel.ldr\n" + ASSEMBLY,
                                    ASSEMBLY.replace("-10 -8", "nan -8")])
def test_studio_rejects_incomplete_or_nonflat_assemblies(tmp_path, content):
    source = tmp_path / "bad.ldr"
    source.write_text(content)
    with pytest.raises(ValueError):
        export_studio(source, tmp_path / "studio")
    assert not (tmp_path / "studio" / "model.io").exists()
    assert json.loads((tmp_path / "studio" / "studio.json").read_text())["status"] == "failed"
