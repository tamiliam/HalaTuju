"""The one-off sweep that files income documents left with a blank household tag (BrightPath #20).

The upload guard now fills the tag at source, but shipping that alone repairs nobody: a document
uploaded in June is never re-read. Without this sweep, whether a duplicate is visible would depend
on whether anyone happened to re-upload since.

What these pin, beyond "it works": that the sweep resolves the member with the SAME two rules as the
upload guard (a second copy would drift), that it is report-only until told otherwise, that an
unreadable copy cannot take the slot from a good one, and that a genuinely undecidable owner is left
blank rather than guessed at.
"""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


class TestBackfillUntaggedIncomeDocs(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c-ut', name='B40', year=2026)

    def _app(self, uid, *, route='str', earner='father'):
        profile = StudentProfile.objects.create(supabase_user_id=uid, name='STUDENT')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='interviewing',
            income_route=route, income_earner=earner,
            profile_completed_at=timezone.now())

    def _doc(self, app, *, member='', kind='salary_slip', name='blurry.jpg'):
        return ApplicantDocument.objects.create(
            application=app, doc_type=kind, household_member=member,
            storage_path=f'{app.id}/{kind}/{name}', original_filename=name)

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_untagged_income_docs', *args, stdout=out)
        return out.getvalue()

    def _live(self, app, kind='salary_slip'):
        return ApplicantDocument.objects.filter(
            application=app, doc_type=kind, superseded_at__isnull=True)

    def test_report_only_by_default_changes_nothing(self):
        app = self._app('u-report')
        blank = self._doc(app)
        out = self._run()
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, '')      # untouched
        self.assertIn('[report]', out)
        self.assertIn('Re-run with --apply', out)

    def test_a_lone_blank_doc_is_tagged_and_keeps_its_slot(self):
        """Application 88's shape: legacy documents that predate tagging and are the ONLY copy.
        They need a tag, not a replacement — nothing is competing for the slot."""
        app = self._app('u-lone')
        blank = self._doc(app, kind='str', name='legacy.jpg')
        self._run('--apply')
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')
        self.assertIsNone(blank.superseded_at)            # still the live STR

    def test_the_blurry_duplicate_goes_behind_the_good_copy(self):
        """Application 73's shape, and the whole point of the sweep. Two live payslips for one
        earner: a good tagged copy, and an untagged one that won an empty blank slot by default.

        ⚠ The count is the assertion. TWO live payslips for one earner is the bug; one is the fix.
        Which one survives is `promotion.should_promote`'s call, not this command's — an unreadable
        copy can never displace a good one, here or at upload.
        """
        app = self._app('u-dup')
        good = self._doc(app, member='father', name='Scanned.pdf')
        blank = self._doc(app, name='IMG-blurry.jpg')
        self._run('--apply')
        blank.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')
        self.assertEqual(self._live(app).count(), 1)      # no live pair survives
        # Whichever kept the slot, the other is RETAINED as history, never deleted.
        loser = blank if blank.superseded_at else good
        self.assertIsNotNone(loser.superseded_at)
        self.assertIsNotNone(loser.superseded_by_id)

    def test_a_not_salary_photo_can_never_take_the_slot_from_a_genuine_payslip(self):
        """Application 73's REAL shape, found by reading the live report before writing anything.

        The live payslip is a genuine scan whose OCR misread one digit of the earner's IC, so
        `doc_match_verdict` calls it NOT usable. The untagged copy is a WhatsApp photo scored
        `not_salary` that read no name and no IC at all — so nothing contradicts, and it reads
        usable. `promotion.doc_quality` leads with `usable`, so by that rule alone the photo takes
        the slot from the real payslip. It must not: for the income proofs the de-dup's rank is the
        answer, and that leads with GENUINENESS.
        """
        app = self._app('u-notsalary')
        # The earner's IC is on file, so the payslip's IC number is actually compared. Live it was
        # a ONE-DIGIT OCR misread; a plainly different number is used here so the fixture does not
        # ride on how near a near-miss may be.
        ic = self._doc(app, member='father', kind='parent_ic', name='father-ic.jpg')
        ic.vision_name = 'RAVI A/L PERIAKARUPPAN'
        ic.vision_nric = '751206-08-5941'
        ic.vision_run_at = timezone.now()
        ic.save(update_fields=['vision_name', 'vision_nric', 'vision_run_at'])
        good = self._doc(app, member='father', name='Scanned.pdf')
        good.vision_fields = {'authenticity': {'status': 'genuine'},
                              'fields': {'name': 'RAVI A/L PERIAKARUPPAN', 'nric': '640101-01-1234',
                                         'gross_income': '2375.73', 'period': 'March 2026'},
                              'student_verdict': 'ok'}
        good.vision_run_at = timezone.now()
        good.save(update_fields=['vision_fields', 'vision_run_at'])
        junk = self._doc(app, name='IMG-WA0071.jpg')
        junk.vision_fields = {'authenticity': {'status': 'not_salary'},
                              'fields': {'name': '', 'nric': '', 'period': 'June 2026'},
                              'student_verdict': 'ok'}          # nothing to contradict → 'usable'
        junk.vision_run_at = timezone.now()
        junk.save(update_fields=['vision_fields', 'vision_run_at'])

        out = self._run('--apply')
        good.refresh_from_db()
        junk.refresh_from_db()
        self.assertEqual(junk.household_member, 'father')       # still tagged...
        self.assertIsNone(good.superseded_at)                   # ...but the real payslip stays live
        self.assertIsNotNone(junk.superseded_at)
        self.assertEqual(junk.superseded_by_id, good.id)
        self.assertIn(f'goes to Replaced behind #{good.id}', out)   # the report SAID so first

    def test_a_salary_route_blank_is_left_alone(self):
        """Undecidable is not a licence to guess. On the salary route several members may each hold
        documents, so the blank must stand — and be REPORTED, so it is visible rather than silent."""
        app = self._app('u-salary', route='salary', earner='')
        blank = self._doc(app)
        out = self._run('--apply')
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, '')
        self.assertIn('owner not determinable', out)
        self.assertIn('1 left blank as undecidable', out)

    def test_the_env_var_is_the_apply_flag_on_the_live_service(self):
        """The cron endpoint calls a command with NO arguments, so `--apply` is unreachable there.
        The env var is how the write is switched on — and its ABSENCE must leave report-only, or a
        job scheduled for a report would silently write."""
        app = self._app('u-env')
        blank = self._doc(app, kind='str', name='legacy.jpg')
        with mock.patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('INCOME_DOC_TAG_APPLY', None)
            self._run()
            blank.refresh_from_db()
            self.assertEqual(blank.household_member, '')   # unset → still a report
            os.environ['INCOME_DOC_TAG_APPLY'] = '1'
            self._run()
        blank.refresh_from_db()
        self.assertEqual(blank.household_member, 'father')

    def test_the_cron_endpoint_can_reach_it(self):
        """⚠ THIS COMMAND CANNOT RUN FROM A CHECKOUT — the production database is reachable only
        from the service. A registry entry is therefore not a convenience; it is the ONLY way the
        repair ever happens. Pin the job NAME the runbook types, not just that some entry exists."""
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS.get('backfill-untagged-income-docs'),
                         'backfill_untagged_income_docs')

    def test_it_resolves_by_name_before_falling_back_to_the_earner(self):
        """The two rules are ORDERED, and the order is the upload guard's. A readable name decides
        first; the single-earner fallback is only for a document nothing can be read from. If these
        ever diverge, a document files one way at upload and another way here."""
        app = self._app('u-name')
        app.father_name = 'RAVI A/L PERIAKARUPPAN'
        app.mother_name = 'KAMALA A/P SUBRAMANIAM'
        app.save(update_fields=['father_name', 'mother_name'])
        blank = self._doc(app, kind='parent_ic', name='mum.jpg')
        blank.vision_name = 'KAMALA A/P SUBRAMANIAM'      # the NAME says mother...
        blank.vision_run_at = timezone.now()
        blank.save(update_fields=['vision_name', 'vision_run_at'])
        self._run('--apply')
        blank.refresh_from_db()
        # ...so it must NOT go to 'father' just because he is the declared STR earner.
        self.assertEqual(blank.household_member, 'mother')
