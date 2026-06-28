"""Post-award lifecycle Sprint 5 — maintenance loop + operational sub-states.

Verifies: sub-states only apply in `maintenance`; valid transitions; `on_hold` BLOCKS a
tranche release (the money pause); the coarse sponsor `support_status` hides probation;
and the substate surfaces on the admin + student serializers (not leaking to the sponsor
card beyond the coarse signal).
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import disbursement as disb
from apps.scholarship import maintenance
from apps.scholarship.disbursement import DisbursementError
from apps.scholarship.maintenance import MaintenanceError
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, SponsorProfile, Consent


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40 Programme', year=2026)


def _app(cohort, status='maintenance', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'm-{suffix}')
    return ScholarshipApplication.objects.create(cohort=cohort, profile=p, status=status)


class TestSubstateGate(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_set_substate_requires_maintenance(self):
        for i, st in enumerate(['active', 'recommended', 'awarded', 'closed']):
            app = _app(self.cohort, status=st, suffix=f'g{i}')
            with self.assertRaises(MaintenanceError) as ctx:
                maintenance.set_substate(app, 'probation')
            self.assertEqual(ctx.exception.code, 'not_in_maintenance')

    def test_bad_substate_rejected(self):
        app = _app(self.cohort, suffix='bad')
        with self.assertRaises(MaintenanceError) as ctx:
            maintenance.set_substate(app, 'nonsense')
        self.assertEqual(ctx.exception.code, 'bad_substate')

    def test_default_is_on_track(self):
        app = _app(self.cohort, suffix='def')
        self.assertEqual(app.maintenance_substate, 'on_track')

    def test_free_transitions(self):
        app = _app(self.cohort, suffix='tr')
        for sub in ['probation', 'on_hold', 'on_track', 'ready_to_close', 'on_track']:
            maintenance.set_substate(app, sub)
            app.refresh_from_db()
            self.assertEqual(app.maintenance_substate, sub)


class TestOnHoldBlocksRelease(TestCase):
    def setUp(self):
        self.cohort = _cohort()
        self.app = _app(self.cohort, status='maintenance', suffix='hold')

    def test_release_blocked_when_on_hold(self):
        d = disb.schedule_tranche(self.app, amount='500')
        maintenance.set_substate(self.app, 'on_hold')
        self.app.refresh_from_db()
        with self.assertRaises(DisbursementError) as ctx:
            disb.release_tranche(d)
        self.assertEqual(ctx.exception.code, 'on_hold')
        d.refresh_from_db()
        self.assertEqual(d.status, 'scheduled')  # unchanged

    def test_release_resumes_after_unhold(self):
        d = disb.schedule_tranche(self.app, amount='500')
        maintenance.set_substate(self.app, 'on_hold')
        maintenance.set_substate(self.app, 'on_track')
        self.app.refresh_from_db()
        disb.release_tranche(d)
        d.refresh_from_db()
        self.assertEqual(d.status, 'released')

    def test_withhold_still_allowed_when_on_hold(self):
        d = disb.schedule_tranche(self.app, amount='500')
        maintenance.set_substate(self.app, 'on_hold')
        disb.withhold_tranche(d)  # must not raise — withholding is fine while paused
        d.refresh_from_db()
        self.assertEqual(d.status, 'withheld')


class TestSponsorSupportStatus(TestCase):
    def setUp(self):
        self.cohort = _cohort()
        self.app = _app(self.cohort, status='maintenance', suffix='sup')

    def test_on_hold_is_paused(self):
        maintenance.set_substate(self.app, 'on_hold')
        self.assertEqual(maintenance.sponsor_support_status(self.app), 'paused')

    def test_ready_to_close_is_completing(self):
        maintenance.set_substate(self.app, 'ready_to_close')
        self.assertEqual(maintenance.sponsor_support_status(self.app), 'completing')

    def test_probation_hidden_from_sponsor(self):
        maintenance.set_substate(self.app, 'probation')
        self.assertIsNone(maintenance.sponsor_support_status(self.app))

    def test_on_track_none(self):
        self.assertIsNone(maintenance.sponsor_support_status(self.app))

    def test_non_maintenance_none(self):
        app = _app(self.cohort, status='active', suffix='nm')
        self.assertIsNone(maintenance.sponsor_support_status(app))


class TestReadyToCloseQueryset(TestCase):
    def test_only_ready_to_close_maintenance(self):
        cohort = _cohort()
        a = _app(cohort, status='maintenance', suffix='r1')
        maintenance.set_substate(a, 'ready_to_close')
        _app(cohort, status='maintenance', suffix='r2')  # on_track
        _app(cohort, status='active', suffix='r3')
        qs = maintenance.ready_to_close_queryset()
        self.assertEqual(list(qs), [a])


class TestSerializerSurfaces(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_admin_detail_exposes_substate(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = _app(self.cohort, status='maintenance', suffix='ad')
        maintenance.set_substate(app, 'probation')
        data = AdminApplicationDetailSerializer(app).data
        self.assertEqual(data['maintenance_substate'], 'probation')

    def test_student_read_exposes_substate(self):
        from apps.scholarship.serializers import ApplicationReadSerializer
        app = _app(self.cohort, status='maintenance', suffix='st')
        maintenance.set_substate(app, 'on_hold')
        data = ApplicationReadSerializer(app).data
        self.assertEqual(data['maintenance_substate'], 'on_hold')

    def test_sponsor_card_coarse_only(self):
        from apps.scholarship.serializers import SponsorPoolCardSerializer
        app = _app(self.cohort, status='maintenance', suffix='sc')
        SponsorProfile.objects.create(application=app, anon_markdown='x', anon_blurb='x', anon_published=True)
        Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
        maintenance.set_substate(app, 'probation')
        data = SponsorPoolCardSerializer(app).data
        # The sponsor card carries the coarse support_status (None for probation) and
        # never the raw maintenance_substate field.
        self.assertIn('support_status', data)
        self.assertIsNone(data['support_status'])
        self.assertNotIn('maintenance_substate', data)
