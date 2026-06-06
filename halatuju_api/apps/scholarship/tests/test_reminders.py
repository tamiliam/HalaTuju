"""Completion-reminder cadence + auto-close (the daily reminder job).

Cadence from reminder_anchor_at: R1 +2, R2 +9, R3 +23, R4 +53; then a 5-day grace and
auto-close (status -> 'expired'). Time is injected via send_application_reminders(now=...)
so every case is deterministic. Emails land in Django's locmem outbox under TestCase."""
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import release_decision, send_application_reminders


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='rem', name='B40', year=2026)

    def setUp(self):
        self._n = 0
        self.now = timezone.now()

    def _app(self, *, anchor_days_ago=None, stage=0, last_reminder_days_ago=None,
             status='shortlisted', completed=False, email='s@example.com'):
        self._n += 1
        p = StudentProfile.objects.create(
            supabase_user_id=f'rem-{self.id()}-{self._n}', name='Test Student',
            nric=f'0801{self._n:02d}-01-1234')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email=email, locale='en',
            reminder_anchor_at=(self.now - timedelta(days=anchor_days_ago)) if anchor_days_ago is not None else None,
            reminder_stage=stage,
            last_reminder_at=(self.now - timedelta(days=last_reminder_days_ago)) if last_reminder_days_ago is not None else None,
            profile_completed_at=self.now if completed else None,
        )


class TestAnchorOnRelease(_Base):
    def test_shortlist_release_stamps_reminder_anchor(self):
        p = StudentProfile.objects.create(supabase_user_id='rel-1', name='X', nric='090101-01-1111')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='submitted', notify_email='x@example.com',
            verdict='shortlisted', decision_due_at=self.now - timedelta(hours=1))
        self.assertTrue(release_decision(app))
        app.refresh_from_db()
        self.assertIsNotNone(app.reminder_anchor_at)
        self.assertEqual(app.reminder_anchor_at, app.shortlisted_at)

    def test_decline_release_sets_no_anchor(self):
        p = StudentProfile.objects.create(supabase_user_id='rel-2', name='Y', nric='090202-02-2222')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='submitted', notify_email='y@example.com',
            verdict='rejected', rejection_category='merit', decision_due_at=self.now - timedelta(hours=1))
        self.assertTrue(release_decision(app))
        app.refresh_from_db()
        self.assertIsNone(app.reminder_anchor_at)


class TestReminderCadence(_Base):
    def _run(self):
        return send_application_reminders(now=self.now)

    def test_r1_fires_at_day_2(self):
        app = self._app(anchor_days_ago=2, stage=0)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['reminded'], 1)
        self.assertEqual(app.reminder_stage, 1)
        self.assertEqual(len(mail.outbox), 1)
        # The reminder links to the application page.
        self.assertIn('/scholarship/application', mail.outbox[0].body)

    def test_nothing_before_day_2(self):
        app = self._app(anchor_days_ago=1, stage=0)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['reminded'], 0)
        self.assertEqual(app.reminder_stage, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_one_stage_per_run_no_burst(self):
        # Anchored at day 2: R1 fires, but R2 (day 9) must NOT also fire in the same run.
        app = self._app(anchor_days_ago=2, stage=0)
        self._run()
        self._run()                                   # a second run, same `now`
        app.refresh_from_db()
        self.assertEqual(app.reminder_stage, 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_r2_r3_r4_progression(self):
        self.assertEqual(self._app(anchor_days_ago=9, stage=1).reminder_stage, 1)
        self._app(anchor_days_ago=23, stage=2)
        self._app(anchor_days_ago=53, stage=3)
        res = self._run()
        self.assertEqual(res['reminded'], 3)          # R2, R3, R4 each advance one app
        bodies = ' '.join(m.body for m in mail.outbox)
        self.assertIn('5 days', bodies)               # the final (R4) warning copy

    def test_completed_app_gets_no_reminder(self):
        # profile_completed_at set → off the track even if still tagged 'shortlisted'.
        app = self._app(anchor_days_ago=30, stage=0, completed=True)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['reminded'], 0)
        self.assertEqual(app.reminder_stage, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_anchor_no_reminder(self):
        self._app(anchor_days_ago=None, stage=0)      # never shortlisted-anchored
        self.assertEqual(self._run()['reminded'], 0)


class TestAutoClose(_Base):
    def _run(self):
        return send_application_reminders(now=self.now)

    def test_closes_after_final_plus_5_days(self):
        app = self._app(anchor_days_ago=58, stage=4, last_reminder_days_ago=5)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['closed'], 1)
        self.assertEqual(app.status, 'expired')
        self.assertIsNotNone(app.expired_at)
        self.assertEqual(len(mail.outbox), 1)         # the closure email
        self.assertIn('/scholarship/application', mail.outbox[0].body)

    def test_no_close_before_grace_elapses(self):
        app = self._app(anchor_days_ago=56, stage=4, last_reminder_days_ago=3)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['closed'], 0)
        self.assertEqual(app.status, 'shortlisted')
        self.assertEqual(len(mail.outbox), 0)

    def test_old_anchor_never_instant_closes_sends_r1_first(self):
        # Belt-and-braces: a back-dated anchor (60 days) with stage 0 must get R1, NOT an
        # instant close — the close is gated on the final reminder actually having gone out.
        app = self._app(anchor_days_ago=60, stage=0, last_reminder_days_ago=None)
        res = self._run()
        app.refresh_from_db()
        self.assertEqual(res['closed'], 0)
        self.assertEqual(res['reminded'], 1)
        self.assertEqual(app.status, 'shortlisted')
        self.assertEqual(app.reminder_stage, 1)


class TestBackfillCommand(_Base):
    def test_backfills_existing_incomplete_to_day_2(self):
        app = self._app(anchor_days_ago=None, stage=0)        # existing, no anchor
        call_command('backfill_reminder_anchors')
        app.refresh_from_db()
        self.assertIsNotNone(app.reminder_anchor_at)
        days = (timezone.now() - app.reminder_anchor_at).days
        self.assertEqual(days, 2)                              # today = day 2 → R1 next run

    def test_idempotent_skips_already_anchored(self):
        anchored = self._app(anchor_days_ago=10, stage=1)     # already on the track
        before = anchored.reminder_anchor_at
        call_command('backfill_reminder_anchors')
        anchored.refresh_from_db()
        self.assertEqual(anchored.reminder_anchor_at, before)  # untouched

    def test_skips_completed(self):
        done = self._app(anchor_days_ago=None, completed=True)
        call_command('backfill_reminder_anchors')
        done.refresh_from_db()
        self.assertIsNone(done.reminder_anchor_at)
