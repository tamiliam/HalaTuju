"""`refresh_sponsor_profiles` command: rolls a prompt bump across the reviewer DRAFT and
the sponsor-facing FINAL. Gemini is mocked at the shared `_call_gemini_text` seam (no
billable call). Covers the gate, targeted-force, version-idempotency, edited-skip, and the
"don't fabricate a final for an undecided student" rule."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    InterviewSession, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)
from apps.scholarship.profile_engine import PROMPT_VERSION

OLD = 'old-version'


def _gemini_ok(prompt, target_language, models=None):
    # The shared seam both generate + refine go through; _with_version then stamps
    # PROMPT_VERSION on the result.
    return {'markdown': 'FRESH MARKDOWN', 'model_used': 'gemini-test'}


class TestRefreshSponsorProfiles(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev', role='reviewer', is_active=True, name='Rev', email='r@x.com')

    _seq = 0

    def _app(self, *, finalised=True, edited=False, version=OLD, assigned=True, session=True):
        type(self)._seq += 1
        profile = StudentProfile.objects.create(
            supabase_user_id=f'rp-{self._seq}', nric='030101-14-1234', name='Priya',
            school='SMK', exam_type='SPM', household_income=1500, household_size=5)
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile,
            status='recommended' if finalised else 'profile_complete',
            assigned_to=self.reviewer if assigned else None,
            aspirations='Become a doctor', plans='Study hard')
        sp = SponsorProfile.objects.create(
            application=app, draft_markdown='OLD DRAFT', prompt_version=version,
            edited_markdown='OFFICER EDIT' if edited else '',
            final_markdown='OLD FINAL' if finalised else '',
            finalised_at=timezone.now() if finalised else None)
        if session:
            InterviewSession.objects.create(
                application=app, status='submitted', submitted_at=timezone.now(),
                findings={'q': {'verdict': 'resolved', 'rationale': 'ok'}},
                rubric={'financial_need': 5}, overall_note='good')
        return app, sp

    def _run(self, **settings_kw):
        out = StringIO()
        with override_settings(CHECK2_AUTO_GENERATE=True, **settings_kw):
            with patch('apps.scholarship.profile_engine._call_gemini_text', _gemini_ok):
                call_command('refresh_sponsor_profiles', stdout=out)
        return out.getvalue()

    @override_settings(CHECK2_AUTO_GENERATE=False)
    def test_gate_off_does_nothing(self):
        app, sp = self._app()
        out = StringIO()
        call_command('refresh_sponsor_profiles', stdout=out)
        self.assertIn('off', out.getvalue())
        sp.refresh_from_db()
        self.assertEqual(sp.draft_markdown, 'OLD DRAFT')   # untouched

    def test_targeted_forces_draft_and_final(self):
        app, sp = self._app(version=PROMPT_VERSION)   # already current → only a force touches it
        self._run(PROFILE_REFRESH_APP_IDS=str(app.id))
        sp.refresh_from_db()
        self.assertEqual(sp.draft_markdown, 'FRESH MARKDOWN')   # re-drafted despite being current
        self.assertEqual(sp.final_markdown, 'FRESH MARKDOWN')   # re-finalised
        self.assertEqual(sp.prompt_version, PROMPT_VERSION)

    def test_full_sweep_skips_current_refreshes_stale(self):
        fresh, sp_fresh = self._app(version=PROMPT_VERSION)
        stale, sp_stale = self._app(version=OLD)
        out = self._run()   # no scoping → version-idempotent sweep
        sp_fresh.refresh_from_db(); sp_stale.refresh_from_db()
        self.assertEqual(sp_fresh.draft_markdown, 'OLD DRAFT')      # current → skipped
        self.assertEqual(sp_stale.draft_markdown, 'FRESH MARKDOWN')  # stale → refreshed
        self.assertIn(f'skipped_current=[{fresh.id}]', out)

    def test_skips_officer_edited(self):
        app, sp = self._app(edited=True, version=OLD)
        self._run(PROFILE_REFRESH_APP_IDS=str(app.id))
        sp.refresh_from_db()
        self.assertEqual(sp.draft_markdown, 'OLD DRAFT')   # never clobber a human edit
        self.assertEqual(sp.edited_markdown, 'OFFICER EDIT')

    def test_undecided_student_gets_draft_but_no_final(self):
        # No recorded decision (finalised_at is None) → re-draft only, never fabricate a final.
        app, sp = self._app(finalised=False, session=False, version=OLD)
        self._run(PROFILE_REFRESH_APP_IDS=str(app.id))
        sp.refresh_from_db()
        self.assertEqual(sp.draft_markdown, 'FRESH MARKDOWN')
        self.assertEqual(sp.final_markdown, '')
        self.assertIsNone(sp.finalised_at)

    def test_had_final_but_no_session_skips_final(self):
        app, sp = self._app(finalised=True, session=False, version=OLD)
        out = self._run(PROFILE_REFRESH_APP_IDS=str(app.id))
        sp.refresh_from_db()
        self.assertEqual(sp.draft_markdown, 'FRESH MARKDOWN')   # draft still refreshed
        self.assertEqual(sp.final_markdown, 'OLD FINAL')        # final left as-is (no session to fold)
        self.assertIn(f'final_no_session=[{app.id}]', out)

    def test_requested_id_not_found_reported(self):
        out = self._run(PROFILE_REFRESH_APP_IDS='999999')
        self.assertIn('requested_not_found=[999999]', out)
