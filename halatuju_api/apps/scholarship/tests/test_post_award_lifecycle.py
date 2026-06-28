"""Post-award lifecycle Sprint 2 — new statuses + re-gated consumers.

Verifies: the discovery pool empties once a funder commits (awarded/active/maintenance/closed);
the in-programme gate spans the funded states (active/maintenance/sponsored) and rejects pre-funding
ones; the progress band is derived for the funded states; and closure_reason is exposed to admin.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import pool
from apps.scholarship.in_programme import (
    InProgrammeError, record_semester_result, _require_in_programme,
)
from apps.scholarship.models import (
    Consent, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40 Programme', year=2026)


def _poolable(cohort, status='recommended', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'pa-{suffix}', grades={'bm': 'A'}, exam_type='spm')
    app = ScholarshipApplication.objects.create(cohort=cohort, profile=p, status=status)
    SponsorProfile.objects.create(application=app, anon_markdown='x', anon_blurb='x', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


class TestPoolExitOnFunderCommit(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_recommended_is_poolable(self):
        app = _poolable(self.cohort, status='recommended')
        self.assertTrue(pool.is_pool_eligible(app))
        self.assertIn(app, list(pool.eligible_pool_queryset(ScholarshipApplication)))

    def test_funder_commit_leaves_the_pool(self):
        for i, status in enumerate(['awarded', 'active', 'maintenance', 'sponsored', 'closed']):
            app = _poolable(self.cohort, status=status, suffix=f's{i}')
            self.assertFalse(pool.is_pool_eligible(app), status)
            self.assertNotIn(app, list(pool.eligible_pool_queryset(ScholarshipApplication)))


class TestInProgrammeGate(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def _app(self, status, suffix='1'):
        p = StudentProfile.objects.create(supabase_user_id=f'ip-{suffix}')
        return ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, status=status)

    def test_funded_states_are_in_programme(self):
        for i, status in enumerate(['active', 'maintenance', 'sponsored']):
            app = self._app(status, suffix=f'f{i}')
            r = record_semester_result(app, semester='Sem 1', cgpa='3.5')  # must not raise
            self.assertEqual(r.application_id, app.id)

    def test_pre_funding_is_not_in_programme(self):
        for i, status in enumerate(['recommended', 'awarded', 'interviewed']):
            app = self._app(status, suffix=f'n{i}')
            with self.assertRaises(InProgrammeError):
                _require_in_programme(app)


class TestProgressBand(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def _app(self, status, suffix='1'):
        p = StudentProfile.objects.create(supabase_user_id=f'pb-{suffix}')
        return ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, status=status)

    def test_band_for_funded_states(self):
        for i, status in enumerate(['active', 'maintenance', 'sponsored']):
            app = self._app(status, suffix=f'b{i}')
            self.assertIn(pool.derive_progress_state(app), pool.PROGRESS_STATES)

    def test_no_band_before_funding(self):
        app = self._app('recommended', suffix='r')
        self.assertIsNone(pool.derive_progress_state(app))


class TestClosureReason(TestCase):
    def test_field_stored_and_exposed_to_admin(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        cohort = _cohort()
        p = StudentProfile.objects.create(supabase_user_id='cr-1')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=p, status='closed', closure_reason='graduated')
        app.refresh_from_db()
        self.assertEqual(app.closure_reason, 'graduated')
        self.assertIn('closure_reason', AdminApplicationDetailSerializer.Meta.fields)
