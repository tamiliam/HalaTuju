"""Tenant invoices and receipts — the service layer (2026-09-14).

What these tests hold the module to, in the owner's terms:

1. **Issued on the 15th for the PREVIOUS month**, computed in Malaysian time — pinned clocks, and
   every month of the year enumerated rather than sampled.
2. **A bill never changes after it is issued.** A rate edited afterwards moves the live charge and
   leaves the invoice alone; a wrong invoice is voided, never edited.
3. **Refuse, never guess.** A supplier bill not yet imported, a missing exchange rate, unrecorded
   request hours, blank billing details — each stops the invoice and says why.
4. **The tenant copy carries no cost and no margin**, and every line multiplies out.
5. **A receipt records money that moved**: a bank reference, never more than is owed.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import invoice_pdf, invoicing, platform_cost
from apps.scholarship.models import (
    BillingRate, BillingSequence, Invoice, InvoiceIssuer, InvoiceLine, OrgBillingAdjustment,
    OrgBillingDetails, OrgBuildHours, PlatformCost,
)
from apps.scholarship.tests import factories

SEPT_15 = date(2026, 9, 15)


class InvoiceWorld(TestCase):
    """A month that is READY: August 2026, looked at on 15 September 2026.

    ⚠ The SEEDED BrightPath organisation, never a new one — a second tenant would halve every
    share and hide arithmetic mistakes behind a 50% split.

    August costs: GCP request-serving RM20 (metered) + Supabase Pro plan RM100 (infrastructure),
    both suppliers also present in July. Margins 15%, RM50/hour. Hours: 10.0 + 2.5.
      metered        20.00 x 1.15 =  23.00
      infrastructure 100.00 x 1.15 = 115.00
      development    57.50 x 10.0 = 575.00 ; 57.50 x 2.5 = 143.75
      subtotal                        856.75
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.get(code='brightpath')
        InvoiceIssuer.objects.create(
            legal_name='HalaTuju Platform', address='1 Jalan Contoh\n50000 Kuala Lumpur',
            email='billing@halatuju.xyz', bank_name='Maybank',
            bank_account_name='HalaTuju Platform', bank_account_no='5140 1234 5678')
        OrgBillingDetails.objects.create(
            organisation=cls.org, bill_to_name='BrightPath Bursary Berhad',
            address='2 Jalan Tenant\nPetaling Jaya', emails=['finance@brightpath.example'])
        for month in ('2026-07', '2026-08'):
            cls._cost(month, 'gcp', 'Cloud Run', 'Services CPU', '20.00', attributable=True)
            cls._cost(month, 'supabase', 'Supabase', 'Pro Plan', '100.00', attributable=False)
        for category in ('infrastructure', 'metered', 'development'):
            BillingRate.objects.create(category=category, kind='margin_pct', value=Decimal('15'),
                                       effective_from=date(2026, 7, 1))
        BillingRate.objects.create(category='development', kind='hourly_rate',
                                   value=Decimal('50'), effective_from=date(2026, 7, 1))
        OrgBuildHours.objects.create(organisation=cls.org, period_month='2026-08',
                                     module='Payments module', hours=Decimal('10.0'),
                                     basis='5 working days at 2h')
        OrgBuildHours.objects.create(organisation=cls.org, period_month='2026-08',
                                     module='Monthly report', hours=Decimal('2.5'),
                                     basis='one afternoon')

    @staticmethod
    def _cost(month, source, service, sku, amount, **kw):
        kw.setdefault('provenance', 'extracted')
        return PlatformCost.objects.create(
            period_month=month, source=source, service=service, sku=sku,
            amount_myr=None if amount is None else Decimal(amount), **kw)

    def issue(self, month='2026-08', today=SEPT_15, **kw):
        return invoicing.issue_invoice(self.org, month, today=today, **kw)

    def codes(self, month='2026-08', today=SEPT_15, org=None):
        return [p['code'] for p in invoicing.readiness(org or self.org, month, today=today)]


# ── Months and the clock ─────────────────────────────────────────────────────

