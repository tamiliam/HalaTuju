"""Back-issuing a month, and what a development line SAYS (2026-10-28).

The owner read the first real invoice previews on 2026-10-28 and asked for two things:

1. **"Issue from July onwards, issued on the 15 of the following month."** Two months had already
   slipped past. Issuing them on the day somebody finally pressed the button would have put a
   November due date on a July bill, so the printed issue date has to be settable — inside bounds
   that cannot be argued with, because a settable date on a money document is also a way to
   pre-date one. Those bounds are `invoicing.issue_date_for` and they are the bulk of this file.

2. **The lines must stop reading like a bug tracker.** August's preview printed
   *"[REQ-12] show year SPM was taken"*. The tag is how a finished request is known to have been
   billed, so it stays in the database and leaves only the paper.

⚠ THE DATE IS A DOOR INTO A MONEY DOCUMENT, so every bound is tested from the side that WIDENS it
(the lesson from the fence work): tomorrow, the last day of the billed month, a month earlier
still, a timestamp wearing a date's clothes. A test that only proves 15 August is accepted proves
nothing — the default already was a valid date.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.scholarship import invoicing, platform_cost
from apps.scholarship.models import Invoice, InvoiceLine, OrgBuildHours, PlatformCost
from apps.scholarship.tests.test_invoicing import SEPT_15, InvoiceWorld

OCT_28 = date(2026, 10, 28)


# ── What a development line says ─────────────────────────────────────────────

class TestTheWordsOnADevelopmentLine(TestCase):
    """`printable_module` — the one place a stored module becomes printed words."""

    def test_the_request_tag_is_stripped_and_nothing_else_is(self):
        self.assertEqual(
            invoicing.printable_module('[REQ-12] show year SPM was taken'),
            'show year SPM was taken')
        self.assertEqual(
            invoicing.printable_module('[REQ-3] Email notification to student'),
            'Email notification to student')

    def test_a_module_with_no_tag_is_returned_whole(self):
        # Hours recorded by hand predate requests entirely; their wording is already the super's.
        self.assertEqual(invoicing.printable_module('Payments module'), 'Payments module')

    def test_only_a_LEADING_tag_goes_and_only_a_real_one(self):
        """⚠ ANCHORED AT THE FRONT. A description that mentions a request mid-sentence is the
        super's own wording and must survive; a word that merely looks like the tag is not it."""
        for text, expected in (
            ('Reviewer page (see [REQ-10])', 'Reviewer page (see [REQ-10])'),
            ('[REQUEST-10] something', '[REQUEST-10] something'),
            ('[REQ-] something', '[REQ-] something'),
            ('[REQ-10]', ''),
            ('  [REQ-10]   spaced  ', 'spaced'),
        ):
            with self.subTest(text=text):
                self.assertEqual(invoicing.printable_module(text), expected)

    def test_blank_and_none_do_not_raise(self):
        for value in ('', None, '   '):
            with self.subTest(value=value):
                self.assertEqual(invoicing.printable_module(value), '')


