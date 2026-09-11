"""Read provider invoice PDFs into the platform cost ledger (2026-09-11).

    python manage.py import_invoices --dir "C:/Users/tamil/Downloads/Billing"
    python manage.py import_invoices --dir "..." --apply     # write the ledger

**Owner ruling, 2026-09-11:** *"Don't use typed by hand. Everything should be extracted from the
relevant systems. We want to avoid anything manual."* This command is that ruling for Google
Workspace, Supabase and Twilio — the three providers with no billing API we can reach.

Three properties, each of which is the reason a figure here can be trusted:

1. **Deterministic parsing, not AI.** Every invoice these providers issue is a text PDF, so the
   figures are READ rather than recognised. Money must come out identical every time.
2. **Each invoice reconciles to its own printed total** before it is allowed to become a row —
   see `invoice_parsers.ParsedInvoice.__post_init__`. A layout change breaks this loudly.
3. **The exchange rate is fetched, not typed** — the ECB closing rate for the last day of the
   billed month (owner's ruling), with the date it was actually published recorded on the row.

Idempotent: rows UPSERT on (period_month, source, service, sku), exactly like `sync_gcp_costs`,
so re-running a folder corrects it instead of doubling it.

⚠ **Google Cloud statements are READ BUT NEVER IMPORTED.** The BigQuery export carries every SKU
and the statement does not, so the export stays authoritative — and on 2026-09-11 it was proved
to match these statements to the cent. The statement is used here purely to CHECK that pull, so
the day it stops matching is the day somebody is told.
"""
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import fx, invoice_parsers, platform_cost
from apps.scholarship.models import PlatformCost


