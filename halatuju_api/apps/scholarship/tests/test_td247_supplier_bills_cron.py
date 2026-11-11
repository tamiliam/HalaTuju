"""TD-247 (A4.5): the supplier bills reach the cost ledger through a cron door.

`import_invoices --drive` reads the PDFs from the Drive folder in SUPPLIER_BILLS_FOLDER. The door is
MONEY (the invoices bill from this ledger), so what is pinned here is what makes it safe to run
unattended:

* the dry run (`supplier-bills-report`, no `--apply`) writes nothing;
* the write is INSERT-ONLY — a second run writes nothing, and a run with no exchange rate cannot blank
  a figure that is already there;
* a bill that claims a line another bill already holds is REPORTED, never swapped in;
* the door is shut without its secret, and its flags come from the registry, not the request;
* the `--dir` path still corrects (upserts) exactly as before.

No network: Drive, the PDF reader and the exchange-rate fetch are all patched.
"""
import io
import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.scholarship import cron_auth, fx, invoice_parsers, supplier_bills
from apps.scholarship.invoice_parsers import InvoiceLine, ParsedInvoice
from apps.scholarship.management.commands import import_invoices
from apps.scholarship.models import PlatformCost
from apps.scholarship.views import CronRunView

FOLDER = {supplier_bills.FOLDER_ENV: '05 Billing/Supplier bills'}
RATE = Decimal('4.2000')


def _invoice(ref='MTSOJA-2026-10', amount='10.00'):
    return ParsedInvoice(source='twilio', invoice_ref=ref, currency='USD', period_month='2026-10',
                         total=Decimal(amount),
                         lines=[InvoiceLine('Twilio', 'Programmable Messaging', Decimal(amount))])


def _rate_ok(amount, currency, on_date):
    return (amount * RATE).quantize(Decimal('0.01')), RATE, date(2026, 10, 31)


def _rate_down(amount, currency, on_date):
    raise fx.RateUnavailable('ECB unreachable')