class TestTheTagStaysInTheDatabase(InvoiceWorld):
    """The tag must leave the invoice WITHOUT leaving the bookkeeping."""

    def setUp(self):
        # ⚠ THE REQUEST HAS TO EXIST, quoted and accepted. This fixture used to write an hours row
        # naming request 12 while no request 12 existed anywhere — harmless when the only question
        # was how the words print, and caught on 2026-10-29 by the new absolute refusal to bill a
        # feature with no quote or acceptance (`request_hours.consent_gaps`), which reads a tag
        # pointing at nothing as exactly the gap it exists to stop. The guard is right; the fixture
        # was not a state production could ever be in.
        from django.utils import timezone

        from apps.courses.models_staff import PartnerAdmin
        from apps.scholarship.models import OrgRequest

        admin = PartnerAdmin.objects.create(
            owning_organisation=self.org, role='org_admin', is_active=True,
            email='finance@brightpath.example')
        OrgRequest.objects.create(
            pk=12, organisation=self.org, submitted_by=admin, kind='feature',
            title='show year SPM was taken', description='show year SPM was taken',
            status='done', triaged_kind='feature', quote_hours=Decimal('6.0'),
            quoted_at=timezone.now(), approved_at=timezone.now())
        self.hours = OrgBuildHours.objects.create(
            organisation=self.org, period_month='2026-08',
            module=f'{platform_cost.request_module_tag(12)} show year SPM was taken',
            hours=Decimal('6.0'), basis='quoted on the request')

    def test_the_invoice_line_carries_no_tag(self):
        """The SQUARE-bracket prefix never prints. The number itself does, at the end.

        The owner asked for both, five hours apart on 2026-10-29, and they are not in conflict:
        `[REQ-12] show year SPM was taken` reads like a bug tracker and is what gets stripped;
        `show year SPM was taken (REQ-12)` reads like a reference and is what the owner wants on
        a sub-item. The suffix is composed from the request id, never from the stored text.
        """
        inv = self.issue()
        printed = [ln.description for ln in inv.lines.all()]
        self.assertIn('show year SPM was taken (REQ-12)', printed)
        self.assertFalse([d for d in printed if '[REQ-' in d],
                         f'a bug-tracker tag reached the paper: {printed}')

    def test_the_hours_row_still_names_the_request_so_it_counts_as_billed(self):
        self.issue()
        self.hours.refresh_from_db()
        self.assertIn('[REQ-12]', self.hours.module)
        # And the consequence that matters: the request is no longer proposed as unbilled.
        proposed = [u['request_id'] for u in platform_cost.unbilled_request_hours(self.org)]
        self.assertNotIn(12, proposed)

    def test_a_tag_with_nothing_after_it_still_prints_something(self):
        """A line with an empty description is a line a reader cannot check. The month stands in."""
        self.hours.module = platform_cost.request_module_tag(12)
        self.hours.save(update_fields=['module'])
        inv = self.issue()
        descriptions = [ln.description for ln in inv.lines.all()]
        self.assertIn('Development, August 2026 (REQ-12)', descriptions)
        self.assertFalse([d for d in descriptions if d.strip() == ''])


# ── The issue date, on its own ───────────────────────────────────────────────

class TestTheIssueDateBounds(TestCase):
    """`issue_date_for` as a pure function, bound by bound."""

    def test_nothing_given_means_today_which_is_every_ordinary_issue(self):
        for empty in (None, ''):
            with self.subTest(empty=empty):
                self.assertEqual(invoicing.issue_date_for('2026-07', empty, OCT_28), OCT_28)

    def test_a_date_after_the_billed_month_is_taken_as_given(self):
        self.assertEqual(invoicing.issue_date_for('2026-07', date(2026, 8, 15), OCT_28),
                         date(2026, 8, 15))
        self.assertEqual(invoicing.issue_date_for('2026-07', '2026-08-15', OCT_28),
                         date(2026, 8, 15))

    def test_the_first_day_after_the_month_ends_is_allowed_and_the_last_day_is_not(self):
        """THE BOUNDARY ITSELF, from both sides. 31 July is inside the month July bills."""
        self.assertEqual(invoicing.issue_date_for('2026-07', '2026-08-01', OCT_28),
                         date(2026, 8, 1))
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_date_for('2026-07', '2026-07-31', OCT_28)
        self.assertEqual(caught.exception.code, 'issue_date_before_month_end')

    def test_a_february_boundary_is_the_real_last_day_not_the_30th(self):
        self.assertEqual(invoicing.issue_date_for('2026-02', '2026-03-01', OCT_28),
                         date(2026, 3, 1))
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_date_for('2026-02', '2026-02-28', OCT_28)
        self.assertEqual(caught.exception.code, 'issue_date_before_month_end')

    def test_a_date_before_the_billed_month_altogether_is_refused(self):
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_date_for('2026-07', '2026-05-20', OCT_28)
        self.assertEqual(caught.exception.code, 'issue_date_before_month_end')

    def test_today_is_allowed_and_tomorrow_is_not(self):
        self.assertEqual(invoicing.issue_date_for('2026-07', OCT_28.isoformat(), OCT_28), OCT_28)
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_date_for('2026-07', '2026-10-29', OCT_28)
        self.assertEqual(caught.exception.code, 'issue_date_future')

    def test_an_unreadable_date_is_its_own_refusal_not_an_out_of_range_one(self):
        """Two different corrections need two different codes: 'that is not a date' and 'that date
        is not allowed' are not the same instruction to the person holding the keyboard."""
        for bad in ('15/08/2026', '2026-8-15', '2026-08', 'August', 'nonsense', '20260815',
                    '2026-13-01', '2026-08-32'):
            with self.subTest(bad=bad):
                with self.assertRaises(invoicing.InvoicingError) as caught:
                    invoicing.issue_date_for('2026-07', bad, OCT_28)
                self.assertEqual(caught.exception.code, 'bad_issue_date')

    def test_a_TIMESTAMP_is_refused_rather_than_silently_losing_its_time(self):
        """⚠ `datetime` IS A SUBCLASS OF `date`, so a plain isinstance check admits one — and a
        timestamp carries a zone, which is exactly what TD-209 keeps out of a date field. Python
        3.11's `date.fromisoformat` also parses the string form, so both shapes are tested."""
        for bad in (datetime(2026, 8, 15, 23, 30, tzinfo=dt_timezone.utc),
                    '2026-08-15T23:30:00+00:00', '2026-08-15 23:30'):
            with self.subTest(bad=bad):
                with self.assertRaises(invoicing.InvoicingError) as caught:
                    invoicing.issue_date_for('2026-07', bad, OCT_28)
                self.assertEqual(caught.exception.code, 'bad_issue_date')

    def test_a_number_is_refused(self):
        for bad in (20260815, 1, [], {}, object()):
            with self.subTest(bad=bad):
                with self.assertRaises(invoicing.InvoicingError) as caught:
                    invoicing.issue_date_for('2026-07', bad, OCT_28)
                self.assertEqual(caught.exception.code, 'bad_issue_date')


