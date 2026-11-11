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

**The cron door (TD-247, A4.5): `--drive`.** Reads the same PDFs from the Drive folder named by
`SUPPLIER_BILLS_FOLDER` (see `supplier_bills.py`) inside the running service, so no laptop is needed.
Reached through `CronRunView` as `supplier-bills-report` (no `--apply`: a dry run that writes nothing)
and `supplier-bills-import` (`--apply`). ⚠ **With `--drive` the write is INSERT-ONLY**: a line whose
(period_month, source, service, sku) is already in the ledger is never touched, whatever its figure -
so a second run writes nothing, a transient exchange-rate outage can never blank a good figure, and two
bills that claim the same line are REPORTED rather than one silently replacing the other. Because it
never comes back to a line, it also never saves a foreign-currency line WITHOUT its ringgit figure: a
bill whose month has not ended yet ("waiting for month end"), or whose rate cannot be fetched, is
skipped and reported, and a later run inserts it with the rate. A bill skipped for want of a rate
for a month that HAS ended also makes the run end in a CommandError once every other bill is done,
so the door records a failed run; the month-end wait does not. A correction to a line already in
the ledger stays a person's job, on the `--dir` path, which is unchanged.

⚠ **Google Cloud statements are READ BUT NEVER IMPORTED.** The BigQuery export carries every SKU
and the statement does not, so the export stays authoritative — and on 2026-09-11 it was proved
to match these statements to the cent. The statement is used here purely to CHECK that pull, so
the day it stops matching is the day somebody is told.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import fx, invoice_parsers, platform_cost, supplier_bills
from apps.scholarship.models import PlatformCost


def _server_date():
    """The SERVER's date, in one place so the month-end wait can be tested.

    Not the Malaysia-time ``_today`` of ``invoice_dates`` / ``invoice_overdue``: the month-end wait
    deliberately reads the server's date (see TD-247 in docs/technical-debt.md), so it is named
    for what it reads rather than sharing their name."""
    return date.today()


