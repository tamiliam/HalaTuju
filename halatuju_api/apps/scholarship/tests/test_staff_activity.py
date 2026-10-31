"""Common profile S3 (2026-10-31): a staff member's own activity list — the writer and every door.

Roadmap `docs/plans/2026-10-31-common-profile-roadmap.md` (S3; D6, D7, D9). The writer is
`apps/scholarship/staff_activity.record`; the table `staff_activity` (`models/staff_activity.py`).

WHAT IS PROVED HERE
  * the writer: one row with the right actor / verb / subject / organisation; a None actor (a cron, a
    system path) writes nothing, quietly; free text in ``meta`` is dropped; an unknown verb is refused;
  * D9 — best-effort: when the write fails (a REAL database error, or the writer's own code raising)
    the action still succeeds and the caller's transaction is still usable; the write sits in its own
    savepoint; and an action that rolls back leaves no row;
  * every S3 verb, through the door(s) that perform it, writes EXACTLY ONE row — including the QC's
    click, which runs a reopen and a decline underneath and must still be one row;
  * the drift test: the functions that name each verb in the source are exactly `S3_WIRED`, and every
    verb in the closed list is either an S3 writer's or declared as an S4 verb.
"""
import ast
import json
import pathlib
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import (
    closure, invitations, source_invite, source_witness, staff_activity, staff_lifecycle,
    staff_permissions_admin,
)
from apps.scholarship.models import (
    BursaryAgreement, InterviewSession, ResolutionItem, StaffActivity, StaffProfile,
)
from apps.scholarship.services import assign_reviewer, release_pending_declines, submit_interview
from apps.scholarship.tests import factories
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)

APPS = '/api/v1/admin/scholarship/applications/'
V = staff_activity.V
LOG = 'apps.scholarship.staff_activity'


def _url(app, tail):
    return f'{APPS}{app.pk}/{tail}'