class TestTheMonthBilled(TestCase):

    def test_every_month_of_the_year_bills_the_one_before_it(self):
        """ENUMERATED, not sampled (the September-blackout lesson): January must reach back into
        the previous YEAR, and nothing else may."""
        expected = {1: '2025-12', 2: '2026-01', 3: '2026-02', 4: '2026-03', 5: '2026-04',
                    6: '2026-05', 7: '2026-06', 8: '2026-07', 9: '2026-08', 10: '2026-09',
                    11: '2026-10', 12: '2026-11'}
        for mon, month in expected.items():
            with self.subTest(mon=mon):
                self.assertEqual(invoicing.previous_month(date(2026, mon, 15)), month)

    def test_the_15th_in_malaysia_is_still_the_14th_in_utc_and_the_malaysian_date_wins(self):
        """⚠ A PINNED CLOCK, never `localdate()` compared with itself (TD-209). 16:30 UTC on 14
        October is 00:30 on 15 October in Kuala Lumpur — the scheduler's day. Reading the UTC date
        would say it is before the cut-off and refuse the whole run."""
        instant = datetime(2026, 10, 14, 16, 30, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=instant):
            self.assertEqual(invoicing._today(), date(2026, 10, 15))
            self.assertEqual(invoicing.previous_month(), '2026-09')

    def test_a_month_that_is_not_a_calendar_month_is_rejected(self):
        for bad in ('2026-00', '2026-13', '2026-8', 'August', ''):
            with self.subTest(bad=bad):
                self.assertIsNone(invoicing.MONTH_RE.match(bad))
        self.assertIsNotNone(invoicing.MONTH_RE.match('2026-12'))

    def test_shift_month_crosses_years_both_ways(self):
        self.assertEqual(invoicing.shift_month('2026-01', -1), '2025-12')
        self.assertEqual(invoicing.shift_month('2026-12', 1), '2027-01')
        self.assertEqual(invoicing.month_label('2026-02'), 'February 2026')


# ── Numbering ────────────────────────────────────────────────────────────────

class TestNumbering(TestCase):

    def test_numbers_are_sequential_per_kind_and_restart_each_year(self):
        with transaction.atomic():
            self.assertEqual(invoicing.next_number('INV', 2026), 'INV-2026-0001')
            self.assertEqual(invoicing.next_number('INV', 2026), 'INV-2026-0002')
            self.assertEqual(invoicing.next_number('RCP', 2026), 'RCP-2026-0001')
            self.assertEqual(invoicing.next_number('INV', 2027), 'INV-2027-0001')

    def test_a_rolled_back_issue_does_not_burn_a_number(self):
        """Gap-free is the point. A failed attempt must hand its number to the next one."""
        try:
            with transaction.atomic():
                invoicing.next_number('INV', 2026)
                raise RuntimeError('the issue failed after drawing a number')
        except RuntimeError:
            pass
        with transaction.atomic():
            self.assertEqual(invoicing.next_number('INV', 2026), 'INV-2026-0001')

    def test_a_number_cannot_be_drawn_outside_a_transaction(self):
        """Outside a transaction the lock protects nothing and a rollback cannot return it."""
        with mock.patch.object(transaction, 'get_connection') as conn:
            conn.return_value.in_atomic_block = False
            with self.assertRaises(invoicing.InvoicingError) as cm:
                invoicing.next_number('INV', 2026)
        self.assertEqual(cm.exception.code, 'numbering_outside_transaction')


# ── Readiness ────────────────────────────────────────────────────────────────

