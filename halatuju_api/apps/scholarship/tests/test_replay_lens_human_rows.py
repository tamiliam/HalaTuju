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
def test_a_status_moved_past_the_decision_is_recovered_by_its_in_review_twin(desk):
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')
    row = rows_by_id()[app.pk]
    assert (row['recomputed_fingerprint'], row['recompute_note']) == (
        app.ai_verdict_context['fingerprint'], lens_human.RECOVERED_BY_TWIN)
    assert row['fresh_snapshot'] == app.ai_verdict_snapshot


def test_a_past_award_status_listed_before_recommended_still_makes_no_twin(desk, monkeypatch):
    from apps.scholarship import closure
    codes = [code for code, _label in ScholarshipApplication.STATUS_CHOICES]
    past = [code for code in codes if code in closure.POST_AWARD_STATUSES]
    assert past and codes.index(past[0]) > codes.index('recommended')   # the order this test turns round
    ordered = [c for c in ScholarshipApplication.STATUS_CHOICES if c[0] in past] + [
        c for c in ScholarshipApplication.STATUS_CHOICES if c[0] not in past]
    monkeypatch.setattr(ScholarshipApplication, 'STATUS_CHOICES', ordered)
    app = decide(desk)
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')
    made = []
    real = R._other_stage_twins

    def spy(case, status_codes):
        assert list(status_codes)[:len(past)] == past                    # the past-award codes come first
        for twin in real(case, status_codes):
            made.append(twin.status)
            yield twin
    monkeypatch.setattr(R, '_other_stage_twins', spy)
    row = rows_by_id()[app.pk]
    assert made and not set(made) & set(closure.POST_AWARD_STATUSES)
    assert (row['recomputed_fingerprint'], row['recompute_note']) == (
        app.ai_verdict_context['fingerprint'], lens_human.RECOVERED_BY_TWIN)


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
def test_every_row_has_the_nine_fields_and_the_stored_values(desk):
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


def test_the_stage_twins_are_copies_and_a_recovered_snapshot_is_built_on_the_twin(desk, monkeypatch):
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
    with CaptureQueriesContext(connection) as queries:
        row = rows_by_id()[app.pk]
    assert row['recompute_note'] == lens_human.RECOVERED_BY_TWIN
    calls = [c for c in seen['context'] if c[0].pk == app.pk]
    real = calls[0][0]
    assert real.status == 'recommended' and [s for _c, s in calls] == ['recommended', 'submitted']
    assert all(case is not real for case, _status in calls[1:])
    (twin, status_at_snapshot), = [s for s in seen['snapshot'] if s[0].pk == app.pk]
    assert twin is calls[1][0] and twin is not real and status_at_snapshot == 'submitted'
    assert real.status == 'recommended'                                     # the real instance untouched
    assert not any(R.at_past_award_stage(status, case.active_at) for case, status in calls)
    assert ScholarshipApplication.objects.filter(pk=app.pk).values().get() == before
    statements = [q['sql'].lstrip().upper() for q in queries.captured_queries]
    assert statements and all(s.startswith(SQL_ALLOWED) for s in statements)


# ── LL5 B2b, task 1: time.time cannot move a row (finding (a)) ─────────────────────────────────────
def informal_slip(desk, vision_extra, extra_fields=None):
    """A made-up salary case whose only proof is a declaration slip the AI doubts, stamped live."""
    cohort, reviewer = desk
    app = make_application('awaiting_qc', outcome='recommend', cohort=cohort, reviewer=reviewer,
                           income_route='salary', income_working_members=['father'], income_earner='',
                           mother_occupation='homemaker', father_name='Made Up', father_occupation='fisherman',
                           other_family_members=[])
    vision = {'fields': {'gross_income': 'RM800', **(extra_fields or {})}, 'student_verdict': 'ok', 'error': '',
              'authenticity': {'status': 'suspect', 'doc_seen': 'declaration', 'probability': 0.5}, **vision_extra}
    create_document(application=app, doc_type='salary_slip', household_member='father', vision_fields=vision,
                    storage_path=f'test/slip/{app.pk}', vision_run_at=timezone.now())
    return record(desk, app)


