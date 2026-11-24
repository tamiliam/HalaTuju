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