class TestReadiness(InvoiceWorld):

    def test_a_complete_month_on_the_15th_is_ready(self):
        self.assertEqual(invoicing.readiness(self.org, '2026-08', today=SEPT_15), [])

    def test_the_month_still_running_can_never_be_issued(self):
        problems = invoicing.readiness(self.org, '2026-09', today=SEPT_15)
        closed = [p for p in problems if p['code'] == 'month_not_closed']
        self.assertEqual(len(closed), 1)
        self.assertFalse(closed[0]['overridable'])

    def test_before_the_15th_is_a_warning_a_super_may_override_and_the_15th_is_not(self):
        problems = invoicing.readiness(self.org, '2026-08', today=date(2026, 9, 14))
        self.assertEqual([p['code'] for p in problems], ['before_cutoff'])
        self.assertTrue(problems[0]['overridable'])
        self.assertEqual(self.codes(today=date(2026, 9, 15)), [])

    def test_an_older_month_is_past_its_cutoff_whatever_the_day(self):
        self.assertNotIn('before_cutoff', self.codes(today=date(2026, 10, 3)))

    def test_a_supplier_that_billed_last_month_but_not_this_one_stops_the_invoice(self):
        """THE REAL FAILURE: on 15 October, Supabase's September PDF simply not imported yet.
        Without this check the invoice is smaller, confident and wrong."""
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        problems = invoicing.readiness(self.org, '2026-08', today=SEPT_15)
        missing = [p for p in problems if p['code'] == 'supplier_missing']
        self.assertEqual(len(missing), 1)
        self.assertIn('supabase', missing[0]['message'])
        self.assertTrue(missing[0]['overridable'])

    def test_a_new_supplier_this_month_is_not_a_problem(self):
        self._cost('2026-08', 'twilio', 'Twilio', 'Phone Numbers', '7.13')
        self.assertEqual(self.codes(), [])

    def test_a_month_with_no_costs_at_all_is_not_ready(self):
        PlatformCost.objects.filter(period_month='2026-08').delete()
        self.assertIn('no_costs', self.codes())

    def test_a_cost_with_no_ringgit_value_stops_the_invoice(self):
        self._cost('2026-08', 'anthropic', 'Anthropic', 'Claude Max', None,
                   currency='USD', amount_original=Decimal('100.00'))
        self.assertIn('fx_missing', self.codes())

    def test_a_missing_margin_stops_the_invoice_rather_than_dropping_the_line(self):
        BillingRate.objects.filter(category='infrastructure').delete()
        self.assertIn('charge_blocked', self.codes())

    def test_finished_request_hours_not_yet_recorded_stop_the_invoice(self):
        row = {'request_id': 12, 'organisation_id': self.org.id, 'hours': Decimal('4.0'),
               'worked_month': '2026-08'}
        other_month = {**row, 'request_id': 13, 'worked_month': '2026-09'}
        with mock.patch.object(platform_cost, 'unbilled_request_hours',
                               return_value=[row, other_month]):
            problems = invoicing.readiness(self.org, '2026-08', today=SEPT_15)
        unbilled = [p for p in problems if p['code'] == 'unbilled_hours']
        self.assertEqual(len(unbilled), 1)
        # Only the request worked IN August counts against August.
        self.assertIn('1 finished request', unbilled[0]['message'])

    def test_blank_issuer_details_block_and_name_the_missing_fields(self):
        InvoiceIssuer.objects.update(bank_account_no='', address='')
        problems = invoicing.readiness(self.org, '2026-08', today=SEPT_15)
        issuer = [p for p in problems if p['code'] == 'issuer_incomplete'][0]
        self.assertFalse(issuer['overridable'])
        self.assertIn('address', issuer['message'])
        self.assertIn('bank_account_no', issuer['message'])

    def test_no_issuer_row_at_all_blocks(self):
        """The production state on the day this ships: nobody has entered a legal entity."""
        InvoiceIssuer.objects.all().delete()
        self.assertIn('issuer_incomplete', self.codes())

    def test_blank_bill_to_details_block(self):
        OrgBillingDetails.objects.update(emails=[])
        self.assertIn('bill_to_incomplete', self.codes())

    def test_a_referral_organisation_is_never_invoiced(self):
        school = PartnerOrganisation.objects.create(code='a-school', name='A School')
        self.assertEqual(self.codes(org=school), ['not_a_tenant'])


# ── Issuing ──────────────────────────────────────────────────────────────────

