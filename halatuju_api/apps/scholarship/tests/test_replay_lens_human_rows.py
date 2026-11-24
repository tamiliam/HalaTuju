"""LL5 phase B2b - the human lens's database half (`eval/replay/lens_human_rows.py`). Made-up rows only,
built with the factories and stamped through the LIVE record-verdict door. The derived key is made up
here. Every exam folder is a pytest temp folder outside the repository."""
import datetime
import json
import logging
import os
import pathlib
import re
import types

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import income_declaration, second_look, verdict_context, verdict_engine
from apps.scholarship.eval.replay import clock, lens_human, netguard
from apps.scholarship.eval.replay import lens_human_rows as R
from apps.scholarship.models import (
    ApplicantDocument, InterviewSession, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.tests.factories import (
    RECOMMEND_VERDICT, TEST_JWT_SECRET, answered_findings, authed_client, create_document, make_admin,
    make_application, make_cohort, make_student,
)

KEY = '9f3a5c7e' * 8                      # 64 made-up hex characters: a derived key for these tests only
NAME_CANARY = 'CANARYNAME ZQXWV'
ID_CANARY = 8642097
NOW = datetime.datetime(2026, 11, 24, 12, 0, tzinfo=datetime.timezone.utc)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SQL_ALLOWED = ('SELECT', 'SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT')

pytestmark = pytest.mark.django_db


@pytest.fixture
def keyed(settings):
    settings.ROOT_URLCONF = 'halatuju.urls'
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    settings.VERDICT_FINGERPRINT_DERIVED_KEY = KEY
    return settings


@pytest.fixture
def desk(keyed):
    cohort = make_cohort()
    return cohort, make_admin('reviewer', owning_org=cohort.owning_organisation)


def decide(desk, **overrides):
    """A case awaiting QC, its verdict recorded (again) through the live door, re-read from the database."""
    cohort, reviewer = desk
    return record(desk, make_application('awaiting_qc', outcome='recommend', cohort=cohort, reviewer=reviewer,
                                         **overrides))


def record(desk, app):
    """``app``'s verdict recorded through the live door, re-read from the database."""
    _cohort, reviewer = desk
    response = authed_client(reviewer).post(
        f'/api/v1/admin/scholarship/applications/{app.pk}/record-verdict/',
        {'officer_verdict': dict(RECOMMEND_VERDICT), 'reason': 'Made-up reason.'}, format='json')
    assert response.status_code == 200, response.status_code
    return ScholarshipApplication.objects.get(pk=app.pk)


def rows_by_id():
    _blank, check = R.human_lens_key_facts()
    return {row['application_id']: row for row in R.human_lens_rows(current_key_check=check)}


# ── T1: the live stamp and the recompute agree ─────────────────────────────────────────────────────
def test_a_case_stamped_by_the_live_door_recomputes_to_its_stored_fingerprint(desk):
    app = decide(desk)
    assert R.human_lens_key_facts() == (False, app.ai_verdict_context['key_check'])
    row = rows_by_id()[app.pk]
    assert row['recomputed_fingerprint'] == app.ai_verdict_context['fingerprint']
    assert row['fresh_snapshot'] == app.ai_verdict_snapshot          # the shape the live save stores
    assert row['engine_version'] == app.ai_verdict_engine_version == verdict_engine.VERDICT_ENGINE_VERSION


# ── T2: evidence changed after the stamp moves the recompute ──────────────────────────────────────
def _changed_document(app):
    ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='test/offer')


def _changed_declared(app):
    ScholarshipApplication.objects.filter(pk=app.pk).update(chosen_pathway='stpm')


def _changed_profile(app):
    StudentProfile.objects.filter(pk=app.profile_id).update(household_size=9)


def _changed_intake(app):
    ScholarshipCohort.objects.filter(pk=app.cohort_id).update(income_ceiling=4321)


@pytest.mark.parametrize('change', [_changed_document, _changed_declared, _changed_profile, _changed_intake])
def test_evidence_changed_after_the_stamp_gives_another_fingerprint(desk, change):
    app = decide(desk)
    change(app)
    recomputed = rows_by_id()[app.pk]['recomputed_fingerprint']
    assert recomputed is not None and recomputed != app.ai_verdict_context['fingerprint']


