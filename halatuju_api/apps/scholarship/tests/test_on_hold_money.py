"""Student maintenance Sprint 1 — ON HOLD STOPS MONEY (owner ruling 2026-10-29), every door.

The live cohort is paid by Vircle payment runs while still `awarded` (`payments.PAYABLE_STATUSES`),
so before this sprint "on hold" (a `maintenance`-only idea) could not stop a single ringgit for any
of them. The doors, each pinned here:

  a. run creation — `payments.eligibility` greys an on-hold student out (`on_hold`); no item;
  b. a hold placed AFTER a run holds her item — `maintenance.set_substate` excludes it from every
     EDITABLE run ('On hold'); a signed run reverts to draft and loses its signatures (D2, "nobody
     signs one list and sends another"); a completed run is history and is left alone;
  c. completion — `payments.complete` refuses (`on_hold_in_run`) if an INCLUDED item's student is
     on hold, and nothing is written;
  d. re-including by hand — `payments.set_item(included=True)` refuses (`on_hold`);
  e. lifting the hold does NOT re-include: the maker does that, by hand;
  f. the tranche door — `disbursement.release_tranche` already refuses (`test_maintenance.py`).
Plus the activity rows each money door writes.
"""
from datetime import date

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import maintenance, payments
from apps.scholarship.models import Disbursement, PaymentRunItem, StudentActivity
from apps.scholarship.models.activity import EVENT_PAYMENT_RELEASED, EVENT_SUBSTATE_CHANGED
from apps.scholarship.maintenance import MaintenanceError
from apps.scholarship.payments import PaymentsError
from apps.scholarship.tests.factories import make_application, make_cohort


def _next_period():
    today = timezone.localdate()
    return date(today.year + (today.month == 12), today.month % 12 + 1, 1)


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class _PaidCohort(TestCase):
    """Two awarded students with live wallets, in one gift, payable next month."""

    def setUp(self):
        self.period = _next_period()
        self.pay_on = max(timezone.localdate(), payments.earliest_payment_date(self.period))
        # The pathway floor is July of the cohort year: last year's cohort has started.
        self.cohort = make_cohort(year=self.period.year - 1)
        self.org, self.programme = self.cohort.owning_organisation, self.cohort.programme
        self.held = self._student('71001')
        self.other = self._student('71002')

    def _student(self, suffix):
        return make_application(
            'awarded', cohort=self.cohort, vircle_activated_at=timezone.now(),
            vircle_id=payments.vircle_id_prefix() + suffix, chosen_pathway='matric',
            reporting_date=date(self.period.year - 1, 6, 8))

    def _run(self):
        return payments.create_run(self.org, self.programme, self.pay_on, self.period,
                                   by_email='maker@example.test')

    def _item(self, run, app):
        return PaymentRunItem.objects.get(run=run, application=app)


class TestOnHoldAtRunCreation(_PaidCohort):
    def test_an_on_hold_awarded_student_gets_no_item(self):
        maintenance.set_substate(self.held, 'on_hold', by_email='officer@example.test')
        run = self._run()
        self.assertEqual(list(run.items.values_list('application_id', flat=True)), [self.other.id])
        elig = payments.eligibility(self.held, self.pay_on, period_month=self.period)
        self.assertIn('on_hold', elig['reasons'])
        self.assertFalse(elig['eligible'])


class TestHoldAfterTheRunWasMade(_PaidCohort):
    def test_a_draft_run_loses_her_item_with_the_reason(self):
        run = self._run()
        maintenance.set_substate(self.held, 'on_hold', by_email='officer@example.test')
        item = self._item(run, self.held)
        self.assertEqual((item.included, item.exclude_reason), (False, 'On hold'))
        self.assertTrue(self._item(run, self.other).included)
        run.refresh_from_db()
        self.assertEqual(run.status, 'draft')
        row = StudentActivity.objects.get(application=self.held, event=EVENT_SUBSTATE_CHANGED)
        self.assertEqual(row.meta['excluded_from_runs'],
                         [{'run': run.reference, 'signatures_cleared': False}])

    def test_a_signed_run_reverts_to_draft_and_loses_her_item(self):
        run = self._run()
        run.status, run.admin_signed_name = 'admin_signed', 'Maker'
        run.admin_signed_email, run.admin_signed_at = 'maker@example.test', timezone.now()
        run.save()
        with self.assertLogs('apps.scholarship.maintenance', 'WARNING') as logs:
            maintenance.set_substate(self.held, 'on_hold')
        self.assertIn('signatures cleared', logs.output[0])
        run.refresh_from_db()
        self.assertEqual((run.status, run.admin_signed_email, run.admin_signed_at),
                         ('draft', '', None))
        row = StudentActivity.objects.get(application=self.held, event=EVENT_SUBSTATE_CHANGED)
        self.assertEqual(row.meta['excluded_from_runs'],
                         [{'run': run.reference, 'signatures_cleared': True}])
        self.assertFalse(self._item(run, self.held).included)

    def test_a_completed_run_is_history_and_is_left_alone(self):
        run = self._run()
        run.status = 'completed'
        run.save(update_fields=['status'])
        maintenance.set_substate(self.held, 'on_hold')
        self.assertTrue(self._item(run, self.held).included)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_lifting_the_hold_does_not_re_include_her(self):
        run = self._run()
        maintenance.set_substate(self.held, 'on_hold')
        maintenance.set_substate(self.held, 'on_track')
        item = self._item(run, self.held)
        self.assertFalse(item.included)
        payments.set_item(item, included=True)      # the maker re-includes, by hand
        self.assertTrue(self._item(run, self.held).included)

    def test_probation_does_not_touch_the_run(self):
        run = self._run()
        maintenance.set_substate(self.held, 'probation')
        self.assertTrue(self._item(run, self.held).included)


