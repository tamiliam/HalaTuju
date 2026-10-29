"""The busy-meter guard: the meter ran, so where is the metered cost? (2026-10-29)

⚠ **WRITTEN FROM A REAL FAULT.** October 2026's invoice preview showed a metered charge of
RM0.00 for a month in which BrightPath ran OCR and Gemini every day. Nothing in `readiness`
objected, because every check it had asked whether the LEDGER was consistent with itself — and
an empty ledger is perfectly consistent. The cause was that `sync_gcp_costs` had never been run
for October.

⚠ **The first diagnosis was WRONG and these tests exist partly to stop it coming back.** I
concluded prepaid Gemini credit was hiding the cost from the BigQuery export. It was not: the
owner's GCP console and AI Studio both read RM34.95 for October, and the export covers prepay
and postpay alike. There is no prepay logic here and there must not be.

What the guard is held to:

1. A busy meter with no metered money REFUSES, and says how many calls it counted.
2. It is OVERRIDABLE — a free-tier month is real — but the monthly job overrides nothing.
3. It is this TENANT'S meter: another organisation's calls, platform work with no organisation,
   and another month's calls all leave this invoice alone.
4. It does not shout over `fx_missing`. A metered total of zero because the exchange rate has
   not arrived is a different fault, already reported, and must be reported once.
5. Only the METERED bucket counts as metered money. Infrastructure, tax and development rows
   are not an answer to "where is the metered cost?"
"""
from datetime import date
from decimal import Decimal

from apps.scholarship import invoicing, metered_usage, platform_cost
from apps.scholarship.models import PlatformCost, UsageEvent
from apps.scholarship.tests.test_invoicing import InvoiceWorld

AUG_14 = '2026-08-14T03:00:00Z'
SEPT_15 = date(2026, 9, 15)


class MeterWorld(InvoiceWorld):
    """August 2026 as `InvoiceWorld` leaves it — ready — plus a meter we can make busy.

    The seeded August has a metered GCP row of RM20, so the guard is silent until a test takes
    that money away. `_zero_the_metered_cost` sets it to RM0.00 rather than deleting the row, so
    that `supplier_missing` (gcp billed in July) stays quiet and the only thing under test is
    this guard.
    """

    def busy(self, *, org=None, month='2026-08', service='gemini', n=1):
        """`n` billable calls in `month`, attributed to `org` (None = platform work)."""
        when = f'{month}-14T03:00:00Z'
        for _ in range(n):
            ev = UsageEvent.objects.create(
                organisation=org if org is not None else None, service=service,
                source='doc_extract')
            UsageEvent.objects.filter(pk=ev.pk).update(created_at=when)

    @staticmethod
    def _zero_the_metered_cost(month='2026-08'):
        (PlatformCost.objects
         .filter(period_month=month, source='gcp')
         .update(amount_myr=Decimal('0.00')))

    def metered_problems(self, month='2026-08', today=SEPT_15):
        return [p for p in invoicing.readiness(self.org, month, today=today)
                if p['code'] == 'metered_without_cost']