# ── F2: a stage that moved since the decision is never guessed ──────────────────────────────────────
def test_a_status_moved_past_the_decision_gives_no_fingerprint(desk):
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')
    assert rows_by_id()[app.pk]['recomputed_fingerprint'] is None


def test_a_status_change_inside_the_same_stage_facts_still_recomputes(desk):
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='interviewing')   # both "in review"
    assert rows_by_id()[app.pk]['recomputed_fingerprint'] == app.ai_verdict_context['fingerprint']


def test_a_full_context_under_another_key_check_is_not_recomputed(desk):
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        ai_verdict_context=dict(app.ai_verdict_context, key_check='00000000'))
    assert rows_by_id()[app.pk]['recomputed_fingerprint'] is None


# ── T3: both engine calls read the case's decision time ───────────────────────────────────────────
def test_each_case_runs_under_its_own_decision_time(desk, monkeypatch):
    apps = [decide(desk) for _ in range(2)]
    seen = {'fp': {}, 'snap': {}}
    real_context, real_verdict = verdict_context.build_verdict_context, verdict_engine.build_verdict

    def spy_context(app):
        seen['fp'].setdefault(app.pk, timezone.now())
        return real_context(app)

    def spy_verdict(app):
        seen['snap'][app.pk] = (timezone.now(), datetime.date.today())
        return real_verdict(app)

    monkeypatch.setattr(verdict_context, 'build_verdict_context', spy_context)
    monkeypatch.setattr(verdict_engine, 'build_verdict', spy_verdict)
    ScholarshipApplication.objects.filter(pk=apps[0].pk).update(
        verdict_decided_at=datetime.datetime(2025, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc))
    rows_by_id()
    for app in ScholarshipApplication.objects.filter(pk__in=[a.pk for a in apps]):
        assert seen['fp'][app.pk] == app.verdict_decided_at
        assert seen['snap'][app.pk][0] == app.verdict_decided_at
    assert seen['snap'][apps[0].pk][1].year == 2025


# ── T4: the key ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('value', ['', '   ', None, KEY[:-1], 'g' * 64, KEY + ' ', ' ' + KEY[1:],
                                   KEY.encode(), 12345, '٣' * 64])
def test_a_key_that_verdict_context_would_not_use_counts_as_blank(keyed, value):
    keyed.VERDICT_FINGERPRINT_DERIVED_KEY = value
    assert R.human_lens_key_facts() == (True, None)


def test_a_missing_key_setting_counts_as_blank(keyed):
    del keyed.VERDICT_FINGERPRINT_DERIVED_KEY
    assert R.human_lens_key_facts() == (True, None)


def test_a_well_formed_key_in_either_case_is_used(keyed):
    for value in (KEY, KEY.upper()):
        keyed.VERDICT_FINGERPRINT_DERIVED_KEY = value
        assert R.human_lens_key_facts() == (False, verdict_context.key_check())


def test_a_blank_key_recomputes_nothing(keyed, desk):
    app = decide(desk)
    keyed.VERDICT_FINGERPRINT_DERIVED_KEY = ''
    assert rows_by_id()[app.pk]['recomputed_fingerprint'] is None


