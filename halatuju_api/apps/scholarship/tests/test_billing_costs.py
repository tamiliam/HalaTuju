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
        # ⚠ THE SEEDED ORGANISATION, not a new one. A data migration creates BrightPath Bursary
        # and it already qualifies as a tenant, so creating a second would give this test world
        # TWO tenants where production has exactly one — and every allocation figure below would
        # silently halve. Reusing it keeps the split at 100%, which is the real situation the
        # charge arithmetic has to be right about today.
        cls.org = PartnerOrganisation.objects.get(code='brightpath')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
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


class TestClaudeIsRecoveredByTheHourlyRateAndNotTwice(_Base):
    """Owner, 2026-09-11: *"My biggest cost is Claude, which needs to be included via the request
    hours."* That sentence decides where the cost belongs, and it is neither of the other two
    buckets.

    ⚠ The mistake this class exists to prevent is the expensive one: leaving Claude in the
    PLATFORM bucket would mark it up as infrastructure AND leave the hourly rate recovering it as
    well — the same ringgit taken twice, on an invoice, quietly.
    """

    def _claude(self, amount, month='2026-08'):
        return self._cost('anthropic', amount, month=month,
                          service='Anthropic', sku='Claude Max subscription',
                          provenance='extracted')

    def test_a_claude_cost_is_a_development_cost_not_a_platform_one(self):
        self.assertEqual(
            platform_cost.cost_bucket('Anthropic', 'Claude Max subscription'), 'development')
        # And the ordinary buckets are unmoved by the new one.
        self.assertEqual(platform_cost.cost_bucket('Cloud Run', 'Jobs CPU'), 'platform')
        self.assertEqual(
            platform_cost.cost_bucket('Cloud Vision API', 'Document Text Detection Operations'),
            'metered')
        self.assertEqual(platform_cost.cost_bucket('Invoice', 'Tax'), 'tax')

    def test_it_is_counted_in_the_month_total_but_kept_out_of_the_platform_slice(self):
        """It is a real cost, so the total must include it. It is not a platform cost, so the
        figure that gets marked up as infrastructure must not."""
        self._cost('gcp', '100.00', service='Cloud Run', sku='Jobs CPU')
        self._claude('400.00')
        totals = platform_cost.month_totals('2026-08')
        self.assertEqual(totals['total_myr'], Decimal('500.00'))
        self.assertEqual(totals['platform_myr'], Decimal('100.00'))
        self.assertEqual(totals['development_myr'], Decimal('400.00'))

    def test_the_infrastructure_charge_does_not_include_it(self):
        """⚠ THE DOUBLE-CHARGE TEST. If Claude ever leaks into the platform bucket this figure
        moves, and the tenant is billed for it twice."""
        BillingRate.objects.create(category='infrastructure', kind='margin_pct',
                                   value=Decimal('15'), effective_from=date(2026, 7, 1))
        self._cost('gcp', '100.00', service='Cloud Run', sku='Jobs CPU')
        self._claude('400.00')
        c = platform_cost.charge_for(self.org, '2026-08')
        infra = next(ln for ln in c['lines'] if ln['category'] == 'infrastructure')
        self.assertEqual(infra['cost_myr'], Decimal('100.00'))
        self.assertEqual(infra['amount_myr'], Decimal('115.00'))

    def test_the_development_line_shows_what_the_tools_cost_beside_what_we_charge(self):
        """The reason it is a development cost rather than a platform one: it turns
        'is RM50/hour enough?' into a figure on a screen."""
        self._rates(hourly='50', margin='15')
        self._claude('400.00')
        self._hours('10.0')
        c = platform_cost.charge_for(self.org, '2026-08')
        dev = next(ln for ln in c['lines'] if ln['category'] == 'development')
        self.assertEqual(dev['tool_cost_myr'], Decimal('400.00'))
        # 10h x RM50 = RM500, +15% = RM575. The tool cost is SHOWN, never added.
        self.assertEqual(dev['amount_myr'], Decimal('575.00'))
        self.assertEqual(c['subtotal_myr'], Decimal('575.00'))

    def test_tools_bought_in_a_month_with_no_billable_hours_are_reported_not_hidden(self):
        """Silence would read as 'nothing was spent'. A real cost was carried and recovered by
        nothing, and that is worth somebody seeing."""
        self._rates(hourly='50', margin='15')
        self._claude('400.00')
        c = platform_cost.charge_for(self.org, '2026-08')
        blocked = {b['category']: b['reason'] for b in c['blocked']}
        self.assertIn('development', blocked)
        self.assertIn('400.00', blocked['development'])


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

    def test_a_category_with_no_margin_set_is_refused_with_a_reason_not_zeroed(self):
        """The rule that stops an unpriced line reaching an invoice as RM0.00.

        Only the development margin is set here, so the two cost lines must REFUSE — and say so.
        """
        self._rates()                       # development only
        self._cost('gcp', '100.00')
        self._hours('4.0')
        c = platform_cost.charge_for(self.org, '2026-08')
        blocked = {b['category']: b['reason'] for b in c['blocked']}
        self.assertIn('metered', blocked)
        self.assertIn('infrastructure', blocked)
        # And neither appears as a RM0.00 line, which is what would get believed.
        self.assertNotIn('metered', [ln['category'] for ln in c['lines']])
        self.assertNotIn('infrastructure', [ln['category'] for ln in c['lines']])


