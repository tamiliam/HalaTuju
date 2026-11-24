"""LL5 phase C2 - the coach grade's result allow-list (`eval/replay/coach_result_schema.py`). Every REAL
report shape `coach_grade.coach_report` gives passes unchanged; a plant of any kind becomes exactly
``{"error": "schema"}``. Synthetic records only (the `test_coach_grade` builders); no database."""
import copy
import datetime
import json

import pytest

from apps.scholarship import coach_grade
from apps.scholarship.eval.replay import coach_result_schema as S
from apps.scholarship.eval.replay import coach_rows, lens_human
from apps.scholarship.fact_bands import CERTAIN, PROBABLE, UNSURE
from apps.scholarship.tests.test_coach_grade import EARLY, LATER, LATEST, many
from apps.scholarship.verdict_engine import PRE_VERSIONING

PLANT = 'Siti Aminah binti Ahmad'
V1, V2, V3 = '2026-03-01.1', '2026-04-01.2', '2026-05-01.3'
SCHEMA_ERROR = {'error': S.SCHEMA}


def _report(records, extra=True):
    return coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS if extra else ())


def _graded(prev, new, extra=True):
    return _report(many(prev, V1, EARLY) + many(new, V2, LATER), extra)


def _round_trip(result):
    """What the child writes and the parent reads back."""
    return S.parse_coach_grade_bytes(S.checked_coach_text(result).encode('utf-8'))


def _passes(result):
    assert S.coach_result_allowed(result)
    assert _round_trip(result) == json.loads(json.dumps(result))


def _fails(result):
    assert not S.coach_result_allowed(result)
    assert json.loads(S.checked_coach_text(result)) == SCHEMA_ERROR
    assert _round_trip(result) == SCHEMA_ERROR


# ── the pinned keys: a new key needs a deliberate change here ─────────────────────────────────────
def test_the_key_sets_are_pinned():
    assert S.TOP_KEYS == {'cell_min_facts', 'coach_min_facts', 'guard_alpha', 'score_z', 'left_out_reasons',
                          'decided_records', 'malformed_records', 'malformed_by_error',
                          'versions_without_marks', 'months', 'coach', 'waiting'}
    assert S.CELL_SMALL_KEYS == {'version', 'unknown_version', 'month', 'too_few'}
    assert S.CELL_KEYS == S.CELL_SMALL_KEYS | {'facts', 'points', 'best', 'score_pct', 'not_scored', 'outcomes'}
    assert S.SIDE_SMALL_KEYS == {'version', 'too_few'}
    assert S.SIDE_KEYS == S.SIDE_SMALL_KEYS | {'facts', 'score_pct', 'coverage', 'generous_wrong'}
    assert S.LINE_SMALL_KEYS == {'too_few'}
    assert S.LINE_KEYS == {'too_few', 'facts', 'points', 'best', 'score_pct', 'left_out'}
    assert S.PAIR_KEYS == {'previous', 'new', 'grade', 'reasons', 'skipped_versions'}
    assert S.COUNT_OF_KEYS == {'count', 'of'} and S.EXTRA_LINE == 'without_left_out'
    assert (S.ERROR_KEYS, S.REFUSAL_KEYS) == ({'error'}, {'refusal'})
    assert S.COACH_FILE_ERROR_CODES == {'schema', 'ValueError', 'TypeError', 'LookupError'}


# ── every real shape passes unchanged ─────────────────────────────────────────────────────────────
def test_no_records_with_and_without_the_extra_line():
    for extra in (True, False):
        _passes(_report([], extra))


def test_records_below_the_cell_floor():
    report = _report(many([(CERTAIN, 'pass', 3)], V1))
    assert report['months'][0]['too_few'] is True and report['waiting'] == [{'version': V1, 'too_few': True}]
    _passes(report)


@pytest.mark.parametrize('prev, new, grade', [
    ([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 40)], 'pass'),
    ([(CERTAIN, 'pass', 40)], [(UNSURE, 'pass', 40)], 'fail'),
    ([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)], 'no_change')])
def test_a_graded_pass_fail_and_no_change(prev, new, grade):
    for extra in (True, False):
        report = _graded(prev, new, extra)
        assert report['coach'][0]['grade'] == grade
        _passes(report)


