"""The one-off sweep that takes the IC lock on already-confirmed records (2026-07-29).

The rule locks at the end of an IC READ, so shipping it alone locks nobody: a student who
uploaded a matching card in June is never re-read. Without this sweep, who is locked would
depend on who happened to press a button recently.

What these pin, beyond "it works": that the sweep uses the SAME predicate as the live path (a
second copy would drift), that it is report-only until told otherwise, and that it declines the
two cases where locking would be wrong or would raise.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)

CARD = 'THARANI A/P A.UDAYA KUMAR'
NRIC = '080722-14-1140'


class TestBackfillNricLocks(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c-bf', name='B40', year=2026)

    def _student(self, uid, *, name=CARD, nric=NRIC, verified=False,
                 card_name=CARD, card_nric=NRIC, status='genuine', superseded=False):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name=name, nric=nric, nric_verified=verified)
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted')
        if card_name is not None:
            ApplicantDocument.objects.create(
                application=app, doc_type='ic', storage_path=f'{app.id}/ic/x',
                vision_name=card_name, vision_nric=card_nric, vision_run_at=timezone.now(),
                superseded_at=timezone.now() if superseded else None,
                vision_fields={'authenticity': {'status': status}} if status else {},
            )
        return profile, app

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_nric_locks', *args, stdout=out)
        return out.getvalue()

    def _verified(self, profile):
        profile.refresh_from_db()
        return profile.nric_verified

    def test_report_only_by_default_changes_nothing(self):
        profile, _ = self._student('bf-1')
        out = self._run()
        self.assertIn('WOULD LOCK: 1', out)
        self.assertFalse(self._verified(profile), 'the report wrote to the database')

    def test_apply_takes_the_lock(self):
        profile, _ = self._student('bf-2')
        self._run('--apply')
        self.assertTrue(self._verified(profile))

    def test_an_unscored_card_is_not_locked_and_is_reported_as_needing_a_rerun(self):
        """The (b) decision. These are a Re-run away, and the report must say so — otherwise
        nobody knows the difference between 'not eligible' and 'not checked yet'."""
        profile, _ = self._student('bf-3', status=None)
        out = self._run('--apply')
        self.assertFalse(self._verified(profile))
        self.assertIn('needs a Re-run', out)

    def test_a_mismatched_number_is_not_locked(self):
        profile, _ = self._student('bf-4', nric='080722-11-1140')
        out = self._run('--apply')
        self.assertFalse(self._verified(profile))
        self.assertIn('student must correct it', out)

    def test_a_superseded_card_decides_nothing(self):
        """A replaced card must not take a permanent lock."""
        profile, _ = self._student('bf-5', superseded=True)
        self._run('--apply')
        self.assertFalse(self._verified(profile))

    def test_a_duplicate_number_is_declined_not_raised(self):
        """Locking arms the partial unique index; a second verified holder would make the
        save raise and abort the whole sweep."""
        StudentProfile.objects.create(
            supabase_user_id='bf-holder', name='SOMEONE ELSE', nric=NRIC, nric_verified=True)
        profile, _ = self._student('bf-6')
        out = self._run('--apply')          # must not raise
        self.assertFalse(self._verified(profile))
        self.assertIn('already verified elsewhere', out)

    def test_an_already_locked_record_is_left_alone(self):
        profile, _ = self._student('bf-7', verified=True)
        out = self._run()
        self.assertIn('already locked', out)
        self.assertTrue(self._verified(profile))

    def test_the_sweep_agrees_with_the_live_rule(self):
        """Source guard: the sweep must ask `identity`, not carry its own copy of the rule.
        A second implementation is how the two would drift apart."""
        import inspect

        from apps.scholarship.management.commands import backfill_nric_locks
        src = inspect.getsource(backfill_nric_locks)
        self.assertIn('identity.locks_now', src)
        self.assertNotIn('canonical_status', src)   # i.e. it does not re-derive genuineness