def test_time_time_far_from_the_stamp_moves_no_byte_of_a_row(award_desk, monkeypatch):
    import time
    real = time.time()
    open_window = informal_slip(award_desk, {income_declaration.APPROVAL_ERROR: 'made-up',
                                             income_declaration.APPROVAL_UNTIL: int(real) + 3600})
    tried = informal_slip(award_desk, {income_declaration.APPROVAL_TRIED: int(real) - 60},
                          {'issuer_header': 'MADE UP', 'approver_title': 'KETUA', 'has_stamp_or_signature': 'stamp'})
    recovered = stamp_at(award_desk, 'interviewed')
    move(recovered, 'awarded', False)
    seen = []
    real_expired = income_declaration.approval_expired

    def spy(doc):
        seen.append(real_expired(doc))
        return seen[-1]

    monkeypatch.setattr(income_declaration, 'approval_expired', spy)
    texts = []
    for now in (real, real + 30 * 24 * 3600, real - 365 * 24 * 3600):
        with monkeypatch.context() as pinned:
            pinned.setattr(time, 'time', lambda now=now: now)
            rows = rows_by_id()
            texts.append(json.dumps([rows[a.pk] for a in (open_window, tried, recovered)], sort_keys=True, default=str))
    assert texts[0] == texts[1] == texts[2]
    assert True in seen and False in seen                 # the window really was read open AND shut
    for app in (open_window, tried, recovered):
        assert rows[app.pk]['recomputed_fingerprint'] == app.ai_verdict_context['fingerprint']
        assert rows[app.pk]['fresh_snapshot'] == app.ai_verdict_snapshot


# ── LL5 B2b narrow B: a moved-on case recovered by an in-review twin ───────────────────────────────
def note_of(row):
    return row['recomputed_fingerprint'], row['recompute_note']


@pytest.mark.parametrize('later,funded', PAST_AWARD_LATER + KEPT_LATER)
def test_decided_in_review_then_moved_on_is_recovered_with_the_stamped_snapshot(award_desk, later, funded):
    app = stamp_at(award_desk, 'interviewed')
    move(app, later, funded)
    moved = ScholarshipApplication.objects.filter(pk=app.pk).values().get()
    row = rows_by_id()[app.pk]
    assert note_of(row) == (app.ai_verdict_context['fingerprint'], lens_human.RECOVERED_BY_TWIN)
    assert row['fresh_snapshot'] == app.ai_verdict_snapshot
    assert ScholarshipApplication.objects.filter(pk=app.pk).values().get() == moved


def test_every_in_review_status_builds_the_same_snapshot_bytes(award_desk):
    """The twin list keeps ONE in-review status per stage-facts group (the first); this holds that any
    other in-review status would have built the same bytes."""
    cases = [decide(award_desk), stamp_at(award_desk, 'interviewed'),
             informal_slip(award_desk, {income_declaration.APPROVAL_ERROR: 'made-up',
                                        income_declaration.APPROVAL_UNTIL: 2_000_000_000})]
    in_review = [code for code, _label in ScholarshipApplication.STATUS_CHOICES
                 if verdict_context.stage_facts(types.SimpleNamespace(profile_completed_at=NOW, status=code))[
                     'in_review_status']]
    assert in_review == ['submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed']
    for app in cases:
        texts = set()
        for status in in_review:
            ScholarshipApplication.objects.filter(pk=app.pk).update(status=status)
            texts.add(json.dumps(built_today(app.pk, app.verdict_decided_at), sort_keys=True))
        assert len(texts) == 1 and json.loads(texts.pop()) == app.ai_verdict_snapshot