def test_a_waiting_version_skipped_versions_and_a_too_few_month():
    records = (many([(CERTAIN, 'pass', 40)], V1, EARLY) + many([(CERTAIN, 'pass', 10)], V2, LATER)
               + many([(CERTAIN, 'pass', 38)], V3, LATEST)
               + many([(CERTAIN, 'pass', 2)], V3, LATEST + datetime.timedelta(days=40)))
    report = _report(records)
    assert [s['version'] for s in report['waiting']] == [V2]
    assert report['coach'][0]['skipped_versions'] == 1
    assert any(cell['too_few'] for cell in report['months'])
    _passes(report)


def test_malformed_records_unknown_and_pre_versioning_cells():
    records = (many([(CERTAIN, 'pass', 6)], None) + many([(CERTAIN, 'pass', 6)], PRE_VERSIONING)
               + [('x',), ([], {}, V1, 'not a time'), (5, {'identity': 'pass'}, V1, EARLY)])
    report = _report(records)
    assert report['malformed_by_error'] == {'TypeError': 1, 'not_a_datetime': 1, 'too_short': 1}
    assert {c['version'] for c in report['months']} == {coach_grade.UNKNOWN_VERSION, PRE_VERSIONING}
    _passes(report)


def test_the_extra_line_shown_and_too_few():
    records = many([(CERTAIN, 'pass', 40), (CERTAIN, 'fail', 3, 'interview_differs')], V1)
    report = _report(records)
    assert report['months'][0]['without_left_out']['left_out'] == 3
    _passes(report)
    report = _report(many([(CERTAIN, 'fail', 5, 'interview_differs')], V1))
    assert report['months'][0]['without_left_out'] == {'too_few': True}
    _passes(report)


def test_the_debug_refusal_and_every_error_code():
    _passes(coach_rows.coach_debug_refusal())
    assert coach_rows.coach_debug_refusal() == {'refusal': lens_human.DEBUG_ON}
    for code in S.COACH_FILE_ERROR_CODES:
        _passes({'error': code})


# ── plants fail whole ─────────────────────────────────────────────────────────────────────────────
def _full():
    records = many([(CERTAIN, 'pass', 40), (CERTAIN, 'fail', 3, 'interview_differs')], V1, EARLY)
    return _report(records + many([(CERTAIN, 'pass', 10)], V2, LATER) + many([(CERTAIN, 'pass', 40)], V3, LATEST)
                   + many([(CERTAIN, 'pass', 6)], None) + [('x',)])


def _planted(path, value):
    report = copy.deepcopy(_full())
    target = report
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return report


@pytest.mark.parametrize('path, value', [
    (('months', 0, 'version'), PLANT), (('months', 0, 'month'), PLANT), (('months', 0, 'month'), '2026-13'),
    (('months', 0, 'facts'), 40.0), (('months', 0, 'facts'), True), (('months', 0, 'score_pct'), '50'),
    (('months', 0, 'outcomes', 'right_sure'), 1.5), (('months', 0, 'outcomes', PLANT), 1),
    (('months', 0, 'without_left_out', 'left_out'), PLANT), (('months', 0, 'unknown_version'), True),
    (('months', 0, PLANT), 1), (('months', -1, 'version'), PLANT), (('coach', 0, 'grade'), PLANT),
    (('coach', 0, 'reasons'), [PLANT]), (('coach', 0, 'new', 'version'), PLANT),
    (('coach', 0, 'new', 'coverage', 'count'), 2.0), (('coach', 0, 'previous', 'facts'), None),
    (('waiting', 0, 'version'), PLANT), (('waiting', 0, 'too_few'), 'yes'),
    (('malformed_by_error', PLANT), 1), (('malformed_by_error', 'too_short'), 2),
    (('left_out_reasons',), [PLANT]), (('left_out_reasons',), []), (('cell_min_facts',), 4),
    (('score_z',), 2.0), (('guard_alpha', 'of'), 21), (('decided_records',), 1.0), (('decided_records',), PLANT),
    (('months',), {}), ((PLANT,), 1), (('coach', 0, 'new', 'without_left_out', PLANT), 1)])
