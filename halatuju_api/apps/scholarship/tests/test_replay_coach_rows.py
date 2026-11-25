"""LL5 phase C2 - the coach grade's database door (`eval/replay/coach_rows.py`). Made-up cases only, on the
local test database: the version-label rule, the DEBUG refusal, SELECT only, and a dry run whose counts
are worked out by hand. No name, case id, reviewer, reason text or planted label reaches the result."""
import datetime
import json
import logging

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship import ai_score, coach_grade
from apps.scholarship.audit import FACTS
from apps.scholarship.eval.replay import coach_result_schema, coach_rows
from apps.scholarship.fact_bands import CERTAIN
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.tests.test_coach_grade import band_fact
from apps.scholarship.verdict_engine import PRE_VERSIONING

pytestmark = pytest.mark.django_db

UTC = datetime.timezone.utc
V1, V2 = '2026-10-01.1', '2026-11-01.1'
OCT, NOV = datetime.datetime(2026, 10, 10, 3, 0, tzinfo=UTC), datetime.datetime(2026, 11, 10, 3, 0, tzinfo=UTC)
PLANTED_LABEL = 'Siti Aminah binti Ahmad'
NAME_CANARY = 'CANARYNAME QZXWV'
REASON_CANARY = 'CANARY REASON TEXT KQ7'
DECIDER_CANARY = 'canary.decider@example.invalid'
ID_CANARY = 7531902


def _case(version, when, verdict=None, **overrides):
    """A made-up case decided at ``when`` (None: not decided) with every fact Certain in its snapshot."""
    verdict = verdict or {fact: 'pass' for fact in FACTS}
    return make_application('awaiting_qc', outcome='recommend', ai_verdict_snapshot=[band_fact(f, CERTAIN) for f in FACTS],
                            officer_verdict=verdict, ai_verdict_engine_version=version, verdict_decided_at=when,
                            verdict_reason=REASON_CANARY, verdict_decided_by=DECIDER_CANARY, **overrides)


def _failed(reason, qc=None):
    verdict = {fact: 'pass' for fact in FACTS}
    verdict.update(identity='fail', fail_reasons={'identity': reason}, overall='accept')
    if qc is not None:
        verdict['qc_fact_checks'] = qc
    return verdict


# ── the version label is database text ────────────────────────────────────────────────────────────
@pytest.mark.parametrize('raw, label', [
    (V1, V1), (f'  {V1} ', V1), ('2026-11-18.12', '2026-11-18.12'), (PRE_VERSIONING, PRE_VERSIONING),
    (PLANTED_LABEL, None), ('', None), (None, None), (5, None), ('2026-13-01.1', None), ('2026-11-01', None),
    ('2026-11-01.1x', None), ('2026-11-01.1234', None), ('PRE-VERSIONING', None), (coach_grade.UNKNOWN_VERSION, None)])
def test_only_a_shaped_label_or_pre_versioning_is_passed_on(raw, label):
    assert coach_rows.stored_version_label(raw) == label


def test_a_text_subclass_label_comes_back_as_plain_text():
    class Odd(str):
        pass
    got = coach_rows.stored_version_label(Odd(V1))
    assert got == V1 and type(got) is str


# ── the DEBUG refusal: before any query ───────────────────────────────────────────────────────────
def test_debug_refuses_before_any_query():
    _case(V1, OCT)
    with override_settings(DEBUG=True), CaptureQueriesContext(connection) as queries:
        result = coach_rows.coach_grade_on_database()
    assert result == {'refusal': 'debug_on'} and queries.captured_queries == []
    assert coach_result_schema.coach_result_allowed(result)


def test_one_select_of_four_columns_and_nothing_else():
    _case(V1, OCT)
    _case(V1, None)
    with CaptureQueriesContext(connection) as queries:
        records = coach_rows.coach_records()
    assert len(queries.captured_queries) == 1
    sql = queries.captured_queries[0]['sql']
    assert sql.lstrip().upper().startswith('SELECT')
    assert 'verdict_decided_by' not in sql and 'verdict_reason' not in sql
    assert len(records) == 1 and len(records[0]) == 4