class TestTheHoldIsNotTheFilePredicate(_PaidCohort):
    """Lead review: `vircle_activated_at` is mirrored from the relay sheet. The money hold must not
    lean on it, and a student the run pays on her wallet ID alone must be holdable."""

    def test_a_hold_survives_a_cleared_activation_stamp(self):
        run = self._run()
        maintenance.set_substate(self.held, 'on_hold')
        self.held.vircle_activated_at = None
        self.held.save(update_fields=['vircle_activated_at'])
        self.assertTrue(maintenance.is_on_hold(self.held))
        # A new run leaves her out...
        fresh = self._run()
        self.assertFalse(fresh.items.filter(application=self.held).exists())
        # ...and an item forced back in still stops the completion.
        PaymentRunItem.objects.filter(run=run, application=self.held).update(
            included=True, exclude_reason='')
        with self.assertRaises(PaymentsError) as ctx:
            payments.complete(run)
        self.assertEqual(ctx.exception.code, 'on_hold_in_run')

    def test_a_stored_hold_can_always_be_lifted(self):
        maintenance.set_substate(self.held, 'on_hold')
        self.held.vircle_activated_at, self.held.vircle_id = None, ''
        self.held.save(update_fields=['vircle_activated_at', 'vircle_id'])
        self.assertFalse(maintenance.is_in_maintenance(self.held))      # no wallet fields left
        self.assertTrue(maintenance.can_set_substate(self.held, 'on_track'))
        self.assertFalse(maintenance.can_set_substate(self.held))        # no NEW sub-state
        maintenance.set_substate(self.held, 'on_track')
        self.held.refresh_from_db()
        self.assertEqual(self.held.maintenance_substate, 'on_track')

    def test_a_paid_student_whose_wallet_is_not_yet_live_can_be_held(self):
        pending = make_application(
            'awarded', cohort=self.cohort, vircle_id=payments.vircle_id_prefix() + '71003',
            chosen_pathway='matric', reporting_date=date(self.period.year - 1, 6, 8))
        self.assertIsNone(pending.vircle_activated_at)
        run = self._run()
        self.assertTrue(run.items.filter(application=pending).exists())   # the run pays her
        maintenance.set_substate(pending, 'on_hold')
        self.assertFalse(self._item(run, pending).included)
        self.assertFalse(self._run().items.filter(application=pending).exists())

    def test_an_awarded_student_with_no_wallet_id_takes_no_substate(self):
        unpaid = make_application('awarded', cohort=self.cohort)
        self.assertEqual(unpaid.vircle_id, '')
        with self.assertRaises(MaintenanceError) as ctx:
            maintenance.set_substate(unpaid, 'on_hold')
        self.assertEqual(ctx.exception.code, 'not_in_maintenance')


class TestReIncludeRefused(_PaidCohort):
    def test_the_maker_cannot_re_include_an_on_hold_student(self):
        run = self._run()
        maintenance.set_substate(self.held, 'on_hold')
        item = self._item(run, self.held)
        with self.assertRaises(PaymentsError) as ctx:
            payments.set_item(item, included=True)
        self.assertEqual(ctx.exception.code, 'on_hold')
        self.assertFalse(self._item(run, self.held).included)


class TestCompletionRefusesAHeldStudent(_PaidCohort):
    def test_complete_refuses_and_writes_nothing(self):
        run = self._run()
        # A hold that reached the row WITHOUT the exclusion (a race, a hand edit): the last door.
        self.held.maintenance_substate = 'on_hold'
        self.held.save(update_fields=['maintenance_substate'])
        with self.assertRaises(PaymentsError) as ctx:
            payments.complete(run)
        self.assertEqual(ctx.exception.code, 'on_hold_in_run')
        self.assertFalse(Disbursement.objects.filter(
            application__in=[self.held, self.other]).exists())
        self.assertFalse(StudentActivity.objects.filter(event=EVENT_PAYMENT_RELEASED).exists())

    def test_an_excluded_held_student_does_not_block_the_run(self):
        run = self._run()
        maintenance.set_substate(self.held, 'on_hold')
        payments.complete(run)
        self.assertFalse(Disbursement.objects.filter(application=self.held).exists())
        self.assertTrue(Disbursement.objects.filter(application=self.other,
                                                    status='released').exists())

    def test_completion_logs_one_payment_released_row_per_paid_student(self):
        run = self._run()
        payments.complete(run)
        rows = StudentActivity.objects.filter(event=EVENT_PAYMENT_RELEASED)
        self.assertEqual(sorted(rows.values_list('application_id', flat=True)),
                         sorted([self.held.id, self.other.id]))
        meta = rows.get(application=self.held).meta
        item = self._item(run, self.held)
        self.assertEqual((meta['run'], meta['amount']), (run.reference, str(item.amount)))
