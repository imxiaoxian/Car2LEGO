from copy import deepcopy
from unittest.mock import Mock, patch

import numpy as np
import pytest

from car2lego3d import staged_model
from car2lego3d.common import write_json
from car2lego3d.semantic import SCHEMA, ownership_report, validate_scene


def node(name, role, parent=None):
    return dict(id=name, role=role, parent=parent, local_transform=np.eye(4).tolist(),
                world_transform=np.eye(4).tolist())


def scene():
    door = node('door', 'door_assembly')
    door['joint'] = dict(type='revolute', frame='parent', origin_m=[0, 0, 0], axis=[1, 0, 0], limits=[0, 1.4])
    return dict(schema=SCHEMA, units='metres', nodes=[door, node('glass', 'side_window', 'door')])


def test_glass_ownership_survives_nested_transforms_and_open_body_types():
    data = scene()
    assert ownership_report(data)['passed']
    data['nodes'][1]['parent'] = None
    assert not ownership_report(data)['passed']
    assert ownership_report(dict(schema=SCHEMA, units='metres', nodes=[node('tub', 'body')])) == dict(
        checks=[], applicable=False, passed=True, contact_verified=False)


@pytest.mark.parametrize('change', ['cycle', 'singular', 'world', 'joint'])
def test_semantic_rejects_invalid_articulated_scene(change):
    data = scene()
    if change == 'cycle':
        data['nodes'][0]['parent'] = 'glass'
    elif change == 'singular':
        data['nodes'][1]['local_transform'][0][0] = 0
    elif change == 'world':
        data['nodes'][1]['world_transform'][0][3] = .5
    else:
        data['nodes'][0]['joint']['frame'] = 'world'
    with pytest.raises(ValueError):
        validate_scene(data)


def test_phase_cannot_remove_previous_geometry():
    original = scene()
    original['nodes'][1]['geometry'] = dict(vertices_m=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        triangles=[[0, 1, 2]], material_indices=[0])
    changed = deepcopy(original)
    changed['nodes'][1].pop('geometry')
    with pytest.raises(ValueError, match='removed existing geometry'):
        staged_model.preserve_objects(original, changed)


def test_visual_review_rolls_back_actual_export_if_it_detaches_door_glass(tmp_path):
    original = scene()
    bad = deepcopy(original)
    bad['nodes'][1]['parent'] = None
    (tmp_path / 'model.blend').write_bytes(b'original')
    (tmp_path / 'render-left.png').write_bytes(b'original-pixels')
    write_json(tmp_path / 'semantic-scene.json', original)
    blender = Mock()

    def execute(code, name):
        if name.startswith('review-export'):
            write_json(tmp_path / 'semantic-scene.json', bad)
            (tmp_path / 'model.blend').write_bytes(b'detached')
            (tmp_path / 'render-left.png').write_bytes(b'bad-pixels')

    blender.execute.side_effect = execute
    quality = dict(status='pass', checks=[], failed_checks=0)
    with patch.object(staged_model, 'image_content', return_value=[]), \
            patch.object(staged_model, 'ask_json', return_value=dict(analysis='Constructed bad patch', code='import bpy')):
        current, result, review = staged_model.review_phase(blender, tmp_path, {}, {}, 'gpt-6-astra', '',
            original, quality, dict(phase='doors-glass'))
    assert review['status'] == 'rejected' and review['scene_restored']
    assert (tmp_path / 'model.blend').read_bytes() == b'original'
    assert (tmp_path / 'render-left.png').read_bytes() == b'original-pixels'
    assert (tmp_path / 'rejected-review/model.blend').read_bytes() == b'detached'
    assert current == original


@pytest.mark.parametrize('response', [{}, {'analysis': 'bad', 'code': None}, {'code': 'import bpy'}])
def test_malformed_model_json_becomes_repairable_failure(response):
    with pytest.raises(ValueError, match='analysis and code'):
        staged_model.validate_response(response)
