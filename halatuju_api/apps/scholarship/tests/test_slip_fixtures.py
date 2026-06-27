"""Real-OCR slip fixtures → end-to-end parse check.

Each fixture under ``fixtures/slips/*.json`` is the FULL Google Vision word
geometry captured from a real student's results slip (text + centroid + height +
baseline angle), plus the human-verified ``expected_grades``. Two are upright
(deterministic parser already read them), two are rotated ~90 deg (one a clean
rotation, one with keystone) which used to fall back to Gemini and transpose.

The parser pairs each subject with the grade ON ITS OWN ROW; these fixtures prove
that holds across orientations. Grades are band-authoritative — where a band's
modifier is OCR-truncated (a bare 'Cemerlang' with a printed 'A') the parser reads
the band (A-), which downstream becomes a soft 'please check', never a confident
wrong answer. ``expected_grades`` records what the PARSER must output.
"""
import json
from pathlib import Path

import pytest

from apps.scholarship.academic_engine import parse_spm_slip, _norm

FIXDIR = Path(__file__).parent / 'fixtures' / 'slips'
FIXTURES = sorted(FIXDIR.glob('*.json'))


def _load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def _words(fx):
    """Expand the fixture's compact word keys (t/cx/cy/h/a) to the shape the parser
    consumes (text/cx/cy/h/angle)."""
    return [{'text': w['t'], 'cx': w['cx'], 'cy': w['cy'], 'h': w['h'],
             'angle': w.get('a')} for w in fx['words']]


@pytest.mark.parametrize('path', FIXTURES, ids=[p.stem for p in FIXTURES])
def test_slip_parses_to_expected_grades(path):
    fx = _load(path)
    parsed = parse_spm_slip(_words(fx))
    if fx.get('expected_fallback'):
        # A slip the positional parser must NOT trust (e.g. a 2-column digital PDF whose GRED
        # column is detached, so the flattened OCR under-reads / mis-pairs grades). It must
        # return None — bouncing to the Gemini image reader — rather than emit a partial,
        # mis-graded result that gets stamped 'ok'. (#66/doc912.)
        assert parsed is None, (
            f"{fx['student']}: expected fallback (None) but parsed "
            f"{len(parsed.get('results', []))} subjects — declared {fx.get('declared_subjects')}")
        return
    assert parsed is not None, f"{fx['student']}: parse returned None (fell back to Gemini)"
    got = {_norm(r['subject']): r['grade'] for r in parsed['results']}
    expected = {_norm(k): v for k, v in fx['expected_grades'].items()}
    missing = [k for k in expected if k not in got]
    assert not missing, f"{fx['student']}: subjects not parsed: {missing}\n got={got}"
    wrong = {k: (got[k], expected[k]) for k in expected if got[k] != expected[k]}
    assert not wrong, f"{fx['student']}: grade mismatches (got, expected): {wrong}\n full={got}"