# ── T5: the row contract ──────────────────────────────────────────────────────────────────────────
def test_every_row_has_the_eight_fields_and_the_stored_values(desk):
    qc = {'identity': 'disagreed', 'income': 'agreed', 'academic': 'shrug', 'not_a_fact': 'agreed'}
    full = decide(desk)
    ScholarshipApplication.objects.filter(pk=full.pk).update(
        officer_verdict=dict(full.officer_verdict, identity='fail', qc_fact_checks=qc))
    undecided = make_application('interviewing', cohort=desk[0])
    pre_interview = make_application(
        'profile_complete', cohort=desk[0], status='rejected', rejection_category='pre_interview',
        officer_verdict=dict(RECOMMEND_VERDICT), ai_verdict_context=dict(full.ai_verdict_context))
    old = make_application('awaiting_qc', outcome='recommend', cohort=desk[0])
    failed = make_application('awaiting_qc', outcome='recommend', cohort=desk[0],
                              ai_verdict_context={'schema': 1, 'error': 'build_failed'})
    no_verdict = make_application('awaiting_qc', outcome='recommend', cohort=desk[0], officer_verdict={})
    rows = rows_by_id()
    assert sorted(rows) == sorted(ScholarshipApplication.objects.values_list('pk', flat=True))
    for row in rows.values():
        assert tuple(row) == lens_human.CASE_FIELDS
        stored = ScholarshipApplication.objects.get(pk=row['application_id'])
        assert row['verdict_decided_at'] == stored.verdict_decided_at
        assert row['stored_context'] == stored.ai_verdict_context
        assert row['human_verdict'] == stored.officer_verdict
        assert row['qc_answers'] == second_look.stored(stored.officer_verdict)
        assert row['engine_version'] == verdict_engine.VERDICT_ENGINE_VERSION
    assert rows[full.pk]['qc_answers'] == {'identity': 'disagreed', 'income': 'agreed'}
    assert rows[full.pk]['verdict_decided_at'].utcoffset() == datetime.timedelta(0)
    for app in (undecided, pre_interview):
        assert rows[app.pk]['verdict_decided_at'] is None
        assert rows[app.pk]['recomputed_fingerprint'] is None and rows[app.pk]['fresh_snapshot'] is None
    assert rows[pre_interview.pk]['human_verdict'] == RECOMMEND_VERDICT
    for app in (old, failed, no_verdict):                # decided: a snapshot, but no stored fingerprint
        assert rows[app.pk]['recomputed_fingerprint'] is None
        assert isinstance(rows[app.pk]['fresh_snapshot'], list) and rows[app.pk]['fresh_snapshot']
    assert rows[old.pk]['stored_context'] == {} and rows[no_verdict.pk]['human_verdict'] == {}
    lens_human.run_human_lens(list(rows.values()), exam_folder='/nonexistent-exam-folder', key_is_blank=False,
                              current_key_check=verdict_context.key_check(), now=NOW)   # the lens takes them


def test_undecided_cases_cost_one_query_in_all(keyed):
    for _ in range(3):
        make_application('interviewing')
    with CaptureQueriesContext(connection) as queries:
        rows = R.human_lens_rows(current_key_check=R.human_lens_key_facts()[1])
    assert len(rows) == 3 and len(queries.captured_queries) == 1


# ── T6: end to end, two runs on one folder outside the repository ─────────────────────────────────
def test_end_to_end_freeze_then_score_the_same_exam_then_a_blank_key(keyed, desk, tmp_path):
    folder = tmp_path / 'exams'
    folder.mkdir()
    assert lens_human.exam_folder_refusal(str(folder)) is None
    assert REPO_ROOT not in folder.resolve().parents
    canary = decide(desk, id=ID_CANARY, student=make_student(name=NAME_CANARY))
    full = [canary] + [decide(desk) for _ in range(51)]
    for _ in range(3):
        make_application('awaiting_qc', outcome='recommend', cohort=desk[0])   # decided before LL4: {}
    make_application('interviewing', cohort=desk[0])
    first = R.run_human_lens_on_database(str(folder), NOW, freeze=True)
    exam_1, exam_old = first['exams']['exam-1'], first['exams']['exam-old']
    assert sorted(os.listdir(folder)) == ['exam-1.json', 'exam-old.json']
    assert exam_1['status'] == 'frozen' and exam_1['still_valid'] == '50 of 50 still valid'
    assert exam_1['score']['facts'] > 0 and exam_old['size'] == 3 and exam_old['still_valid'] == '3 of 3 still valid'
    listed = json.loads((folder / 'exam-1.json').read_text())['application_ids']
    assert listed == [a.pk for a in sorted(full, key=lambda a: (a.verdict_decided_at, a.pk))][:50]
    assert first['cases_read'] == 56 and first['not_decided'] == 1
    second = R.run_human_lens_on_database(str(folder), NOW + datetime.timedelta(days=1))
    assert second == first and sorted(os.listdir(folder)) == ['exam-1.json', 'exam-old.json']
    keyed.VERDICT_FINGERPRINT_DERIVED_KEY = ''
    blank =R.run_human_lens_on_database(str(folder), NOW)
    assert blank['exams']['exam-1']['refusal'] == lens_human.KEY_BLANK and blank['exams']['exam-1']['score'] is None
    assert blank['exams']['exam-old'] == exam_old
    text = json.dumps([first, second, blank], default=str)
    for secret in (str(ID_CANARY), NAME_CANARY, KEY, KEY.upper()):
        assert secret not in text


