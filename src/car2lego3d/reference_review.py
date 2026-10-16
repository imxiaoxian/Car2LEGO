"""Vision review of actual generated references; manifests alone cannot verify content."""
import json
from pathlib import Path

from .common import digest, write_json
from .dialogue import ask_json, image_content
from .references import load_references


PROMPT = """Inspect the actual labelled vehicle reference images. The anchor locks identity, not pose.
Check each TARGET against its own camera, state and focus contract. Check doors, covers, pop-up lamps,
wheel orientation, door/window ownership, light shape, body variant, rims and paint. Whole-car closed
views must NOT show raised scissor doors or raised pop-up headlamps. Open detail views must show the
requested moving assembly and surrounding attachment. Do not mistake a correct open-detail pose for
an identity inconsistency. Synthetic hidden mechanisms are design inference, never verified real data.
Return JSON {shots:[{id, status:'pass'|'needs_revision'|'indeterminate', observed_state, issues:[string],
correction:string}]}. Include each TARGET exactly once. Corrections must be specific to visible errors.
Use indeterminate for details that cannot be inspected. Never pass a view that violates its state.
Judge visible content and useful framing, not whether a photograph proves measured thickness or hidden
mechanical accuracy. Do not demand that a single photo expose occluded surfaces. Hidden mechanisms can
remain uncertain if the requested attachment region is shown. Ignore sub-degree camera-elevation
differences; fail camera direction, wrong side, major perspective distortion or missing subject context.
"""


def validate_review(response, names):
    if not isinstance(response, dict) or not isinstance(response.get('shots'), list):
        raise ValueError('Reference review requires a shots list')
    records = response['shots']
    if len(records) != len(names) or {r.get('id') for r in records} != set(names):
        raise ValueError('Reference review omitted or duplicated target shots')
    for item in records:
        if (item.get('status') not in {'pass', 'needs_revision', 'indeterminate'}
                or not isinstance(item.get('observed_state'), str)
                or not isinstance(item.get('issues'), list)
                or any(not isinstance(issue, str) for issue in item['issues'])
                or not isinstance(item.get('correction'), str)
                or (item['status'] != 'pass' and not item['correction'].strip())
                or (item['status'] == 'pass' and item['issues'])):
            raise ValueError('Incomplete reference content review')
    return records


def review_references(manifest_path, directory, model='gpt-6.1-sol'):
    directory = Path(directory)
    manifest, images = load_references(manifest_path)
    shots = manifest.get('shots', manifest.get('views'))
    results = {}
    names = list(images)
    for offset in range(0, len(names), 5):
        batch = names[offset:offset + 5]
        contracts = {name: {key: shots[name].get(key) for key in ('camera', 'state', 'focus', 'modules')}
                     for name in batch}
        content = [{'type': 'text', 'text': json.dumps(dict(brief=manifest.get('brief'), targets=contracts))},
                   *image_content({'IDENTITY_ANCHOR': images['overview']}),
                   *image_content({'TARGET_' + name: images[name] for name in batch})]
        response = ask_json([{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': content}],
            directory, f'review-{offset // 5 + 1}', max_tokens=6000, model=model, stream=True,
            timeout=180, transient_retries=2, reuse_completed=True, reasoning_effort='medium')
        for item in validate_review(response, batch):
            results[item['id']] = {**item, 'sha256': shots[item['id']]['sha256']}
    report = dict(schema='car2lego3d.reference-content-review.v1', model=model,
        manifest_sha256=digest(manifest_path), status='pass' if all(
            item['status'] == 'pass' for item in results.values()) else 'needs_revision',
        shots=results, appearance_accepted=False, physical_measurement_verified=False)
    write_json(directory / 'report.json', report)
    return report


def repair_corrections(report, previous=None):
    corrections = dict(previous or {})
    for name, result in report['shots'].items():
        if result['status'] != 'pass':
            corrections[name] = result['correction'] + '\nReplace the rejected image with source SHA256 ' + result['sha256']
    return corrections