# ── the dry run ───────────────────────────────────────────────────────────────────────────────────
def _dry_run_cases():
    """V1: 10 cases in October (40 facts, all right). V2: one in October (4 facts, a too-few cell) and 10
    in November (40 facts), two of them with an identity Fail on a Certain band (-10 each): one with the
    reason interview_differs, one with reason other and a QC "disagreed" (the QC answer is carried in the
    stored verdict and, as on F4's card, does not change the mark). Two pre-versioning cases, two with a
    planted name as their label (the unknown version), one not decided. One case carries a canary name
    and id."""
    _case(V1, OCT, id=ID_CANARY, student=make_student(name=NAME_CANARY))
    for _ in range(9):
        _case(V1, OCT)
    _case(V2, OCT + datetime.timedelta(days=10))
    for _ in range(8):
        _case(V2, NOV)
    _case(V2, NOV, verdict=_failed('interview_differs'))
    _case(V2, NOV, verdict=_failed('other', qc={'identity': 'disagreed'}))
    for _ in range(2):
        _case(PRE_VERSIONING, NOV)
        _case(PLANTED_LABEL, NOV)
    _case(V2, None)


def test_dry_run_counts_select_only_and_no_case_data(capfd, caplog):
    _dry_run_cases()
    capfd.readouterr()
    with caplog.at_level(logging.DEBUG), CaptureQueriesContext(connection) as queries:
        report = coach_rows.coach_grade_on_database()
    statements = [q['sql'] for q in queries.captured_queries]
    assert len(statements) == 1 and all(s.lstrip().upper().startswith('SELECT') for s in statements)

    assert (report['decided_records'], report['malformed_records'], report['versions_without_marks']) == (25, 0, 0)
    assert report['left_out_reasons'] == ['interview_differs']
    cells = [(c['version'], c['month'], c['too_few'], c.get('facts'), c.get('points')) for c in report['months']]
    assert cells == [(V1, '2026-10', False, 40, 80), (V2, '2026-10', True, None, None),
                     (V2, '2026-11', False, 40, 56),
                     (coach_grade.UNKNOWN_VERSION, '2026-11', False, 8, 16), (PRE_VERSIONING, '2026-11', False, 8, 16)]
    assert report['months'][2]['without_left_out'] == {'too_few': False, 'facts': 39, 'points': 66, 'best': 78,
                                                       'score_pct': 85, 'left_out': 1}
    (pair,) = report['coach']
    assert (pair['previous']['version'], pair['new']['version'], pair['grade']) == (V1, V2, 'no_change')
    assert pair['new']['facts'] == 44 and pair['new']['generous_wrong'] == {'count': 2, 'of': 44}
    assert pair['new']['without_left_out']['left_out'] == 1 and report['waiting'] == []

    # the mirror: the same marks as F4's score over the same decided rows
    rows = [(a, b, c, d) for a, b, c, d in coach_rows.coach_records() if c == V2]
    assert ai_score.score_marks(rows)['points'] == 64

    assert coach_result_schema.coach_result_allowed(report)
    text = coach_result_schema.checked_coach_text(report)
    assert json.loads(text) == report
    captured = capfd.readouterr()
    everything = '\n'.join([text, captured.out, captured.err, caplog.text])
    for canary in (PLANTED_LABEL, NAME_CANARY, REASON_CANARY, DECIDER_CANARY, str(ID_CANARY), 'Aminah'):
        assert canary not in everything


# ── the fold of odd malformed kinds into other_error ─────────────────────────────────────────────
GOOD_KINDS = {'KeyError': 7, 'ValidationError': 8, 'too_short': 9}
ODD_KINDS = {'maria': 1, 'keyerror': 2, 'A' * 56 + 'Error': 3, 'Key_Error': 4, 'Key.Error': 5, 'SitiAminah': 6}


def _with_kinds(kinds):
    report = coach_grade.coach_report([])
    report['malformed_by_error'] = dict(kinds)
    report['malformed_records'] = sum(kinds.values())
    return report


