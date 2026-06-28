"""Post-award lifecycle Sprint 6 — manual closure + reasons + thank-you re-gating.

Verifies: a funded application closes manually with a valid reason (stamping closed_at/by);
closure is gated to funded states + valid reasons; a closed student can NO LONGER receive a
tranche but CAN still submit a graduation thank-you; and the admin/student serializers expose
the closure fields.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import closure, disbursement as disb
from apps.scholarship.closure import ClosureError
from apps.scholarship.disbursement import DisbursementError
from apps.scholarship.in_programme import submit_graduation_message, record_semester_result, InProgrammeError
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40 Programme', year=2026)


def _app(cohort, status='maintenance', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'c-{suffix}')
    return ScholarshipApplication.objects.create(cohort=cohort, profile=p, status=status)


class TestCloseGate(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_close_requires_funded(self):
        for i, st in enumerate(['recommended', 'awarded', 'interviewed', 'closed', 'rejected']):
            app = _app(self.cohort, status=st, suffix=f'g{i}')
            with self.assertRaises(ClosureError) as ctx:
                closure.close_application(app, closure_reason='graduated')
            self.assertEqual(ctx.exception.code, 'not_closeable')

    def test_bad_reason_rejected(self):
        app = _app(self.cohort, status='maintenance', suffix='br')
        for bad in ('', 'nonsense', None):
            with self.assertRaises(ClosureError) as ctx:
                closure.close_application(app, closure_reason=bad)
            self.assertEqual(ctx.exception.code, 'bad_reason')

    def test_close_from_active_and_maintenance(self):
        for i, st in enumerate(['active', 'maintenance']):
            app = _app(self.cohort, status=st, suffix=f'ok{i}')
            closure.close_application(app, closure_reason='graduated', by_email='a@x.my')
            app.refresh_from_db()
            self.assertEqual(app.status, 'closed')
            self.assertEqual(app.closure_reason, 'graduated')
            self.assertEqual(app.closed_by, 'a@x.my')
            self.assertIsNotNone(app.closed_at)

    def test_all_valid_reasons_accepted(self):
        for i, reason in enumerate(['graduated', 'completed', 'withdrawn', 'lapsed', 'terminated']):
            app = _app(self.cohort, status='maintenance', suffix=f'r{i}')
            closure.close_application(app, closure_reason=reason)
            app.refresh_from_db()
            self.assertEqual((app.status, app.closure_reason), ('closed', reason))


class TestCloseMoneyInvariant(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_cannot_release_tranche_after_close(self):
        app = _app(self.cohort, status='maintenance', suffix='money')
        d = disb.schedule_tranche(app, amount='500')
        closure.close_application(app, closure_reason='terminated')
        d.refresh_from_db()
        with self.assertRaises(DisbursementError) as ctx:
            disb.release_tranche(d)
        self.assertEqual(ctx.exception.code, 'not_in_programme')
        d.refresh_from_db()
        self.assertEqual(d.status, 'scheduled')  # never paid


class TestThankYouReGating(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_thank_you_allowed_after_close(self):
        app = _app(self.cohort, status='maintenance', suffix='ty')
        closure.close_application(app, closure_reason='graduated')
        msg = submit_graduation_message(app, raw_text='Thank you so much for believing in me.')
        self.assertEqual(msg.application_id, app.id)
        self.assertIn(msg.status, ('pending', 'blocked'))

    def test_thank_you_allowed_in_maintenance(self):
        app = _app(self.cohort, status='maintenance', suffix='tym')
        msg = submit_graduation_message(app, raw_text='Grateful for the support this year.')
        self.assertEqual(msg.application_id, app.id)

    def test_thank_you_blocked_before_funded(self):
        app = _app(self.cohort, status='recommended', suffix='tyb')
        with self.assertRaises(InProgrammeError):
            submit_graduation_message(app, raw_text='Too early.')

    def test_semester_result_still_blocked_after_close(self):
        # Closure does NOT reopen the funded-only writes (results / promo consent).
        app = _app(self.cohort, status='maintenance', suffix='sr')
        closure.close_application(app, closure_reason='completed')
        with self.assertRaises(InProgrammeError):
            record_semester_result(app, semester='Final', cgpa='3.8')


class TestSerializerSurfaces(TestCase):
    def test_admin_detail_exposes_closure_fields(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        cohort = _cohort()
        app = _app(cohort, status='maintenance', suffix='ad')
        closure.close_application(app, closure_reason='completed', by_email='admin@x.my')
        data = AdminApplicationDetailSerializer(app).data
        self.assertEqual(data['status'], 'closed')
        self.assertEqual(data['closure_reason'], 'completed')
        self.assertEqual(data['closed_by'], 'admin@x.my')
        self.assertIsNotNone(data['closed_at'])

    def test_student_read_exposes_closure_reason(self):
        from apps.scholarship.serializers import ApplicationReadSerializer
        cohort = _cohort()
        app = _app(cohort, status='maintenance', suffix='st')
        closure.close_application(app, closure_reason='graduated')
        data = ApplicationReadSerializer(app).data
        self.assertEqual(data['status'], 'closed')
        self.assertEqual(data['closure_reason'], 'graduated')