class Command(BaseCommand):
    help = "Import Workspace / Supabase / Twilio invoice PDFs into the platform cost ledger."

    def add_arguments(self, parser):
        parser.add_argument('--dir', required=True,
                            help='Folder holding the invoice PDFs.')
        parser.add_argument('--apply', action='store_true',
                            help='Write to the ledger. Without it this only reports.')

    def handle(self, *args, **opts):
        folder = Path(opts['dir'])
        if not folder.is_dir():
            raise CommandError(f'Not a folder: {folder}')
        pdfs = sorted(folder.glob('*.pdf'))
        if not pdfs:
            raise CommandError(
                f'No PDFs in {folder}. An empty folder is NOT the same as a month with no bills.')

        apply = opts['apply']
        written = failed = skipped = 0
        # Collected and printed at the END rather than raised on the spot: one unreadable
        # invoice must not stop the other seven being imported, but it must not scroll away
        # either. Every failure is repeated in the summary.
        problems = []
        checks = []

        for path in pdfs:
            try:
                text = invoice_parsers.pdf_text(path)
            except invoice_parsers.InvoiceParseError as exc:
                problems.append(f'{path.name}: {exc}')
                failed += 1
                continue

            if invoice_parsers.detect_gcp_statement(text):
                checks.append((path.name, invoice_parsers.parse_gcp_statement(text)))
                skipped += 1
                continue

            try:
                invoice = invoice_parsers.parse_text(text)
            except invoice_parsers.InvoiceParseError as exc:
                problems.append(f'{path.name}: {exc}')
                failed += 1
                continue
            if invoice is None:
                problems.append(f'{path.name}: not recognised as any provider we can read.')
                failed += 1
                continue

            written += self._import_one(path, invoice, apply, problems)

        self._report(written, failed, skipped, checks, problems, apply)

    # ── one invoice ───────────────────────────────────────────────────────────

    def _import_one(self, path, invoice, apply, problems):
        # The rate at the END of the billed month — the owner's ruling. A MYR invoice short-
        # circuits inside `fx`, so Workspace can never fail on an exchange-rate outage.
        rate = published = None
        try:
            _probe, rate, published = fx.to_myr(Decimal('1'), invoice.currency,
                                                platform_cost.month_end(invoice.period_month))
        except fx.RateUnavailable as exc:
            # ⚠ NOT a failure of the import. The invoice is still recorded, with no ringgit
            # figure, and `month_totals` will report the month as a FLOOR until a rate exists.
            # An honest gap beats a plausible number nobody can source.
            problems.append(f'{path.name}: {exc}')

        self.stdout.write(
            f'\n{path.name}  ->  {invoice.source} {invoice.period_month} '
            f'{invoice.invoice_ref}  {invoice.currency} {invoice.total}'
            + (f'  @ {rate} ({published})' if rate is not None else '  [NO RATE]'))
        if invoice.period_note:
            self.stdout.write(f'    note: {invoice.period_note}')

        count = 0
        for line in invoice.lines:
            myr = ((line.amount * rate).quantize(Decimal('0.01'))
                   if rate is not None else None)
            is_attr = platform_cost.classify_sku(line.service, line.sku)
            flag = ('tax' if platform_cost.is_tax(line.service, line.sku)
                    else ('TENANT' if is_attr else 'platform'))
            self.stdout.write(
                f'    {line.sku[:44]:46}{line.amount:>9} {invoice.currency}'
                f'{(str(myr) + " MYR") if myr is not None else "     —    ":>14}  {flag}')

            if apply:
                PlatformCost.objects.update_or_create(
                    period_month=invoice.period_month, source=invoice.source,
                    service=line.service, sku=line.sku,
                    defaults={
                        'currency': invoice.currency,
                        # The invoiced figure is kept in its OWN currency whatever happens, so a
                        # rate that arrives later can convert it without re-reading the PDF.
                        'amount_original': (line.amount if invoice.currency != 'MYR' else None),
                        'fx_rate': rate if invoice.currency != 'MYR' else None,
                        'amount_myr': myr,
                        'attributable': is_attr,
                        'provenance': 'extracted',
                        'invoice_ref': invoice.invoice_ref,
                        'period_note': invoice.period_note,
                        'note': (f'Parsed from {path.name} by import_invoices; reconciled to the '
                                 f'invoice total of {invoice.currency} {invoice.total}.'
                                 + (f' Converted at the ECB closing rate {rate} published '
                                    f'{published}.' if rate is not None else
                                    ' No exchange rate was available; the ringgit figure is '
                                    'deliberately blank.')),
                    })
                count += 1
        return count

    # ── the summary ───────────────────────────────────────────────────────────

    def _report(self, written, failed, skipped, checks, problems, apply):
        self.stdout.write('')
        for name, parsed in checks:
            if parsed is None:
                self.stdout.write(self.style.WARNING(
                    f'{name}: a Google Cloud statement, but its total could not be read.'))
                continue
            month, stated = parsed
            # ⚠ The cross-check reads the ledger, and a dry run must still be useful without a
            # database — the parse half is the valuable half. A failure here SAYS the check could
            # not run; it never quietly reports a pass.
            try:
                ledger = platform_cost.month_totals(month)['total_myr']
                gcp = sum((r.amount_myr or Decimal('0.00')) for r in
                          PlatformCost.objects.filter(period_month=month, source='gcp'))
            except Exception as exc:        # noqa: BLE001 - any DB failure, reported not hidden
                self.stdout.write(self.style.WARNING(
                    f'{name}: statement says MYR {stated} for {month}. The ledger could not be '
                    f'read, so this was NOT checked ({exc.__class__.__name__}).'))
                continue
            ok = abs(gcp - stated) <= Decimal('0.05')
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(
                f'{name}: statement says MYR {stated} for {month}; the ledger holds MYR {gcp} '
                f'from BigQuery. {"MATCHES." if ok else "THESE DISAGREE - re-run sync_gcp_costs."}'
                f'  (whole ledger for {month}: MYR {ledger})'))

        if problems:
            self.stdout.write('')
            for p in problems:
                self.stdout.write(self.style.ERROR(f'  ! {p}'))

        self.stdout.write('')
        self.stdout.write(
            f'{written} ledger rows {"written" if apply else "would be written"}, '
            f'{failed} file(s) could not be read, {skipped} statement(s) used as a check only.')
        if not apply:
            self.stdout.write(self.style.WARNING(
                'Report only - re-run with --apply to write.'))