class TestIssue(InvoiceWorld):

    def test_a_ready_month_issues_a_numbered_invoice_whose_lines_reach_the_total(self):
        inv = self.issue()
        self.assertEqual(inv.number, 'INV-2026-0001')
        self.assertEqual(inv.period_month, '2026-08')
        self.assertEqual(inv.issued_on, SEPT_15)
        self.assertEqual(inv.due_on, date(2026, 10, 15))   # 30 days
        self.assertEqual(inv.subtotal_myr, Decimal('856.75'))
        self.assertEqual(inv.total_myr, Decimal('856.75'))
        amounts = [ln.amount_myr for ln in inv.lines.all()]
        self.assertEqual(amounts, [Decimal('115.00'), Decimal('23.00'),
                                   Decimal('575.00'), Decimal('143.75')])
        self.assertEqual(sum(amounts), inv.subtotal_myr)
        self.assertEqual(inv.status, 'issued')

    def test_every_development_line_multiplies_out(self):
        """A tenant checks hours x rate = amount with a calculator. It must agree."""
        dev = InvoiceLine.objects.filter(invoice=self.issue(), category='development')
        self.assertEqual(dev.count(), 2)
        for ln in dev:
            self.assertEqual(ln.unit_amount_myr, Decimal('57.50'))   # RM50 + 15%
            self.assertEqual((ln.quantity * ln.unit_amount_myr).quantize(Decimal('0.01')),
                             ln.amount_myr)

    def test_lines_that_do_not_multiply_out_at_whole_cents_still_add_up_to_the_charge(self):
        """RM45.55 + 12.5% is 51.24375 — not whole cents. The charge is the sum of the lines at
        the billed rate, so the invoice total and the live charge still agree to the cent."""
        BillingRate.objects.filter(category='development', kind='hourly_rate').update(
            value=Decimal('45.55'))
        BillingRate.objects.filter(category='development', kind='margin_pct').update(
            value=Decimal('12.5'))
        OrgBuildHours.objects.create(organisation=self.org, period_month='2026-08',
                                     module='Odd one', hours=Decimal('0.1'), basis='x')
        charge = platform_cost.charge_for(self.org, '2026-08')
        inv = self.issue()
        self.assertEqual(inv.subtotal_myr, charge['subtotal_myr'])
        self.assertEqual(sum(ln.amount_myr for ln in inv.lines.all()), inv.subtotal_myr)

    def test_the_tenant_line_has_nowhere_to_put_a_cost_or_a_margin(self):
        """Structural, not a filter: the columns do not exist, so no future serializer can leak
        them."""
        names = {f.name for f in InvoiceLine._meta.get_fields()}
        for leak in ('cost_myr', 'margin_pct', 'tool_cost_myr', 'rate_myr', 'share_rule'):
            self.assertNotIn(leak, names)

    def test_issuer_and_bill_to_are_snapshotted_so_a_later_edit_never_rewrites_the_invoice(self):
        inv = self.issue()
        InvoiceIssuer.objects.update(bank_account_no='9999')
        OrgBillingDetails.objects.update(bill_to_name='Renamed Sdn Bhd')
        inv.refresh_from_db()
        self.assertEqual(inv.issuer_snapshot['bank_account_no'], '5140 1234 5678')
        self.assertEqual(inv.bill_to_snapshot['bill_to_name'], 'BrightPath Bursary Berhad')
        self.assertIn('5140 1234 5678', invoice_pdf.render_invoice_html(inv))

    def test_a_rate_changed_after_issue_moves_the_live_charge_and_not_the_invoice(self):
        """The whole difference between a bill and a readout."""
        inv = self.issue()
        BillingRate.objects.filter(category='infrastructure').update(value=Decimal('50'))
        self.assertNotEqual(platform_cost.charge_for(self.org, '2026-08')['charged_myr'],
                            Decimal('856.75'))
        inv.refresh_from_db()
        self.assertEqual(inv.total_myr, Decimal('856.75'))
        self.assertEqual(inv.lines.get(category='infrastructure').amount_myr, Decimal('115.00'))

    def test_a_refused_issue_writes_nothing_and_burns_no_number(self):
        InvoiceIssuer.objects.update(legal_name='')
        with self.assertRaises(invoicing.InvoiceRefused) as cm:
            self.issue()
        self.assertEqual([p['code'] for p in cm.exception.problems], ['issuer_incomplete'])
        self.assertFalse(Invoice.objects.exists())
        InvoiceIssuer.objects.update(legal_name='HalaTuju Platform')
        self.assertEqual(self.issue().number, 'INV-2026-0001')

    def test_an_overridable_warning_needs_a_written_reason_which_is_kept_with_the_warning(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        with self.assertRaises(invoicing.InvoiceRefused):
            self.issue()
        with self.assertRaises(invoicing.InvoiceRefused):
            self.issue(override_reason='   ')
        inv = self.issue(override_reason='Supabase was cancelled in July.',
                         issued_by_email='super@x.com')
        self.assertIn('Supabase was cancelled in July.', inv.override_reason)
        self.assertIn('supabase', inv.override_reason)
        self.assertEqual(inv.issued_by_email, 'super@x.com')

    def test_an_absolute_problem_cannot_be_overridden_by_any_reason(self):
        with self.assertRaises(invoicing.InvoiceRefused) as cm:
            self.issue(month='2026-09', override_reason='I really mean it')
        self.assertIn('month_not_closed', [p['code'] for p in cm.exception.problems])
        self.assertFalse(Invoice.objects.exists())

    def test_a_month_already_invoiced_is_refused_not_doubled(self):
        self.issue()
        with self.assertRaises(invoicing.InvoiceRefused) as cm:
            self.issue()
        self.assertEqual([p['code'] for p in cm.exception.problems], ['already_issued'])
        self.assertEqual(Invoice.objects.count(), 1)

    def test_the_database_also_refuses_a_second_live_invoice(self):
        """The readiness check is the polite refusal; the partial unique constraint is the one a
        race cannot get past."""
        inv = self.issue()
        dup = Invoice(number='INV-2026-0999', organisation=self.org, period_month='2026-08',
                      issued_on=SEPT_15, due_on=SEPT_15, subtotal_myr=0, total_myr=0)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError), transaction.atomic():
            dup.save()
        self.assertEqual(inv.number, 'INV-2026-0001')

    def test_a_voided_invoice_can_be_replaced_and_the_replacement_names_it(self):
        first = self.issue()
        invoicing.void_invoice(first, reason='Wrong hours recorded')
        second = self.issue()
        self.assertEqual(second.number, 'INV-2026-0002')   # a void keeps its number for ever
        self.assertEqual(second.replaces_id, first.id)

    def test_a_fully_discounted_month_owes_nothing_and_is_not_called_paid(self):
        """July: *"100% discount. But show the values."* Nothing arrived, so nothing is PAID."""
        OrgBillingAdjustment.objects.create(organisation=self.org, period_month='2026-08',
                                            discount_pct=Decimal('100'), reason='Pre-launch')
        inv = self.issue()
        self.assertEqual(inv.subtotal_myr, Decimal('856.75'))
        self.assertEqual(inv.discount_myr, Decimal('856.75'))
        self.assertEqual(inv.total_myr, Decimal('0.00'))
        self.assertEqual(inv.discount_reason, 'Pre-launch')
        self.assertEqual(inv.status, 'issued')

    def test_lines_that_do_not_reach_the_charge_refuse_to_become_an_invoice(self):
        charge = {'subtotal_myr': Decimal('10.00'), 'lines': [
            {'category': 'metered', 'amount_myr': Decimal('9.99'), 'share_pct': Decimal('100')}]}
        with self.assertRaises(invoicing.InvoicingError) as cm:
            invoicing.build_lines(charge, '2026-08')
        self.assertEqual(cm.exception.code, 'lines_do_not_add_up')

    def test_a_share_below_100_percent_is_stated_on_the_line(self):
        charge = {'subtotal_myr': Decimal('5.00'), 'lines': [
            {'category': 'infrastructure', 'amount_myr': Decimal('5.00'),
             'share_pct': Decimal('50.00')}]}
        self.assertIn('your share: 50%', invoicing.build_lines(charge, '2026-08')[0]['description'])


