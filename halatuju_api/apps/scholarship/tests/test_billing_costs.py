"""The COST side reaching a screen, and the bill that comes out of it (2026-09-11).

The owner sent August's real invoices — GCP, Supabase, Google Workspace, Twilio — and said none
of it appears on the Usage & Billing page. It did not: the ledger, the BigQuery sync, the
reconciliation maths and the rates endpoint were all built in July 2026 and then starved. No
endpoint had ever read any of it.

Four properties carry this sprint, and every one of them is about not lying on an invoice:

1. **A month is shown in full and THEN discounted.** The owner's July instruction was *"we do
   not bill anything for July. 100% discount. But show the values."* Suppressing the month would
   satisfy the first half and destroy the second.
2. **A discount carries a reason.** A waived month with no stated reason is indistinguishable
   from a bug that produced zero.
3. **A category that cannot be priced is REFUSED, never zeroed.** A line the reader can see is
   missing gets fixed; a zero gets believed.
4. **The truthfulness flags reach the screen.** A total mixing measured and hand-typed figures
   without saying so is not an audit.
"""
from datetime import date
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import platform_cost
from apps.scholarship.models import (
    BillingRate, OrgBillingAdjustment, OrgBuildHours, OrgRequest, PlatformCost,
)
from rest_framework.test import APIClient

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
COSTS_URL = '/api/v1/admin/scholarship/billing/costs/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='bp', name='BrightPath')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        # An ACTIVE org_admin is what makes `org` a tenant to `.tenants()` — the queryset the
        # endpoint uses. Without one the org is a referral partner and carries no bill.
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OA', email='oa@x.com')

    def _client(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def _cost(self, source, amount, month='2026-08', **kw):
        kw.setdefault('provenance', 'entered')
        kw.setdefault('service', source)
        kw.setdefault('sku', '')
        return PlatformCost.objects.create(
            period_month=month, source=source, amount_myr=Decimal(str(amount)), **kw)

    def _rates(self, hourly='150', margin='20', on='2026-07-01'):
        BillingRate.objects.create(
            category='development', kind='hourly_rate', value=Decimal(hourly),
            effective_from=date.fromisoformat(on))
        BillingRate.objects.create(
            category='development', kind='margin_pct', value=Decimal(margin),
            effective_from=date.fromisoformat(on))

    def _hours(self, hours, month='2026-08', module='Payments module'):
        return OrgBuildHours.objects.create(
            organisation=self.org, period_month=month, module=module,
            hours=Decimal(str(hours)), basis='20 working days at 4h')


class TestWorkspaceIsItsOwnSource(_Base):
    """Google Workspace is a standing monthly line, not an 'other'."""

    def test_workspace_is_an_allowed_source_and_totals_under_its_own_name(self):
        self._cost('workspace', '18.90')
        self._cost('twilio', '7.60')
        totals = platform_cost.month_totals('2026-08')
        self.assertEqual(totals['by_source']['workspace'], Decimal('18.90'))
        self.assertEqual(totals['by_source']['twilio'], Decimal('7.60'))
        # It must NOT have fallen into `other`, where it could not be told apart from a one-off.
        self.assertNotIn('other', totals['by_source'])


class TestTheChargeShowsItsWorking(_Base):
    """A charge is a set of lines with reasons, never a single unexplained number."""

    def test_development_hours_become_a_charge_at_the_rate_in_force(self):
        self._rates(hourly='150', margin='20')
        self._hours('10.0')
        c = platform_cost.charge_for(self.org, '2026-08')
        # 10h x RM150 = RM1500, +20% margin = RM1800.
        self.assertEqual(c['subtotal_myr'], Decimal('1800.00'))
        self.assertEqual(c['charged_myr'], Decimal('1800.00'))
        self.assertEqual([ln['category'] for ln in c['lines']], ['development'])

    def test_metered_and_infrastructure_are_refused_with_a_reason_not_zeroed(self):
        """The rule that stops an invented price reaching an invoice."""
        self._rates()
        self._hours('4.0')
        c = platform_cost.charge_for(self.org, '2026-08')
        blocked = {b['category']: b['reason'] for b in c['blocked']}
        self.assertIn('metered', blocked)
        self.assertIn('infrastructure', blocked)
        self.assertTrue(blocked['metered'])
        self.assertTrue(blocked['infrastructure'])
        # And neither appears as a RM0.00 line, which is what would get believed.
        self.assertNotIn('metered', [ln['category'] for ln in c['lines']])
        self.assertNotIn('infrastructure', [ln['category'] for ln in c['lines']])

    def test_hours_with_no_hourly_rate_block_the_line_rather_than_billing_nothing(self):
        """No rate set. The month must say it cannot be worked out."""
        self._hours('10.0')   # hours exist, rates do not
        c = platform_cost.charge_for(self.org, '2026-08')
        blocked = {b['category']: b['reason'] for b in c['blocked']}
        self.assertIn('development', blocked)
        self.assertEqual(c['lines'], [])
        self.assertEqual(c['subtotal_myr'], Decimal('0.00'))


class TestJulyIsShownInFullAndChargedNothing(_Base):
    """The owner's instruction, both halves of it."""

    def test_a_hundred_percent_discount_leaves_the_subtotal_visible(self):
        self._rates(on='2026-07-01')
        self._hours('10.0', month='2026-07')
        OrgBillingAdjustment.objects.create(
            organisation=self.org, period_month='2026-07', discount_pct=Decimal('100.00'),
            reason='Pre-launch goodwill period', set_by_email='super@x.com')

        c = platform_cost.charge_for(self.org, '2026-07')
        # SHOWN in full...
        self.assertEqual(c['subtotal_myr'], Decimal('1800.00'))
        # ...and charged nothing, with the discount as its own visible line.
        self.assertEqual(c['discount_pct'], Decimal('100.00'))
        self.assertEqual(c['discount_myr'], Decimal('1800.00'))
        self.assertEqual(c['charged_myr'], Decimal('0.00'))
        self.assertEqual(c['discount_reason'], 'Pre-launch goodwill period')

    def test_a_discount_belongs_to_one_month_and_does_not_roll_into_the_next(self):
        """The reason this is not an effective-dated rate: a waiver must not continue itself."""
        self._rates()
        self._hours('10.0', month='2026-07')
        self._hours('10.0', month='2026-08')
        OrgBillingAdjustment.objects.create(
            organisation=self.org, period_month='2026-07', discount_pct=Decimal('100.00'),
            reason='Pre-launch goodwill period')

        self.assertEqual(platform_cost.charge_for(self.org, '2026-07')['charged_myr'],
                         Decimal('0.00'))
        self.assertEqual(platform_cost.charge_for(self.org, '2026-08')['charged_myr'],
                         Decimal('1800.00'))


class TestFinishedRequestWorkIsFoundAndCountedOnce(_Base):
    """27.5 quoted hours sat on production and reached no invoice, because nothing joined
    `OrgRequest.quote_hours` to `OrgBuildHours`."""

    def _request(self, hours, status_='done', title='Add a report'):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.org_admin, kind='feature',
            title=title, description='x', status=status_,
            quote_hours=(Decimal(str(hours)) if hours is not None else None))

    def test_a_finished_quoted_request_is_reported_as_unbilled(self):
        r = self._request('7.5')
        rows = platform_cost.unbilled_request_hours()
        self.assertEqual([x['request_id'] for x in rows], [r.id])
        self.assertEqual(rows[0]['hours'], Decimal('7.5'))
        # The prefilled module carries the tag, so the human never has to type it.
        self.assertIn(platform_cost.request_module_tag(r.id), rows[0]['module'])

    def test_unfinished_and_unquoted_requests_are_not_billable(self):
        self._request('7.5', status_='approved')
        self._request(None, status_='done')
        self.assertEqual(platform_cost.unbilled_request_hours(), [])

    def test_once_its_hours_are_recorded_the_request_stops_being_outstanding(self):
        """The join. Without it the same work would be offered for billing every month."""
        r = self._request('7.5')
        self.assertEqual(len(platform_cost.unbilled_request_hours()), 1)
        self._hours('7.5', module=f'{platform_cost.request_module_tag(r.id)} Add a report')
        self.assertEqual(platform_cost.unbilled_request_hours(), [])


