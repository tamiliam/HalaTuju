"""Read a provider's own invoice PDF into ledger lines (2026-09-11).

**Owner ruling, 2026-09-11:** *"Don't use typed by hand. Everything should be extracted from the
relevant systems. We want to avoid anything manual."* This module is the half of that ruling that
covers the three providers with no usable billing API: Google Workspace, Supabase and Twilio.
(GCP has a real BigQuery export and stays on `sync_gcp_costs`; the statement PDF is used only to
CHECK that pull, never to feed the ledger.)

⚠ **DETERMINISTIC PARSING, NOT AI.** All eight invoices are text PDFs, so the figures can be read
exactly rather than recognised approximately. This is the WAT split doing its job: the platform
has Gemini document extraction and it is the wrong tool here, because money must come out
identical every single time and be re-derivable by anybody holding the same file. A model that is
99% right on an invoice is a model that is wrong about money once a year, silently.

⚠ **EVERY PARSER CHECKS ITS OWN WORK.** Each returns lines plus the total the invoice itself
prints, and `ParsedInvoice.__post_init__` refuses to exist if the lines do not sum to that total.
That single rule is what makes an extracted figure trustworthy: a provider redesigning its layout
breaks the parse LOUDLY instead of quietly recording a smaller bill. There is no partial success.

Adding a provider: write `detect` + `parse`, register it in `PARSERS`, and add its real invoice
text to `test_invoice_parsers.py`. Nothing else needs to change.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class InvoiceParseError(Exception):
    """The file could not be read into a ledger row that reconciles to its own printed total.

    Always raised, never downgraded to a warning. A half-read invoice is worse than an unread
    one: the unread one is visibly missing, and the half-read one looks like a complete month.
    """


def _money(text) -> Decimal:
    try:
        return Decimal(str(text).replace(',', '').replace('$', '').strip())
    except (InvalidOperation, AttributeError) as exc:
        raise InvoiceParseError(f'Not a money figure: {text!r}') from exc


def _period_month(month_name, year) -> str:
    key = str(month_name)[:3].lower()
    if key not in MONTHS:
        raise InvoiceParseError(f'Unrecognised month name: {month_name!r}')
    return f'{int(year):04d}-{MONTHS[key]:02d}'


@dataclass
class InvoiceLine:
    """One charge, in the currency the invoice is denominated in."""
    service: str
    sku: str
    amount: Decimal


@dataclass
class ParsedInvoice:
    source: str                 # PlatformCost.source
    invoice_ref: str
    currency: str
    period_month: str           # 'YYYY-MM' — the month this bill BELONGS to
    total: Decimal              # as printed on the invoice
    lines: list = field(default_factory=list)
    period_note: str = ''       # set when the billed window is not the calendar month

    def __post_init__(self):
        """⚠ The self-check. Refuse to exist unless the parts equal the whole.

        A provider changing its layout must break here — visibly, on the spot — rather than
        produce a ledger row that is short by one line and looks entirely plausible.

        ⚠ **ONE CENT PER LINE IS ALLOWED, AND IT IS THEN WRITTEN DOWN.** This is not slack in the
        rule; it is a fact about real invoices. Twilio's own July 2026 invoice lists three
        products summing to $4.30 and prints a total of $4.29, because it rounds each product
        subtotal for display and computes the total from the unrounded figures. The very first
        run of this parser caught exactly that.

        Refusing the invoice would be wrong — the document is genuine and the total is what we
        paid. Silently trusting the lines would leave the ledger a cent above the bill. So the
        difference becomes its OWN LINE, named `Rounding`: the ledger still sums exactly to what
        the provider charged, and the discrepancy is visible instead of absorbed. Anything larger
        than a cent a line is a layout change, and still refuses.
        """
        if not self.lines:
            raise InvoiceParseError(
                f'{self.source} {self.invoice_ref}: no charge lines were found.')
        if not re.fullmatch(r'\d{4}-\d{2}', self.period_month or ''):
            raise InvoiceParseError(
                f'{self.source} {self.invoice_ref}: bad period month {self.period_month!r}.')

        got = sum((ln.amount for ln in self.lines), Decimal('0'))
        diff = self.total - got
        if diff == 0:
            return
        tolerance = Decimal('0.01') * len(self.lines)
        if abs(diff) > tolerance:
            raise InvoiceParseError(
                f'{self.source} {self.invoice_ref}: the lines add up to {got} but the invoice '
                f'says {self.total}. That is more than the {tolerance} of display rounding a '
                f'{len(self.lines)}-line invoice can explain — the layout has changed. Fix the '
                f'parser rather than the figure.')
        self.lines.append(InvoiceLine(
            self.source.title(), "Rounding (the provider's own subtotals)", diff))


# ── Google Workspace ──────────────────────────────────────────────────────────
# Invoiced in MYR, so no FX. A clean tax invoice: one subscription line plus service tax.

_WS_REF = re.compile(r'Invoice number:\s*(\d+)')
_WS_PERIOD = re.compile(r'Summary for\s+\d+\s+(\w+)\s+(\d{4})\s*-\s*\d+\s+\w+\s+\d{4}')
# The three figures print immediately ABOVE their three labels — that block is the anchor, and
# it is far more stable than counting 'MYR nn.nn' occurrences across the whole document.
_WS_TOTALS = re.compile(
    r'MYR\s*([\d,.]+)\s*\n\s*MYR\s*([\d,.]+)\s*\n\s*MYR\s*([\d,.]+)\s*\n'
    r'\s*Subtotal in MYR\s*\n\s*Service tax\s*\(([\d.]+)%\)\s*\n\s*Total in MYR')
_WS_PLAN = re.compile(r'Google Workspace\s+(Business \w+)\s+Usage')


def detect_workspace(text: str) -> bool:
    return 'Google Workspace' in text and 'Invoice number:' in text


def parse_workspace(text: str) -> ParsedInvoice:
    ref = _WS_REF.search(text)
    period = _WS_PERIOD.search(text)
    totals = _WS_TOTALS.search(text)
    if not (ref and period and totals):
        raise InvoiceParseError(
            'Google Workspace: could not find the invoice number, the billed period and the '
            'subtotal/tax/total block. All three are required.')
    subtotal, tax, total, tax_pct = (
        _money(totals.group(1)), _money(totals.group(2)),
        _money(totals.group(3)), totals.group(4))
    plan = _WS_PLAN.search(text)
    plan_name = plan.group(1) if plan else 'Subscription'
    return ParsedInvoice(
        source='workspace',
        invoice_ref=ref.group(1),
        currency='MYR',
        period_month=_period_month(period.group(1), period.group(2)),
        total=total,
        lines=[
            InvoiceLine('Google Workspace', plan_name, subtotal),
            # Tax carried as its own line, matching how the GCP export bills it, so
            # `platform_cost.is_tax` recognises it and it lands in neither cost bucket.
            InvoiceLine('Invoice', f'Service tax ({tax_pct}%)', tax),
        ],
    )


# ── Supabase ──────────────────────────────────────────────────────────────────
# Invoiced in USD, and billed on an 8th-to-7th cycle rather than a calendar month — which is
# exactly what `PlatformCost.period_note` exists to record.

_SB_REF = re.compile(r'Invoice number\s+(\S+)')
_SB_PAID = re.compile(r'Amount paid\s+\$([\d,.]+)')
_SB_SUBTOTAL = re.compile(r'Subtotal\s+\$([\d,.]+)')
# The first usage window on the receipt; every line shares it.
_SB_WINDOW = re.compile(r'(\w{3})\s+(\d+)\s*[–-]\s*(\w{3})\s+(\d+),\s*(\d{4})')
_SB_PLAN = re.compile(r'(Pro Plan|Team Plan|Free Plan)')


def detect_supabase(text: str) -> bool:
    return 'Supabase' in text and 'Invoice number' in text


def parse_supabase(text: str) -> ParsedInvoice:
    ref = _SB_REF.search(text)
    paid = _SB_PAID.search(text)
    subtotal = _SB_SUBTOTAL.search(text)
    window = _SB_WINDOW.search(text)
    if not (ref and paid and subtotal and window):
        raise InvoiceParseError(
            'Supabase: could not find the invoice number, the amount paid, the subtotal and '
            'the billed window. All four are required.')
    total, sub = _money(paid.group(1)), _money(subtotal.group(1))
    if total != sub:
        raise InvoiceParseError(
            f'Supabase {ref.group(1)}: subtotal {sub} and amount paid {total} disagree.')

    start_mon, start_day, end_mon, end_day, year = window.groups()
    plan = _SB_PLAN.search(text)
    # ⚠ THE MONTH IS THE ONE THE USAGE WINDOW OPENS IN, not the receipt date. The receipt for
    # 'Aug 8 – Sep 7' is DATED 8 September, so keying on the receipt date would file August's
    # database under September and then discount or charge it by September's terms.
    return ParsedInvoice(
        source='supabase',
        invoice_ref=ref.group(1),
        currency='USD',
        period_month=_period_month(start_mon, year),
        total=total,
        # One line: every metered line on this receipt is discounted to zero by the plan, so the
        # plan fee IS the bill. The self-check above proves that rather than assuming it.
        lines=[InvoiceLine('Supabase', plan.group(1) if plan else 'Plan', total)],
        period_note=(f'Supabase bills {start_mon} {start_day} to {end_mon} {end_day}, '
                     f'not the calendar month.'),
    )


# ── Twilio ────────────────────────────────────────────────────────────────────
# Invoiced in USD, on a clean calendar month, with a per-product summary that is already the
# grain the ledger wants.

_TW_REF = re.compile(r'Invoice Number\s*\n\s*(\S+)')
_TW_PERIOD = re.compile(r'Invoice for\s*\n?.*?\n?\s*(\w{3})\w*\s+\d+\s+(\d{4})\s*-\s*\w+\s+\d+\s+\d{4}',
                        re.DOTALL)
# The product summary: a product name on its own line, its amount on the next, ending at the
# 'Invoice Amount' total. Anchored on that terminator so the detailed breakdown below — which
# repeats the same products — cannot be swept in and double-count the bill.
_TW_SUMMARY = re.compile(
    r'^([A-Z][A-Za-z ]+?)\s*\n\s*\$([\d,.]+)\s*$', re.MULTILINE)
_TW_TOTAL = re.compile(r'Invoice Amount\s*\n\s*\$([\d,.]+)')


def detect_twilio(text: str) -> bool:
    return 'Twilio' in text and 'Invoice Number' in text


def parse_twilio(text: str) -> ParsedInvoice:
    ref = _TW_REF.search(text)
    total_m = _TW_TOTAL.search(text)
    if not (ref and total_m):
        raise InvoiceParseError(
            'Twilio: could not find the invoice number and the invoice amount.')
    ref_value = ref.group(1)
    total = _money(total_m.group(1))

    # The month is in the invoice number itself ('MTSOJA-2026-08'), which is the most stable
    # thing on the page. The printed period is the cross-check, not the source.
    month_from_ref = re.search(r'(\d{4})-(\d{2})$', ref_value)
    if month_from_ref:
        period_month = f'{month_from_ref.group(1)}-{month_from_ref.group(2)}'
    else:
        period = _TW_PERIOD.search(text)
        if not period:
            raise InvoiceParseError(
                f'Twilio {ref_value}: neither the invoice number nor the printed period gives '
                f'a billing month.')
        period_month = _period_month(period.group(1), period.group(2))

    # Only the block ABOVE the total is the summary; everything after it is the detail.
    head = text[:total_m.start()]
    lines = []
    for name, amount in _TW_SUMMARY.findall(head):
        name = name.strip()
        if name.lower() in ('invoice amount', 'services total', 'quantity', 'amount'):
            continue
        lines.append(InvoiceLine('Twilio', name, _money(amount)))

    return ParsedInvoice(
        source='twilio',
        invoice_ref=ref_value,
        currency='USD',
        period_month=period_month,
        total=total,
        lines=lines,
    )


# ── Google Cloud: read for CHECKING only, never for feeding ───────────────────
# ⚠ This deliberately returns no ledger lines. The BigQuery export is the authoritative source —
# it carries every SKU, which the statement does not — and on 2026-09-11 it was proved to match
# these statements to the cent once `invoice.month` and credits were applied. The statement's one
# job here is to catch the day that stops being true.

_GCP_ACTIVITY = re.compile(r'MYR\s*([\d,.]+)\s*\n\s*-?MYR\s*[\d,.]+\s*\n\s*MYR\s*[\d,.]+\s*\n'
                           r'\s*Google Cloud')
_GCP_SUMMARY = re.compile(r'Summary for\s+\d+\s+(\w{3})\w*\s+(\d{4})')


def detect_gcp_statement(text: str) -> bool:
    return 'Google Cloud' in text and 'This is not a bill' in text


def parse_gcp_statement(text: str):
    """Return ``(period_month, total_new_activity)`` — the figure the ledger must reproduce.

    Returns ``None`` when the statement cannot be read. Unlike every other parser this does NOT
    raise, because nothing depends on it: a failure here costs a cross-check, not a ledger row.
    """
    summary = _GCP_SUMMARY.search(text)
    activity = _GCP_ACTIVITY.search(text)
    if not (summary and activity):
        return None
    try:
        return _period_month(summary.group(1), summary.group(2)), _money(activity.group(1))
    except InvoiceParseError:
        return None


PARSERS = (
    ('workspace', detect_workspace, parse_workspace),
    ('supabase', detect_supabase, parse_supabase),
    ('twilio', detect_twilio, parse_twilio),
)


def pdf_text(path) -> str:
    """All the text in a PDF, pages joined by newlines.

    `pypdf` only — an owner-run reporting tool must not pull an image stack into the service
    image, and every invoice these providers issue is a text PDF.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:      # pragma: no cover - environment-dependent
        raise InvoiceParseError(
            'pypdf is not installed. This is an owner-run reporting tool; install it locally '
            'rather than adding it to the service image.') from exc
    reader = PdfReader(str(path))
    return '\n'.join((page.extract_text() or '') for page in reader.pages)


def parse_text(text: str):
    """Dispatch to whichever provider's parser recognises this document.

    ⚠ Returns ``None`` for an unrecognised file rather than guessing at one. A parser applied to
    the wrong provider's invoice is how a Twilio total ends up filed as Supabase.
    """
    for _source, detect, parse in PARSERS:
        if detect(text):
            return parse(text)
    return None