class _Drive:
    """Patch the seams: the Drive folder listing, the PDF text, the parser, the rate and today.

    Today defaults to a date after October 2026 ends, so the bills in these tests are ready for
    their closing rate whatever the real clock says.
    """

    def __init__(self, invoices, rate=_rate_ok, today=date(2026, 11, 15)):
        self.pdfs = [(f'bill-{i}.pdf', b'%PDF-fake') for i in range(len(invoices))]
        self.invoices = list(invoices)
        self.rate = rate
        self.today = today

    def __enter__(self):
        texts = iter(f'text {i}' for i in range(len(self.invoices)))
        by_text = {f'text {i}': inv for i, inv in enumerate(self.invoices)}
        self._patches = [
            patch.dict(os.environ, FOLDER),
            patch.object(supplier_bills, 'drive_pdfs', return_value=self.pdfs),
            patch.object(invoice_parsers, 'pdf_text', side_effect=lambda _src: next(texts)),
            patch.object(invoice_parsers, 'parse_text', side_effect=lambda t: by_text[t]),
            patch.object(fx, 'to_myr', side_effect=self.rate),
            patch.object(import_invoices, '_server_date', return_value=self.today),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()


def _run(*args):
    out = io.StringIO()
    call_command('import_invoices', *args, stdout=out)
    return out.getvalue()


def _run_failing(case, *args):
    """Run the command expecting the end-of-run CommandError (a bill skipped for want of a rate
    for an ENDED month); returns (the printed report, the error text)."""
    out = io.StringIO()
    with case.assertRaises(CommandError) as ctx:
        call_command('import_invoices', *args, stdout=out)
    return out.getvalue(), str(ctx.exception)


def _myr_bill():
    return ParsedInvoice(source='workspace', invoice_ref='WS-2026-10', currency='MYR',
                         period_month='2026-10', total=Decimal('36.00'),
                         lines=[InvoiceLine('Google Workspace', 'Business Starter',
                                            Decimal('36.00'))])


def _rate_down_but_ringgit(amount, currency, on_date):
    """The rate service is down; a ringgit bill still needs no rate (as `fx` short-circuits it)."""
    if currency == 'MYR':
        return amount, Decimal('1'), on_date
    raise fx.RateUnavailable('ECB unreachable')


class TestTheDriveDoor(TestCase):
    def test_the_dry_run_writes_nothing(self):
        with _Drive([_invoice()]):
            out = _run('--drive')
        self.assertEqual(PlatformCost.objects.count(), 0)
        self.assertIn('would be written', out)

    def test_apply_writes_the_bill_once_and_a_second_run_writes_nothing(self):
        with _Drive([_invoice()]):
            first = _run('--drive', '--apply')
        self.assertIn('1 ledger rows written', first)
        row = PlatformCost.objects.get()
        self.assertEqual(row.amount_myr, Decimal('42.00'))
        stamp = row.updated_at

        with _Drive([_invoice()]):
            second = _run('--drive', '--apply')
        self.assertIn('0 ledger rows written', second)
        self.assertEqual(PlatformCost.objects.count(), 1)
        row.refresh_from_db()
        self.assertEqual(row.updated_at, stamp)   # not even re-saved

    def test_a_rerun_with_no_exchange_rate_cannot_blank_a_good_figure(self):
        with _Drive([_invoice()]):
            _run('--drive', '--apply')
        with _Drive([_invoice()], rate=_rate_down):
            _run_failing(self, '--drive', '--apply')   # the outage is reported as a failed run
        row = PlatformCost.objects.get()
        self.assertEqual(row.amount_myr, Decimal('42.00'))
        self.assertEqual(row.fx_rate, RATE)

    def test_a_second_bill_claiming_the_same_line_is_reported_not_swapped_in(self):
        with _Drive([_invoice('MTSOJA-2026-10', '10.00'), _invoice('OTHER-REF', '99.00')]):
            out = _run('--drive', '--apply')
        row = PlatformCost.objects.get()
        self.assertEqual(row.invoice_ref, 'MTSOJA-2026-10')
        self.assertEqual(row.amount_original, Decimal('10.00'))
        self.assertIn('already in the ledger from invoice MTSOJA-2026-10, not OTHER-REF', out)

    def test_the_same_bill_with_a_different_figure_is_reported_not_swapped_in(self):
        with _Drive([_invoice(amount='10.00')]):
            _run('--drive', '--apply')
        with _Drive([_invoice(amount='12.00')]):
            out = _run('--drive', '--apply')
        self.assertIn('0 ledger rows written', out)
        row = PlatformCost.objects.get()
        self.assertEqual(row.amount_original, Decimal('10.00'))
        self.assertIn('from invoice MTSOJA-2026-10 is already in the ledger at USD 10.00, but this '
                      'copy says USD 12.00', out)

    def test_the_same_bill_with_the_same_figure_says_nothing(self):
        with _Drive([_invoice()]):
            _run('--drive', '--apply')
        with _Drive([_invoice()]):
            out = _run('--drive', '--apply')
        self.assertNotIn('  ! ', out)


class TestNoBlankFigureThroughTheDoor(TestCase):
    """A blank ringgit figure saved by the insert-only door would never be filled in, and the next
    month's invoice job would stop on fx_missing. So such a bill is skipped until it can carry one."""

    def test_an_unended_month_waits_then_goes_in_with_its_rate(self):
        # Still October: no closing rate yet, and none is even asked for.
        with _Drive([_invoice()], today=date(2026, 10, 20)):
            out = _run('--drive', '--apply')
            self.assertEqual(fx.to_myr.call_count, 0)
        self.assertIn('NOT saved - waiting for month end', out)
        self.assertIn('0 ledger rows written', out)
        self.assertEqual(PlatformCost.objects.count(), 0)

        # The last day itself still waits: the closing rate is not final until the day is over.
        with _Drive([_invoice()], today=date(2026, 10, 31)):
            out = _run('--drive', '--apply')
        self.assertIn('waiting for month end', out)
        self.assertEqual(PlatformCost.objects.count(), 0)

        # After the month ends: inserted once, with the rate.
        with _Drive([_invoice()], today=date(2026, 11, 2)):
            out = _run('--drive', '--apply')
        self.assertIn('1 ledger rows written', out)
        row = PlatformCost.objects.get()
        self.assertEqual(row.amount_myr, Decimal('42.00'))
        self.assertEqual(row.fx_rate, RATE)

        # And a rerun writes nothing.
        with _Drive([_invoice()], today=date(2026, 11, 3)):
            out = _run('--drive', '--apply')
        self.assertIn('0 ledger rows written', out)
        self.assertEqual(PlatformCost.objects.count(), 1)

    def test_an_unended_month_is_not_counted_in_the_dry_run_either(self):
        with _Drive([_invoice()], today=date(2026, 10, 20)):
            out = _run('--drive')
        self.assertIn('0 ledger rows would be written', out)
        self.assertIn('waiting for month end', out)

    def test_an_ended_month_with_the_rate_service_down_is_skipped_then_inserted(self):
        with _Drive([_invoice()], rate=_rate_down):
            out, err = _run_failing(self, '--drive', '--apply')
        self.assertIn('NOT saved - no USD->MYR closing rate for 2026-10-31', out)
        self.assertIn('1 bill(s) NOT saved', err)
        self.assertIn('twilio 2026-10 MTSOJA-2026-10', err)
        self.assertEqual(PlatformCost.objects.count(), 0)

        with _Drive([_invoice()]):
            _run('--drive', '--apply')   # the rate is back: no error, inserted
        self.assertEqual(PlatformCost.objects.get().amount_myr, Decimal('42.00'))

    def test_a_missing_rate_for_an_ended_month_fails_the_run_after_the_other_bills(self):
        # bill-0 (USD, October ended) cannot get a rate; bill-1 (ringgit) needs none.
        with _Drive([_invoice(), _myr_bill()], rate=_rate_down_but_ringgit):
            out, err = _run_failing(self, '--drive', '--apply')
        self.assertIn('1 ledger rows written', out)          # the summary still printed
        self.assertIn('1 bill(s) NOT saved', err)
        self.assertIn('bill-0.pdf', err)
        self.assertNotIn('bill-1.pdf', err)
        row = PlatformCost.objects.get()                     # the other bill went in
        self.assertEqual((row.source, row.amount_myr), ('workspace', Decimal('36.00')))

    def test_the_dry_run_also_fails_on_a_missing_rate_for_an_ended_month(self):
        with _Drive([_invoice()], rate=_rate_down):
            out, _err = _run_failing(self, '--drive')
        self.assertIn('0 ledger rows would be written', out)
        self.assertEqual(PlatformCost.objects.count(), 0)

    def test_waiting_for_month_end_alone_is_not_a_failure(self):
        # Still October: the USD bill waits (no rate is even asked for); the ringgit bill goes in.
        with _Drive([_invoice(), _myr_bill()], rate=_rate_down_but_ringgit,
                    today=date(2026, 10, 20)):
            out = _run('--drive', '--apply')                 # no CommandError
        self.assertIn('waiting for month end', out)
        self.assertIn('1 ledger rows written', out)
        self.assertEqual(PlatformCost.objects.get().source, 'workspace')

    def test_a_ringgit_bill_never_waits(self):
        bill = ParsedInvoice(source='workspace', invoice_ref='WS-2026-10', currency='MYR',
                             period_month='2026-10', total=Decimal('36.00'),
                             lines=[InvoiceLine('Google Workspace', 'Business Starter',
                                                Decimal('36.00'))])
        def myr(amount, currency, on_date):
            return amount, Decimal('1'), on_date

        with _Drive([bill], rate=myr, today=date(2026, 10, 20)):
            out = _run('--drive', '--apply')
        self.assertIn('1 ledger rows written', out)
        self.assertEqual(PlatformCost.objects.get().amount_myr, Decimal('36.00'))

    def test_no_folder_configured_refuses_and_writes_nothing(self):
        with patch.dict(os.environ, {supplier_bills.FOLDER_ENV: ''}):
            with self.assertRaises(CommandError):
                _run('--drive', '--apply')
        self.assertEqual(PlatformCost.objects.count(), 0)

    def test_an_unreadable_folder_is_not_an_empty_one(self):
        with patch.dict(os.environ, FOLDER), \
                patch.object(supplier_bills, 'drive_pdfs', return_value=None):
            with self.assertRaisesMessage(CommandError, 'Could not read the Drive folder'):
                _run('--drive', '--apply')

    def test_drive_pdfs_is_none_when_workspace_is_off(self):
        with patch.object(supplier_bills, '_drive', return_value=None):
            self.assertIsNone(supplier_bills.drive_pdfs('05 Billing'))

    def test_pdf_text_reads_bytes_as_well_as_a_path(self):
        from pypdf import PdfWriter
        writer, buf = PdfWriter(), io.BytesIO()
        writer.add_blank_page(width=200, height=200)
        writer.write(buf)
        self.assertEqual(invoice_parsers.pdf_text(buf.getvalue()), '')

    def test_one_of_dir_or_drive_is_required(self):
        with self.assertRaises(CommandError):
            _run('--apply')


class TestTheDirPathIsUnchanged(TestCase):
    def test_dir_still_corrects_an_existing_line(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'bill.pdf').write_bytes(b'%PDF-fake')
            with _Drive([_invoice(amount='10.00')]):
                _run('--dir', d, '--apply')
            with _Drive([_invoice(amount='12.00')]):
                _run('--dir', d, '--apply')
        row = PlatformCost.objects.get()
        self.assertEqual(row.amount_original, Decimal('12.00'))   # upsert, as it always was


@override_settings(CRON_SECRET='', CRON_FAMILY_SECRETS={
    'money': 'k-money', 'paid': 'k-paid', 'email': 'k-email', 'maintenance': 'k-maint'})
class TestTheCronDoor(TestCase):
    def test_both_doors_are_money_jobs_with_fixed_flags(self):
        self.assertEqual(CronRunView.JOBS['supplier-bills-import'],
                         ('import_invoices', ('--drive', '--apply')))
        self.assertEqual(CronRunView.JOBS['supplier-bills-report'],
                         ('import_invoices', ('--drive',)))
        self.assertEqual(cron_auth.JOB_FAMILY['supplier-bills-import'], 'money')
        self.assertEqual(cron_auth.JOB_FAMILY['supplier-bills-report'], 'money')

    def test_the_door_is_shut_without_the_money_key(self):
        client = APIClient()
        for header in ('', 'k-maint', 'k-email'):
            r = client.post('/api/v1/internal/cron/supplier-bills-import/',
                            HTTP_X_CRON_SECRET=header)
            self.assertEqual(r.status_code, 403, header)
        self.assertEqual(PlatformCost.objects.count(), 0)

    def test_the_report_door_ignores_an_apply_in_the_request(self):
        client = APIClient()
        with _Drive([_invoice()]):
            r = client.post('/api/v1/internal/cron/supplier-bills-report/?apply=1',
                            {'apply': True, 'args': ['--apply']}, format='json',
                            HTTP_X_CRON_SECRET='k-money')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('error', r.json())
        self.assertEqual(PlatformCost.objects.count(), 0)

    def test_the_import_door_writes_once_across_two_calls(self):
        client = APIClient()
        for _ in range(2):
            with _Drive([_invoice()]):
                r = client.post('/api/v1/internal/cron/supplier-bills-import/',
                                HTTP_X_CRON_SECRET='k-money')
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('error', r.json())
        self.assertEqual(PlatformCost.objects.count(), 1)

    def test_a_missing_rate_for_an_ended_month_is_a_failed_run_at_the_door(self):
        # The door answers HTTP 200 whatever happens (a 5xx only makes Cloud Scheduler retry -
        # cron_health.run_job); the failure is the body's `error` and a FAILED run recorded for
        # the System health light.
        from apps.scholarship import system_health_store
        client = APIClient()
        with _Drive([_invoice(), _myr_bill()], rate=_rate_down_but_ringgit), \
                patch.object(system_health_store, 'record_cron') as record:
            r = client.post('/api/v1/internal/cron/supplier-bills-import/',
                            HTTP_X_CRON_SECRET='k-money')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn('1 bill(s) NOT saved', body['error'])
        self.assertNotIn('output', body)
        record.assert_called_once()
        self.assertEqual(record.call_args.args[:2], ('supplier-bills-import', False))
        self.assertEqual(PlatformCost.objects.get().source, 'workspace')   # the rest went in

    def test_waiting_for_month_end_is_a_successful_run_at_the_door(self):
        from apps.scholarship import system_health_store
        client = APIClient()
        with _Drive([_invoice()], today=date(2026, 10, 20)), \
                patch.object(system_health_store, 'record_cron') as record:
            r = client.post('/api/v1/internal/cron/supplier-bills-import/',
                            HTTP_X_CRON_SECRET='k-money')
        self.assertNotIn('error', r.json())
        self.assertEqual(record.call_args.args[:2], ('supplier-bills-import', True))