# ── What the back-dated invoice itself carries ───────────────────────────────

class TestBackIssuingAMonth(InvoiceWorld):

    def test_the_issue_date_the_due_date_and_the_number_all_follow_the_given_date(self):
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual(inv.issued_on, date(2026, 9, 15))
        # Terms are 30 days and they run from the PRINTED date, not from today.
        self.assertEqual(inv.due_on, date(2026, 10, 15))
        self.assertTrue(inv.number.startswith('INV-2026-'), inv.number)

    def test_nothing_else_about_the_month_moves(self):
        """The figures are the month's, not the issue date's. A back-dated invoice is the same
        bill, printed with the date it should have carried."""
        same_day = self.issue(today=SEPT_15)
        same_day.delete()
        back = self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual(back.total_myr, Decimal('856.75'))
        self.assertEqual(back.period_month, '2026-08')

    def test_a_date_in_a_CLOSED_YEAR_is_refused_outright(self):
        """⚠ THE BOUND THAT ADVERSARIAL REVIEW ADDED, 2026-10-28. `Invoice.number` is *"numbered
        by the year of issue"*, so a date in a previous year does not merely look odd — it opens a
        NEW RUN of numbers for a year that is closed and filed, irreversibly, today. The screen's
        own month picker could reach November 2025 and prefill 15 December 2025, and every other
        check passed it.

        A month that slipped past a year-end is an accounting decision, not a keystroke."""
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_invoice(self.org, '2026-08', today=date(2027, 2, 1),
                                    issued_on='2026-09-15')
        self.assertEqual(caught.exception.code, 'issue_date_last_year')
        self.assertFalse(Invoice.objects.exists())

    def test_inside_the_open_year_the_number_still_follows_the_PRINTED_date(self):
        """The year floor does not make the rule pointless: within the open year the number is
        still drawn from the printed year, which is what keeps one run of numbers per year."""
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual(inv.issued_on.year, 2026)
        self.assertTrue(inv.number.startswith('INV-2026-'), inv.number)

    def test_a_bad_date_is_refused_BEFORE_the_readiness_list_so_the_fix_is_one_thing(self):
        """A month with warnings AND a mistyped date must answer about the date. Burying it under
        a readiness list is how a one-character correction gets missed."""
        from apps.scholarship.models import PlatformCost

        # ⚠ THE MONTH IS MADE UNREADY ON PURPOSE, and asserted, not assumed. An earlier draft of
        # this test claimed July already carried warnings; it does not, and the test would then
        # have proved only that a bad date is refused — which the bounds tests already prove.
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        self.assertIn('supplier_missing', self.codes(today=OCT_28))

        with self.assertRaises(invoicing.InvoicingError) as caught:
            # A mistyped date AND an unready month, with no override reason: the answer must be
            # about the date, which is the one thing a keystroke fixes.
            self.issue(today=OCT_28, issued_on='2026-08-31')
        self.assertEqual(caught.exception.code, 'issue_date_before_month_end')
        self.assertNotIsInstance(caught.exception, invoicing.InvoiceRefused)
        self.assertFalse(Invoice.objects.exists(), 'a refused date must leave no invoice')

    def test_a_refused_date_burns_no_invoice_number(self):
        from apps.scholarship.models import BillingSequence
        with self.assertRaises(invoicing.InvoicingError):
            self.issue(today=OCT_28, issued_on='2026-11-30')
        self.assertFalse(BillingSequence.objects.filter(kind='INV').exists())

    def test_the_monthly_job_still_dates_everything_today_and_passes_no_date(self):
        """⚠ The 15th's run must NOT acquire a date argument by accident: an unattended job that
        can back-date is an unattended job that can pre-date."""
        with mock.patch.object(invoicing, 'issue_invoice',
                               wraps=invoicing.issue_invoice) as spy:
            invoicing.issue_month('2026-08', today=SEPT_15)
        self.assertTrue(spy.called)
        for call in spy.call_args_list:
            self.assertNotIn('issued_on', call.kwargs)

    def test_the_pdf_prints_the_back_dated_day(self):
        from apps.scholarship import invoice_pdf
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        html = invoice_pdf.render_invoice_html(inv)
        self.assertIn('15 September 2026', html)
        self.assertIn('15 October 2026', html)
        self.assertNotIn('28 October 2026', html)

    def test_lines_still_add_up_to_the_subtotal_on_a_back_dated_invoice(self):
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        total = sum((ln.amount_myr for ln in inv.lines.all()), Decimal('0.00'))
        self.assertEqual(total, inv.subtotal_myr)
        self.assertEqual(InvoiceLine.objects.filter(invoice=inv).count(), inv.lines.count())


