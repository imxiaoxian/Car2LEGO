import numpy as np
import pytest

from car2lego3d.kinematics import motion_report, pose_transforms
from car2lego3d.semantic import SCHEMA


def node(name, parent=None, offset=(0, 0, 0), joint=None):
    local = np.eye(4)
    local[:3, 3] = offset
    return dict(id=name, role=name, parent=parent, local_transform=local.tolist(),
                world_transform=local.tolist(), joint=joint)


def test_parent_frame_rotation_moves_glass_and_nested_rolling_hub_together():
    door = node('door', joint=dict(type='revolute', frame='parent', axis=[0, 0, 1], origin_m=[1, 0, 0], limits=[0, 2]))
    frame = node('frame', 'door', offset=(2, 0, 0))
    glass = node('glass', 'frame', offset=(0, 0, 1))
    glass['world_transform'] = (np.array(frame['local_transform']) @ np.array(glass['local_transform'])).tolist()
    scene = dict(schema=SCHEMA, units='metres', nodes=[door, frame, glass])
    pose = pose_transforms(scene, {'door': np.pi / 2})
    np.testing.assert_allclose(pose['glass'][:3, 3], [1, 1, 1], atol=1e-12)
    np.testing.assert_allclose(pose['frame'][:3, 3], [1, 1, 0], atol=1e-12)
    with pytest.raises(ValueError, match='limits'):
        pose_transforms(scene, {'door': 3})


def test_motion_samples_combinations_refines_near_collisions_and_keeps_unknown_unknown():
    steer = node('steer', joint=dict(type='revolute', frame='parent', axis=[0, 0, 1], origin_m=[0, 0, 0], limits=[-.3, .3], purpose='steering'))
    spring = node('spring', 'steer', joint=dict(type='prismatic', frame='parent', axis=[0, 0, 1], origin_m=[0, 0, 0], limits=[-.01, .01], purpose='suspension'))
    data = dict(schema=SCHEMA, units='metres', nodes=[steer, spring])
    unknown = motion_report(data)
    assert unknown['status'] == 'unverified'
    assert len(unknown['joints'][0]['samples']) == 9
    assert len(unknown['steering_suspension_combinations'][0]['samples']) == 81

    def check(transforms):
        angle = np.arctan2(transforms['steer'][1, 0], transforms['steer'][0, 0])
        return dict(coverage='complete', collisions=['fender'] if angle > .2 else [], clearance_m=.001)

    measured = motion_report(data, check, refinements=1)
    assert measured['status'] == 'fail'
    assert len(measured['joints'][0]['samples']) == 17
    partial = motion_report(data, lambda matrices: dict(coverage='partial', collisions=[]))
    assert partial['status'] == 'unverified'