# ── T7: read only, one case's failure stays its own, nothing leaks ────────────────────────────────
def test_the_row_build_issues_selects_only(desk):
    moved = decide(desk)
    ScholarshipApplication.objects.filter(pk=moved.pk).update(status='recommended')   # the stage twins run
    decide(desk)
    make_application('interviewing', cohort=desk[0])
    with CaptureQueriesContext(connection) as queries:
        rows_by_id()
    statements = [q['sql'].lstrip().upper() for q in queries.captured_queries]
    assert statements and all(s.startswith(SQL_ALLOWED) for s in statements), statements[:3]


def _breaks_for(pk, error, real):
    def broken(app):
        if app.pk == pk:
            raise error
        return real(app)
    return broken


def test_a_snapshot_the_engine_cannot_build_gives_none_for_that_case_only(desk, monkeypatch):
    bad, good = decide(desk), decide(desk)
    for error in (ValueError('x'), TypeError('x'), KeyError('x')):
        monkeypatch.setattr(verdict_engine, 'build_verdict', _breaks_for(bad.pk, error, verdict_engine.build_verdict))
        rows = rows_by_id()
        assert rows[bad.pk]['fresh_snapshot'] is None and rows[bad.pk]['recomputed_fingerprint'] is not None
        assert rows[good.pk]['fresh_snapshot'] == good.ai_verdict_snapshot
        monkeypatch.undo()


def test_the_snapshot_has_the_shape_the_json_column_gives_back(desk, monkeypatch):
    app = decide(desk)
    monkeypatch.setattr(verdict_engine, 'build_verdict', lambda _app: ({'fact': 'income', 'notes': ('a', 'b')},))
    assert rows_by_id()[app.pk]['fresh_snapshot'] == [{'fact': 'income', 'notes': ['a', 'b']}]
    monkeypatch.setattr(verdict_engine, 'build_verdict', lambda _app: [{'value': float('nan')}])
    assert rows_by_id()[app.pk]['fresh_snapshot'] is None        # no stored form: the case is not scored


def test_a_fingerprint_that_cannot_be_hashed_gives_none_for_that_case_only(desk, monkeypatch):
    bad, good = decide(desk), decide(desk)
    real = verdict_context.build_verdict_context
    monkeypatch.setattr(verdict_context, 'build_verdict_context', _breaks_for(bad.pk, TypeError('x'), real))
    rows = rows_by_id()
    assert rows[bad.pk]['recomputed_fingerprint'] is None and rows[bad.pk]['fresh_snapshot'] is not None
    assert rows[good.pk]['recomputed_fingerprint'] == good.ai_verdict_context['fingerprint']


@pytest.mark.parametrize('target', ['snapshot', 'fingerprint'])
@pytest.mark.parametrize('error', [AttributeError, NameError, ZeroDivisionError, RuntimeError])
def test_a_programming_error_still_raises(desk, monkeypatch, target, error):
    app = decide(desk)
    module, name = (verdict_engine, 'build_verdict') if target == 'snapshot' else (
        verdict_context, 'build_verdict_context')
    monkeypatch.setattr(module, name, _breaks_for(app.pk, error('x'), getattr(module, name)))
    with pytest.raises(error):
        rows_by_id()


def test_no_id_name_or_key_reaches_a_log_stdout_or_stderr(desk, tmp_path, caplog, capfd, monkeypatch):
    moved = decide(desk, id=ID_CANARY, student=make_student(name=NAME_CANARY))   # every path runs on the canary
    decide(desk)
    ScholarshipApplication.objects.filter(pk=moved.pk).update(status='recommended')
    monkeypatch.setattr(verdict_engine, 'build_verdict',
                        _breaks_for(moved.pk, ValueError(NAME_CANARY), verdict_engine.build_verdict))
    caplog.set_level(logging.DEBUG)
    for name in ('apps', 'django'):          # these two do not propagate to the root, where caplog listens
        monkeypatch.setattr(logging.getLogger(name), 'handlers', [*logging.getLogger(name).handlers, caplog.handler])
    caplog.clear()
    capfd.readouterr()                       # only what the lens run itself writes is checked
    out = R.run_human_lens_on_database(str(tmp_path), NOW)
    captured = capfd.readouterr()
    text = '\n'.join([caplog.text, captured.out, captured.err, json.dumps(out, default=str)])
    for secret in (str(ID_CANARY), NAME_CANARY, KEY, KEY.upper()):
        assert secret not in text


