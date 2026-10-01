"""TD-257 — the brakes and the gates in front of the money, driven through HTTP.

Three routes the TD-219 guard listed as never driven by any test:
  * `applications/<pk>/hold-award/`      — stops an accepted award inside the cool-off (AdminHoldAwardView)
  * `applications/<pk>/reporting-date/`  — the date the bursary is SIZED from     (AdminReportingDateView)
  * `admin/sponsors/<pk>/membership/`    — accepts a benefactor into a gift; `record_admin_credit`
                                           refuses money without it      (AdminSponsorMembershipView)

Each test reads what the SERVICE wrote (the sponsorship lapsed and the money back in the
sponsor's wallet; the date on the row and the AUDIT line naming who typed it; a membership row a
money call then accepts), never only the status code. The cool-off pair's other half,
`cancel-decline`, has been driven since TD-203 (2026-09-30).
"""
import datetime

from django.test import TestCase, override_settings

from apps.scholarship import sponsorship
from apps.scholarship.models import Sponsor, SponsorProgrammeMembership
from apps.scholarship.tests.factories import (
    REPORTING_DATE, TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
    make_programme, unique_suffix,
)
from apps.scholarship.tests.test_endpoints_disbursements import fund_through_the_product

API = '/api/v1/admin/scholarship/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestHoldAward(TestCase):
    """POST applications/<pk>/hold-award/ — the brake between a mistaken award and a told student."""

    def setUp(self):
        self.cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.client = authed_client(self.reviewer)

    def _hold(self, app, client=None):
        return (client or self.client).post(f'{API}applications/{app.id}/hold-award/', {},
                                            format='json')

    def test_a_held_award_goes_back_to_the_pool_and_the_money_back_to_the_sponsor(self):
        app, sponsor, sp = fund_through_the_product(self.cohort, reviewer=self.reviewer,
                                                    cooloff_days=2)
        self.assertEqual(app.status, 'awarded')
        self.assertIsNotNone(app.award_due_at)
        self.assertEqual(sponsorship.sponsor_balance(sponsor, app.programme), 0)

        r = self._hold(app)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, app.award_due_at, sp.status),
                         ('recommended', None, 'lapsed'))
        self.assertEqual(sponsorship.sponsor_balance(sponsor, app.programme), app.award_amount)

    def test_holding_twice_is_harmless(self):
        app, _sponsor, _sp = fund_through_the_product(self.cohort, reviewer=self.reviewer,
                                                      cooloff_days=2)
        self._hold(app)
        self.assertEqual(self._hold(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')

    def test_the_brake_cannot_reach_an_award_that_has_already_been_confirmed(self):
        # Cool-off 0: the accept finalised at once, the student was told, the case is funded.
        # The view answers 200 either way (it is idempotent by design) — what matters is that
        # NOTHING moved: a confirmed award is not this endpoint's to take back.
        app, _sponsor, sp = fund_through_the_product(self.cohort, reviewer=self.reviewer,
                                                     cooloff_days=0)
        self.assertEqual(self._hold(app).status_code, 200)
        app.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((app.status, sp.status), ('active', 'active'))

    def test_a_reviewer_not_assigned_to_the_case_cannot_hold_it(self):
        app, _sponsor, sp = fund_through_the_product(self.cohort, reviewer=self.reviewer,
                                                     cooloff_days=2)
        other = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
        self.assertEqual(self._hold(app, client=authed_client(other)).status_code, 403)
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'active')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReportingDate(TestCase):
    """POST applications/<pk>/reporting-date/ — QC refuses a case without one; this clears it."""

    def setUp(self):
        cohort = make_cohort()
        self.reviewer = make_admin('reviewer', owning_org=cohort.owning_organisation)
        self.app = make_application('interviewing', cohort=cohort, reviewer=self.reviewer)
        self.client = authed_client(self.reviewer)

    def _set(self, value):
        return self.client.post(f'{API}applications/{self.app.id}/reporting-date/',
                                {'date': value}, format='json')

    def test_the_assigned_reviewer_sets_the_date_and_the_audit_line_names_them(self):
        with self.assertLogs('apps.scholarship.services', 'INFO') as logs:
            r = self._set('2026-09-14')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.reporting_date, datetime.date(2026, 9, 14))
        self.assertEqual(r.json()['reporting_date'], '2026-09-14')
        audit = [line for line in logs.output if 'reporting_date_set' in line]
        self.assertEqual(len(audit), 1, logs.output)
        self.assertIn(f'by={self.reviewer.email}', audit[0])

    def test_a_blank_or_unreadable_date_is_refused_and_the_old_one_kept(self):
        for value in ('', '14/09/2026', None):
            r = self._set(value)
            self.assertEqual((r.status_code, r.json()['code']), (400, 'date_required'), value)
        self.app.refresh_from_db()
        self.assertEqual(self.app.reporting_date, REPORTING_DATE)

    def test_a_partner_cannot_set_it(self):
        partner = make_admin('partner', owning_org=self.app.owning_organisation)
        r = authed_client(partner).post(f'{API}applications/{self.app.id}/reporting-date/',
                                        {'date': '2026-09-14'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.app.refresh_from_db()
        self.assertEqual(self.app.reporting_date, REPORTING_DATE)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorMembership(TestCase):
    """POST admin/sponsors/<pk>/membership/ — the gate a second gift's money waits behind."""

    def setUp(self):
        cohort = make_cohort()
        self.org = cohort.owning_organisation
        self.programme = cohort.programme
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.maker = make_admin('admin', owning_org=self.org)        # who keys a credit in
        self.sponsor = self._sponsor('approved')
        self.client = authed_client(self.org_admin)

    def _sponsor(self, status):
        return Sponsor.objects.create(
            supabase_user_id=unique_suffix('sponsor-uid-'), name='Test Benefactor',
            email=f'{unique_suffix("benefactor-")}@example.test', status=status)

    def _set(self, sponsor, programme, status='approved', client=None):
        return (client or self.client).post(
            f'/api/v1/admin/sponsors/{sponsor.id}/membership/',
            {'programme_id': programme.id, 'status': status}, format='json')

    def _credit(self):
        return sponsorship.record_admin_credit(
            sponsor=self.sponsor, programme=self.programme, amount=1000,
            external_reference='BANK-REF-1', admin=self.maker)

    def test_accepting_a_benefactor_opens_the_gift_to_their_money(self):
        with self.assertRaises(sponsorship.CreditError) as before:
            self._credit()
        self.assertEqual(str(before.exception), 'sponsor_not_in_programme')

        with self.assertLogs('apps.scholarship.views_admin', 'INFO') as logs:
            r = self._set(self.sponsor, self.programme)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {'programme_id': self.programme.id,
                                    'programme': self.programme.code, 'status': 'approved'})
        m = SponsorProgrammeMembership.objects.get(sponsor=self.sponsor, programme=self.programme)
        self.assertEqual((m.status, m.vetted_by), ('approved', self.org_admin.email))
        self.assertIsNotNone(m.vetted_at)
        self.assertTrue(any('sponsor_membership_set' in line for line in logs.output))

        # The point of the route: the money call that refused above now records a draft credit.
        self.assertEqual(self._credit().status, 'draft')

    def test_an_account_that_is_not_vetted_cannot_be_accepted_into_a_gift(self):
        pending = self._sponsor('pending')
        r = self._set(pending, self.programme)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'account_not_approved'))
        self.assertFalse(SponsorProgrammeMembership.objects.filter(sponsor=pending).exists())

    def test_another_organisations_gift_is_not_found(self):
        foreign = make_programme()                              # a gift in a different tenant
        r = self._set(self.sponsor, foreign)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(SponsorProgrammeMembership.objects.filter(sponsor=self.sponsor).exists())

    def test_a_reviewer_cannot_decide_who_funds_the_organisations_students(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        r = self._set(self.sponsor, self.programme, client=authed_client(reviewer))
        self.assertEqual(r.status_code, 403)
        self.assertFalse(SponsorProgrammeMembership.objects.filter(sponsor=self.sponsor).exists())