class _Base(TestCase):
    """One organisation, its staff, and a cohort inside it."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.cohort = make_cohort(programme=make_programme(organisation=cls.org))
        cls.superadmin = make_admin('super', super_admin=True)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.reviewer2 = make_admin('reviewer', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)

    def app(self, stage, **kw):
        return make_application(stage, cohort=self.cohort, **kw)

    def assertOneRow(self, verb, actor, subject=None, *, org=None, subject_type=None):
        """Exactly one row in the whole table, and it says what it should."""
        rows = list(StaffActivity.objects.all())
        self.assertEqual([r.verb for r in rows], [verb], [(r.verb, r.meta) for r in rows])
        row = rows[0]
        self.assertEqual(row.actor_id, actor.pk)
        if subject is not None:
            self.assertEqual(row.subject_id, subject.pk)
            self.assertEqual(row.subject_type, subject_type or 'application')
        self.assertEqual(row.organisation_id, (org or self.org).pk if org is not False else None)
        self.assertFalse(row.backfilled)
        return row

    def assertNoRows(self):
        self.assertEqual(list(StaffActivity.objects.values_list('verb', flat=True)), [])


# ── the writer ─────────────────────────────────────────────────────────────────────────────────
class TestTheWriter(_Base):

    def test_one_row_with_the_subjects_organisation(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        row = staff_activity.record(self.reviewer, V.VERDICT_RECORDED, app, meta={'overall': 'accept'})
        self.assertEqual(self.assertOneRow(V.VERDICT_RECORDED, self.reviewer, app), row)
        self.assertEqual(row.meta, {'overall': 'accept'})

    def test_with_no_subject_the_organisation_is_the_actors(self):
        staff_activity.record(self.reviewer, V.FIRST_SIGN_IN)
        row = self.assertOneRow(V.FIRST_SIGN_IN, self.reviewer)
        self.assertEqual((row.subject_type, row.subject_id), ('', None))

    def test_a_super_outside_any_organisation_has_none(self):
        staff_activity.record(self.superadmin, V.PROFILE_UPDATED, meta={'fields': ['name']})
        self.assertOneRow(V.PROFILE_UPDATED, self.superadmin, org=False)

    def test_a_none_actor_writes_nothing_and_says_nothing(self):
        with self.assertNoLogs(LOG, 'WARNING'):
            self.assertIsNone(staff_activity.record(None, V.CASE_CLOSED))
        self.assertNoRows()

    def test_an_actor_that_is_not_a_staff_row_writes_nothing(self):
        student = factories.make_student()
        with self.assertLogs(LOG, 'WARNING'):
            self.assertIsNone(staff_activity.record(student, V.FIRST_SIGN_IN))
        self.assertNoRows()

    def test_an_unknown_verb_is_refused_not_raised(self):
        with self.assertLogs(LOG, 'WARNING'):
            self.assertIsNone(staff_activity.record(self.reviewer, 'made_tea'))
        self.assertNoRows()

    def test_free_text_in_meta_is_dropped_and_the_row_still_written(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        with self.assertLogs(LOG, 'WARNING') as logs:
            staff_activity.record(self.reviewer, V.QUERY_RAISED, app, meta={
                'kind': 'doc',                          # a code: kept
                'item': 7,                              # an id: kept
                'to_admin': self.reviewer2,             # a model instance: stored as its id
                'reason': 'He was rude on the phone',   # a sentence in a code key: dropped
                'fields': ['name', 'Kala Devi'],        # a name in a list of codes: dropped
                'note': 'anything',                     # a key that is not on the list: dropped
                'emailed': 'yes',                       # not a boolean: dropped
                'overall': 'a' * 41,                    # too long to be a code: dropped
            })
        row = StaffActivity.objects.get()
        self.assertEqual(row.meta, {'kind': 'doc', 'item': 7, 'to_admin': self.reviewer2.pk})
        self.assertEqual(len(logs.records), 5)
        self.assertNotIn('rude', json.dumps(row.meta))

    def test_meta_that_is_not_a_dict_is_dropped(self):
        staff_activity.record(self.reviewer, V.FIRST_SIGN_IN, meta=['free', 'text'])
        self.assertEqual(StaffActivity.objects.get().meta, {})

    def test_a_meta_callable_is_evaluated_inside_the_guard(self):
        with self.assertLogs(LOG, 'WARNING'):
            self.assertIsNone(staff_activity.record(self.reviewer, V.FIRST_SIGN_IN,
                                                    meta=lambda: 1 / 0))
        self.assertNoRows()

    def test_a_subject_of_an_unknown_model_is_refused_not_raised(self):
        with self.assertLogs(LOG, 'WARNING'):
            self.assertIsNone(staff_activity.record(self.reviewer, V.FIRST_SIGN_IN,
                                                    subject=self.cohort))
        self.assertNoRows()

    def test_the_actor_deleted_takes_their_rows_with_them(self):
        """D6: the list is own-only, so it goes with the person (CASCADE)."""
        gone = make_admin('reviewer', owning_org=self.org)
        staff_activity.record(gone, V.FIRST_SIGN_IN)
        gone.delete()
        self.assertNoRows()

    def test_the_subject_is_an_id_so_a_purged_student_leaves_the_row(self):
        """D7: `subject_id` is not a foreign key — deleting the application keeps the history."""
        app = self.app('interviewing', reviewer=self.reviewer)
        staff_activity.record(self.reviewer, V.VERDICT_RECORDED, app)
        pk = app.pk
        app.delete()
        self.assertEqual(StaffActivity.objects.get().subject_id, pk)


# ── D9: best-effort ────────────────────────────────────────────────────────────────────────────
def _a_real_db_error():
    """Make the INSERT fail in the database itself (NOT NULL on `verb`), not in Python."""
    real = StaffActivity.objects.create

    def broken(**kw):
        return real(**{**kw, 'verb': None})
    return mock.patch.object(StaffActivity.objects, 'create', side_effect=broken)


def _the_writer_itself_raising():
    return mock.patch('apps.scholarship.staff_activity.clean_meta', side_effect=RuntimeError('boom'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestBestEffort(_Base):

    def test_the_write_sits_in_its_own_savepoint(self):
        depth = {}
        real = StaffActivity.objects.create

        def spy(**kw):
            depth['inside'] = len(connection.savepoint_ids)
            return real(**kw)
        with transaction.atomic():
            depth['outside'] = len(connection.savepoint_ids)
            with mock.patch.object(StaffActivity.objects, 'create', side_effect=spy):
                staff_activity.record(self.reviewer, V.FIRST_SIGN_IN)
        self.assertEqual(depth['inside'], depth['outside'] + 1)

    def test_a_db_error_leaves_the_callers_transaction_usable(self):
        with transaction.atomic():
            with _a_real_db_error(), self.assertLogs(LOG, 'WARNING'):
                self.assertIsNone(staff_activity.record(self.reviewer, V.FIRST_SIGN_IN))
            self.assertFalse(connection.needs_rollback)
            PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(name='Still Writable')
        self.assertEqual(PartnerAdmin.objects.get(pk=self.reviewer.pk).name, 'Still Writable')
        self.assertNoRows()

    def _each_failure(self):
        return (('db error', _a_real_db_error), ('writer raising', _the_writer_itself_raising))

    def test_verify_accept_still_succeeds(self):
        for label, failure in self._each_failure():
            with self.subTest(label):
                app = self.app('verdict_recorded', outcome='recommend', reviewer=self.reviewer)
                with failure(), mock.patch(
                        'apps.scholarship.views_admin.applications.application_completeness',
                        return_value={'complete': True}):
                    resp = authed_client(self.reviewer).post(
                        _url(app, 'verify-accept/'), {'checklist': factories.VERIFY_CHECKLIST},
                        format='json')
                self.assertEqual(resp.status_code, 200, resp.content)
                app.refresh_from_db()
                self.assertEqual((app.status, app.verified_by), ('interviewed', self.reviewer.email))
        self.assertNoRows()

    def test_a_close_still_succeeds_inside_its_row_lock(self):
        for label, failure in self._each_failure():
            with self.subTest(label):
                app = self.app('interviewing', reviewer=self.reviewer)
                with failure():
                    resp = authed_client(self.superadmin).post(
                        _url(app, 'close/'), {'closure_reason': 'stalled'}, format='json')
                self.assertEqual(resp.status_code, 200, resp.content)
                app.refresh_from_db()
                self.assertEqual(app.status, 'closed')
        self.assertNoRows()

    def test_an_assignment_still_succeeds_inside_the_reviewers_lock(self):
        for label, failure in self._each_failure():
            with self.subTest(label):
                app = self.app('assigned', reviewer=self.reviewer)
                with failure():
                    assign_reviewer(app, reviewer=self.reviewer2, by_admin=self.org_admin)
                app.refresh_from_db()
                self.assertEqual(app.assigned_to_id, self.reviewer2.pk)
        self.assertNoRows()

    def test_a_reopen_still_succeeds(self):
        for label, failure in self._each_failure():
            with self.subTest(label):
                app = self.app('recommended', reviewer=self.reviewer)
                with failure():
                    resp = authed_client(self.superadmin).post(
                        _url(app, 'reopen-decision/'), {'reason': 'Wrong income band'},
                        format='json')
                self.assertEqual(resp.status_code, 200, resp.content)
                app.refresh_from_db()
                self.assertIsNotNone(app.decision_reopened_at)
        self.assertNoRows()

    def test_a_first_sign_in_still_succeeds(self):
        for label, failure in self._each_failure():
            with self.subTest(label):
                newcomer = make_admin('reviewer', owning_org=self.org)
                with failure():
                    resp = authed_client(newcomer).get('/api/v1/admin/role/')
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertTrue(resp.json()['is_admin'])
        self.assertNoRows()

    def test_a_rolled_back_action_leaves_no_row(self):
        app = self.app('assigned', reviewer=self.reviewer)

        class Abandon(Exception):
            pass
        with self.assertRaises(Abandon):
            with transaction.atomic():
                assign_reviewer(app, reviewer=self.reviewer2, by_admin=self.org_admin)
                self.assertEqual(StaffActivity.objects.count(), 1)   # it WAS written, inside
                raise Abandon
        self.assertNoRows()

    def test_a_rolled_back_close_leaves_no_row(self):
        app = self.app('interviewing', reviewer=self.reviewer)

        class Abandon(Exception):
            pass
        with self.assertRaises(Abandon):
            with transaction.atomic():
                closure.close_application(app, closure_reason='stalled', actor=self.superadmin)
                raise Abandon
        self.assertNoRows()


# ── the doors: each action, exactly one row ────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   CHECK2_AUTO_GENERATE=False, STUDENT_ASSIGNMENT_EMAIL_ENABLED=False)
class TestTheCaseActions(_Base):

    def test_assign_and_unassign(self):
        app = self.app('assigned', reviewer=self.reviewer)
        assign_reviewer(app, reviewer=self.reviewer2, by_admin=self.org_admin)
        row = self.assertOneRow(V.ASSIGNED, self.org_admin, app)
        self.assertEqual(row.meta, {'from_admin': self.reviewer.pk, 'to_admin': self.reviewer2.pk})
        row.delete()
        assign_reviewer(app, reviewer=None, by_admin=self.org_admin)
        row = self.assertOneRow(V.UNASSIGNED, self.org_admin, app)
        self.assertEqual(row.meta, {'from_admin': self.reviewer2.pk, 'to_admin': None})

    def test_an_unchanged_assignee_writes_nothing(self):
        app = self.app('assigned', reviewer=self.reviewer)
        assign_reviewer(app, reviewer=self.reviewer, by_admin=self.org_admin)
        self.assertNoRows()

    def test_the_assign_endpoint(self):
        app = self.app('assigned', reviewer=self.reviewer)
        resp = authed_client(self.org_admin).post(
            _url(app, 'assign/'), {'reviewer_id': self.reviewer2.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertOneRow(V.ASSIGNED, self.org_admin, app)

    def test_query_raised_as_a_ticket(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        resp = authed_client(self.reviewer).post(
            _url(app, 'resolution-items/'),
            {'kind': 'explanation', 'prompt': 'Tell us about your fees'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QUERY_RAISED, self.reviewer, app)
        item = ResolutionItem.objects.get(application=app, source='officer')
        self.assertEqual(row.meta, {'item': item.pk, 'kind': 'explanation'})
        self.assertNotIn('fees', json.dumps(row.meta))

    def test_query_raised_as_a_note(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        with mock.patch('apps.scholarship.views_admin.resolution.send_request_info_email'):
            resp = authed_client(self.reviewer).post(
                _url(app, 'request-info/'), {'note': 'Please send the March slip'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QUERY_RAISED, self.reviewer, app)
        self.assertEqual(row.meta, {'kind': 'note'})

    def _item(self, app):
        return ResolutionItem.objects.create(
            application=app, source='officer', code='officer_1', kind='confirm', prompt='?')

    def test_query_resolved_by_the_officer(self):
        for action in ('resolve', 'waive'):
            with self.subTest(action):
                StaffActivity.objects.all().delete()
                app = self.app('interviewing', reviewer=self.reviewer)
                item = self._item(app)
                resp = authed_client(self.reviewer).post(
                    f'/api/v1/admin/scholarship/resolution-items/{item.pk}/{action}/', {},
                    format='json')
                self.assertEqual(resp.status_code, 200, resp.content)
                row = self.assertOneRow(V.QUERY_RESOLVED, self.reviewer, app)
                self.assertEqual(row.meta, {'item': item.pk, 'action': action})

    def test_ask_again_raises_the_query_again(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        item = self._item(app)
        resp = authed_client(self.reviewer).post(
            f'/api/v1/admin/scholarship/resolution-items/{item.pk}/reopen/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QUERY_RAISED, self.reviewer, app)
        self.assertEqual(row.meta, {'item': item.pk, 'asked_again': True})

    def test_a_students_own_answer_writes_nothing(self):
        from apps.scholarship.resolution import resolve_item
        app = self.app('interviewing', reviewer=self.reviewer)
        resolve_item(self._item(app), text='I confirm', by='student')
        self.assertNoRows()

    def test_interview_submitted_by_the_person_who_pressed_submit(self):
        """The submitter is the actor even when somebody else is the session's interviewer."""
        app = self.app('assigned', reviewer=self.reviewer)
        session = InterviewSession.objects.create(
            application=app, interviewer=self.reviewer2, status='draft',
            findings=factories.answered_findings(app))
        resp = authed_client(self.reviewer).post(_url(app, 'interview/submit/'), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.INTERVIEW_SUBMITTED, self.reviewer, app)
        self.assertEqual(row.meta, {'session': session.pk, 'interviewer': self.reviewer2.pk})
        session.refresh_from_db()
        submit_interview(session, actor=self.reviewer)       # already submitted: no second row
        self.assertEqual(StaffActivity.objects.count(), 1)

    def test_interview_submitted_with_no_actor_writes_nothing(self):
        app = self.app('assigned', reviewer=self.reviewer)
        submit_interview(InterviewSession.objects.create(
            application=app, interviewer=self.reviewer, status='draft',
            findings=factories.answered_findings(app)))
        self.assertNoRows()

    @mock.patch('apps.scholarship.views_admin.verdict.decision_refusal', return_value=None)
    @mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
    def test_verdict_recorded(self, *_):
        app = self.app('interviewing', reviewer=self.reviewer)
        resp = authed_client(self.reviewer).post(
            _url(app, 'record-verdict/'), {'officer_verdict': factories.RECOMMEND_VERDICT,
                                           'reason': 'Strong case, clear need'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.VERDICT_RECORDED, self.reviewer, app)
        self.assertEqual(row.meta, {'overall': 'accept', 'finalised': False})

    def test_verify_and_accept(self):
        app = self.app('verdict_recorded', outcome='recommend', reviewer=self.reviewer)
        with mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                        return_value={'complete': True}):
            resp = authed_client(self.reviewer).post(
                _url(app, 'verify-accept/'), {'checklist': factories.VERIFY_CHECKLIST},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertOneRow(V.VERIFY_ACCEPT, self.reviewer, app)

    def test_decline_sent_to_qc(self):
        app = self.app('verdict_recorded', outcome='decline', reviewer=self.reviewer)
        resp = authed_client(self.reviewer).post(_url(app, 'submit-decline/'), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertOneRow(V.DECLINE_SENT_TO_QC, self.reviewer, app)

    def test_declined_directly(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        resp = authed_client(self.superadmin).post(
            _url(app, 'reject/'), {'category': 'interview'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.DECLINED, self.superadmin, app)
        self.assertEqual(row.meta, {'category': 'interview'})

    def test_declined_by_the_org_admin_keeps_no_copy_of_the_reason(self):
        app = self.app('shortlisted')
        resp = authed_client(self.org_admin).post(
            _url(app, 'org-reject/'), {'comments': 'Stopped replying in July'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.DECLINED, self.org_admin, app)
        self.assertEqual(row.meta, {'category': 'incomplete'})

    def test_the_cron_releasing_a_decline_writes_nothing(self):
        app = self.app('awaiting_qc', outcome='decline', reviewer=self.reviewer)
        authed_client(self.qc).post(_url(app, 'qc-decision/'), {'decision': 'accept'}, format='json')
        StaffActivity.objects.all().delete()
        release_pending_declines(now=timezone.now() + timedelta(days=30))
        self.assertNoRows()

    # ── the QC's click is ONE row, whatever runs underneath ────────────────────────────────────
    def test_qc_upholds_a_decline(self):
        app = self.app('awaiting_qc', outcome='decline', reviewer=self.reviewer)
        resp = authed_client(self.qc).post(_url(app, 'qc-decision/'), {'decision': 'accept'},
                                           format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QC_DECISION, self.qc, app)
        self.assertEqual(row.meta, {'decision': 'accept', 'outcome': 'declined'})

    @mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
    def test_qc_accepts_a_recommendation(self, _):
        app = self.app('awaiting_qc', outcome='recommend', reviewer=self.reviewer)
        resp = authed_client(self.qc).post(_url(app, 'qc-decision/'), {'decision': 'accept'},
                                           format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QC_DECISION, self.qc, app)
        self.assertEqual(row.meta, {'decision': 'accept', 'outcome': 'recommended'})

    def test_qc_reopens(self):
        app = self.app('awaiting_qc', outcome='recommend', reviewer=self.reviewer)
        resp = authed_client(self.qc).post(
            _url(app, 'qc-decision/'), {'decision': 'reopen', 'comments': 'Missing slip'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QC_DECISION, self.qc, app)       # NOT a second `decision_reopened`
        self.assertEqual(row.meta, {'decision': 'reopen', 'outcome': 'reopened'})

    def test_qc_rejects(self):
        app = self.app('awaiting_qc', outcome='recommend', reviewer=self.reviewer)
        resp = authed_client(self.qc).post(
            _url(app, 'qc-decision/'), {'decision': 'reject', 'comments': 'Income not shown'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.QC_DECISION, self.qc, app)       # not reopen + decline as well
        self.assertEqual(row.meta, {'decision': 'reject', 'outcome': 'declined'})

    def test_decision_reopened_by_a_super(self):
        app = self.app('recommended', reviewer=self.reviewer)
        resp = authed_client(self.superadmin).post(
            _url(app, 'reopen-decision/'), {'reason': 'Wrong income band'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.DECISION_REOPENED, self.superadmin, app)
        self.assertEqual(row.meta, {'from_status': 'recommended'})

    def test_case_closed(self):
        app = self.app('interviewing', reviewer=self.reviewer)
        resp = authed_client(self.superadmin).post(
            _url(app, 'close/'), {'closure_reason': 'stalled'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.CASE_CLOSED, self.superadmin, app)
        self.assertEqual(row.meta, {'reason': 'stalled', 'from_status': 'interviewing'})

    def test_a_close_from_management_code_writes_nothing(self):
        closure.close_application(self.app('interviewing', reviewer=self.reviewer),
                                  closure_reason='stalled', by_email='ops@example.test')
        self.assertNoRows()


# ── witnessing a contract: the source's door and the super's ───────────────────────────────────
@mock.patch('apps.scholarship.bursary._regenerate_artefact')
class TestWitness(_Base):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.source = make_source(organisation=cls.org)
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source,
                              first_seen_at=timezone.now())

    def _agreement(self):
        app = self.app('awarded', source=self.source)
        signed = timezone.now() - timedelta(days=2)
        return app, BursaryAgreement.objects.create(
            application=app, version='2026-v1', student_signed_name='Stu', guarantor_name='Guar',
            student_signed_at=signed, guarantor_signed_at=signed,
            pdf_storage_path=f'{self.org.pk}/{app.pk}/bursary_agreement.pdf')

    def test_the_source_users_witness(self, _):
        app, agreement = self._agreement()
        source_witness.record_once(agreement, org=self.source, by_name='Kala',
                                   witness_name='Kala Devi', admin=self.user)
        row = self.assertOneRow(V.CONTRACT_WITNESSED, self.user, app)
        self.assertEqual(row.meta, {'agreement': agreement.pk, 'by': 'source'})

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_supers_witness_through_the_endpoint(self, _):
        app, agreement = self._agreement()
        resp = authed_client(self.superadmin).post(
            _url(app, 'bursary-agreement/witness/'), {'witness_name': 'Kala Devi'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.CONTRACT_WITNESSED, self.superadmin, app)
        self.assertEqual(row.meta, {'agreement': agreement.pk, 'by': 'staff'})

    def test_a_second_witness_is_refused_and_writes_no_second_row(self, _):
        app, agreement = self._agreement()
        source_witness.record_once(agreement, org=self.source, by_name='K', admin=self.user)
        with self.assertRaises(source_witness.AlreadyWitnessed):
            source_witness.record_once(agreement, org=self.source, by_name='S',
                                       actor=self.superadmin)
        self.assertEqual(StaffActivity.objects.count(), 1)


# ── people: invitations, first sign-in, permissions, profile ───────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestThePeopleActions(_Base):

    def test_first_sign_in_and_the_invitation_it_accepts(self):
        newcomer = make_admin('reviewer', owning_org=self.org)
        inv = invitations.create_or_refresh(
            audience='staff', email=newcomer.email, name=newcomer.name, role='reviewer',
            organisation=self.org, partner_admin=newcomer)
        self.assertEqual(authed_client(newcomer).get('/api/v1/admin/role/').status_code, 200)
        rows = {r.verb: r for r in StaffActivity.objects.all()}
        self.assertEqual(set(rows), {V.FIRST_SIGN_IN, V.INVITATION_ACCEPTED})
        self.assertEqual(rows[V.FIRST_SIGN_IN].actor_id, newcomer.pk)
        self.assertEqual(rows[V.FIRST_SIGN_IN].organisation_id, self.org.pk)
        accepted = rows[V.INVITATION_ACCEPTED]
        self.assertEqual((accepted.actor_id, accepted.subject_type, accepted.subject_id,
                          accepted.organisation_id), (newcomer.pk, 'invitation', inv.pk, self.org.pk))
        # The second visit is not a first sign-in, and the invitation is already closed.
        authed_client(newcomer).get('/api/v1/admin/role/')
        self.assertEqual(StaffActivity.objects.count(), 2)

    def test_a_first_sign_in_with_no_invitation_writes_only_the_sign_in(self):
        newcomer = make_admin('qc', owning_org=self.org)
        authed_client(newcomer).get('/api/v1/admin/role/')
        self.assertOneRow(V.FIRST_SIGN_IN, newcomer)

    def test_invitation_sent_on_a_staff_resend(self):
        target = make_admin('reviewer', owning_org=self.org)
        with mock.patch('apps.courses.staff_reinvite.reissue_credential',
                        return_value=('Temp-pass-123', None)), \
                mock.patch('apps.courses.views_staff.send_partner_welcome_email', return_value=True):
            resp = authed_client(self.org_admin).post(
                f'/api/v1/admin/admins/{target.pk}/resend/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        inv = invitations.open_invitation('staff', target.email)
        row = self.assertOneRow(V.INVITATION_SENT, self.org_admin, inv, subject_type='invitation')
        self.assertEqual(row.meta, {'audience': 'staff', 'emailed': True, 'resend': False})

    def test_invitation_sent_on_a_source_resend(self):
        source = make_source(organisation=self.org)
        target = make_admin('source_partner', owning_org=self.org, source=source)
        with mock.patch('apps.courses.staff_reinvite.reissue_credential',
                        return_value=('Temp-pass-123', None)), \
                mock.patch('apps.scholarship.emails.send_source_invitation_email',
                           return_value=(False, 'bounced')):
            emailed, refusal = source_invite.resend(self.org_admin, target)
        self.assertEqual((emailed, refusal), (False, None))
        inv = invitations.open_invitation(source_invite.AUDIENCE, target.email)
        row = self.assertOneRow(V.INVITATION_SENT, self.org_admin, inv, subject_type='invitation')
        self.assertEqual(row.meta['emailed'], False)

    def test_invitation_sent_for_a_sponsor(self):
        with mock.patch('apps.scholarship.emails.send_sponsor_invitation_email',
                        return_value=(True, '')):
            resp = authed_client(self.org_admin).post(
                '/api/v1/admin/invitations/',
                {'audience': 'sponsor', 'email': 'donor@example.test', 'name': 'Donor'},
                format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        inv = invitations.open_invitation('sponsor', 'donor@example.test')
        row = self.assertOneRow(V.INVITATION_SENT, self.org_admin, inv, subject_type='invitation')
        self.assertEqual(row.meta['audience'], 'sponsor')

    def test_the_backfill_and_an_unattributed_send_write_nothing(self):
        inv = invitations.create_or_refresh(audience='staff', email='x@example.test',
                                            organisation=self.org)
        invitations.record_send(inv, True)
        self.assertNoRows()

    def test_permissions_changed_on_the_editor(self):
        target = make_admin('reviewer', owning_org=self.org)
        staff_permissions_admin.change_permissions(target.pk, ['review', 'spending'],
                                                   by=self.org_admin)
        row = self.assertOneRow(V.PERMISSIONS_CHANGED, self.org_admin, target, subject_type='staff')
        self.assertEqual(row.meta, {'kind': 'edit', 'added': ['spending'], 'removed': []})

    def test_permissions_changed_by_a_role_change_that_reset_a_custom_set(self):
        target = make_admin('reviewer', owning_org=self.org, permissions=['review', 'spending'])
        staff_lifecycle.change_role(target.pk, 'qc', by=self.org_admin)
        row = self.assertOneRow(V.PERMISSIONS_CHANGED, self.org_admin, target, subject_type='staff')
        self.assertEqual(row.meta['kind'], 'role_change')

    def test_a_save_that_changes_nothing_writes_nothing(self):
        target = make_admin('reviewer', owning_org=self.org)
        staff_permissions_admin.change_permissions(target.pk, ['review'], by=self.org_admin)
        self.assertNoRows()

    # ── profile ──────────────────────────────────────────────────────────────────────────────
    def test_profile_updated_on_admin_me_names_fields_never_values(self):
        resp = authed_client(self.reviewer).patch(
            '/api/v1/admin/me/', {'job_title': 'Lead reviewer', 'about': 'I love maths'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.PROFILE_UPDATED, self.reviewer)
        self.assertEqual(row.meta, {'fields': ['about', 'job_title']})
        self.assertNotIn('maths', json.dumps(row.meta))

    def test_profile_updated_on_the_reviewer_cards(self):
        resp = authed_client(self.reviewer).patch(
            '/api/v1/admin/reviewer-profile/', {'university': 'Universiti Malaya'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        row = self.assertOneRow(V.PROFILE_UPDATED, self.reviewer)
        self.assertEqual(row.meta, {'fields': ['university']})

    def test_profile_updated_on_a_photo(self):
        with mock.patch('apps.scholarship.staff_photo.replace',
                        return_value=f'staff-photos/{self.reviewer.pk}/a.webp'), \
                mock.patch('apps.scholarship.staff_photo.signed_url', return_value='https://x'):
            resp = authed_client(self.reviewer).post(
                '/api/v1/admin/me/photo/', {'photo': _png()}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.assertOneRow(V.PROFILE_UPDATED, self.reviewer).meta,
                         {'fields': ['photo']})

    def test_profile_updated_when_a_photo_is_removed_and_not_when_there_was_none(self):
        authed_client(self.reviewer).delete('/api/v1/admin/me/photo/')
        self.assertNoRows()
        StaffProfile.objects.update_or_create(
            partner_admin=self.reviewer,
            defaults={'photo_path': f'staff-photos/{self.reviewer.pk}/a.webp'})
        with mock.patch('apps.scholarship.staff_photo.storage.delete_objects', return_value=True):
            resp = authed_client(self.reviewer).delete('/api/v1/admin/me/photo/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertOneRow(V.PROFILE_UPDATED, self.reviewer)

    def test_profile_updated_on_a_password_change(self):
        sa = 'apps.courses.supabase_admin.'
        with mock.patch(sa + 'read_auth_user', return_value={
                'email': self.reviewer.email, 'app_metadata': {'providers': ['email']}}), \
                mock.patch(sa + 'take_password_attempt', return_value=True), \
                mock.patch(sa + 'verify_password', return_value=True), \
                mock.patch(sa + 'set_password', return_value=True), \
                mock.patch(sa + 'sign_out_other_sessions', return_value=True):
            resp = authed_client(self.reviewer).post(
                '/api/v1/admin/me/password/',
                {'current_password': 'old-secret', 'new_password': 'new-secret-1'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.assertOneRow(V.PROFILE_UPDATED, self.reviewer).meta,
                         {'fields': ['password']})

    def test_profile_updated_on_the_source_console(self):
        source = make_source(organisation=self.org)
        user = make_admin('source_partner', owning_org=self.org, source=source)
        resp = authed_client(user).patch(
            '/api/v1/admin/source/profile/',
            {'user': {'name': 'Kala Devi'}, 'source': {'phone': '03-1234 5678'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.assertOneRow(V.PROFILE_UPDATED, user).meta,
                         {'fields': ['name', 'organisation']})

    def test_profile_updated_by_a_referral_partner(self):
        partner = make_admin('partner', org=make_org())
        resp = authed_client(partner).put(
            '/api/v1/admin/profile/', {'name': 'New Name', 'org_phone': '03-555'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.assertOneRow(V.PROFILE_UPDATED, partner, org=False).meta,
                         {'fields': ['name', 'organisation']})


def _png():
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile('me.png', b'\x89PNG\r\n\x1a\n' + b'0' * 64, content_type='image/png')


# ── the drift test ─────────────────────────────────────────────────────────────────────────────
APPS_DIR = pathlib.Path(__file__).resolve().parents[2]
VERB_NAMES = {name: getattr(staff_activity, name) for name in dir(staff_activity)
              if name.isupper() and isinstance(getattr(staff_activity, name), str)
              and getattr(staff_activity, name) in staff_activity.VERBS}


def _writers():
    """``{(verb, 'path:qualname')}`` for every function in `apps/` (tests excluded) that names a
    verb: ``staff_activity.<VERB>`` or ``staff_activity_hook.record(actor, '<verb>', ...)``."""
    found = set()

    def visit(node, path, stack):
        for child in ast.iter_child_nodes(node):
            inner = stack
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = stack + [child.name]
            where = f'{path}:{".".join(n for n in stack)}'
            if (isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name)
                    and child.value.id == 'staff_activity' and child.attr in VERB_NAMES):
                found.add((VERB_NAMES[child.attr], where))
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                    and child.func.attr == 'record' and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'staff_activity_hook' and len(child.args) >= 2
                    and isinstance(child.args[1], ast.Constant)):
                found.add((child.args[1].value, where))
            visit(child, path, inner)

    for file in APPS_DIR.rglob('*.py'):
        rel = file.relative_to(APPS_DIR).as_posix()
        if '/tests/' in rel or '/migrations/' in rel or rel == 'scholarship/staff_activity.py':
            continue
        text = file.read_text(encoding='utf-8')
        if 'staff_activity' in text:
            visit(ast.parse(text), rel, [])
    return found


class TestTheVerbListHasNoDrift(TestCase):

    def test_every_verb_is_either_wired_in_s3_or_declared_for_s4(self):
        wired = set(staff_activity.S3_WIRED)
        self.assertEqual(wired & staff_activity.S4_VERBS, set())
        self.assertEqual(wired | staff_activity.S4_VERBS, staff_activity.VERBS)

    def test_the_writers_in_the_source_are_exactly_the_registry(self):
        registry = {(verb, where) for verb, places in staff_activity.S3_WIRED.items()
                    for where in places}
        found = _writers()
        self.assertEqual(found - registry, set(), 'a writer that S3_WIRED does not list '
                                                  '(a second door writing the same verb?)')
        self.assertEqual(registry - found, set(), 'S3_WIRED lists a writer that names no verb')

    def test_no_s4_verb_is_written_yet(self):
        self.assertEqual({verb for verb, _ in _writers()} & staff_activity.S4_VERBS, set())

    def test_every_meta_key_has_a_known_type(self):
        kinds = {staff_activity.ID, staff_activity.BOOL, staff_activity.NUMBER,
                 staff_activity.CODE, staff_activity.CODES}
        self.assertEqual(set(staff_activity.META_KEYS.values()) - kinds, set())