def test_a_twin_in_the_decided_group_is_never_recovered(award_desk):
    app = stamp_at(award_desk, 'recommended')
    move(app, 'interviewing', False)                     # back in review (a database move)
    row = rows_by_id()[app.pk]
    assert note_of(row) == (None, 'decided_group_twin') and row['fresh_snapshot'] is None


def test_past_the_award_with_a_direct_match_is_not_recomputed(award_desk):
    app = stamp_at(award_desk, 'recommended')
    move(app, 'awarded', False)
    row = rows_by_id()[app.pk]
    assert note_of(row) == (None, 'past_award_stage') and row['fresh_snapshot'] is None


@pytest.mark.parametrize('stamped', ['interviewed', 'recommended'])
def test_no_twin_match_is_evidence_changed(award_desk, stamped):
    app = stamp_at(award_desk, stamped)
    move(app, 'interviewing' if stamped == 'recommended' else 'recommended', False)
    _changed_document(app)
    row = rows_by_id()[app.pk]
    assert row['recomputed_fingerprint'] not in (None, app.ai_verdict_context['fingerprint'])
    assert row['recompute_note'] is None and row['fresh_snapshot'] is not None


@pytest.mark.parametrize('later,funded', [('recommended', False), ('awarded', False), ('active', True)])
def test_moved_on_and_evidence_changed_is_evidence_changed_never_valid(award_desk, later, funded):
    app = stamp_at(award_desk, 'interviewed')
    move(app, later, funded)
    _changed_document(app)
    row = rows_by_id()[app.pk]
    assert row['recomputed_fingerprint'] not in (None, app.ai_verdict_context['fingerprint'])
    assert row['recompute_note'] is None
    assert (row['fresh_snapshot'] is None) == (later != 'recommended')     # B1: no snapshot past the award


def _twins_at(*statuses):
    def twins(app, _codes):
        for status in statuses:
            twin = R.copy.copy(app)
            twin.status = status
            yield twin
    return twins


@pytest.mark.parametrize('statuses,differ,note', [
    (('submitted', 'interviewed'), True, 'twin_not_unique'),
    (('submitted', 'interviewed'), False, lens_human.RECOVERED_BY_TWIN),
    (('submitted', 'recommended'), False, 'twin_not_unique'),
    (('recommended',), False, 'decided_group_twin'),
])
def test_matching_twins_must_all_be_in_review_with_the_same_snapshot_bytes(desk, monkeypatch, statuses, differ, note):
    """Two twins never match with the real list (other stage facts hash apart), so the list is patched."""
    app = decide(desk)
    move(app, 'closed', False)
    stored = app.ai_verdict_context['fingerprint']
    real_context, real_verdict = verdict_context.build_verdict_context, verdict_engine.build_verdict
    monkeypatch.setattr(R, '_other_stage_twins', _twins_at(*statuses))
    monkeypatch.setattr(verdict_context, 'build_verdict_context', lambda case: dict(
        real_context(case), fingerprint=stored if case.status != 'closed' else 'today'))
    monkeypatch.setattr(verdict_engine, 'build_verdict', lambda case: real_verdict(case) + (
        [{'fact': case.status}] if differ else []))
    row = rows_by_id()[app.pk]
    recovered = note == lens_human.RECOVERED_BY_TWIN
    assert note_of(row) == (stored if recovered else None, note)
    assert row['fresh_snapshot'] == (app.ai_verdict_snapshot if recovered else None)


def test_a_twin_whose_fingerprint_differs_is_not_recovered(desk, monkeypatch):
    app = decide(desk)
    move(app, 'closed', False)
    real_context = verdict_context.build_verdict_context
    monkeypatch.setattr(R, '_other_stage_twins', _twins_at('submitted'))
    monkeypatch.setattr(verdict_context, 'build_verdict_context', lambda case: dict(
        real_context(case), fingerprint='today' if case.status == 'closed' else 'neither'))
    assert note_of(rows_by_id()[app.pk]) == ('today', None)