class TestTheCostsEndpoint(_Base):
    def test_super_reads_the_ledger_and_the_truthfulness_flags(self):
        self._cost('gcp', '23.92', provenance='measured', service='Cloud Run',
                   sku='Services CPU', attributable=True)
        self._cost('supabase', '105.00', period_note='Bills the 8th to the 7th')
        res = self._client('super-uid').get(f'{COSTS_URL}?month=2026-08')
        self.assertEqual(res.status_code, 200)
        costs = res.data['costs']
        self.assertEqual(costs['total_myr'], '128.92')
        self.assertEqual(costs['attributable_myr'], '23.92')
        # The flags the module computes must survive the serialisation, not die in it.
        self.assertEqual(costs['entered_sources'], ['supabase'])
        self.assertTrue(costs['is_complete'])
        self.assertEqual(costs['period_caveats'], ['Bills the 8th to the 7th'])

    def test_a_held_invoice_marks_the_total_a_floor_rather_than_being_dropped(self):
        self._cost('gcp', '23.92', provenance='measured')
        PlatformCost.objects.create(
            period_month='2026-08', source='twilio', service='sms', sku='',
            provenance='entered', currency='USD', amount_original=Decimal('1.77'),
            amount_myr=None, invoice_ref='TW-9')
        res = self._client('super-uid').get(f'{COSTS_URL}?month=2026-08')
        self.assertFalse(res.data['costs']['is_complete'])
        self.assertEqual(len(res.data['costs']['unconverted']), 1)
        self.assertEqual(res.data['costs']['unconverted'][0]['invoice_ref'], 'TW-9')

    def test_the_month_list_comes_from_the_ledger_not_from_a_range(self):
        """A month with no rows is a month nobody has entered — offering it would read as
        'we paid nothing', which is a different claim entirely."""
        self._cost('gcp', '10.00', month='2026-06')
        self._cost('gcp', '20.00', month='2026-08')
        res = self._client('super-uid').get(COSTS_URL + '?month=2026-08')
        self.assertEqual(res.data['months'], ['2026-08', '2026-06'])

    def test_the_charge_block_names_every_tenant_and_no_referral_partner(self):
        PartnerOrganisation.objects.create(code='sm', name='Sri Murugan Centre')
        self._rates()
        self._hours('10.0')
        res = self._client('super-uid').get(f'{COSTS_URL}?month=2026-08')
        names = [c['organisation'] for c in res.data['charges']]
        self.assertIn('BrightPath', names)
        # ⚠ The point of the test. This table is dual-role — ten rows on production and one
        # tenant — so `.filter(is_active=True)` would put a bill against nine schools and NGOs
        # that have never been customers. Sri Murugan Centre is one of those real rows.
        self.assertNotIn('Sri Murugan Centre', names)

    def test_org_admin_is_refused_with_403_not_404(self):
        """Same ruling as the rates screen: the contents are commercial, the route is not."""
        res = self._client('oa').get(COSTS_URL)
        self.assertEqual(res.status_code, 403)

    def test_a_bad_month_is_refused(self):
        res = self._client('super-uid').get(f'{COSTS_URL}?month=August')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['code'], 'bad_month')


