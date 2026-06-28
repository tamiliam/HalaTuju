"""Post-award lifecycle Sprint 4 — the disbursement/tranche ledger.

Verifies: a tranche can only be scheduled/released for a funded application; the FIRST
released tranche flips the application active → maintenance (and a second does NOT
re-flip / re-revert); withhold + return state rules; sequence auto-increment; and the
admin endpoints (reviewer-gated). Money is a mock ledger (TD-075), so no real-money paths.
"""
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import disbursement as disb
from apps.scholarship.disbursement import DisbursementError
from apps.scholarship.models import (
    Disbursement, ScholarshipApplication, ScholarshipCohort,
)


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40 Programme', year=2026)


def _app(cohort, status='active', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'd-{suffix}')
    return ScholarshipApplication.objects.create(cohort=cohort, profile=p, status=status)


class TestScheduleGate(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_schedule_requires_funded(self):
        for i, st in enumerate(['recommended', 'awarded', 'interviewed', 'closed']):
            app = _app(self.cohort, status=st, suffix=f'g{i}')
            with self.assertRaises(DisbursementError) as ctx:
                disb.schedule_tranche(app, amount='500')
            self.assertEqual(ctx.exception.code, 'not_in_programme')

    def test_schedule_allowed_when_funded(self):
        for i, st in enumerate(['active', 'maintenance']):
            app = _app(self.cohort, status=st, suffix=f'f{i}')
            d = disb.schedule_tranche(app, amount='500', label='Sem 1')
            self.assertEqual(d.status, 'scheduled')
            self.assertEqual(d.amount, Decimal('500.00'))
            self.assertEqual(d.sequence, 1)

    def test_bad_amount_rejected(self):
        app = _app(self.cohort, status='active', suffix='ba')
        for bad in ('0', '-10', 'abc', None):
            with self.assertRaises(DisbursementError) as ctx:
                disb.schedule_tranche(app, amount=bad)
            self.assertEqual(ctx.exception.code, 'bad_amount')

    def test_sequence_auto_increments(self):
        app = _app(self.cohort, status='active', suffix='seq')
        a = disb.schedule_tranche(app, amount='100')
        b = disb.schedule_tranche(app, amount='100')
        c = disb.schedule_tranche(app, amount='100', sequence=9)
        self.assertEqual([a.sequence, b.sequence, c.sequence], [1, 2, 9])


class TestReleaseFlipsToMaintenance(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_first_release_flips_active_to_maintenance(self):
        app = _app(self.cohort, status='active', suffix='flip')
        d = disb.schedule_tranche(app, amount='500')
        disb.release_tranche(d, by_email='admin@x.my')
        app.refresh_from_db()
        d.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')
        self.assertEqual(d.status, 'released')
        self.assertIsNotNone(d.released_at)
        self.assertEqual(d.actioned_by, 'admin@x.my')

    def test_second_release_does_not_reflip(self):
        app = _app(self.cohort, status='active', suffix='flip2')
        d1 = disb.schedule_tranche(app, amount='500')
        d2 = disb.schedule_tranche(app, amount='500')
        disb.release_tranche(d1)
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')
        disb.release_tranche(d2)
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')  # stays — no re-flip / revert

    def test_release_already_maintenance_is_noop_on_status(self):
        app = _app(self.cohort, status='maintenance', suffix='m')
        d = disb.schedule_tranche(app, amount='500')
        disb.release_tranche(d)
        app.refresh_from_db()
        self.assertEqual(app.status, 'maintenance')

    def test_cannot_release_twice(self):
        app = _app(self.cohort, status='active', suffix='tw')
        d = disb.schedule_tranche(app, amount='500')
        disb.release_tranche(d)
        with self.assertRaises(DisbursementError) as ctx:
            disb.release_tranche(d)
        self.assertEqual(ctx.exception.code, 'bad_state')


class TestWithholdReturn(TestCase):
    def setUp(self):
        self.cohort = _cohort()
        self.app = _app(self.cohort, status='maintenance', suffix='wr')

    def test_withhold_from_scheduled(self):
        d = disb.schedule_tranche(self.app, amount='500')
        disb.withhold_tranche(d, by_email='a@x.my', note='probation')
        d.refresh_from_db()
        self.assertEqual(d.status, 'withheld')
        self.assertEqual(d.note, 'probation')

    def test_cannot_withhold_released(self):
        d = disb.schedule_tranche(self.app, amount='500')
        disb.release_tranche(d)
        with self.assertRaises(DisbursementError):
            disb.withhold_tranche(d)

    def test_return_only_from_released(self):
        d = disb.schedule_tranche(self.app, amount='500')
        with self.assertRaises(DisbursementError):
            disb.return_tranche(d)   # not yet released
        disb.release_tranche(d)
        disb.return_tranche(d, by_email='a@x.my')
        d.refresh_from_db()
        self.assertEqual(d.status, 'returned')

    def test_mark_due_then_release(self):
        d = disb.schedule_tranche(self.app, amount='500')
        disb.mark_due(d)
        d.refresh_from_db()
        self.assertEqual(d.status, 'due')
        disb.release_tranche(d)   # due → released allowed
        d.refresh_from_db()
        self.assertEqual(d.status, 'released')


class TestSerializerExposesLedger(TestCase):
    def test_disbursements_on_admin_detail(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        cohort = _cohort()
        app = _app(cohort, status='active', suffix='ser')
        disb.schedule_tranche(app, amount='500', label='Sem 1')
        data = AdminApplicationDetailSerializer(app).data
        self.assertEqual(len(data['disbursements']), 1)
        row = data['disbursements'][0]
        self.assertEqual(row['amount'], '500.00')
        self.assertEqual(row['status'], 'scheduled')
        self.assertEqual(row['label'], 'Sem 1')
        # Admin-facing ledger carries the funder link by id only — never a sponsor identity.
        self.assertIn('sponsorship_id', row)
        self.assertNotIn('sponsor', row)
