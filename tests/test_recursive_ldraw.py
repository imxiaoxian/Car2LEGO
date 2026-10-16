import json
from zipfile import ZipFile

import numpy as np
import pytest

from car2lego3d.ldraw_document import Document
from car2lego3d.studio import export_studio, verify_archive


MPD = """0 FILE main.ldr
1 4 20 0 0 0 0 1 0 1 0 -1 0 0 door.ldr
0 STEP
0 FILE door.ldr
1 16 10 -8 0 1 0 0 0 1 0 0 0 1 3023.dat
1 40 0 -20 0 1 0 0 0 1 0 0 0 1 c2l-glass.dat
0 FILE c2l-glass.dat
0 !LDRAW_ORG Unofficial_Part
3 16 0 0 0 20 0 0 0 -20 0
0 NOFILE
"""


def test_nested_transform_color_and_custom_geometry(tmp_path):
    document = Document(MPD)
    parts = document.instances()
    assert parts[0]['position'] == [20, -8, -10]
    assert parts[0]['color'] == 4
    assert parts[1]['custom'] and parts[1]['color'] == 40
    source = tmp_path / 'input.mpd'
    source.write_text(MPD)
    output = export_studio(source, tmp_path / 'studio')
    assert verify_archive(output, source)['submodel_count'] == 1
    assert verify_archive(output, source)['custom_part_count'] == 1
    flat = Document(document.flatten()).instances()
    assert np.allclose(flat[0]['rotation'], parts[0]['rotation'])
    assert document.inventory()[1]['custom']


@pytest.mark.parametrize('text', [
    MPD.replace('door.ldr\n0 STEP', '../door.ldr\n0 STEP'),
    MPD.replace('0 FILE door.ldr', '0 FILE main.ldr'),
    MPD.replace('3023.dat', 'missing.ldr'),
    MPD.replace('3023.dat', 'main.ldr'),
    MPD.replace('20 0 0 0 0 1', '20 0 0 0 0 2'),
])
def test_unsafe_or_invalid_recursive_documents_rejected(text):
    with pytest.raises(ValueError):
        Document(text)