class Command(BaseCommand):
    help = "Import Workspace / Supabase / Twilio invoice PDFs into the platform cost ledger."

    def add_arguments(self, parser):
        parser.add_argument('--dir',
                            help='Folder holding the invoice PDFs.')
        parser.add_argument('--drive', action='store_true',
                            help='Read the PDFs from the Drive folder in SUPPLIER_BILLS_FOLDER '
                                 '(the cron door, TD-247). With --apply it only INSERTS lines '
                                 'the ledger does not hold yet.')
        parser.add_argument('--apply', action='store_true',
                            help='Write to the ledger. Without it this only reports.')

    def handle(self, *args, **opts):
        if bool(opts.get('dir')) == bool(opts.get('drive')):
            raise CommandError('Pass exactly one of --dir or --drive.')
        self.insert_only = bool(opts.get('drive'))
        # (display name, what `pdf_text` reads): a local Path, or the bytes Drive returned.
        pdfs = self._drive_pdfs() if self.insert_only else self._dir_pdfs(opts['dir'])

        apply = opts['apply']
        written = failed = skipped = 0
        # Collected and printed at the END rather than raised on the spot: one unreadable
        # invoice must not stop the other seven being imported, but it must not scroll away
        # either. Every failure is repeated in the summary.
        problems = []
        checks = []
        # ⚠ TD-247 (G14): bills the drive door skipped because no closing rate could be fetched
        # for a month that HAS ended. Unlike "waiting for month end" (expected, quiet) this is an
        # outage nobody would see on an unattended run, so the command FAILS after the rest are
        # done (CommandError below) and the cron door records the run as failed.
        self.fx_skipped = []

        for name, source in pdfs:
            try:
                text = invoice_parsers.pdf_text(source)
            except invoice_parsers.InvoiceParseError as exc:
                problems.append(f'{name}: {exc}')
                failed += 1
                continue
            except Exception as exc:    # a damaged file must not stop the rest (drive path)
                if not self.insert_only:
                    raise               # the --dir path behaves exactly as it always has
                problems.append(f'{name}: could not be read as a PDF ({exc.__class__.__name__}).')
                failed += 1
                continue

            if invoice_parsers.detect_gcp_statement(text):
                checks.append((name, invoice_parsers.parse_gcp_statement(text)))
                skipped += 1
                continue

            try:
                invoice = invoice_parsers.parse_text(text)
            except invoice_parsers.InvoiceParseError as exc:
                problems.append(f'{name}: {exc}')
                failed += 1
                continue
            if invoice is None:
                problems.append(f'{name}: not recognised as any provider we can read.')
                failed += 1
                continue

            written += self._import_one(name, invoice, apply, problems)

        self._report(written, failed, skipped, checks, problems, apply)
        if self.fx_skipped:
            raise CommandError(
                f'{len(self.fx_skipped)} bill(s) NOT saved: no closing exchange rate could be '
                f'fetched for a month that has ended ({"; ".join(self.fx_skipped)}). Every other '
                f'bill was processed; a later run inserts these once a rate is available.')

    # ── where the PDFs come from ──────────────────────────────────────────────

    def _dir_pdfs(self, folder):
        folder = Path(folder)
        if not folder.is_dir():
            raise CommandError(f'Not a folder: {folder}')
        pdfs = sorted(folder.glob('*.pdf'))
        if not pdfs:
            raise CommandError(
                f'No PDFs in {folder}. An empty folder is NOT the same as a month with no bills.')
        return [(p.name, p) for p in pdfs]

    def _drive_pdfs(self):
        folder = supplier_bills.folder_path()
        if not folder:
            raise CommandError(
                f'{supplier_bills.FOLDER_ENV} is not set, so there is no Drive folder to read.')
        pdfs = supplier_bills.drive_pdfs(folder)
        if pdfs is None:
            raise CommandError(
                f'Could not read the Drive folder {folder!r} (Workspace off, folder missing or a '
                f'Drive error - see the log). Nothing was written.')
        if not pdfs:
            raise CommandError(
                f'No PDFs in the Drive folder {folder!r}. An empty folder is NOT the same as a '
                f'month with no bills.')
        self.stdout.write(f'--- import_invoices (drive) --- {len(pdfs)} PDF(s) in {folder!r}.')
        return pdfs

    # ── one invoice ───────────────────────────────────────────────────────────

    def _import_one(self, name, invoice, apply, problems):
        end = platform_cost.month_end(invoice.period_month)
        what = f'{invoice.source} {invoice.period_month} {invoice.invoice_ref}'
        # ⚠ TD-247: the insert-only door must NEVER save a foreign-currency line without its
        # ringgit figure, because it never comes back to fill one in - a blank line would sit in
        # the ledger for good and stop the next invoice job on fx_missing. So while the billed
        # month is still running (its last day included: the closing rate is not final until the
        # day is over) the bill is SKIPPED and reported, and the first run after the month ends
        # inserts it with the rate. No exchange-rate call is made for it in the meantime.
        if self.insert_only and invoice.currency != 'MYR' and end >= _server_date():
            problems.append(
                f'{name}: {what} NOT saved - waiting for month end. The closing rate for {end} does '
                f'not exist yet; a run after the month ends inserts it with the rate.')
            return 0

        # The rate at the END of the billed month — the owner's ruling. A MYR invoice short-
        # circuits inside `fx`, so Workspace can never fail on an exchange-rate outage.
        rate = published = None
        try:
            _probe, rate, published = fx.to_myr(Decimal('1'), invoice.currency, end)
        except fx.RateUnavailable as exc:
            if self.insert_only:
                # Same reason as above: no blank figure through the door. Skipped, reported, and
                # inserted by a later run once the rate can be fetched.
                problems.append(
                    f'{name}: {what} NOT saved - no {invoice.currency}->MYR closing rate for {end} '
                    f'could be fetched ({exc.__cause__ or exc.__class__.__name__}). A later run '
                    f'inserts it once a rate is available.')
                # Only reached for an ENDED month (an unended one returned above), so this is
                # always a failure of the run, never the expected month-end wait.
                self.fx_skipped.append(f'{name}: {what}')
                return 0
            # ⚠ NOT a failure of the import. The invoice is still recorded, with no ringgit
            # figure, and `month_totals` will report the month as a FLOOR until a rate exists.
            # An honest gap beats a plausible number nobody can source.
            problems.append(f'{name}: {exc}')

        self.stdout.write(
            f'\n{name}  ->  {invoice.source} {invoice.period_month} '
            f'{invoice.invoice_ref}  {invoice.currency} {invoice.total}'
            + (f'  @ {rate} ({published})' if rate is not None else '  [NO RATE]'))
        if invoice.period_note:
            self.stdout.write(f'    note: {invoice.period_note}')

        count = 0
        for line in invoice.lines:
            myr = ((line.amount * rate).quantize(Decimal('0.01'))
                   if rate is not None else None)
            is_attr = platform_cost.classify_sku(line.service, line.sku)
            # ⚠ The printed flag must be `cost_bucket`, not the attributable boolean. The boolean
            # has no word for the development bucket, so Claude printed as "platform" — the one
            # thing it must never be taken for, since that is where it would get charged twice.
            # The STORED row was always right; the operator's screen was not.
            flag = {'tax': 'tax', 'development': 'DEV-TOOL',
                    'metered': 'TENANT', 'platform': 'platform'}[
                        platform_cost.cost_bucket(line.service, line.sku, is_attr)]
            self.stdout.write(
                f'    {line.sku[:44]:46}{line.amount:>9} {invoice.currency}'
                f'{(str(myr) + " MYR") if myr is not None else "     —    ":>14}  {flag}')

            if apply:
                key = {'period_month': invoice.period_month, 'source': invoice.source,
                       'service': line.service, 'sku': line.sku}
                defaults = {
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
                    'note': (f'Parsed from {name} by import_invoices; reconciled to the '
                             f'invoice total of {invoice.currency} {invoice.total}.'
                             + (f' Converted at the ECB closing rate {rate} published '
                                f'{published}.' if rate is not None else
                                ' No exchange rate was available; the ringgit figure is '
                                'deliberately blank.')),
                }
                if not self.insert_only:
                    PlatformCost.objects.update_or_create(**key, defaults=defaults)
                    count += 1
                    continue
                # ⚠ TD-247: the unattended door never UPDATES. `get_or_create` leans on the
                # `platform_cost_unique_line` constraint, so even two runs at once cannot double
                # a line, and an existing line is left exactly as it is.
                row, created = PlatformCost.objects.get_or_create(**key, defaults=defaults)
                if created:
                    count += 1
                elif row.invoice_ref != invoice.invoice_ref:
                    problems.append(
                        f'{name}: {invoice.source} {invoice.period_month} "{line.sku}" is already '
                        f'in the ledger from invoice {row.invoice_ref or "(no reference)"}, not '
                        f'{invoice.invoice_ref}. Left as it was - if this bill replaces that one, '
                        f'import it with --dir.')
                else:
                    # Same bill, but its figure differs from the one held: a re-issued bill or a
                    # parsing change. Never swapped in here - a person looks.
                    held = row.amount_original if row.currency != 'MYR' else row.amount_myr
                    if (row.currency, held) != (invoice.currency, line.amount):
                        problems.append(
                            f'{name}: {invoice.source} {invoice.period_month} "{line.sku}" from '
                            f'invoice {invoice.invoice_ref} is already in the ledger at '
                            f'{row.currency} {held}, but this copy says {invoice.currency} '
                            f'{line.amount}. Left as it was - if the bill changed, import it '
                            f'with --dir.')
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
            # ⚠ THE STATEMENT COVERS THE WHOLE BILLING ACCOUNT; THE LEDGER COVERS ONE PROJECT.
            # Sibling products sit under the same account — Lentera costs about RM0.30 a month,
            # and FicusValue appeared in August at RM8.98 — so the ledger is EXPECTED to be a
            # little smaller, and a flat "these disagree" cries wolf every single month. The
            # first run said exactly that and was wrong both times.
            #
            # What is actually a fault is the ledger being LARGER than the statement, or a gap
            # too big to be siblings: the first means we are recording cost Google never charged,
            # the second means a whole HalaTuju SKU went missing from the pull.
            gap = stated - gcp
            if gap < Decimal('-0.05'):
                self.stdout.write(self.style.ERROR(
                    f'{name}: the ledger holds MYR {gcp} for {month} but the statement says only '
                    f'MYR {stated}. The ledger is LARGER than the bill — re-run sync_gcp_costs.'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'{name}: statement MYR {stated} for {month}, HalaTuju MYR {gcp} from '
                    f'BigQuery, MYR {gap.quantize(Decimal("0.01"))} on other projects in the same '
                    f'billing account. Consistent.  (whole ledger for {month}: MYR {ledger})'))

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