class TestIssueMonth(InvoiceWorld):

    def test_the_run_issues_ready_tenants_and_skips_ones_already_invoiced(self):
        report = invoicing.issue_month(today=SEPT_15)
        self.assertEqual(report['month'], '2026-08')
        self.assertEqual([i['number'] for i in report['issued']], ['INV-2026-0001'])
        again = invoicing.issue_month(today=SEPT_15)
        self.assertEqual(again['issued'], [])
        self.assertEqual(len(again['skipped']), 1)
        self.assertEqual(again['refused'], [])
        self.assertEqual(Invoice.objects.count(), 1)

    def test_the_run_never_overrides(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        report = invoicing.issue_month(today=SEPT_15)
        self.assertEqual(report['issued'], [])
        self.assertIn('supabase', ' '.join(report['refused'][0]['problems']))
        self.assertFalse(Invoice.objects.exists())

    def test_an_already_invoiced_tenant_is_not_re_reported_for_warnings_it_was_issued_past(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        self.issue(override_reason='Cancelled.')
        report = invoicing.issue_month(today=SEPT_15)
        self.assertEqual(report['refused'], [])
        self.assertEqual(len(report['skipped']), 1)


# ── Void ─────────────────────────────────────────────────────────────────────

class TestVoid(InvoiceWorld):

    def test_a_void_needs_a_reason(self):
        inv = self.issue()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            invoicing.void_invoice(inv, reason=' ')
        self.assertEqual(cm.exception.code, 'reason_required')
        self.assertIsNone(Invoice.objects.get(pk=inv.pk).voided_at)

    def test_an_invoice_with_money_against_it_cannot_be_voided(self):
        inv = self.issue()
        invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr='100.00',
                                 reference='MBB123', today=SEPT_15)
        with self.assertRaises(invoicing.InvoicingError) as cm:
            invoicing.void_invoice(inv, reason='oops')
        self.assertEqual(cm.exception.code, 'has_receipts')

    def test_a_void_cannot_be_voided_again_or_sent(self):
        inv = invoicing.void_invoice(self.issue(), reason='Wrong month')
        self.assertEqual(inv.status, 'void')
        with self.assertRaises(invoicing.InvoicingError):
            invoicing.void_invoice(inv, reason='again')
        with self.assertRaises(invoicing.InvoicingError) as cm:
            invoicing.send_invoice(inv)
        self.assertEqual(cm.exception.code, 'invoice_void')


# ── Receipts ─────────────────────────────────────────────────────────────────

class TestReceipts(InvoiceWorld):

    def receipt(self, inv, amount, **kw):
        kw.setdefault('received_on', SEPT_15)
        kw.setdefault('reference', 'MBB-TRX-001')
        return invoicing.record_receipt(inv, amount_myr=amount, today=SEPT_15, **kw)

    def test_part_then_full_payment_moves_the_status_and_the_balance(self):
        inv = self.issue()
        r1 = self.receipt(inv, '500.00')
        self.assertEqual(r1.number, 'RCP-2026-0001')
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'part_paid')
        self.assertEqual(inv.balance(), Decimal('356.75'))
        r2 = self.receipt(inv, '356.75', reference='MBB-TRX-002')
        self.assertEqual(r2.number, 'RCP-2026-0002')
        self.assertEqual(Invoice.objects.get(pk=inv.pk).status, 'paid')

    def test_more_than_is_owed_is_refused(self):
        inv = self.issue()
        self.receipt(inv, '800.00')
        with self.assertRaises(invoicing.InvoicingError) as cm:
            self.receipt(inv, '56.76')
        self.assertEqual(cm.exception.code, 'overpayment')
        self.assertEqual(inv.receipts.count(), 1)

    def test_a_receipt_without_a_bank_reference_is_refused(self):
        inv = self.issue()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            self.receipt(inv, '10.00', reference='  ')
        self.assertEqual(cm.exception.code, 'reference_required')

    def test_money_cannot_arrive_in_the_future(self):
        inv = self.issue()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            self.receipt(inv, '10.00', received_on=date(2026, 9, 16))
        self.assertEqual(cm.exception.code, 'bad_date')

    def test_amounts_must_be_positive_whole_cents(self):
        inv = self.issue()
        for bad in ('0', '-5', '1.234', 'abc', None):
            with self.subTest(bad=bad), self.assertRaises(invoicing.InvoicingError) as cm:
                self.receipt(inv, bad)
            self.assertEqual(cm.exception.code, 'bad_amount')

    def test_a_voided_invoice_takes_no_payment(self):
        inv = invoicing.void_invoice(self.issue(), reason='Wrong')
        with self.assertRaises(invoicing.InvoicingError) as cm:
            self.receipt(inv, '10.00')
        self.assertEqual(cm.exception.code, 'invoice_void')

    def test_a_receipt_prints_the_balance_on_its_own_day_not_todays(self):
        """Re-downloaded after a second payment, the first receipt must still say what it said."""
        inv = self.issue()
        first = self.receipt(inv, '500.00', received_on=date(2026, 9, 10))
        self.receipt(inv, '356.75', reference='second')
        html = invoice_pdf.render_receipt_html(first)
        self.assertIn('RM356.75', html)    # balance after the FIRST payment
        self.assertIn('RM500.00', html)


