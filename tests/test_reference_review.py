import pytest

from car2lego3d.reference_review import validate_review


def record(name, status='pass', issues=None, correction=''):
    return dict(id=name, status=status, observed_state='closed', issues=issues or [], correction=correction)


def test_review_cannot_pass_with_observed_errors_or_omit_targets():
    with pytest.raises(ValueError, match='omitted or duplicated'):
        validate_review(dict(shots=[record('front')]), ['front', 'left'])
    with pytest.raises(ValueError, match='Incomplete'):
        validate_review(dict(shots=[record('left', issues=['door is open'])]), ['left'])
    with pytest.raises(ValueError, match='Incomplete'):
        validate_review(dict(shots=[record('left', status='needs_revision')]), ['left'])
    assert validate_review(dict(shots=[record('left', status='needs_revision',
        issues=['door is open'], correction='Close both doors')]), ['left'])[0]['status'] == 'needs_revision'