class TestWhatAdversarialReviewFound(InvoiceWorld):
    """The five guards added on 2026-10-28 after the diff was reviewed for the door NOT on my list.

    Each one is a thing a settable date made reachable that was not reachable before it.
    """

    def test_the_series_may_not_run_backwards_against_its_dates(self):
        """⚠ `next_number` counts in KEYPRESS order and the date is now free. Catch up on three
        months in the obvious order — newest first — and the numbers ascend while the dates
        descend, which for a numbered tax-document series is the classic audit finding. It would
        have happened on the owner's very first sitting."""
        later = self.issue(today=OCT_28, issued_on='2026-10-15')
        self.assertEqual(later.number, 'INV-2026-0001')
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_invoice(self.org, '2026-07', today=OCT_28, issued_on='2026-08-15')
        self.assertEqual(caught.exception.code, 'issue_date_out_of_order')
        self.assertIn('INV-2026-0001', caught.exception.message)
        self.assertIn('oldest month first', caught.exception.message)

    def test_issuing_oldest_first_is_allowed_and_is_what_the_message_asks_for(self):
        """The guard must not block the owner's actual task. July, then August, in that order."""
        july = invoicing.issue_invoice(self.org, '2026-07', today=OCT_28, issued_on='2026-08-15')
        august = self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual([july.number, august.number], ['INV-2026-0001', 'INV-2026-0002'])
        self.assertLess(july.issued_on, august.issued_on)

    def test_the_same_date_twice_is_allowed(self):
        """Two months issued on one day is ordinary; only going BACKWARDS is refused."""
        invoicing.issue_invoice(self.org, '2026-07', today=OCT_28, issued_on='2026-10-01')
        self.assertTrue(self.issue(today=OCT_28, issued_on='2026-10-01').number)

    def test_a_VOIDED_invoice_still_holds_its_place_in_the_series(self):
        """Its number was drawn and filed. If a void released the date, a void-and-reissue could
        walk the series backwards one step at a time."""
        first = self.issue(today=OCT_28, issued_on='2026-10-15')
        invoicing.void_invoice(first, reason='Wrong month')
        with self.assertRaises(invoicing.InvoicingError) as caught:
            self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual(caught.exception.code, 'issue_date_out_of_order')

    def test_a_month_with_nothing_in_it_refuses_instead_of_printing_an_empty_bill(self):
        """⚠ TESTED ON THE SUBTOTAL, not on the lines, because an empty line list sums to zero and
        so passes `build_lines`' own add-up check. A super overriding `no_costs` would otherwise
        mint a numbered, frozen, permanent document with nothing on it."""
        PlatformCost.objects.filter(period_month='2026-08').delete()
        OrgBuildHours.objects.filter(period_month='2026-08').delete()
        with self.assertRaises(invoicing.InvoicingError) as caught:
            self.issue(today=OCT_28, override_reason='Nothing was spent.')
        self.assertEqual(caught.exception.code, 'nothing_to_bill')
        self.assertFalse(Invoice.objects.exists())

    def test_a_month_whose_lines_are_all_RM0_is_the_same_refusal(self):
        """The shape the empty-list check would have MISSED: a month with no ledger rows still
        produces an infrastructure line and a metered line, each RM0.00. A document reading
        'Platform infrastructure, August 2026 … RM0.00' is not a bill either."""
        PlatformCost.objects.filter(period_month='2026-08').delete()
        OrgBuildHours.objects.filter(period_month='2026-08').delete()
        charge = platform_cost.charge_for(self.org, '2026-08')
        self.assertTrue(invoicing.build_lines(charge, '2026-08'),
                        'this test needs a month that DOES produce lines, all of them zero')
        with self.assertRaises(invoicing.InvoicingError) as caught:
            self.issue(today=OCT_28, override_reason='Nothing was spent.')
        self.assertEqual(caught.exception.code, 'nothing_to_bill')

    def test_a_month_before_any_rate_existed_refuses_too(self):
        """The genuinely line-LESS shape: every margin blocked, no hours, so `build_lines` returns
        an empty list whose sum equals the zero subtotal."""
        self._cost('2026-06', 'gcp', 'Cloud Run', 'Services CPU', '20.00', attributable=True)
        from apps.scholarship.models import BillingRate
        BillingRate.objects.all().delete()
        charge = platform_cost.charge_for(self.org, '2026-06')
        self.assertEqual(invoicing.build_lines(charge, '2026-06'), [])
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.issue_invoice(self.org, '2026-06', today=OCT_28, issued_on='2026-07-15',
                                    override_reason='No rates were set that far back.')
        self.assertEqual(caught.exception.code, 'nothing_to_bill')

    def test_a_fully_discounted_month_is_NOT_an_empty_one(self):
        """July is discounted to zero and must still issue: it carries its lines and a discount
        row. The `no_lines` refusal must not reach it."""
        from apps.scholarship.models import OrgBillingAdjustment

        OrgBillingAdjustment.objects.create(
            organisation=self.org, period_month='2026-08', discount_pct=Decimal('100.00'),
            reason='Not billed.')
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        self.assertEqual(inv.total_myr, Decimal('0.00'))
        self.assertGreater(inv.lines.count(), 0)
        self.assertGreater(inv.subtotal_myr, Decimal('0.00'))

    def test_a_month_still_running_says_so_rather_than_arguing_about_the_date(self):
        """⚠ Every date is 'before the end of this month' while the month is still running, so the
        date check would answer 'October ends on the 31st' — a correctable-looking sentence — in
        front of the real, absolute reason, which is that October's cost is not known yet."""
        with self.assertRaises(invoicing.InvoiceRefused) as caught:
            invoicing.issue_invoice(self.org, '2026-10', today=OCT_28, issued_on='2026-10-20')
        self.assertEqual([p['code'] for p in caught.exception.problems], ['month_not_closed'])
        self.assertFalse(caught.exception.problems[0]['overridable'])

    def test_money_cannot_arrive_before_the_bill_it_pays(self):
        """Unreachable while every invoice was dated the day it was issued. Back-dating opens it:
        the owner is now recording July, August and September money against invoices carrying
        July, August and September dates, where a month-out typo no longer looks absurd."""
        inv = self.issue(today=OCT_28, issued_on='2026-09-15')
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.record_receipt(inv, received_on='2026-09-14', amount_myr='10.00',
                                     reference='MBB-1', today=OCT_28)
        self.assertEqual(caught.exception.code, 'received_before_issued')
        # The issue date itself is fine: a bill paid the day it was raised is ordinary.
        self.assertTrue(invoicing.record_receipt(
            inv, received_on='2026-09-15', amount_myr='10.00', reference='MBB-1',
            today=OCT_28).number)