def test_the_module_never_logs_prints_writes_or_reads_the_environment():
    source = pathlib.Path(R.__file__).read_text(encoding='utf-8')
    for banned in (r'\blogging\b', r'\blogger\b', r'\bprint\(', r'\bopen\(', r'\benviron\b', r'getenv',
                   r'\.save\(', r'\.update\(', r'\.delete\(', r'\.create\(', r'bulk_', r'\bcursor\b', r'\.raw\(',
                   r'\bSECRET_KEY\b(?!``)', r'timezone\.now', r'except Exception', r'except BaseException',
                   r'except:', r'\.write\(', r'\bos\.', r'\bsys\.'):
        assert not re.search(banned, source.split('"""', 2)[2]), banned   # the code after the docstring
    assert source.count('from apps.scholarship.models import') == 1   # inside `human_lens_rows` only
    head = source.split('\ndef ', 1)[0]
    assert 'from apps' not in head and 'import apps' not in head   # no engine or model at import time


# ── T8: no network ────────────────────────────────────────────────────────────────────────────────
def test_the_rows_build_with_every_socket_refused(desk):
    app = decide(desk)
    with netguard.refuse_network():
        row = rows_by_id()[app.pk]
    assert row['recomputed_fingerprint'] == app.ai_verdict_context['fingerprint']
    assert row['fresh_snapshot'] == app.ai_verdict_snapshot


def test_a_naive_decision_time_is_refused_by_the_pin_not_swallowed():
    with pytest.raises(ValueError):
        with clock.pinned_clock(datetime.datetime(2026, 1, 1)):
            pass


# ── B1 (review round 1): a case now past the award is never called valid ──────────────────────────
PAST_AWARD_LATER = [('awarded', False), ('active', True), ('maintenance', True), ('closed', True)]
KEPT_LATER = [('recommended', False), ('rejected', False), ('closed', False)]


@pytest.fixture
def award_desk(desk, settings):
    settings.DOC_GENUINENESS_CHECK_ENABLED = True     # the made-up slip's genuineness band is read
    return desk


def stamp_at(desk, status):
    """A made-up salary case whose income fact reads the past-award split, its verdict recorded through
    the live door AT ``status`` (a rejected case only once a super reopened it, as the door demands)."""
    cohort, reviewer = desk
    app = make_application('awaiting_qc', outcome='recommend', cohort=cohort, reviewer=reviewer,
                           income_route='salary', income_working_members=['father'], income_earner='',
                           mother_occupation='homemaker', father_name='Made Up', father_occupation='fisherman',
                           other_family_members=[])
    fields = {'gross_income': 'RM800', 'issuer_header': 'MADE-UP OFFICE', 'approver_name': '',
              'approver_title': 'KETUA KAMPUNG', 'has_stamp_or_signature': 'stamp'}
    create_document(application=app, doc_type='salary_slip', household_member='father',
                    storage_path=f'test/slip/{app.pk}', vision_run_at=timezone.now(),
                    vision_fields={'fields': fields, 'student_verdict': 'ok', 'error': '',
                                   'authenticity': {'status': 'genuine', 'doc_seen': 'declaration',
                                                    'probability': 0.97}})
    InterviewSession.objects.create(application=app, status='submitted', findings=answered_findings(app),
                                    started_at=timezone.now(), submitted_at=timezone.now())
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status=status, decision_reopened_at=timezone.now() if status == 'rejected' else None)
    app = record(desk, ScholarshipApplication.objects.get(pk=app.pk))
    assert app.status == status and app.ai_verdict_context.get('fingerprint')
    return app


def move(app, status, funded):
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status=status, decision_reopened_at=None, active_at=timezone.now() if funded else None)


def built_today(pk, when):
    fresh = ScholarshipApplication.objects.select_related('profile', 'cohort').get(pk=pk)
    with clock.pinned_clock(when):
        return json.loads(json.dumps(verdict_engine.build_verdict(fresh)))