# ── Sending and the document ─────────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='noreply@halatuju.xyz')
class TestSend(InvoiceWorld):

    def test_send_emails_the_pdf_to_the_frozen_bill_to_inboxes_then_marks_it_sent(self):
        inv = self.issue()
        OrgBillingDetails.objects.update(emails=['changed-after-issue@example.com'])
        invoicing.send_invoice(inv, sent_by_email='super@x.com')
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['finance@brightpath.example'])     # the SNAPSHOT
        self.assertEqual(msg.reply_to, ['billing@halatuju.xyz'])
        self.assertIn('INV-2026-0001', msg.subject)
        name, content, mime = msg.attachments[0]
        self.assertEqual((name, mime), ('INV-2026-0001.pdf', 'application/pdf'))
        self.assertTrue(content.startswith(b'%PDF'))
        inv.refresh_from_db()
        self.assertIsNotNone(inv.sent_at)
        self.assertEqual(inv.sent_to, ['finance@brightpath.example'])
        self.assertEqual(inv.status, 'sent')

    def test_it_speaks_as_the_platform_billing_the_tenant_not_as_the_tenants_own_team(self):
        invoicing.send_invoice(self.issue())
        msg = mail.outbox[0]
        self.assertIn('HalaTuju Platform', msg.subject)
        self.assertNotIn('Bursary Team', msg.body)

    def test_a_failed_send_does_not_mark_the_invoice_sent(self):
        """⚠ The ordering lesson: make the send FAIL and assert silence on the record."""
        inv = self.issue()
        with mock.patch('apps.scholarship.emails.send_invoice_email', return_value=False):
            with self.assertRaises(invoicing.InvoicingError) as cm:
                invoicing.send_invoice(inv)
        self.assertEqual(cm.exception.code, 'send_failed')
        inv.refresh_from_db()
        self.assertIsNone(inv.sent_at)
        self.assertEqual(inv.status, 'issued')

    def test_an_invoice_with_no_recipients_is_not_sent(self):
        inv = self.issue()
        Invoice.objects.filter(pk=inv.pk).update(bill_to_snapshot={'bill_to_name': 'x'})
        inv.refresh_from_db()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            invoicing.send_invoice(inv)
        self.assertEqual(cm.exception.code, 'no_recipients')
        self.assertEqual(mail.outbox, [])


