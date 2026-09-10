"""The backfill that labels predictions banked before the predictor had a version.

⚠ THE DANGEROUS THING THIS MUST NOT DO is re-run `build_verdict`. A snapshot is the historical
record of what the AI asserted when the officer decided; regenerating it would overwrite that with
today's answer and destroy the only evidence the AI Reliability scorecard rests on. These tests
assert the snapshot is byte-identical afterwards.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.verdict_engine import PRE_VERSIONING, VERDICT_ENGINE_VERSION

_SNAP = [{'fact': 'identity', 'status': 'verified', 'evidence': [], 'unresolved': []}]


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='C', year=2026)

    def _app(self, *, decided, version='', snapshot=None, tag=''):
        prof = StudentProfile.objects.create(
            supabase_user_id=f'bf-{self.id()}-{tag}', name='SWETHA A/P PILAAPPARAO',
            nric='081011-01-1416')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, status='profile_complete',
            ai_verdict_snapshot=snapshot if snapshot is not None else list(_SNAP),
            ai_verdict_engine_version=version,
            verdict_decided_at=timezone.now() if decided else None)

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_verdict_engine_version', *args, stdout=out)
        return out.getvalue()


class TestTheDryRunIsTheDefault(_Base):
    def test_it_reports_without_writing(self):
        app = self._app(decided=True)
        out = self._run()
        self.assertIn('decided rows with no engine version: 1', out)
        self.assertIn('DRY RUN', out)
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_engine_version, '')   # ⚠ nothing written

    def test_apply_writes_the_sentinel(self):
        app = self._app(decided=True)
        out = self._run('--apply')
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_engine_version, PRE_VERSIONING)
        self.assertIn('no decided row is left unlabelled', out)


class TestWhatItMustNotTouch(_Base):
    def test_an_UNDECIDED_row_keeps_its_empty_version(self):
        # ⚠ Empty means "never decided" and must stay empty, so a future decision stamps the REAL
        # engine. Labelling it 'pre-versioning' would attribute a prediction that never happened.
        app = self._app(decided=False)
        self._run('--apply')
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_engine_version, '')

    def test_a_row_already_carrying_a_REAL_version_is_left_alone(self):
        app = self._app(decided=True, version=VERDICT_ENGINE_VERSION, tag='real')
        self._run('--apply')
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_engine_version, VERDICT_ENGINE_VERSION)

    def test_it_is_idempotent(self):
        app = self._app(decided=True)
        self._run('--apply')
        out = self._run('--apply')
        self.assertIn('decided rows with no engine version: 0', out)
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_engine_version, PRE_VERSIONING)

    def test_THE_SNAPSHOT_IS_NEVER_REGENERATED(self):
        # ⚠ THE LOAD-BEARING ONE. The stored snapshot is evidence, not a cache. This fixture's
        # snapshot could never be produced by build_verdict on an empty application — if the
        # command re-ran the engine, this would come back as the real (four-fact) verdict.
        app = self._app(decided=True)
        before = app.ai_verdict_snapshot
        self._run('--apply')
        app.refresh_from_db()
        self.assertEqual(app.ai_verdict_snapshot, before)
        self.assertEqual(app.ai_verdict_snapshot, _SNAP)


class TestItHasADoorToTheLiveService(TestCase):
    def test_it_is_registered_in_CronRunView_JOBS(self):
        # ⚠ A repair that cannot be reached is indistinguishable from a repair that is finished —
        # `backfill_untagged_income_docs` sat unrunnable for a fortnight. The by-name guard in
        # test_repair_commands_have_a_door.py covers this too; this states it at the command.
        from apps.scholarship.views import CronRunView
        self.assertIn('backfill_verdict_engine_version', CronRunView.JOBS.values())