class TestConvertingAHeldRow(TestCase):
    """`record_platform_cost --convert-held` (2026-10-28).

    ⚠ A HELD ROW COULD NOT CONVERT ITSELF, AND NOTHING ELSE COULD EITHER. A row is held when its
    foreign amount is known and no exchange rate was available — the ordinary state of a bill
    imported before the month has ended, because the ECB publishes the closing rate afterwards.
    `import_invoices` fetches the rate at IMPORT time and never comes back, so the only remedy was
    to re-import the original PDF. On production that left Anthropic's September line — RM400-odd
    of real cost — with no ringgit value, which makes the month incomplete and refuses its invoice.
    """

    def setUp(self):
        from apps.scholarship.models import PlatformCost

        self.row = PlatformCost.objects.create(
            period_month='2026-09', source='anthropic', service='Anthropic',
            sku='Max plan - 5x', currency='USD', amount_original=Decimal('100.00'),
            fx_rate=None, amount_myr=None, provenance='extracted',
            invoice_ref='ZOX36MBZ 0011', note='Parsed from a PDF.')

    def _run(self):
        from django.core.management import call_command
        call_command('record_platform_cost', '--month', '2026-09', '--convert-held', verbosity=0)
        self.row.refresh_from_db()

    def test_it_writes_the_rate_and_the_ringgit_figure(self):
        with mock.patch('apps.scholarship.fx.closing_rate',
                        return_value=(Decimal('4.078'), date(2026, 9, 30))) as rate:
            self._run()
        # ⚠ THE LAST DAY OF THE BILLED MONTH — the owner's rule, and the one `import_invoices`
        # uses, so a converted row and an imported one agree.
        self.assertEqual(rate.call_args.args, ('USD', date(2026, 9, 30)))
        self.assertEqual(self.row.fx_rate, Decimal('4.078'))
        self.assertEqual(self.row.amount_myr, Decimal('407.80'))

    def test_the_note_says_which_rate_and_when_it_was_PUBLISHED(self):
        # The published date differs from the date asked for over a weekend, and it is the one a
        # reader can look up again.
        with mock.patch('apps.scholarship.fx.closing_rate',
                        return_value=(Decimal('4.078'), date(2026, 9, 28))):
            self._run()
        self.assertIn('published 2026-09-28', self.row.note)
        self.assertIn('Parsed from a PDF.', self.row.note)

    def test_provenance_is_untouched_because_converting_is_not_re_sourcing(self):
        with mock.patch('apps.scholarship.fx.closing_rate',
                        return_value=(Decimal('4.078'), date(2026, 9, 30))):
            self._run()
        self.assertEqual(self.row.provenance, 'extracted')

    def test_a_rate_that_cannot_be_fetched_leaves_the_row_HELD_rather_than_guessing(self):
        from apps.scholarship import fx

        with mock.patch('apps.scholarship.fx.closing_rate',
                        side_effect=fx.RateUnavailable('ECB is down')):
            self._run()
        self.assertIsNone(self.row.amount_myr)
        self.assertIsNone(self.row.fx_rate)

    def test_a_row_that_already_has_a_figure_is_not_touched(self):
        from apps.scholarship.models import PlatformCost

        done = PlatformCost.objects.create(
            period_month='2026-09', source='supabase', service='Supabase', sku='Pro Plan',
            currency='USD', amount_original=Decimal('25.00'), fx_rate=Decimal('4.000'),
            amount_myr=Decimal('100.00'), provenance='extracted')
        with mock.patch('apps.scholarship.fx.closing_rate',
                        return_value=(Decimal('9.999'), date(2026, 9, 30))):
            self._run()
        done.refresh_from_db()
        self.assertEqual((done.fx_rate, done.amount_myr), (Decimal('4.000'), Decimal('100.00')))