class TestTheDocument(InvoiceWorld):

    def test_the_invoice_prints_what_a_payer_needs(self):
        html = invoice_pdf.render_invoice_html(self.issue())
        for needed in ('INV-2026-0001', 'August 2026', 'BrightPath Bursary Berhad',
                       'HalaTuju Platform', 'Maybank', '5140 1234 5678', 'RM856.75',
                       'RM57.50', 'Payments module', '15 October 2026'):
            self.assertIn(needed, html)

    def test_the_invoice_never_prints_what_the_platform_paid(self):
        """August's costs were RM20.00 and RM100.00, at a 15% margin. None of that is the
        tenant's to read."""
        import re
        html = invoice_pdf.render_invoice_html(self.issue())
        # The VISIBLE text only: the stylesheet legitimately says `margin:` about page layout.
        text = re.sub(r'<[^>]+>', ' ', re.sub(r'<style>.*?</style>', '', html, flags=re.S))
        for leak in ('RM20.00', 'RM100.00', 'margin', 'Margin', 'RM50.00', '15%'):
            self.assertNotIn(leak, text)

    def test_a_real_pdf_is_produced_for_both_documents(self):
        inv = self.issue()
        receipt = invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr='856.75',
                                           reference='MBB1', today=SEPT_15)
        self.assertTrue(invoice_pdf.invoice_pdf(inv).startswith(b'%PDF'))
        self.assertTrue(invoice_pdf.receipt_pdf(receipt).startswith(b'%PDF'))

    def test_a_void_invoice_says_so_on_the_document(self):
        inv = invoicing.void_invoice(self.issue(), reason='Hours were for September')
        html = invoice_pdf.render_invoice_html(inv)
        self.assertIn('VOID', html)
        self.assertIn('Hours were for September', html)


