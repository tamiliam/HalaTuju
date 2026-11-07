"""A1.11a / TD-486 — Cancel reopen restores from the RECORDED origin, not the current status.

The probe (TD-486): awaiting-QC decline -> QC reopen -> reviewer submit-decline -> super cancel-reopen
used to end at `recommended` with a decline verdict, past the QC decision.
"""
from django.test import TestCase, override_settings

from apps.scholarship import reopen
from apps.scholarship.models import DecisionReopen, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCancelReopenFromTheRecord(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('admin', super_admin=True)
        cls.cohort = make_cohort(owning_organisation=cls.org)

    def _app(self, outcome='decline'):
        return make_application('awaiting_qc', outcome=outcome, cohort=self.cohort,
                                reviewer=make_admin('reviewer', owning_org=self.org))

    def _post(self, app, tail, body=None):
        return authed_client(self.super).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/{tail}/', body or {}, format='json')

    def test_the_probe_a_declined_case_never_lands_at_recommended(self):
        app = self._app('decline')
        reopen.reopen_decision(app, by_admin=self.super, reason='QC sends it back')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        self.assertEqual(DecisionReopen.objects.get(application=app).reopened_from, 'interviewed')
        r = self._post(app, 'submit-decline')                 # back to AWAITING QC, reopen still open
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertIsNotNone(app.decision_reopened_at)
        r = self._post(app, 'cancel-reopen')
        self.assertEqual(r.status_code, 200, r.content[:300])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')           # still AWAITING QC — the QC decides
        self.assertIsNone(app.decision_reopened_at)
        self.assertIsNone(app.recommended_at)

    def test_a_qc_reopen_cancelled_at_once_returns_to_awaiting_qc(self):
        app = self._app('decline')
        reopen.reopen_decision(app, by_admin=self.super, reason='x')
        app.refresh_from_db()
        reopen.cancel_reopen(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

    def test_a_super_reopen_of_a_recommended_case_cancels_back_to_recommended(self):
        app = self._app('recommend')
        ScholarshipApplication.objects.filter(pk=app.pk).update(status='recommended')
        app.refresh_from_db()
        reopen.reopen_decision(app, by_admin=self.super, reason='x')
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertEqual(DecisionReopen.objects.get(application=app).reopened_from, 'recommended')
        reopen.cancel_reopen(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_a_row_from_before_the_field_keeps_the_old_inference(self):
        app = self._app('decline')
        reopen.reopen_decision(app, by_admin=self.super, reason='x')
        DecisionReopen.objects.filter(application=app).update(reopened_from='')
        app.refresh_from_db()
        reopen.cancel_reopen(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')            # interviewing -> interviewed, as before

    def test_the_target_rule(self):
        row = DecisionReopen(reopened_from='interviewed')
        self.assertEqual(reopen._cancel_target(row, 'interviewing'), 'interviewed')
        self.assertIsNone(reopen._cancel_target(row, 'interviewed'))
        row.reopened_from = 'recommended'
        self.assertEqual(reopen._cancel_target(row, 'interviewed'), 'recommended')
        self.assertIsNone(reopen._cancel_target(row, 'rejected'))
        row.reopened_from = ''
        self.assertEqual(reopen._cancel_target(row, 'interviewed'), 'recommended')