@pytest.mark.parametrize('stamped', ['recommended', 'rejected'])
def test_a_case_stamped_in_the_decided_group_and_now_past_the_award_is_not_recomputed(award_desk, stamped):
    app = stamp_at(award_desk, stamped)
    seen_a_moved_snapshot = False
    for later, funded in PAST_AWARD_LATER:
        move(app, later, funded)
        row = rows_by_id()[app.pk]
        assert (row['recomputed_fingerprint'], row['fresh_snapshot']) == (None, None), later
        seen_a_moved_snapshot |= built_today(app.pk, app.verdict_decided_at) != app.ai_verdict_snapshot
    assert seen_a_moved_snapshot          # the shape is the one B1 found: the stage facts alone hid it
    for later, funded in KEPT_LATER:
        move(app, later, funded)
        row = rows_by_id()[app.pk]
        assert row['recomputed_fingerprint'] == app.ai_verdict_context['fingerprint'], later
        assert row['fresh_snapshot'] == app.ai_verdict_snapshot, later


def test_the_past_award_rule_matches_the_engines_own_split():
    for status, _label in ScholarshipApplication.STATUS_CHOICES:
        for active_at in (None, NOW):
            doc = types.SimpleNamespace(application_id=1,
                                        application=types.SimpleNamespace(status=status, active_at=active_at))
            assert R.at_past_award_stage(status, active_at) is income_declaration._past_award(doc), status


def test_the_exam_old_path_still_builds_a_snapshot_past_the_award(desk):
    old = make_application('awaiting_qc', outcome='recommend', cohort=desk[0])    # decided before LL4: {}
    ScholarshipApplication.objects.filter(pk=old.pk).update(status='awarded')
    row = rows_by_id()[old.pk]
    assert row['recomputed_fingerprint'] is None and isinstance(row['fresh_snapshot'], list)


def test_a_normal_run_never_freezes_then_a_past_award_case_is_not_scored(award_desk, tmp_path):
    folder = tmp_path / 'exams'
    folder.mkdir()
    moved = stamp_at(award_desk, 'recommended')
    others = [decide(award_desk) for _ in range(49)]
    first = R.run_human_lens_on_database(str(folder), NOW)                      # R11: freeze is OFF by default
    assert first['exams']['exam-1']['refusal'] == lens_human.EXAM_MISSING and os.listdir(folder) == []
    frozen = R.run_human_lens_on_database(str(folder), NOW, freeze=True)
    assert frozen['exams']['exam-1']['still_valid'] == '50 of 50 still valid'
    move(moved, 'awarded', False)
    rows = rows_by_id()
    after = R.run_human_lens_on_database(str(folder), NOW)['exams']['exam-1']
    assert after['validity']['could_not_recompute'] == 1 and after['validity']['valid'] == 49
    assert len(others) == 49 and after['still_valid'] == '49 of 50 still valid'
    without = lens_human.run_human_lens([r for pk, r in rows.items() if pk != moved.pk], exam_folder=str(folder),
                                        key_is_blank=False, current_key_check=verdict_context.key_check(),
                                        now=NOW)['exams']['exam-1']
    assert without['validity']['missing'] == 1
    for key in ('score', 'score_without_interview_fails', 'fails', 'qc_turned_to_pass'):
        assert after[key] == without[key], key        # the refused case adds nothing to the score


def test_the_stage_twins_are_copies_and_the_snapshot_reads_todays_real_status(desk, monkeypatch):
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')   # the stage twins run
    before = ScholarshipApplication.objects.filter(pk=app.pk).values().get()
    seen = {'context': [], 'snapshot': []}
    real_context, real_verdict = verdict_context.build_verdict_context, verdict_engine.build_verdict

    def spy_context(case):
        seen['context'].append((case, case.status))
        return real_context(case)

    def spy_verdict(case):
        seen['snapshot'].append((case, case.status))
        return real_verdict(case)

    monkeypatch.setattr(verdict_context, 'build_verdict_context', spy_context)
    monkeypatch.setattr(verdict_engine, 'build_verdict', spy_verdict)
    assert rows_by_id()[app.pk]['recomputed_fingerprint'] is None
    (real, status_at_snapshot), = [s for s in seen['snapshot'] if s[0].pk == app.pk]
    assert status_at_snapshot == real.status == 'recommended'
    calls = [c for c in seen['context'] if c[0].pk == app.pk]
    assert calls[0][0] is real and len(calls) > 1
    assert all(case is not real for case, _status in calls[1:])
    assert not any(R.at_past_award_stage(status, case.active_at) for case, status in calls)
    assert ScholarshipApplication.objects.filter(pk=app.pk).values().get() == before