class TestTheCostsWePaidAreChargedOnWithTheirMargin(_Base):
    """Owner ruling 2026-09-11: *"For everything apply the markup/margin as determined by the
    rate that is set."* The two cost lines are grounded in the real invoices, not in a
    unit-price table nobody has written."""

    def _margin(self, category, pct, on='2026-07-01'):
        BillingRate.objects.create(
            category=category, kind='margin_pct', value=Decimal(str(pct)),
            effective_from=date.fromisoformat(on))

    def test_the_platform_driven_slice_is_charged_at_the_infrastructure_margin(self):
        self._margin('infrastructure', '15')
        # RM100 of our own cron/CI cost, no tenant-driven cost, no tax.
        self._cost('gcp', '100.00', service='Cloud Run', sku='Jobs CPU')
        c = platform_cost.charge_for(self.org, '2026-08')
        line = next(ln for ln in c['lines'] if ln['category'] == 'infrastructure')
        self.assertEqual(line['cost_myr'], Decimal('100.00'))     # what we paid
        self.assertEqual(line['amount_myr'], Decimal('115.00'))   # +15%
        self.assertEqual(c['charged_myr'], Decimal('115.00'))

    def test_the_tenant_driven_slice_is_charged_at_the_metered_margin(self):
        self._margin('metered', '30')
        self._cost('gcp', '50.00', service='Cloud Vision API',
                   sku='Document Text Detection Operations', attributable=True)
        c = platform_cost.charge_for(self.org, '2026-08')
        line = next(ln for ln in c['lines'] if ln['category'] == 'metered')
        self.assertEqual(line['cost_myr'], Decimal('50.00'))
        self.assertEqual(line['amount_myr'], Decimal('65.00'))

    def test_tax_is_shared_between_the_two_lines_so_nothing_is_billed_below_cost(self):
        """⚠ Tax belongs to neither bucket on its own. Dropping it would quietly bill under
        what the providers actually charged us."""
        self._margin('infrastructure', '0')
        self._margin('metered', '0')
        self._cost('gcp', '75.00', service='Cloud Run', sku='Jobs CPU')
        self._cost('gcp', '25.00', service='Cloud Vision API',
                   sku='Document Text Detection Operations', attributable=True)
        self._cost('gcp', '8.00', service='Invoice', sku='Tax')

        c = platform_cost.charge_for(self.org, '2026-08')
        by = {ln['category']: ln for ln in c['lines']}
        # 75/100 of the tax to infrastructure, 25/100 to metered.
        self.assertEqual(by['infrastructure']['cost_myr'], Decimal('81.00'))
        self.assertEqual(by['metered']['cost_myr'], Decimal('27.00'))
        # At a zero margin the charge is exactly the whole bill back — nothing lost, nothing
        # invented.
        self.assertEqual(c['charged_myr'], Decimal('108.00'))

    def test_a_month_of_pure_tax_does_not_invent_a_bucket_to_put_it_in(self):
        self._margin('infrastructure', '10')
        self._margin('metered', '10')
        self._cost('gcp', '5.00', service='Invoice', sku='Tax')
        c = platform_cost.charge_for(self.org, '2026-08')
        self.assertEqual(c['subtotal_myr'], Decimal('0.00'))

    def test_the_single_tenant_carries_the_whole_platform_cost_and_says_which_rule(self):
        """⚠ There is ONE tenant, so the split is 100% and has never been exercised. The rule is
        stated in the payload so a second tenant makes it a decision somebody reviews."""
        self._margin('infrastructure', '0')
        self._cost('gcp', '40.00', service='Cloud Run', sku='Jobs CPU')
        c = platform_cost.charge_for(self.org, '2026-08')
        line = next(ln for ln in c['lines'] if ln['category'] == 'infrastructure')
        self.assertEqual(line['share_pct'], Decimal('100.00'))
        self.assertTrue(line['share_rule'])

    def test_all_three_lines_add_up_and_then_discount(self):
        """The whole bill end to end, and the July rule on top of it."""
        self._margin('infrastructure', '15')
        self._margin('metered', '15')
        self._rates(hourly='150', margin='20')
        self._cost('gcp', '100.00', service='Cloud Run', sku='Jobs CPU')
        self._cost('gcp', '20.00', service='Cloud Vision API',
                   sku='Document Text Detection Operations', attributable=True)
        self._hours('10.0')

        c = platform_cost.charge_for(self.org, '2026-08')
        self.assertEqual(
            sorted(ln['category'] for ln in c['lines']),
            ['development', 'infrastructure', 'metered'])
        # 115.00 + 23.00 + 1800.00
        self.assertEqual(c['subtotal_myr'], Decimal('1938.00'))
        self.assertEqual(c['blocked'], [])

    def test_a_rate_set_later_does_not_re_price_an_earlier_month(self):
        """The effective-dating, proved through the cost line rather than only the hourly rate."""
        self._margin('infrastructure', '10', on='2026-07-01')
        self._margin('infrastructure', '50', on='2026-09-01')
        self._cost('gcp', '100.00', month='2026-08', service='Cloud Run', sku='Jobs CPU')
        c = platform_cost.charge_for(self.org, '2026-08')
        self.assertEqual(c['charged_myr'], Decimal('110.00'))

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
        self.assertIn(self.org.name, names)
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