def test_the_fold_moves_each_odd_kind_into_other_error_and_keeps_the_good_ones():
    report = _with_kinds({**ODD_KINDS, **GOOD_KINDS})
    before = json.loads(json.dumps(report))
    assert not coach_result_schema.coach_result_allowed(report)
    folded = coach_rows.fold_odd_kinds(report)
    assert folded['malformed_by_error'] == {**GOOD_KINDS, coach_grade.OTHER_ERROR: 21}
    assert list(folded['malformed_by_error']) == sorted(folded['malformed_by_error'])
    assert sum(folded['malformed_by_error'].values()) == folded['malformed_records'] == 45
    assert coach_result_schema.coach_result_allowed(folded)
    assert {k: v for k, v in folded.items() if k != 'malformed_by_error'} == {
        k: v for k, v in report.items() if k != 'malformed_by_error'}
    assert report == before and folded is not report     # a copy: the given report is never changed
    text = coach_result_schema.checked_coach_text(folded)
    for kind in ODD_KINDS:
        assert kind not in text
    assert 'Aminah' not in text and 'maria' not in text


def test_the_fold_adds_to_an_other_error_already_there_and_makes_one_when_absent():
    folded = coach_rows.fold_odd_kinds(_with_kinds({coach_grade.OTHER_ERROR: 5, 'maria': 2, 'TypeError': 1}))
    assert folded['malformed_by_error'] == {coach_grade.OTHER_ERROR: 7, 'TypeError': 1}
    folded = coach_rows.fold_odd_kinds(_with_kinds({'maria': 2}))
    assert folded['malformed_by_error'] == {coach_grade.OTHER_ERROR: 2} and folded['malformed_records'] == 2
    for folded in (coach_rows.fold_odd_kinds(_with_kinds({coach_grade.OTHER_ERROR: 5, 'maria': 2})),
                   coach_rows.fold_odd_kinds(_with_kinds({'maria': 2}))):
        assert coach_result_schema.coach_result_allowed(folded)


def test_the_fold_leaves_a_clean_report_and_odd_shapes_alone():
    clean = _with_kinds(GOOD_KINDS)
    assert coach_rows.fold_odd_kinds(clean) is clean
    bad_count = _with_kinds({'maria': 1})
    bad_count['malformed_by_error']['maria'] = 1.0       # not an int: left for the allow-list to fail
    assert coach_rows.fold_odd_kinds(bad_count) is bad_count
    assert not coach_result_schema.coach_result_allowed(bad_count)
    for odd in ({'refusal': 'debug_on'}, {'error': 'schema'}, [], None):
        assert coach_rows.fold_odd_kinds(odd) is odd


class Maria(Exception):
    """A real error class whose name is a word, not an error class name."""


class OddRecordProblem(ValueError):
    pass


class RecordReadError(Exception):
    pass


def _raises(error_class):
    class Record:
        def __len__(self):
            raise error_class('the message never leaves')
    return Record()


def test_end_to_end_an_odd_class_name_from_coach_report_is_folded(monkeypatch):
    """Real `coach_report` code: a record whose length raises is filed under the error's class name."""
    _case(V1, OCT)
    real = coach_rows.coach_records()
    planted = [_raises(Maria), _raises(Maria), _raises(OddRecordProblem), _raises(RecordReadError)]
    raw = coach_grade.coach_report(real + planted, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
    assert raw['malformed_by_error'] == {'Maria': 2, 'OddRecordProblem': 1, 'RecordReadError': 1}
    monkeypatch.setattr(coach_rows, 'coach_records', lambda: real + planted)
    report = coach_rows.coach_grade_on_database()
    assert report['malformed_by_error'] == {'RecordReadError': 1, coach_grade.OTHER_ERROR: 3}
    assert report['malformed_records'] == 4
    assert {k: v for k, v in report.items() if k != 'malformed_by_error'} == {
        k: v for k, v in raw.items() if k != 'malformed_by_error'}
    text = coach_result_schema.checked_coach_text(report)
    assert json.loads(text) == report
    for word in ('Maria', 'OddRecordProblem', 'the message never leaves'):
        assert word not in text
