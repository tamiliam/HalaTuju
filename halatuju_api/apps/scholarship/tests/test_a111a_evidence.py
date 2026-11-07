"""A1.11a / TD-485 — the QC separation guard's evidence is written with the action, or neither.

`staff_activity.record` is best-effort (D9) for every verb EXCEPT the ones `qc_separation.refusal`
reads: a lost one of those let the person QC the case they reviewed. Such a write now raises
`EvidenceNotRecorded` (a 503) and the action's own transaction rolls back with it.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import qc_separation, staff_activity
from apps.scholarship.models import InterviewSession, StaffActivity
from apps.scholarship.services import querying
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org)


def _a_real_db_error():
    """The INSERT fails in the database itself (NOT NULL on `verb`)."""
    real = StaffActivity.objects.create

    def broken(**kw):
        return real(**{**kw, 'verb': None})
    return mock.patch.object(StaffActivity.objects, 'create', side_effect=broken)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestGuardEvidenceIsNotBestEffort(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.cohort = make_cohort(owning_organisation=cls.org)

    def test_the_strict_verbs_are_exactly_the_guards(self):
        self.assertEqual({str(v) for v in staff_activity.GUARD_EVIDENCE},
                         set(qc_separation.REVIEW_VERBS))

    def test_another_verb_stays_best_effort(self):
        with _a_real_db_error(), self.assertLogs('apps.scholarship.staff_activity', 'WARNING'):
            self.assertIsNone(staff_activity.record(self.reviewer, staff_activity.FIRST_SIGN_IN))

    def test_a_lost_guard_row_raises(self):
        app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        with _a_real_db_error(), self.assertLogs('apps.scholarship.staff_activity', 'ERROR'):
            with self.assertRaises(staff_activity.EvidenceNotRecorded):
                staff_activity.record(self.reviewer, staff_activity.DECLINE_SENT_TO_QC, app)

    def test_submit_decline_rolls_back_without_its_evidence(self):
        app = make_application('verdict_recorded', outcome='decline', cohort=self.cohort,
                               reviewer=self.reviewer)
        before = app.status
        with _a_real_db_error():
            r = authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{app.pk}/submit-decline/', {},
                format='json')
        self.assertEqual((r.status_code, r.json().get('code')), (503, 'evidence_not_recorded'),
                         r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, before)
        self.assertFalse(StaffActivity.objects.filter(subject_id=app.pk).exists())

    def test_submit_interview_rolls_back_without_its_evidence(self):
        app = make_application('profile_complete', cohort=self.cohort, reviewer=self.reviewer)
        session = InterviewSession.objects.create(application=app, interviewer=self.reviewer)
        with _a_real_db_error(), mock.patch.object(querying, '_maybe_autofinalise') as finalise:
            with self.assertRaises(staff_activity.EvidenceNotRecorded):
                querying.submit_interview(session, actor=self.reviewer)
        finalise.assert_not_called()
        session.refresh_from_db()
        app.refresh_from_db()
        self.assertNotEqual(session.status, 'submitted')
        self.assertEqual(app.status, 'profile_complete')

    def test_submit_interview_finalises_outside_the_transaction(self):
        from django.db import connection
        app = make_application('profile_complete', cohort=self.cohort, reviewer=self.reviewer)
        session = InterviewSession.objects.create(application=app, interviewer=self.reviewer)
        depth = {}
        with mock.patch.object(querying, '_maybe_autofinalise',
                               side_effect=lambda *a: depth.setdefault(
                                   'n', len(connection.savepoint_ids))):
            outer = len(connection.savepoint_ids)
            self.assertTrue(querying.submit_interview(session, actor=self.reviewer))
        self.assertEqual(depth['n'], outer)   # the Gemini call holds no extra transaction
        self.assertTrue(StaffActivity.objects.filter(
            subject_id=app.pk, verb=staff_activity.INTERVIEW_SUBMITTED).exists())
