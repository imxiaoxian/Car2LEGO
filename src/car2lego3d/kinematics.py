"""Hierarchical rest-frame motion and bounded adaptive digital interference sampling."""
from itertools import combinations, product

import numpy as np

from .semantic import validate_scene


def joint_delta(joint, value):
    axis, origin = np.asarray(joint['axis'], dtype=float), np.asarray(joint['origin_m'], dtype=float)
    result = np.eye(4)
    if joint['type'] == 'prismatic':
        result[:3, 3] = axis * value
    else:
        x, y, z = axis
        skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
        rotation = np.eye(3) + np.sin(value) * skew + (1 - np.cos(value)) * (skew @ skew)
        result[:3, :3] = rotation
        result[:3, 3] = origin - rotation @ origin
    return result


def pose_transforms(scene, positions=None):
    named = validate_scene(scene)
    positions, transforms = positions or {}, {}
    for name, value in positions.items():
        if name not in named or not named[name].get('joint'):
            raise ValueError('Pose references an unknown joint: ' + name)
        lower, upper = named[name]['joint']['limits']
        if not np.isfinite(value) or not lower <= value <= upper:
            raise ValueError('Pose exceeds joint limits: ' + name)

    def visit(name):
        if name in transforms:
            return transforms[name]
        node = named[name]
        local = np.asarray(node['local_transform'], dtype=float)
        if node.get('joint'):
            local = joint_delta(node['joint'], positions.get(name, 0)) @ local
        transforms[name] = (visit(node['parent']) @ local) if node.get('parent') else local
        return transforms[name]

    for name in named:
        visit(name)
    return transforms


def motion_report(scene, collision_check=None, samples=9, refinements=3, near_contact_m=.002):
    if samples < 9 or refinements < 0:
        raise ValueError('Motion inspection requires at least nine samples and nonnegative refinement depth')
    named = validate_scene(scene)
    joints = {name: node['joint'] for name, node in named.items() if node.get('joint')}
    cache = {}

    def evaluate(values):
        key = tuple(sorted(values.items()))
        if key not in cache:
            transforms = pose_transforms(scene, values)
            measured = collision_check(transforms) if collision_check else {}
            verified = measured.get('coverage') == 'complete' and isinstance(measured.get('collisions'), list)
            collisions = measured.get('collisions')
            cache[key] = dict(positions=values, status=('fail' if collisions else 'pass') if verified else 'unverified',
                collisions=collisions, clearance_m=measured.get('clearance_m'), coverage=measured.get('coverage', 'missing'),
                world_transforms={name: matrix.tolist() for name, matrix in transforms.items() if named[name].get('joint')})
        return cache[key]

    reports = []
    for name, joint in joints.items():
        values = np.linspace(*joint['limits'], samples).tolist()
        poses = {value: evaluate({name: value}) for value in values}
        for _ in range(refinements):
            insert = []
            ordered = sorted(poses)
            for left, right in zip(ordered, ordered[1:]):
                a, b = poses[left], poses[right]
                near = any(p.get('clearance_m') is not None and p['clearance_m'] <= near_contact_m for p in (a, b))
                if a['status'] != b['status'] or near or a.get('collisions') or b.get('collisions'):
                    insert.append((left + right) / 2)
            if not insert:
                break
            poses.update({value: evaluate({name: value}) for value in insert})
        reports.append(dict(joint=name, purpose=joint.get('purpose'), samples=[poses[v] for v in sorted(poses)]))
    combined = []
    for a, b in combinations(joints, 2):
        if {joints[a].get('purpose'), joints[b].get('purpose')} != {'steering', 'suspension'}:
            continue
        poses = [evaluate({a: float(x), b: float(y)}) for x, y in product(
            np.linspace(*joints[a]['limits'], samples), np.linspace(*joints[b]['limits'], samples))]
        combined.append(dict(joints=[a, b], samples=poses))
    statuses = [pose['status'] for pose in cache.values()]
    return dict(schema='car2lego3d.motion-report.v1', units='metres/radians', joints=reports,
        steering_suspension_combinations=combined, evaluated_poses=len(cache),
        status='fail' if 'fail' in statuses else 'pass' if statuses and all(s == 'pass' for s in statuses) else 'unverified',
        collision_engine_supplied=collision_check is not None, physical_verified=False,
        limitations=['Digital interference checks do not establish physical strength or friction.'])