class TestTheGuardFires(MeterWorld):

    def test_a_busy_meter_with_no_metered_money_stops_the_invoice(self):
        self.busy(org=self.org, n=3)
        self._zero_the_metered_cost()
        found = self.metered_problems()
        self.assertEqual(len(found), 1)
        self.assertIn('3 billable call(s)', found[0]['message'])
        self.assertIn('RM0.00', found[0]['message'])
        self.assertIn(self.org.name, found[0]['message'])
        self.assertIn('August 2026', found[0]['message'])

    def test_it_is_overridable_because_a_free_tier_month_is_real(self):
        self.busy(org=self.org)
        self._zero_the_metered_cost()
        self.assertTrue(self.metered_problems()[0]['overridable'])

    def test_a_ledger_with_no_rows_at_all_reports_both_faults(self):
        """The October shape exactly: the sync never ran, so there is nothing in the month.
        `no_costs` says the ledger is empty; this guard says the empty ledger is WRONG."""
        self.busy(org=self.org, n=12)
        PlatformCost.objects.filter(period_month='2026-08').delete()
        codes = [p['code'] for p in invoicing.readiness(self.org, '2026-08', today=SEPT_15)]
        self.assertIn('no_costs', codes)
        self.assertIn('metered_without_cost', codes)

    def test_a_metered_row_of_exactly_zero_is_not_an_answer(self):
        """A row that exists and says RM0.00 is the same silence as no row at all. The whole
        point is that a zero gets believed."""
        self.busy(org=self.org)
        self._zero_the_metered_cost()
        rows, myr, awaiting = metered_usage.metered_rows('2026-08')
        self.assertEqual((rows, myr, awaiting), (1, Decimal('0.00'), 0))
        self.assertIsNotNone(
            platform_cost.metered_activity_without_cost(self.org, '2026-08'))


class TestTheGuardStaysQuiet(MeterWorld):

    def test_a_quiet_meter_is_not_a_fault(self):
        """No calls means nothing to charge. A tenant that ran nothing pays nothing."""
        self._zero_the_metered_cost()
        self.assertEqual(self.metered_problems(), [])

    def test_a_busy_meter_with_metered_money_present_is_fine(self):
        self.busy(org=self.org, n=50)
        self.assertEqual(invoicing.readiness(self.org, '2026-08', today=SEPT_15), [])

    def test_another_organisations_calls_do_not_stop_this_invoice(self):
        from apps.courses.models import PartnerOrganisation

        other = PartnerOrganisation.objects.create(code='zz-other', name='Somebody Else')
        self.busy(org=other, n=9)
        self._zero_the_metered_cost()
        self.assertEqual(self.metered_problems(), [])

    def test_platform_work_with_no_organisation_does_not_stop_this_invoice(self):
        """Course-selector reports and ops mail belong to nobody. Charging a tenant for them is
        the mistake `tenant_shares` already refuses to make."""
        self.busy(org=None, n=40)
        self._zero_the_metered_cost()
        self.assertEqual(self.metered_problems(), [])

    def test_calls_in_another_month_do_not_stop_this_month(self):
        self.busy(org=self.org, month='2026-07', n=20)
        self._zero_the_metered_cost()
        self.assertEqual(self.metered_problems(), [])

    def test_a_month_awaiting_an_exchange_rate_reports_fx_missing_only(self):
        """⚠ ONE FAULT, ONE MESSAGE. A metered total of zero because the rate has not arrived is
        `fx_missing`'s business. Saying it twice sends somebody hunting a second fault."""
        self.busy(org=self.org, n=5)
        self._zero_the_metered_cost()
        self._cost('2026-08', 'anthropic', 'Gemini API', 'Generate_content tokens', None,
                   currency='USD', amount_original=Decimal('30.00'), attributable=True)
        codes = [p['code'] for p in invoicing.readiness(self.org, '2026-08', today=SEPT_15)]
        self.assertIn('fx_missing', codes)
        self.assertNotIn('metered_without_cost', codes)


class TestWhatCountsAsMeteredMoney(MeterWorld):

    def test_infrastructure_tax_and_development_rows_are_not_metered_money(self):
        """The seeded Supabase row is infrastructure. Money in the month is not the question;
        money in the METERED bucket is."""
        self.busy(org=self.org)
        self._zero_the_metered_cost()
        self._cost('2026-08', 'supabase', 'Supabase', 'Sales Tax', '6.00', attributable=False)
        self._cost('2026-08', 'anthropic', 'Anthropic', 'Claude Max plan', '400.00',
                   attributable=False)
        rows, myr, awaiting = metered_usage.metered_rows('2026-08')
        self.assertEqual((rows, myr, awaiting), (1, Decimal('0.00'), 0))
        self.assertEqual(len(self.metered_problems()), 1)

    def test_a_metered_row_from_any_supplier_answers_the_question(self):
        """Twilio and Brevo are metered too. The guard asks for metered MONEY, not for GCP."""
        self.busy(org=self.org, service='whatsapp', n=4)
        self._zero_the_metered_cost()
        self._cost('2026-08', 'twilio', 'Twilio', 'WhatsApp outbound messages', '3.40',
                   attributable=True)
        self.assertEqual(self.metered_problems(), [])