def test_a_caught_recompute_error_and_another_key_carry_their_reason(desk, monkeypatch):
    bad, other_key, blank_later = decide(desk), decide(desk), decide(desk)
    ScholarshipApplication.objects.filter(pk=other_key.pk).update(
        ai_verdict_context=dict(other_key.ai_verdict_context, key_check='00000000'))
    monkeypatch.setattr(verdict_context, 'build_verdict_context',
                        _breaks_for(bad.pk, ValueError('x'), verdict_context.build_verdict_context))
    rows = rows_by_id()
    assert note_of(rows[bad.pk]) == (None, 'recompute_error') and rows[bad.pk]['fresh_snapshot'] is not None
    assert note_of(rows[other_key.pk]) == (None, 'key_not_current')
    blank = {row['application_id']: row for row in R.human_lens_rows(current_key_check=None)}
    assert note_of(blank[blank_later.pk]) == (None, 'key_not_current')


def test_the_query_cost_of_a_direct_and_a_recovered_case(award_desk):
    direct = decide(award_desk)
    base = _queries()
    recovered = decide(award_desk)
    with_direct = _queries()
    move(recovered, 'recommended', False)
    with_recovered = _queries()
    assert note_of(rows_by_id()[direct.pk])[1] is None
    # one SELECT for the cases; a recovered case costs a direct one plus one: the twin's fingerprint read
    assert with_recovered - base == (with_direct - base) + 1 == (base - 1) + 1
    assert note_of(rows_by_id()[recovered.pk])[1] == lens_human.RECOVERED_BY_TWIN


def _queries():
    with CaptureQueriesContext(connection) as queries:
        rows_by_id()
    return len(queries.captured_queries)


def test_end_to_end_a_mix_gives_exactly_the_expected_counts(award_desk, tmp_path, monkeypatch):
    folder = tmp_path / 'exams'
    folder.mkdir()
    direct = [decide(award_desk) for _ in range(44)]
    twin_award, twin_qc = stamp_at(award_desk, 'interviewed'), stamp_at(award_desk, 'interviewed')
    decided_twin, past_award = stamp_at(award_desk, 'recommended'), stamp_at(award_desk, 'recommended')
    changed, broken = stamp_at(award_desk, 'interviewed'), decide(award_desk)
    frozen = R.run_human_lens_on_database(str(folder), NOW, freeze=True)['exams']['exam-1']
    assert frozen['valid_split'] == {'matched_directly': 50, 'recovered_by_twin': 0}
    assert set(frozen['could_not_recompute_reasons'].values()) == {0}
    move(twin_award, 'awarded', False)
    move(twin_qc, 'recommended', False)
    move(decided_twin, 'interviewing', False)
    move(past_award, 'awarded', False)
    move(changed, 'recommended', False)
    _changed_document(changed)
    monkeypatch.setattr(verdict_context, 'build_verdict_context',
                        _breaks_for(broken.pk, ValueError('x'), verdict_context.build_verdict_context))
    e = R.run_human_lens_on_database(str(folder), NOW)['exams']['exam-1']
    assert e['validity'] == {'valid': 46, 'evidence_changed': 1, 'could_not_recompute': 3, 'missing': 0,
                             'context_changed': 0, 'no_longer_decided': 0, 'decided_again': 0}
    assert e['valid_split'] == {'matched_directly': 44, 'recovered_by_twin': 2} and len(direct) == 44
    assert e['could_not_recompute_reasons'] == {'past_award_stage': 1, 'decided_group_twin': 1,
                                                'twin_not_unique': 0, 'recompute_error': 1, 'key_not_current': 0}
    assert sum(e['valid_split'].values()) == e['validity']['valid']
    assert sum(e['could_not_recompute_reasons'].values()) == e['validity']['could_not_recompute']
    assert e['still_valid'] == '46 of 50 still valid'
