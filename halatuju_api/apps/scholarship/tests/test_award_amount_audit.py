"""TD-203 — every writer of `application.award_amount` leaves an AUDIT line.

`award_amount` decides HOW MUCH a student is promised, and until 2026-09-30 none of its writers
said who changed it or what it was before (app 103 held RM1,000 with nothing to say where it came
from). Each writer now logs, on the SAME logger its module's other audit lines use:

    AUDIT award_amount_set app_id=… by=… was=… now=… via=<override|verdict|reject|cancel>

and ONLY when the value actually changes. The loggers are asserted by their exact names (never a
parent) — lessons.md H11: a submodule logger drops out of the Cloud Logging scrape silently.

The verdict recorder's two writes (apply on accept, clear on decline) share ONE line emitted
after the save lands, so a failed save never leaves an audit line for a change that did not
happen; both paths are tested below.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import services
from apps.scholarship.models import InterviewSession, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
)

VIEWS_LOGGER = 'apps.scholarship.views_admin'
SERVICES_LOGGER = 'apps.scholarship.services'


def _award_lines(cm):
    return [m for m in cm.output if 'AUDIT award_amount_set' in m]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   DECLINE_COOLOFF_DAYS=7)
class AwardAmountAuditTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.sup = make_admin('super', super_admin=True, email='sup@aaa.x')
        cls.rev = make_admin('reviewer', owning_org=cls.cohort.owning_organisation,
                             email='rev@aaa.x')

    def _app(self, amount=None):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.rev)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            award_amount=Decimal(amount) if amount is not None else None)
        app.refresh_from_db()
        # TD-253: the reviewer's decision needs a submitted interview with every item answered.
        InterviewSession.objects.create(application=app, status='submitted',
                                        submitted_at=timezone.now(),
                                        findings=answered_findings(app))
        return app

    def _record(self, app, overall):
        return authed_client(self.rev).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/record-verdict/',
            {'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                                 'income': 'pass', 'overall': overall},
             'reason': 'ok'}, format='json')

    def _override(self, app, amount):
        return authed_client(self.sup).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/award-amount/',
            {'amount': amount}, format='json')

    # ── via=override: the super-only set-award endpoint ────────────────────────────────────
    def test_override_logs_who_from_what_to_what(self):
        app = self._app(amount='2000')
        with self.assertLogs(VIEWS_LOGGER, level='INFO') as cm:
            r = self._override(app, '2500')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_award_lines(cm), [
            f'INFO:{VIEWS_LOGGER}:AUDIT award_amount_set app_id={app.id} by=sup@aaa.x '
            f'was=2000.00 now=2500 via=override'])

    def test_override_clear_logs_a_dash(self):
        app = self._app(amount='2000')
        with self.assertLogs(VIEWS_LOGGER, level='INFO') as cm:
            self._override(app, '')
        self.assertEqual(len(_award_lines(cm)), 1)
        self.assertIn('was=2000.00 now=- via=override', _award_lines(cm)[0])

    def test_override_to_the_same_amount_logs_nothing(self):
        app = self._app(amount='2500')
        with self.assertNoLogs(VIEWS_LOGGER, level='INFO'):
            r = self._override(app, '2500')
        self.assertEqual(r.status_code, 200, r.content)

    def test_an_override_whose_save_fails_logs_nothing(self):
        # Review F3: the line records a change that HAPPENED — so it follows the save.
        from unittest.mock import patch
        from django.db import DatabaseError
        app = self._app(amount='2000')
        with patch.object(ScholarshipApplication, 'save', side_effect=DatabaseError('boom')), \
                self.assertNoLogs(VIEWS_LOGGER, level='INFO'), \
                self.assertRaises(DatabaseError):
            self._override(app, '2500')

    # ── via=verdict: apply on accept, clear on decline ─────────────────────────────────────
    def test_verdict_accept_logs_the_applied_amount(self):
        app = self._app(amount=None)
        with self.assertLogs(VIEWS_LOGGER, level='INFO') as cm:
            r = self._record(app, 'accept')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(_award_lines(cm)), 1, cm.output)
        self.assertIn(f'app_id={app.id} by=rev@aaa.x was=- now=2000 via=verdict',
                      _award_lines(cm)[0])

    def test_verdict_decline_logs_the_clear(self):
        app = self._app(amount='2000')
        with self.assertLogs(VIEWS_LOGGER, level='INFO') as cm:
            r = self._record(app, 'decline')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(_award_lines(cm)), 1, cm.output)
        self.assertIn(f'app_id={app.id} by=rev@aaa.x was=2000.00 now=- via=verdict',
                      _award_lines(cm)[0])

    def test_verdict_that_keeps_the_amount_logs_nothing(self):
        # Accept over a super's override keeps it; decline of an unset amount clears nothing.
        kept = self._app(amount='2500')
        unset = self._app(amount=None)
        with self.assertNoLogs(VIEWS_LOGGER, level='INFO'):
            self.assertEqual(self._record(kept, 'accept').status_code, 200)
            self.assertEqual(self._record(unset, 'decline').status_code, 200)
        kept.refresh_from_db()
        self.assertEqual(kept.award_amount, Decimal('2500'))

    # ── via=reject: the one choke-point every decline passes through ───────────────────────
    def test_reject_logs_the_clear(self):
        app = self._app(amount='3000')
        with self.assertLogs(SERVICES_LOGGER, level='INFO') as cm:
            services.admin_reject(app, self.sup, 'interview')
        self.assertEqual(_award_lines(cm), [
            f'INFO:{SERVICES_LOGGER}:AUDIT award_amount_set app_id={app.id} by=sup@aaa.x '
            f'was=3000.00 now=- via=reject'])

    def test_reject_of_an_unset_amount_logs_nothing(self):
        app = self._app(amount=None)
        with self.assertNoLogs(SERVICES_LOGGER, level='INFO'):
            services.admin_reject(app, self.sup, 'interview')

    # ── via=cancel: cancel-decline restores the snapshot ───────────────────────────────────
    def test_cancel_decline_logs_the_restore_with_the_acting_admin(self):
        app = self._app(amount='3000')
        services.admin_reject(app, self.sup, 'interview')
        with self.assertLogs(SERVICES_LOGGER, level='INFO') as cm:
            r = authed_client(self.sup).post(
                f'/api/v1/admin/scholarship/applications/{app.id}/cancel-decline/', {},
                format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(_award_lines(cm), [
            f'INFO:{SERVICES_LOGGER}:AUDIT award_amount_set app_id={app.id} by=sup@aaa.x '
            f'was=- now=3000.00 via=cancel'])
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('3000'))

    def test_cancel_decline_with_no_snapshot_logs_nothing(self):
        app = self._app(amount=None)
        services.admin_reject(app, self.sup, 'interview')
        with self.assertNoLogs(SERVICES_LOGGER, level='INFO'):
            self.assertTrue(services.cancel_pending_decline(app, by_email='sup@aaa.x'))
