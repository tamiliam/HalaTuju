"""Student maintenance Sprint 1 — the adversarial review's fixes (M1, L1, L2, L3).

  * M1: a move to/from `on_hold` is a money act — reviewer refused (403 `hold_needs_payments`), a
    `payments_prepare` holder allowed; a refused approval leaves the run signed and unpaid;
  * L1: an award that falls through resets a stored hold to on_track, stamped and logged;
  * L2: `set_substate` judges the STORED sub-state, not a stale in-memory copy;
  * L3: the run item says `on_hold`, and the refusal says how many.
"""
from datetime import date

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import maintenance, payments
from apps.scholarship.award_revert import revert_to_pool
from apps.scholarship.models import (
    Disbursement, PaymentRunItem, ScholarshipApplication, StudentActivity,
)
from apps.scholarship.models.activity import EVENT_SUBSTATE_CHANGED
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)
from apps.scholarship.tests.test_on_hold_money import _paid_cohort_year_and_pathway

API = '/api/v1/admin/scholarship/'


def _next_period():
    today = timezone.localdate()
    return date(today.year + (today.month == 12), today.month % 12 + 1, 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class _Org(TestCase):
    def setUp(self):
        self.period = _next_period()
        self.pay_on = max(timezone.localdate(), payments.earliest_payment_date(self.period))
        # A cohort + pathway the default schedule pays in `period`, whatever today is.
        year, pathway = _paid_cohort_year_and_pathway(self.period)
        self.cohort = make_cohort(year=year)
        org = self.cohort.owning_organisation
        self.reviewer = make_admin('reviewer', owning_org=org)
        self.maker = make_admin('admin', owning_org=org, name='Maker One')
        self.approver = make_admin('org_admin', owning_org=org, name='Approver One')
        self.app = make_application(
            'awarded', cohort=self.cohort, reviewer=self.reviewer,
            vircle_activated_at=timezone.now(), vircle_id=payments.vircle_id_prefix() + '72001',
            chosen_pathway=pathway, reporting_date=date(year, 6, 8))

    def _substate(self, admin, substate, app=None):
        app = app or self.app
        return authed_client(admin).post(f'{API}applications/{app.id}/maintenance/',
                                         {'substate': substate}, format='json')


class TestHoldIsAMoneyAct(_Org):
    def test_a_reviewer_cannot_place_or_lift_a_hold(self):
        r = self._substate(self.reviewer, 'on_hold')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'hold_needs_payments'))
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_track')
        maintenance.set_substate(self.app, 'on_hold', by_email='x@example.test')
        r = self._substate(self.reviewer, 'on_track')
        self.assertEqual((r.status_code, r.json()['code']), (403, 'hold_needs_payments'))

    def test_a_reviewer_keeps_the_other_substates(self):
        self.assertEqual(self._substate(self.reviewer, 'probation').status_code, 200)

    def test_a_payments_prepare_holder_may_hold(self):
        held = make_application('awarded', cohort=self.cohort, reviewer=self.maker,
                                vircle_activated_at=timezone.now())
        self.assertTrue(self.maker.has_perm('payments_prepare'))
        r = self._substate(self.maker, 'on_hold', app=held)
        self.assertEqual(r.status_code, 200, r.content)
        held.refresh_from_db()
        self.assertEqual((held.maintenance_substate, held.maintenance_substate_changed_by),
                         ('on_hold', self.maker.email))

    def test_a_refused_approval_leaves_the_run_signed_and_unpaid(self):
        run = payments.create_run(self.cohort.owning_organisation, self.cohort.programme,
                                  self.pay_on, self.period, by_email=self.maker.email)
        sign = f'{API}payment-runs/{run.id}/sign/'
        r = authed_client(self.maker).post(sign, {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r.json()['status'], 'admin_signed', r.content)
        # A hold that reached the row without the exclusion (race / hand edit): the last door.
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(maintenance_substate='on_hold')
        detail = authed_client(self.maker).get(f'{API}payment-runs/{run.id}/').json()
        self.assertTrue(detail['items'][0]['on_hold'])
        r = authed_client(self.approver).post(sign, {'typed_name': 'Approver One'}, format='json')
        self.assertEqual((r.status_code, r.json()['code'], r.json()['count']),
                         (400, 'on_hold_in_run', 1))
        run.refresh_from_db()
        self.assertEqual((run.status, run.admin_signed_email, run.org_admin_signed_at),
                         ('admin_signed', self.maker.email, None))
        self.assertFalse(Disbursement.objects.filter(application=self.app).exists())


class TestAFallenThroughAwardStartsClean(_Org):
    def test_revert_resets_a_hold_and_logs_it(self):
        maintenance.set_substate(self.app, 'on_hold', by_email='officer@example.test')
        revert_to_pool(self.app)
        self.app.refresh_from_db()
        self.assertIn(self.app.status, ('recommended', 'interviewed'))
        self.assertEqual((self.app.maintenance_substate, self.app.maintenance_substate_changed_by),
                         ('on_track', 'system'))
        row = StudentActivity.objects.filter(application=self.app,
                                             event=EVENT_SUBSTATE_CHANGED).order_by('-id').first()
        self.assertEqual((row.meta['old'], row.meta['new'], row.meta['reason']),
                         ('on_hold', 'on_track', 'award_reverted'))

    def test_revert_of_an_on_track_case_writes_no_row(self):
        revert_to_pool(self.app)
        self.assertFalse(StudentActivity.objects.filter(application=self.app).exists())


class TestStoredSubstateIsJudged(_Org):
    def test_a_stale_copy_cannot_skip_a_real_change(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)     # reads on_track
        maintenance.set_substate(self.app, 'on_hold')                   # stored: on_hold
        maintenance.set_substate(stale, 'on_track')                     # stale thinks no-op
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_track')
        row = StudentActivity.objects.filter(application=self.app).order_by('-id').first()
        self.assertEqual((row.meta['old'], row.meta['new']), ('on_hold', 'on_track'))

    def test_a_stale_copy_of_the_same_value_is_a_no_op(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)
        maintenance.set_substate(self.app, 'probation')
        maintenance.set_substate(stale, 'probation')                    # already stored
        self.assertEqual(StudentActivity.objects.filter(application=self.app).count(), 1)
        self.assertEqual(stale.maintenance_substate, 'probation')


class TestRunItemFlag(_Org):
    def test_the_item_dict_carries_on_hold(self):
        run = payments.create_run(self.cohort.owning_organisation, self.cohort.programme,
                                  self.pay_on, self.period)
        item = PaymentRunItem.objects.get(run=run, application=self.app)
        detail = authed_client(self.maker).get(f'{API}payment-runs/{run.id}/').json()
        self.assertEqual([i['on_hold'] for i in detail['items'] if i['id'] == item.id], [False])