class TestRecordingADiscount(_Base):
    def _post(self, uid='super-uid', **over):
        body = {'organisation_id': self.org.id, 'period_month': '2026-07',
                'discount_pct': '100', 'reason': 'Pre-launch goodwill period'}
        body.update(over)
        return self._client(uid).post(COSTS_URL, body, format='json')

    def test_a_super_records_a_discount_with_their_name_on_it(self):
        res = self._post()
        self.assertEqual(res.status_code, 201)
        row = OrgBillingAdjustment.objects.get()
        self.assertEqual(row.discount_pct, Decimal('100.00'))
        self.assertEqual(row.set_by_email, 'super@x.com')

    def test_a_discount_with_no_reason_is_refused(self):
        """The property that keeps a waiver distinguishable from a bug."""
        res = self._post(reason='   ')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['code'], 'reason_required')
        self.assertFalse(OrgBillingAdjustment.objects.exists())

    def test_a_discount_over_a_hundred_percent_is_refused(self):
        res = self._post(discount_pct='120')
        self.assertEqual(res.status_code, 400)

    def test_recording_twice_corrects_the_month_rather_than_stacking_two_answers(self):
        self._post()
        self._post(discount_pct='50', reason='Half waived after review')
        self.assertEqual(OrgBillingAdjustment.objects.count(), 1)
        self.assertEqual(OrgBillingAdjustment.objects.get().discount_pct, Decimal('50.00'))

    def test_org_admin_may_not_discount_their_own_bill(self):
        res = self._post(uid='oa')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(OrgBillingAdjustment.objects.exists())
