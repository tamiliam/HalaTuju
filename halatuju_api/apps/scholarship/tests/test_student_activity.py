"""Student maintenance Sprint 1 — the activity log foundation and the sub-state's who/when.

Each WIRED door writes its row in the same transaction as the change it records (a change that
rolls back leaves no row); `add_entry` validates a manual entry; the admin sub-state endpoint
records WHO moved the sub-state and when. The payment rows are pinned in `test_on_hold_money.py`.
"""
from unittest import mock

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import activity, closure, disbursement, maintenance
from apps.scholarship.activity import ActivityError
from apps.scholarship.models import StudentActivity
from apps.scholarship.models.activity import (
    EVENT_CLOSED, EVENT_PAYMENT_RELEASED, EVENT_RESULT_SUBMITTED, EVENT_SUBSTATE_CHANGED, EVENTS,
)
from apps.scholarship.tests.factories import (
    record_result,
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

API = '/api/v1/admin/scholarship/'


class TestSubstateWhoAndWhen(TestCase):
    def setUp(self):
        self.app = make_application('awarded', vircle_activated_at=timezone.now())

    def test_set_substate_stamps_who_and_when_and_logs_old_and_new(self):
        before = timezone.now()
        maintenance.set_substate(self.app, 'probation', by_email='officer@example.test')
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate_changed_by, 'officer@example.test')
        self.assertGreaterEqual(self.app.maintenance_substate_changed_at, before)
        row = StudentActivity.objects.get(application=self.app)
        self.assertEqual((row.kind, row.event, row.actor_email, row.internal),
                         ('system', EVENT_SUBSTATE_CHANGED, 'officer@example.test', True))
        self.assertEqual((row.meta['old'], row.meta['new']), ('on_track', 'probation'))

    def test_setting_the_same_substate_writes_nothing(self):
        maintenance.set_substate(self.app, 'on_track', by_email='officer@example.test')
        self.app.refresh_from_db()
        self.assertIsNone(self.app.maintenance_substate_changed_at)
        self.assertFalse(StudentActivity.objects.exists())

    def test_a_log_that_cannot_be_written_rolls_the_change_back(self):
        """The log is part of the record: no hold without its row."""
        with mock.patch.object(activity, 'log_event', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                maintenance.set_substate(self.app, 'on_hold', by_email='officer@example.test')
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_track')
        self.assertIsNone(self.app.maintenance_substate_changed_at)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSubstateEndpointRecordsTheActor(TestCase):
    def test_the_view_passes_the_officers_email(self):
        cohort = make_cohort()
        org_admin = make_admin('org_admin', owning_org=cohort.owning_organisation)
        app = make_application('awarded', cohort=cohort, vircle_activated_at=timezone.now())
        r = authed_client(org_admin).post(f'{API}applications/{app.id}/maintenance/',
                                          {'substate': 'on_hold'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual((app.maintenance_substate, app.maintenance_substate_changed_by),
                         ('on_hold', org_admin.email))
        self.assertEqual(StudentActivity.objects.get(application=app).actor_email, org_admin.email)


class TestWiredDoors(TestCase):
    def test_a_semester_result_writes_result_submitted(self):
        app = make_application('maintenance')
        row = record_result(app, semester='Sem 2', cgpa='3.10')
        log = StudentActivity.objects.get(application=app)
        self.assertEqual((log.event, log.meta['result_id'], log.meta['cgpa']),
                         (EVENT_RESULT_SUBMITTED, row.id, '3.10'))

    def test_a_close_writes_closed_with_the_reason(self):
        app = make_application('maintenance')
        closure.close_application(app, closure_reason='graduated', by_email='officer@example.test')
        log = StudentActivity.objects.get(application=app)
        self.assertEqual((log.event, log.actor_email, log.meta['reason'], log.meta['from']),
                         (EVENT_CLOSED, 'officer@example.test', 'graduated', 'maintenance'))

    def test_a_refused_close_writes_nothing(self):
        app = make_application('maintenance')
        with self.assertRaises(closure.ClosureError):
            closure.close_application(app, closure_reason='nonsense')
        self.assertFalse(StudentActivity.objects.exists())

    def test_a_tranche_release_writes_payment_released(self):
        app = make_application('maintenance')
        tranche = disbursement.schedule_tranche(app, amount='500')
        disbursement.release_tranche(tranche, by_email='officer@example.test')
        log = StudentActivity.objects.get(application=app)
        self.assertEqual((log.event, log.meta['amount'], log.meta['disbursement_id']),
                         (EVENT_PAYMENT_RELEASED, '500.00', tranche.id))

    def test_a_row_written_inside_a_rolled_back_block_is_gone(self):
        app = make_application('maintenance')
        try:
            with transaction.atomic():
                activity.log_event(app, EVENT_CLOSED)
                raise RuntimeError('roll back')
        except RuntimeError:
            pass
        self.assertFalse(StudentActivity.objects.exists())


class TestWriters(TestCase):
    def setUp(self):
        self.app = make_application('maintenance')

    def test_log_event_refuses_an_unknown_code(self):
        with self.assertRaises(ValueError):
            activity.log_event(self.app, 'nonsense')

    def test_the_roadmap_event_list(self):
        self.assertEqual(set(EVENTS), {
            'substate_changed', 'result_submitted', 'result_reviewed', 'letter_issued',
            'mentor_assigned', 'session_logged', 'payment_released', 'closed', 'results_overdue',
            'letter_withdrawn', 'letter_acknowledged'})   # S6b

    def test_add_entry_writes_a_manual_row(self):
        row = activity.add_entry(self.app, 'call', '  Rang her mother.  ',
                                 actor_email='officer@example.test')
        self.assertEqual((row.kind, row.event, row.body, row.internal),
                         ('call', '', 'Rang her mother.', False))

    def test_add_entry_validates(self):
        for kind, body, code in (('system', 'x', 'bad_kind'), ('sms', 'x', 'bad_kind'),
                                 ('note', '   ', 'empty_body'),
                                 ('note', 'x' * (activity.BODY_MAX + 1), 'too_long')):
            with self.subTest(code=code, kind=kind):
                with self.assertRaises(ActivityError) as ctx:
                    activity.add_entry(self.app, kind, body, actor_email='o@example.test')
                self.assertEqual(ctx.exception.code, code)
        self.assertFalse(StudentActivity.objects.exists())
