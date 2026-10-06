"""TD-257 — the money-out routes, driven through HTTP for the first time.

Five routes the TD-219 guard listed as never driven by any test:
  * `applications/<pk>/disbursements/`        — schedule a tranche          (AdminDisbursementScheduleView)
  * `disbursements/<pk>/<action>/`            — release / withhold / return / mark_due (AdminDisbursementActionView)
  * `applications/<pk>/maintenance/`          — the on-hold brake on releases (AdminMaintenanceSubstateView)
  * `applications/<pk>/close/`                — terminal closure            (AdminCloseApplicationView)

The services behind them (`disbursement`, `maintenance`, `closure`) have their own suites. What
was never tested is the CALL between the view and the service — the seam TD-219 found 500-ing for
eighteen days on the Requests module. So every test here posts the way the cockpit posts and reads
the ROW the service writes, never only the status code: a test that passed with the service body
replaced by `pass` would be the gap this file exists to close (three of them were bitten that way;
see the TD-257 retro).

THE FUNDED STUDENT IS BUILT THROUGH THE PRODUCT, not by setting `status='active'`. The factory takes
the case to `recommended` (in the pool); then a sponsor with money in that gift funds it
(`sponsorship.fund_student`) and the student accepts (`respond_to_award`). With the award cool-off
at 0 the accept finalises at once, which is the flag-OFF production path to `active`. That matters
here: a tranche links itself to the LIVE sponsorship (`_current_sponsorship`), and a hand-set
`active` row has none — the link would be `None` and the assertion on it would prove nothing.
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import sponsorship
from apps.scholarship.models import Disbursement, Donation, Sponsor
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)

API = '/api/v1/admin/scholarship/'


def fund_through_the_product(cohort, *, reviewer, cooloff_days=0):
    """A case the product has FUNDED: factory to `recommended`, then the real money path.

    `cooloff_days=0` finalises the accept immediately (status `active`, the funded state a tranche
    needs); a positive value leaves it `awarded` with `award_due_at` set — the window the
    hold-award brake works inside. Returns (application, sponsor, sponsorship).
    """
    app = make_application('recommended', cohort=cohort, reviewer=reviewer)
    sponsor = Sponsor.objects.create(
        supabase_user_id=unique_suffix('sponsor-uid-'), name='Test Funder',
        email=f'{unique_suffix("funder-")}@example.test', status='approved',
        consent_at=timezone.now())
    # Money in THIS gift's wallet: `fund_student` spends per programme, never a total.
    Donation.objects.create(sponsor=sponsor, amount=Decimal(app.award_amount),
                            programme=app.programme)
    sponsorship.fund_student(sponsor, app)                       # -> 'awarded', offer 'offered'
    with override_settings(AWARD_COOLOFF_DAYS=cooloff_days, BURSARY_AGREEMENT_ENABLED=False):
        sp = sponsorship.respond_to_award(app, action='accept')  # -> 'active' or held 'awarded'
    app.refresh_from_db()
    return app, sponsor, sp


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _FundedCase(TestCase):
    """One funded (`active`) student, the reviewer assigned to them, and a client for each role."""

    def setUp(self):
        self.cohort = make_cohort()
        org = self.cohort.owning_organisation
        self.reviewer = make_admin('reviewer', owning_org=org)
        self.org_admin = make_admin('org_admin', owning_org=org)
        self.app, self.sponsor, self.sp = fund_through_the_product(
            self.cohort, reviewer=self.reviewer)
        self.assertEqual(self.app.status, 'active', 'the product path did not fund the case')
        self.client = authed_client(self.reviewer)

    def _schedule(self, amount='500', **extra):
        return self.client.post(f'{API}applications/{self.app.id}/disbursements/',
                                {'amount': amount, **extra}, format='json')

    def _act(self, tranche, action, **body):
        return self.client.post(f'{API}disbursements/{tranche.id}/{action}/', body, format='json')

    def _tranche(self):
        """Schedule one tranche over HTTP and return the row the service wrote."""
        r = self._schedule()
        self.assertEqual(r.status_code, 200, r.content)
        return Disbursement.objects.filter(application=self.app).order_by('-sequence').first()


class TestScheduleTranche(_FundedCase):
    """POST applications/<pk>/disbursements/ — the schedule every payment is made against."""

    def test_the_assigned_reviewer_schedules_a_tranche_linked_to_the_live_sponsorship(self):
        r = self._schedule('750.5', label='Semester 1', scheduled_for='2026-11-01')
        self.assertEqual(r.status_code, 200, r.content)
        row = Disbursement.objects.get(application=self.app)
        self.assertEqual((row.amount, row.status, row.sequence, row.label),
                         (Decimal('750.50'), 'scheduled', 1, 'Semester 1'))
        # Only the service knows which sponsorship is live; the view never names it.
        self.assertEqual(row.sponsorship_id, self.sp.id)
        self.assertEqual([d['id'] for d in r.json()['disbursements']], [row.id])

    def test_the_sequence_is_numbered_by_the_service_not_the_caller(self):
        self._schedule()
        self._schedule()
        self.assertEqual(
            list(Disbursement.objects.filter(application=self.app)
                 .order_by('sequence').values_list('sequence', flat=True)), [1, 2])

    def test_a_case_that_is_not_funded_is_refused_and_nothing_is_written(self):
        unfunded = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        r = self.client.post(f'{API}applications/{unfunded.id}/disbursements/',
                             {'amount': '500'}, format='json')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'not_in_programme'))
        self.assertFalse(Disbursement.objects.filter(application=unfunded).exists())

    def test_a_bad_amount_is_refused(self):
        r = self._schedule('-5')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_amount'))
        self.assertFalse(Disbursement.objects.exists())

    def test_a_reviewer_not_assigned_to_the_case_is_refused(self):
        other = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        r = authed_client(other).post(f'{API}applications/{self.app.id}/disbursements/',
                                      {'amount': '500'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Disbursement.objects.exists())


class TestTrancheActions(_FundedCase):
    """POST disbursements/<pk>/<action>/ — every action the view accepts, with its precondition."""

    def test_mark_due_then_release_pays_the_tranche_and_moves_the_case_to_maintenance(self):
        tranche = self._tranche()
        self.assertEqual(self._act(tranche, 'mark_due').status_code, 200)
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'due')

        r = self._act(tranche, 'release', note='Paid to eWallet')
        self.assertEqual(r.status_code, 200, r.content)
        tranche.refresh_from_db()
        self.assertEqual((tranche.status, tranche.actioned_by, tranche.reference, tranche.note),
                         ('released', self.reviewer.email, 'mock', 'Paid to eWallet'))
        self.assertIsNotNone(tranche.released_at)
        # The FIRST release is what moves a student into the funded loop.
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'maintenance')
        self.assertIsNotNone(self.app.maintenance_at)

    def test_release_straight_from_scheduled_is_allowed(self):
        tranche = self._tranche()
        self.assertEqual(self._act(tranche, 'release').status_code, 200)
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'released')

    def test_a_released_tranche_cannot_be_paid_twice(self):
        tranche = self._tranche()
        self._act(tranche, 'release')
        r = self._act(tranche, 'release')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_state'))

    def test_withhold_holds_back_an_unpaid_tranche_and_leaves_the_case_where_it_was(self):
        tranche = self._tranche()
        r = self._act(tranche, 'withhold', note='Results outstanding')
        self.assertEqual(r.status_code, 200, r.content)
        tranche.refresh_from_db()
        self.assertEqual((tranche.status, tranche.actioned_by), ('withheld', self.reviewer.email))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'active')

    def test_return_needs_a_released_tranche(self):
        tranche = self._tranche()
        r = self._act(tranche, 'return')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_state'))
        self._act(tranche, 'release')
        self.assertEqual(self._act(tranche, 'return', note='Withdrew').status_code, 200)
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'returned')

    def test_mark_due_needs_a_scheduled_tranche(self):
        tranche = self._tranche()
        self._act(tranche, 'withhold')
        r = self._act(tranche, 'mark_due')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_state'))

    def test_an_unknown_action_is_refused_before_anything_is_read(self):
        tranche = self._tranche()
        r = self._act(tranche, 'refund')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_action'))
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'scheduled')

    def test_a_reviewer_not_assigned_to_the_case_cannot_release(self):
        tranche = self._tranche()
        other = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        r = authed_client(other).post(f'{API}disbursements/{tranche.id}/release/', {},
                                      format='json')
        self.assertEqual(r.status_code, 403)
        tranche.refresh_from_db()
        self.assertEqual(tranche.status, 'scheduled')

    def test_finance_cannot_release(self):
        # Finance checks money; it never acts on an applicant's case (role matrix 2026-07-23).
        tranche = self._tranche()
        finance = make_admin('finance', owning_org=self.cohort.owning_organisation)
        r = authed_client(finance).post(f'{API}disbursements/{tranche.id}/release/', {},
                                        format='json')
        self.assertEqual(r.status_code, 403)


class TestMaintenanceBrake(_FundedCase):
    """POST applications/<pk>/maintenance/ — `on_hold` is the only thing that stops a release."""

    def _into_maintenance(self):
        self._act(self._tranche(), 'release')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'maintenance')

    def _substate(self, substate):
        return self.client.post(f'{API}applications/{self.app.id}/maintenance/',
                                {'substate': substate}, format='json')

    def test_on_hold_is_recorded_and_then_refuses_the_next_release(self):
        self._into_maintenance()
        r = self._substate('on_hold')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.maintenance_substate, 'on_hold')

        nxt = self._tranche()
        r = self._act(nxt, 'release')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'on_hold'))
        nxt.refresh_from_db()
        self.assertEqual(nxt.status, 'scheduled')

        # Resuming lifts the brake.
        self._substate('on_track')
        self.assertEqual(self._act(nxt, 'release').status_code, 200)

    def test_a_case_not_yet_in_maintenance_has_no_substate(self):
        r = self._substate('probation')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'not_in_maintenance'))
        self.app.refresh_from_db()
        self.assertNotEqual(self.app.maintenance_substate, 'probation')   # nothing was written

    def test_an_unknown_substate_is_refused(self):
        self._into_maintenance()
        r = self._substate('suspended')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_substate'))


class TestCloseApplication(_FundedCase):
    """POST applications/<pk>/close/ — terminal. Nothing walks it back."""

    def _close(self, reason, client=None):
        return (client or self.client).post(f'{API}applications/{self.app.id}/close/',
                                            {'closure_reason': reason}, format='json')

    def test_the_org_admin_closes_a_funded_case_with_a_reason(self):
        r = self._close('graduated', client=authed_client(self.org_admin))
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.closure_reason, self.app.closed_by),
                         ('closed', 'graduated', self.org_admin.email))
        self.assertIsNotNone(self.app.closed_at)

    def test_a_tranche_left_scheduled_at_closure_can_no_longer_be_paid(self):
        leftover = self._tranche()
        self.assertEqual(self._close('withdrawn').status_code, 200)
        r = self._act(leftover, 'release')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'not_in_programme'))

    def test_an_unknown_reason_is_refused_and_the_case_stays_open(self):
        r = self._close('moved_away')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'bad_reason'))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'active')

    def test_a_finished_case_cannot_be_closed_here(self):
        # TD-352: a never-funded case in play CAN now be closed (test_close_stalled.py); a
        # finished one still cannot.
        declined = make_application('rejected', cohort=self.cohort, reviewer=self.reviewer)
        r = self.client.post(f'{API}applications/{declined.id}/close/',
                             {'closure_reason': 'withdrawn'}, format='json')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'not_closeable'))
        declined.refresh_from_db()
        self.assertEqual(declined.status, 'rejected')
