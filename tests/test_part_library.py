import numpy as np
import pytest

from car2lego3d.ldraw_document import Document
from car2lego3d.part_library import PartLibrary


def test_custom_native_recursion_colors_and_placement_share_one_geometry(tmp_path):
    native, package = tmp_path / 'native', tmp_path / 'custom'
    for root in (native, package):
        (root / 'parts').mkdir(parents=True)
    (native / 'parts/face.dat').write_text('3 16 0 0 0 2 0 0 0 2 0\n3 0x2FF8800 0 0 1 2 0 1 0 2 1\n')
    (package / 'parts/c2l-panel.dat').write_text('1 4 10 20 30 0 -1 0 1 0 0 0 0 1 face.dat\n')
    resolver = PartLibrary(native, [package])
    row = dict(part='c2l-panel', rotation=np.eye(3).ravel().tolist(), position=[100, 0, 0], color=15)
    triangles, colors = resolver.instance(row)
    np.testing.assert_allclose(triangles.min(axis=(0, 1)), [108, 20, 30])
    np.testing.assert_allclose(triangles.max(axis=(0, 1)), [110, 22, 31])
    assert colors.tolist() == [4, 0x2FF8800]
    assert len(resolver.dependency_record()['files']) == 2
    assert 'c2l-panel.dat' in resolver.geometry([row])
    document = Document('1 0x2FF8800 0 0 0 1 0 0 0 1 0 0 0 1 face.dat\n')
    assert Document(document.flatten()).instances() == document.instances()


def test_changed_nested_dependency_invalidates_geometry_cache(tmp_path):
    (tmp_path / 'parts').mkdir()
    child = tmp_path / 'parts/child.dat'
    child.write_text('3 16 0 0 0 1 0 0 0 1 0\n')
    (tmp_path / 'parts/parent.dat').write_text('1 16 0 0 0 1 0 0 0 1 0 0 0 1 child.dat\n')
    library = PartLibrary(tmp_path)
    assert library.triangles('parent.dat')[0].max() == 1
    child.write_text('3 16 0 0 0 2 0 0 0 2 0\n')
    assert library.triangles('parent.dat')[0].max() == 2


def test_missing_cyclic_and_stretched_geometry_are_rejected(tmp_path):
    (tmp_path / 'parts').mkdir()
    library = PartLibrary(tmp_path)
    with pytest.raises(FileNotFoundError):
        library.triangles('missing.dat')
    (tmp_path / 'parts/cycle.dat').write_text('1 16 0 0 0 1 0 0 0 1 0 0 0 1 cycle.dat\n')
    with pytest.raises(ValueError, match='Cyclic'):
        library.triangles('cycle.dat')
    (tmp_path / 'parts/triangle.dat').write_text('3 16 0 0 0 1 0 0 0 1 0\n')
    with pytest.raises(ValueError, match='stretches'):
        library.instance(dict(part='triangle.dat', rotation=(np.eye(3) * 2).ravel().tolist(), position=[0, 0, 0], color=4))
