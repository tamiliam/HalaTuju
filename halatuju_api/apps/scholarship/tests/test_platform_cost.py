"""Platform cost ledger — classification, idempotency, reconciliation.

The one real judgement in this feature is `classify_sku`: which invoice lines move with
TENANT activity and which are ours. Get it wrong toward "tenant" and an organisation is
over-charged for our cron schedule; get it wrong toward "platform" and we absorb a cost we
could fairly pass on. The first is a refund and an apology, the second is a pricing
conversation — so the rule defaults to platform, and these tests pin that direction.

The June 2026 invoice is used as the fixture throughout: it is the only real data we have,
and every figure in it was measured from the BigQuery billing export.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerOrganisation
from apps.scholarship import platform_cost
from apps.scholarship.models import PlatformCost, UsageEvent

# The real June 2026 bill, SKU by SKU. (service, sku, MYR, expected_attributable)
JUNE = [
    ('Cloud Run',        'Jobs CPU in asia-southeast1',                  29.81, False),
    ('Artifact Registry', 'Artifact Registry Storage',                   26.95, False),
    ('Cloud Run',        'Services CPU Tier 2 (Request-based billing)',   8.38, True),
    ('Cloud Vision API', 'Document Text Detection Operations',            5.89, True),
    ('Cloud Scheduler',  'Jobs',                                          3.37, False),
    ('Cloud Run',        'Jobs Memory in asia-southeast1',                3.31, False),
    ('Cloud Run',        'Cloud Run Network Internet Data Transfer Out',  3.29, True),
    ('Gemini API',       'Generate content output token count gemini 2',  1.12, True),
    ('Cloud Run',        'Services Memory Tier 2 (Request-based billin',  0.87, True),
    ('Cloud Storage',    'Standard Storage Singapore',                    0.10, True),
    ('Cloud Build',      'Cloud Build: Network Data Transfer Out Inter',  0.05, False),
]


class TestClassification(TestCase):
    def test_every_june_sku_classifies_as_measured(self):
        """The whole June bill, line by line. This is the regression guard: a future tweak to
        the markers that flips any of these has changed what a tenant is charged for."""
        for service, sku, _amt, expected in JUNE:
            with self.subTest(sku=sku):
                self.assertEqual(platform_cost.classify_sku(service, sku), expected)

    def test_cloud_run_is_split_by_sku_not_by_service(self):
        """The trap that hid the biggest line for a month. 'Cloud Run' contains BOTH the
        request-serving a tenant drives and the Jobs compute our crons drive. Classifying on
        the service name would sweep them together."""
        self.assertTrue(platform_cost.classify_sku('Cloud Run', 'Services CPU Tier 2'))
        self.assertFalse(platform_cost.classify_sku('Cloud Run', 'Jobs CPU in asia-southeast1'))

    def test_an_unrecognised_sku_defaults_to_platform(self):
        """Conservative by design: a new Google SKU must not silently start billing tenants."""
        self.assertFalse(platform_cost.classify_sku('Some New Service', 'Some New SKU'))

    def test_tax_is_neither_side(self):
        self.assertTrue(platform_cost.is_tax('Invoice', 'Tax'))
        self.assertFalse(platform_cost.is_tax('Cloud Run', 'Services CPU Tier 2'))

    def test_the_june_split_reproduces_the_investigation(self):
        """~23% tenant-driven / ~72% platform — the finding the whole pricing approach rests
        on. If this drifts, the 'infrastructure is the cost' conclusion needs re-stating."""
        attributable = sum(a for _s, _k, a, exp in JUNE if exp)
        total = sum(a for _s, _k, a, _e in JUNE)
        self.assertAlmostEqual(attributable, 19.65, places=1)
        self.assertLess(attributable / total, 0.30)


class TestLedger(TestCase):
    def _line(self, sku, amount, attributable=False, month='2026-06', **kw):
        return PlatformCost.objects.create(
            period_month=month, source=kw.pop('source', 'gcp'),
            service=kw.pop('service', 'Cloud Run'), sku=sku,
            amount_myr=Decimal(str(amount)), attributable=attributable,
            provenance=kw.pop('provenance', 'measured'), note=kw.pop('note', ''))

    def test_a_month_upserts_rather_than_doubling(self):
        """A month is not final until Google closes it, so the sync MUST be re-runnable.
        Same key, second write → one row with the corrected amount."""
        self._line('Jobs CPU', 29.81)
        PlatformCost.objects.update_or_create(
            period_month='2026-06', source='gcp', service='Cloud Run', sku='Jobs CPU',
            defaults={'amount_myr': Decimal('31.00'), 'attributable': False,
                      'provenance': 'measured'})
        self.assertEqual(PlatformCost.objects.count(), 1)
        self.assertEqual(PlatformCost.objects.get().amount_myr, Decimal('31.00'))

    def test_totals_split_tenant_platform_and_tax(self):
        self._line('Services CPU Tier 2', 8.38, attributable=True)
        self._line('Jobs CPU', 29.81)
        self._line('Tax', 5.04, service='Invoice')
        t = platform_cost.month_totals('2026-06')
        self.assertEqual(t['total_myr'], Decimal('43.23'))
        self.assertEqual(t['attributable_myr'], Decimal('8.38'))
        self.assertEqual(t['platform_myr'], Decimal('29.81'))
        self.assertEqual(t['tax_myr'], Decimal('5.04'))

    def test_totals_reconcile_to_the_sum_of_lines(self):
        """A count the owner asked for is not the same as a count that ADDS UP (lessons.md).
        The three buckets must exhaust the total — no line may fall between them."""
        for _s, sku, amt, attr in JUNE:
            self._line(sku, amt, attributable=attr)
        self._line('Tax', 5.04, service='Invoice')
        t = platform_cost.month_totals('2026-06')
        self.assertEqual(
            t['attributable_myr'] + t['platform_myr'] + t['tax_myr'], t['total_myr'])

    def test_hand_entered_sources_are_surfaced_not_hidden(self):
        """Supabase has no billing API, so its figures are typed from a PDF. A total that
        mixes measured and entered figures without saying so is not an audit."""
        self._line('Services CPU Tier 2', 8.38, attributable=True)
        self._line('Pro plan', 118.00, source='supabase', service='Pro plan',
                   provenance='entered')
        t = platform_cost.month_totals('2026-06')
        self.assertEqual(t['entered_sources'], ['supabase'])

    def test_months_do_not_bleed_into_each_other(self):
        self._line('Jobs CPU', 29.81, month='2026-06')
        self._line('Jobs CPU', 1.00, month='2026-07')
        self.assertEqual(platform_cost.month_totals('2026-07')['total_myr'], Decimal('1.00'))


class TestForeignCurrencyInvoice(TestCase):
    """Supabase invoices in USD ($25.00, refs TPTHYS-0000N). The ledger must hold that
    honestly rather than convert it at a rate somebody half-remembered."""

    def _supabase(self, **kw):
        return PlatformCost.objects.create(
            period_month=kw.pop('month', '2026-06'), source='supabase',
            service='Pro plan', sku='', currency=kw.pop('currency', 'USD'),
            amount_original=kw.pop('amount_original', Decimal('25.00')),
            fx_rate=kw.pop('fx_rate', None), amount_myr=kw.pop('amount_myr', None),
            attributable=False, provenance='entered',
            invoice_ref=kw.pop('invoice_ref', 'TPTHYS-00007'),
            period_note=kw.pop('period_note', ''), note=kw.pop('note', ''))

    def test_an_invoice_with_no_rate_is_HELD_not_guessed(self):
        """The core of the design. No rate → no ringgit figure → the month says so."""
        self._supabase()
        t = platform_cost.month_totals('2026-06')
        self.assertFalse(t['is_complete'])
        self.assertEqual(len(t['unconverted']), 1)
        self.assertEqual(t['unconverted'][0]['invoice_ref'], 'TPTHYS-00007')
        self.assertEqual(t['unconverted'][0]['currency'], 'USD')
        self.assertEqual(t['unconverted'][0]['amount_original'], Decimal('25.00'))

    def test_a_held_invoice_never_silently_vanishes_from_a_total(self):
        """It is excluded from the arithmetic (we cannot add USD to MYR) but COUNTED in
        `lines` and named in `unconverted`. A quietly-omitted RM100 line is the failure mode
        this guards: the total must announce that it is a floor."""
        PlatformCost.objects.create(
            period_month='2026-06', source='gcp', service='Cloud Run', sku='Jobs CPU',
            amount_myr=Decimal('29.81'), attributable=False, provenance='measured')
        self._supabase()
        t = platform_cost.month_totals('2026-06')
        self.assertEqual(t['lines'], 2)                    # both rows are visible
        self.assertEqual(t['total_myr'], Decimal('29.81'))  # only the convertible one sums
        self.assertFalse(t['is_complete'])                  # and the total admits it

    def test_a_converted_invoice_completes_the_month_and_keeps_the_audit_trail(self):
        self._supabase(fx_rate=Decimal('4.7200'), amount_myr=Decimal('118.00'))
        t = platform_cost.month_totals('2026-06')
        self.assertTrue(t['is_complete'])
        self.assertEqual(t['total_myr'], Decimal('118.00'))
        row = PlatformCost.objects.get(source='supabase')
        # All three survive, so the conversion can be re-checked rather than trusted.
        self.assertEqual(row.amount_original, Decimal('25.00'))
        self.assertEqual(row.fx_rate, Decimal('4.7200'))
        self.assertEqual(row.currency, 'USD')

    def test_a_mismatched_billing_period_is_surfaced_as_a_caveat(self):
        """Supabase invoices on the 8th; the GCP lines are calendar-month. A reconciliation
        that mixes those windows without saying so is a wrong number wearing a right one's
        clothes."""
        self._supabase(period_note='Supabase cycle 08 Jun - 08 Jul 2026')
        t = platform_cost.month_totals('2026-06')
        self.assertEqual(t['period_caveats'], ['Supabase cycle 08 Jun - 08 Jul 2026'])

    def test_a_month_with_only_measured_myr_rows_is_complete_and_uncaveated(self):
        """The guard must not cry wolf on the ordinary case."""
        PlatformCost.objects.create(
            period_month='2026-06', source='gcp', service='Cloud Run', sku='Jobs CPU',
            amount_myr=Decimal('29.81'), attributable=False, provenance='measured')
        t = platform_cost.month_totals('2026-06')
        self.assertTrue(t['is_complete'])
        self.assertEqual(t['unconverted'], [])
        self.assertEqual(t['period_caveats'], [])


class TestReconciliation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='aa', name='Alpha Org')

    def test_reconciliation_reports_the_meters_blind_spot(self):
        """Unattributed events are the figure that says a tenant is being under-charged.
        It belongs on the reconciliation, in the open."""
        now = timezone.now()
        month = now.strftime('%Y-%m')
        PlatformCost.objects.create(
            period_month=month, source='gcp', service='Cloud Vision API',
            sku='Document Text Detection Operations', amount_myr=Decimal('5.89'),
            attributable=True, provenance='measured')
        UsageEvent.objects.create(organisation=self.org, service='vision_ocr')
        UsageEvent.objects.create(organisation=None, service='email')

        r = platform_cost.reconcile(month)
        self.assertEqual(r['metered_events'], 2)
        self.assertEqual(r['metered_org_null'], 1)
        self.assertEqual(r['metered_org_null_pct'], 50.0)
        self.assertEqual(r['attributable_myr'], Decimal('5.89'))

    def test_reconcile_on_an_empty_month_does_not_divide_by_zero(self):
        r = platform_cost.reconcile('2020-01')
        self.assertEqual(r['lines'], 0)
        self.assertEqual(r['metered_org_null_pct'], 0.0)

    def test_v1_publishes_no_implied_unit_price(self):
        """Sprint 13a decided NO prices in v1. A unit price invented on a reconciliation
        screen becomes the number people quote, so the payload must not carry one."""
        r = platform_cost.reconcile('2026-06')
        for key in r:
            self.assertNotIn('price', key, f'{key} looks like a price — v1 carries none')
            self.assertNotIn('rate', key, f'{key} looks like a rate — v1 carries none')