# ── The receipt box, over the wire ───────────────────────────────────────────
# TD-261 defect 3: 'Infinity' typed into the receipt box used to be a 500, because
# `Decimal('Infinity')` parses and the quantise that followed raised from outside the guard.
# The service-level proof is in `test_helper_characterisation`; this is the one that matters to
# the person holding the mouse — the endpoint answers 400 with the code the screen reads.

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=factories.TEST_JWT_SECRET)
class TestReceiptEndpointRefusals(InvoiceWorld):

    def setUp(self):
        super().setUp()
        self.super_admin = factories.make_admin('super', super_admin=True)
        self.client = factories.authed_client(self.super_admin)

    def post(self, inv, amount):
        return self.client.post(
            f'/api/v1/admin/scholarship/billing/invoices/{inv.pk}/receipt/',
            {'received_on': SEPT_15.isoformat(), 'amount_myr': amount,
             'reference': 'MBB-TRX-001'}, format='json')

    def test_a_non_finite_amount_is_a_400_bad_amount_and_records_nothing(self):
        inv = self.issue()
        for amount in ('Infinity', '-Infinity', 'NaN', 'sNaN'):
            with self.subTest(amount=amount):
                response = self.post(inv, amount)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['code'], 'bad_amount')
        self.assertEqual(inv.receipts.count(), 0)

    def test_a_figure_too_big_to_express_at_two_places_is_a_400_not_a_500(self):
        """⚠ THE AUDIT OF 2026-09-21, AND IT IS TD-261's DEFECT WEARING A DIFFERENT HAT.

        TD-261 guarded the `quantize` call and the non-finite values. It did not guard the
        quantise inside `money.parse_money`'s `places_exact` comparison — and `_receipt_amount`
        asks for `places_exact` — so `1E+100` in the receipt box raised a raw
        `decimal.InvalidOperation` straight past the `except money.MoneyError` and out of this
        endpoint as a **500**. The figure is not exotic: `1e3` is already an accepted amount here
        (pinned in the characterisation table), so exponent notation is something this box takes.

        `1E+26` is in the list deliberately — it is the FIRST figure that escapes, and a test
        that only ever tried absurd ones would pass against a parser that refused every
        exponent."""
        inv = self.issue()
        for amount in ('1E+26', '1E+100', '1e30', '-1E+100', '9' * 40):
            with self.subTest(amount=amount):
                response = self.post(inv, amount)
                self.assertEqual(response.status_code, 400,
                                 f'{amount!r} answered {response.status_code}, not 400 — a money '
                                 f'figure escaped money.parse_money as something other than a '
                                 f'MoneyError. See the note at the top of money.py.')
                self.assertEqual(response.json()['code'], 'bad_amount')
        self.assertEqual(inv.receipts.count(), 0)

    def test_an_ordinary_bad_amount_still_answers_the_same_way(self):
        """The control: the new refusal must be indistinguishable from the old ones, or the
        screen would have to learn a second shape."""
        inv = self.issue()
        for amount in ('abc', '0', '-5', '1.234'):
            with self.subTest(amount=amount):
                response = self.post(inv, amount)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['code'], 'bad_amount')

    def test_a_good_amount_still_records_a_receipt(self):
        inv = self.issue()
        self.assertEqual(self.post(inv, '500.00').status_code, 200)
        self.assertEqual(inv.receipts.count(), 1)