def test_a_plant_anywhere_fails_whole(path, value):
    _passes(_full())
    _fails(_planted(path, value))


def test_a_missing_key_a_plant_in_a_list_and_bad_top_shapes_fail():
    report = _full()
    del report['waiting']
    _fails(report)
    _fails(_planted(('months',), _full()['months'] + [PLANT]))
    _fails(_planted(('coach',), _full()['coach'] + [{'note': PLANT}]))
    for bad in ({'error': PLANT}, {'refusal': PLANT}, {'error': 'schema', 'note': PLANT}, [], PLANT, None):
        _fails(bad)


def test_a_planted_name_never_reaches_the_written_text():
    text = S.checked_coach_text(_planted(('months', 0, 'version'), PLANT))
    assert PLANT not in text and json.loads(text) == SCHEMA_ERROR


def test_the_parent_reads_bad_bytes_as_bad_output():
    for raw in (b'{"refusal": ', b'[]', b'{"refusal": "debug_on", "refusal": "debug_on"}', b'{"a": NaN}',
                b'\xff', b' ' * (S.MAX_RESULT_BYTES + 1)):
        assert S.parse_coach_grade_bytes(raw) == {'error': S.BAD_OUTPUT}


def test_a_class_name_kind_passes_and_an_error_name_is_the_nearest_known_class():
    report = _planted(('malformed_by_error',), {'KeyError': 1})
    _passes(report)
    _fails(_planted(('malformed_by_error',), {'A' * 61: 1}))
    _fails(_planted(('malformed_by_error',), {'not ascii é': 1}))
    assert S.coach_error_name(KeyError('x')) == 'LookupError'
    assert S.coach_error_name(UnicodeDecodeError('utf-8', b'', 0, 1, 'x')) == 'ValueError'
    assert S.coach_error_name(RuntimeError('x')) == S.SCHEMA


# ── the malformed kinds: three forms only ─────────────────────────────────────────────────────────
ALLOWED_KINDS = ('too_short', 'not_a_datetime', 'no_offset', 'other_error', 'KeyError', 'ValidationError',
                 'Error', 'Exception', 'DoesNotExistException', 'X' * 55 + 'Error', 'Http404Error')
BAD_KINDS = ('maria', 'Maria', 'SitiAminah', 'keyerror', 'TOO_SHORT', 'Other_error', 'X' * 56 + 'Error',
             'Key_Error', 'Key.Error', 'keyError', '1Error', 'Key Error', 'KeyError\n', ' KeyError',
             'KeyErrorx', 'Errors', 'ÄError', 'KeyErroré', '', PLANT)


def test_the_predicate_is_the_three_forms():
    assert S.ERROR_NAME_ENDINGS == ('Error', 'Exception')
    assert set(coach_grade.MALFORMED_LABELS) == {'too_short', 'not_a_datetime', 'no_offset'}
    for kind in ALLOWED_KINDS:
        assert S.malformed_kind_ok(kind), kind
    for kind in BAD_KINDS + (None, 1, b'KeyError'):
        assert not S.malformed_kind_ok(kind), kind

    class Text(str):
        pass
    assert not S.malformed_kind_ok(Text('KeyError'))
    assert coach_rows.malformed_kind_ok is S.malformed_kind_ok      # one definition, both sides


@pytest.mark.parametrize('kind', ALLOWED_KINDS)
def test_each_allowed_kind_passes(kind):
    _passes(_planted(('malformed_by_error',), {kind: 1}))


@pytest.mark.parametrize('kind', BAD_KINDS)
def test_each_bad_kind_fails_whole_and_never_reaches_the_text(kind):
    report = _planted(('malformed_by_error',), {kind: 1})
    _fails(report)
    assert S.coach_result_allowed(coach_rows.fold_odd_kinds(report))
    if kind.strip():
        assert kind not in S.checked_coach_text(report)
        assert kind not in json.dumps(_round_trip(report))


def test_a_planted_word_kind_beside_good_ones_fails_whole():
    report = _planted(('malformed_by_error',), {'KeyError': 1, 'SitiAminah': 2, 'too_short': 3})
    report['malformed_records'] = 6
    _fails(report)
    assert 'Aminah' not in S.checked_coach_text(report)
