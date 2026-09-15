"""The verdict clock, and the proof that every caller actually reads it.

Two claims carry this file, and the second is the one that earns its keep:

1. **The bands are the nudge sweep's own boundaries.** `now == due` is OVERDUE, because that is
   when `send_review_nudges` sends the overdue email. A `>` there would leave a case reading
   "due soon" on the Programme Overview in the same minute its reviewer was told it was late.

2. **A helper with three surviving copies beside it is a FOURTH copy.** `assigned_at + sla` used
   to be written out inline in the nudge sweep, the assignment email and the interview reminder.
   Extracting it proves nothing unless the callers were migrated too — so each of the three has a
   test that patches `review_sla.review_due` to raise and asserts the caller raises. If somebody
   quietly reinstates an inline `timedelta`, that test goes green-to-red rather than the module
   drifting away unnoticed. (`docs/lessons.md`, "count the callers".)

`test_review_nudges.py` is deliberately UNCHANGED by this refactor and is the regression net.
"""
import datetime
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import review_sla
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

_SLA = dict(REVIEW_SLA_DAYS=10, REVIEW_NUDGE_SOON_DAYS=2, REVIEW_ESCALATE_GRACE_DAYS=3)


@override_settings(**_SLA)
class TheClockTests(TestCase):
    """`review_due` and `review_band` on their own."""

    def setUp(self):
        self.now = timezone.now()

    def test_due_is_assigned_plus_the_organisations_sla(self):
        assigned = self.now - datetime.timedelta(days=3)
        self.assertEqual(review_sla.review_due(assigned),
                         assigned + datetime.timedelta(days=10))

    def test_an_unassigned_case_has_no_due_date_at_all(self):
        # None, not "now" — "never assigned" and "due this instant" must not render the same.
        self.assertIsNone(review_sla.review_due(None))
        self.assertIsNone(review_sla.review_band(None, now=self.now))

    def test_a_fresh_case_is_open(self):
        assigned = self.now - datetime.timedelta(days=1)
        self.assertEqual(review_sla.review_band(assigned, now=self.now), 'open')

    def test_the_soon_window_opens_exactly_soon_days_before_the_due_date(self):
        # due - 2 days is INSIDE the window (<=); a second earlier is not.
        assigned = self.now - datetime.timedelta(days=8)
        self.assertEqual(review_sla.review_band(assigned, now=self.now), 'due_soon')
        just_before = self.now - datetime.timedelta(seconds=1)
        self.assertEqual(review_sla.review_band(assigned, now=just_before), 'open')

    def test_the_due_instant_itself_is_overdue_not_due_soon(self):
        """⚠ THE BOUNDARY BELONGS TO THE LATER BAND — the sweep fires at `now >= due`."""
        assigned = self.now - datetime.timedelta(days=10)
        self.assertEqual(review_sla.review_band(assigned, now=self.now), 'overdue')
        a_moment_earlier = self.now - datetime.timedelta(seconds=1)
        self.assertEqual(review_sla.review_band(assigned, now=a_moment_earlier), 'due_soon')

    def test_a_late_case_stays_overdue(self):
        assigned = self.now - datetime.timedelta(days=30)
        self.assertEqual(review_sla.review_band(assigned, now=self.now), 'overdue')

    def test_supplied_clocks_are_used_instead_of_reading_the_config(self):
        """The per-organisation cache the sweep keeps must still be honoured."""
        assigned = self.now - datetime.timedelta(days=4)
        self.assertEqual(review_sla.review_due(assigned, clocks=(3, 1, 1)),
                         assigned + datetime.timedelta(days=3))
        self.assertEqual(review_sla.review_band(assigned, now=self.now, clocks=(3, 1, 1)),
                         'overdue')

    def test_the_terminal_set_is_the_one_the_sweep_uses(self):
        from apps.scholarship.management.commands import send_review_nudges
        self.assertIs(send_review_nudges._TERMINAL, review_sla.TERMINAL)


@override_settings(**_SLA)
class ClocksReadTheOrganisationTests(TestCase):
    def test_a_stored_value_beats_the_platform_default(self):
        from apps.courses.models import OrganisationConfiguration
        org = PartnerOrganisation.objects.create(code='sla-org', name='SLA Org')
        OrganisationConfiguration.objects.create(
            organisation=org, values={'review_sla_days': 4})
        org.refresh_from_db()
        self.assertEqual(review_sla.clocks(org)[0], 4)
        self.assertEqual(review_sla.clocks(None)[0], 10)


@override_settings(**_SLA)
class EveryCallerReadsTheOneClockTests(TestCase):
    """⚠ THE POINT OF THE MODULE. Patch `review_due` to raise; each caller must raise."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='sla-callers', name='SLA Callers')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='sla-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Rohini', email='rohini@sla.test')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='sla-rev2', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Bala', email='bala@sla.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='sla-su', is_super_admin=True, is_active=True,
            name='Super', email='su@sla.test')
        cls.cohort = ScholarshipCohort.objects.create(
            code='sla-2026', name='SLA', year=2026, owning_organisation=cls.org)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='sla-stud', nric='030101-14-9999', name='Priya')

    def _app(self, **kw):
        now = timezone.now()
        kw.setdefault('status', 'interviewing')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, notify_email='priya@sla.test',
            assigned_to=self.reviewer, assigned_at=now - datetime.timedelta(days=9), **kw)

    @staticmethod
    def _boom():
        return mock.patch('apps.scholarship.review_sla.review_due',
                          side_effect=RuntimeError('review_due was not called'))

    @override_settings(REVIEW_NUDGES_ENABLED=True)
    def test_the_nudge_sweep_reads_it(self):
        self._app()
        with self._boom(), self.assertRaises(RuntimeError):
            call_command('send_review_nudges')

    def test_the_assignment_email_reads_it(self):
        from apps.scholarship.services import assign_reviewer
        app = self._app()
        # A REASSIGNMENT, so the first-assignment readiness gate is not in the way.
        with self._boom(), self.assertRaises(RuntimeError):
            assign_reviewer(app, reviewer=self.other_reviewer, by_admin=self.super)

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
    def test_the_interview_reminder_reads_it(self):
        self._app(interview_status='booked',
                  interview_start=timezone.now() + datetime.timedelta(hours=2))
        with self._boom(), self.assertRaises(RuntimeError):
            call_command('send_interview_reminders')