class TestIssuingPastTheGuard(MeterWorld):

    def test_the_monthly_job_never_issues_past_a_busy_meter(self):
        """⚠ THE PROTECTION THAT MATTERS. An unattended run is how an under-billed month would
        otherwise reach a customer."""
        self.busy(org=self.org, n=7)
        self._zero_the_metered_cost()
        with self.assertRaises(invoicing.InvoiceRefused) as cm:
            self.issue()
        self.assertIn('metered_without_cost', [p['code'] for p in cm.exception.problems])

    def test_a_super_may_issue_it_with_a_written_reason(self):
        self.busy(org=self.org, n=7)
        self._zero_the_metered_cost()
        inv = self.issue(override_reason='August fell inside the Gemini free tier; checked '
                                        'against the AI Studio page.')
        self.assertIsNotNone(inv.pk)
        # The invoice stores the super's reason AND the problem it was issued despite, in the
        # problem's own words. Those words are the audit trail, so they are what is asserted.
        self.assertIn('free tier', inv.override_reason)
        self.assertIn('Issued despite: The meter recorded 7 billable call(s)',
                      inv.override_reason)


class TestTheSplitKeptEveryName(MeterWorld):
    """`tenant_shares` and `reconcile` MOVED to `metered_usage.py` on 2026-10-29. A split is not
    a rename: every `platform_cost.<name>` caller and every `mock.patch.object` must still work.
    """

    def test_the_moved_names_are_still_reachable_through_platform_cost(self):
        for name in ('tenant_shares', 'reconcile', 'metered_activity_without_cost'):
            with self.subTest(name=name):
                self.assertIs(getattr(platform_cost, name), getattr(metered_usage, name))

    def test_tenant_shares_still_answers_through_the_old_name(self):
        self.busy(org=self.org, n=4)
        shares = platform_cost.tenant_shares('2026-08')
        self.assertEqual(shares[self.org.id]['metered'], Decimal('1'))

    def test_reconcile_still_answers_through_the_old_name(self):
        self.busy(org=self.org, n=4)
        self.busy(org=None, n=1)
        report = platform_cost.reconcile('2026-08')
        self.assertEqual(report['metered_events'], 5)
        self.assertEqual(report['metered_org_null'], 1)
        self.assertEqual(report['attributable_myr'], Decimal('20.00'))

    def test_an_unreadable_month_matches_nothing_rather_than_crashing(self):
        """⚠ A BUG THIS TEST FOUND, carried in from the old code. Both functions used to set
        `year = mon = 0` on a month they could not read, on the reasoning that year zero matches
        no row. Django's `__year` lookup builds `datetime(0, 1, 1)` to bound the query and raises
        `ValueError: year 0 is out of range`, so the month crashed rather than coming back empty.
        """
        self.busy(org=self.org, n=4)
        for bad in ('August', '', '2026', None):
            with self.subTest(bad=repr(bad)):
                self.assertIsNone(metered_usage._year_month(bad))
                self.assertEqual(platform_cost.reconcile(bad)['metered_events'], 0)
                self.assertEqual(platform_cost.reconcile(bad)['metered_org_null'], 0)
                self.assertIsNone(
                    platform_cost.metered_activity_without_cost(self.org, bad))
                self.assertEqual(platform_cost.tenant_shares(bad)[self.org.id]['metered'],
                                 Decimal('1'))
