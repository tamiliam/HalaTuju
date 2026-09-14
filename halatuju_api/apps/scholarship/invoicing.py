"""Tenant invoices and receipts — issue, send, void, record payment (2026-09-14).

`platform_cost.charge_for` answers "what WOULD this organisation be charged for a month?" and
answers it fresh on every call. This module turns one of those answers into a bill: a numbered
document, frozen at the moment of issue, that a later rate change or a late ledger row can never
rewrite.

Owner rulings, 2026-09-14:

* **Issued on the 15th, for the PREVIOUS calendar month.** Suppliers bill late — Supabase's
  invoice runs 8th-to-8th, and on the last day of a month its cost is simply not known. The 15th
  is the first day a month's real cost reliably exists. `issue_monthly_invoices` runs then.
* **Held, not sent.** Issuing creates the invoice; nothing leaves the building until a super
  presses Send. A tenant does not SEE an invoice until it has been sent — showing it on their
  screen first would be sending it by another door.

⚠ **REFUSE, NEVER GUESS** — the rule `BillingRate` already follows, applied to a whole invoice.
`readiness` lists everything that would make the month's figure wrong or unprintable. Some of it
is absolute (the month has not closed; no issuer is set) and some a super may override with a
written reason (a supplier that billed last month has not billed this one — perhaps the service
really was cancelled). The monthly job NEVER overrides: an unattended run that under-bills is the
exact failure this module exists to stop.
"""
import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')

#: A real calendar month. `2026-00` must not slip through: index -1 would print it as December.
MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

#: The day of the month the previous month's invoices are issued (owner, 2026-09-14). The Cloud
#: Scheduler job fires on this day; `readiness` warns about any earlier issue of that month.
ISSUE_DAY = 15

MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
               'September', 'October', 'November', 'December')


class InvoicingError(Exception):
    """A request that cannot be carried out, with a stable code for the API to return."""

    def __init__(self, code, message=''):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class InvoiceRefused(InvoicingError):
    """Issuing was refused. `problems` is the full `readiness` list, so the caller can show
    every reason at once rather than one per attempt."""

    def __init__(self, problems):
        super().__init__('invoice_refused', '; '.join(p['message'] for p in problems))
        self.problems = problems


# ── Months (TD-209: always Malaysian local time) ─────────────────────────────

def _today(today=None):
    # ⚠ `localdate`, never `now().date()`. Stored times are UTC; at 00:30 on 15 October in
    # Malaysia it is still 14 October in UTC, and the job would bill the wrong month's cut-off.
    return today or timezone.localdate()


def month_of(d):
    return f'{d.year:04d}-{d.month:02d}'


def shift_month(period_month, delta):
    year, mon = (int(x) for x in str(period_month).split('-'))
    index = year * 12 + (mon - 1) + delta
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def previous_month(today=None):
    """The month the 15th's run bills: the calendar month before today's."""
    return shift_month(month_of(_today(today)), -1)


def month_label(period_month):
    year, mon = (int(x) for x in str(period_month).split('-'))
    return f'{MONTH_NAMES[mon - 1]} {year}'


# ── Numbering ────────────────────────────────────────────────────────────────

def next_number(kind, year):
    """The next gap-free number for a document kind in a year, e.g. 'INV-2026-0007'.

    MUST be called inside the transaction that creates the document: the counter row is locked
    with `select_for_update`, so a rolled-back issue rolls the counter back and never burns a
    number, and two concurrent issues cannot draw the same one.
    """
    from .models import BillingSequence

    if not transaction.get_connection().in_atomic_block:
        raise InvoicingError('numbering_outside_transaction',
                             'A document number must be drawn inside the issuing transaction.')
    seq, _ = BillingSequence.objects.get_or_create(kind=kind, year=year)
    seq = BillingSequence.objects.select_for_update().get(pk=seq.pk)
    seq.last += 1
    seq.save(update_fields=['last'])
    return f'{kind}-{year:04d}-{seq.last:04d}'


# ── Who bills, who is billed ─────────────────────────────────────────────────

def issuer():
    """The single issuer row, or an unsaved blank one. Never creates a row on read."""
    from .models import InvoiceIssuer
    return InvoiceIssuer.objects.order_by('id').first() or InvoiceIssuer()


def billing_details(organisation):
    from .models import OrgBillingDetails
    return (OrgBillingDetails.objects.filter(organisation=organisation).first()
            or OrgBillingDetails(organisation=organisation))


# ── Readiness ────────────────────────────────────────────────────────────────

def _problem(code, message, overridable):
    return {'code': code, 'message': message, 'overridable': overridable}


def readiness(organisation, period_month, *, today=None):
    """Every reason this organisation's invoice for `period_month` should not be issued now.

    An empty list means ready. Each problem says whether a super may override it with a written
    reason; the monthly job overrides nothing.
    """
    from apps.courses.models import PartnerOrganisation

    from . import platform_cost
    from .models import Invoice, PlatformCost

    problems = []
    label = month_label(period_month)

    # ── Absolute: no reason makes these right ────────────────────────────────
    if not PartnerOrganisation.objects.tenants().filter(pk=organisation.pk).exists():
        # `.tenants()` — this table is dual-role and holds referral schools that are not customers.
        problems.append(_problem('not_a_tenant', f'{organisation.name} is not a tenant.', False))
        return problems
    if period_month >= month_of(_today(today)):
        problems.append(_problem(
            'month_not_closed',
            f'{label} has not ended, so its cost is not known yet.', False))
    elif period_month == previous_month(today) and _today(today).day < ISSUE_DAY:
        # The owner's cut-off. Overridable, because a month whose every bill is already in is a
        # month a super may reasonably close early — but never by the job, which runs ON the 15th.
        problems.append(_problem(
            'before_cutoff',
            f'Invoices for {label} are issued from the {ISSUE_DAY}th, when every supplier bill '
            f'for the month should be in.', True))
    # org-fence: scoped to the one organisation the (super-only or job) caller named
    if Invoice.objects.filter(organisation=organisation, period_month=period_month,
                              voided_at__isnull=True).exists():
        problems.append(_problem(
            'already_issued', f'{organisation.name} already has an invoice for {label}.', False))
    missing_issuer = issuer().missing()
    if missing_issuer:
        problems.append(_problem(
            'issuer_incomplete',
            'Your own billing details are incomplete: ' + ', '.join(missing_issuer) + '.', False))
    missing_bill_to = billing_details(organisation).missing()
    if missing_bill_to:
        problems.append(_problem(
            'bill_to_incomplete',
            f'Billing details for {organisation.name} are incomplete: '
            + ', '.join(missing_bill_to) + '.', False))

    # ── The cost ledger: is the month's figure complete? ─────────────────────
    this_sources = set(PlatformCost.objects.filter(period_month=period_month)
                       .values_list('source', flat=True))
    if not this_sources:
        problems.append(_problem(
            'no_costs', f'No supplier costs are recorded for {label} yet.', True))
    else:
        # ⚠ SELF-MAINTAINING, NOT A HAND-KEPT LIST. Every supplier that billed the month before
        # is expected again. This is the check that catches the real failure: on 15 October,
        # Supabase's September PDF simply not having been imported yet, which would otherwise
        # produce a smaller, confident, wrong invoice.
        prev_sources = set(PlatformCost.objects.filter(period_month=shift_month(period_month, -1))
                           .values_list('source', flat=True))
        missing = sorted(prev_sources - this_sources)
        if missing:
            problems.append(_problem(
                'supplier_missing',
                f'These suppliers billed in {month_label(shift_month(period_month, -1))} but '
                f'have nothing recorded for {label}: ' + ', '.join(missing) + '.', True))
        totals = platform_cost.month_totals(period_month)
        if not totals['is_complete']:
            held = sorted({u['source'] for u in totals['unconverted']})
            problems.append(_problem(
                'fx_missing',
                f'Some {label} costs have no ringgit value yet (no exchange rate): '
                + ', '.join(held) + '.', True))

    # ── The charge itself ────────────────────────────────────────────────────
    charge = platform_cost.charge_for(organisation, period_month)
    for b in charge['blocked']:
        problems.append(_problem('charge_blocked', b['reason'], True))

    unbilled = [u for u in platform_cost.unbilled_request_hours(organisation)
                if u['worked_month'] == period_month]
    if unbilled:
        hours = sum((Decimal(u['hours']) for u in unbilled), Decimal('0'))
        problems.append(_problem(
            'unbilled_hours',
            f'{len(unbilled)} finished request(s) worked in {label} ({hours} hours) are not '
            f'recorded as billable hours yet.', True))
    return problems


# ── Issuing ──────────────────────────────────────────────────────────────────

def _share_note(line):
    share = line.get('share_pct')
    if share is None or Decimal(share) >= Decimal('100'):
        return ''
    return f' (your share: {Decimal(share).normalize():f}%)'


def build_lines(charge, period_month):
    """The frozen, tenant-safe lines for a charge. Carries NO cost and NO margin.

    ⚠ Checks its own arithmetic before returning, the way `invoice_parsers.ParsedInvoice` refuses
    to exist unless its lines reach the printed total: if the lines do not add up to the charge's
    subtotal, an invoice that does not add up must not be issued.
    """
    label = month_label(period_month)
    out = []
    for ln in charge['lines']:
        cat = ln['category']
        if cat == 'infrastructure':
            out.append({'category': cat, 'quantity': None, 'unit_amount_myr': None,
                        'description': f'Platform infrastructure, {label}{_share_note(ln)}',
                        'amount_myr': ln['amount_myr']})
        elif cat == 'metered':
            out.append({'category': cat, 'quantity': None, 'unit_amount_myr': None,
                        'description': (f'Metered usage (AI, document reading, email and '
                                        f'messaging), {label}{_share_note(ln)}'),
                        'amount_myr': ln['amount_myr']})
        elif cat == 'development':
            for d in ln.get('detail', []):
                out.append({'category': cat, 'quantity': d['hours'],
                            'unit_amount_myr': ln['billed_rate_myr'],
                            'description': (d['module'] or 'Development')[:300],
                            'amount_myr': d['amount_myr']})
    total = sum((Decimal(x['amount_myr']) for x in out), Decimal('0.00'))
    if total != Decimal(charge['subtotal_myr']):
        raise InvoicingError(
            'lines_do_not_add_up',
            f'The invoice lines add up to RM{total} but the charge is RM{charge["subtotal_myr"]}.')
    return out


def issue_invoice(organisation, period_month, *, issued_by_email='', override_reason='',
                  today=None):
    """Issue ONE invoice, or raise `InvoiceRefused` with every reason it cannot be.

    `override_reason` lets a super issue past the overridable problems; it is refused when blank
    and it is stored on the invoice together with the warnings it overrode.
    """
    from . import platform_cost
    from .models import Invoice, InvoiceLine

    today = _today(today)
    problems = readiness(organisation, period_month, today=today)
    absolute = [p for p in problems if not p['overridable']]
    overridable = [p for p in problems if p['overridable']]
    override_reason = (override_reason or '').strip()
    if absolute or (overridable and not override_reason):
        raise InvoiceRefused(problems)

    charge = platform_cost.charge_for(organisation, period_month)
    lines = build_lines(charge, period_month)
    who = issuer()
    bill_to = billing_details(organisation)

    stored_override = ''
    if overridable:
        stored_override = (override_reason + '\n\nIssued despite: '
                           + ' | '.join(p['message'] for p in overridable))

    try:
        with transaction.atomic():
            # org-fence: the organisation being issued for; super-only or the job
            replaces = (Invoice.objects
                        .filter(organisation=organisation, period_month=period_month,
                                voided_at__isnull=False)
                        .order_by('-voided_at').first())
            # org-fence: creates the invoice for the organisation named above
            invoice = Invoice.objects.create(
                number=next_number('INV', today.year),
                organisation=organisation,
                period_month=period_month,
                issued_on=today,
                due_on=today + timedelta(days=int(who.payment_terms_days or 0)),
                subtotal_myr=charge['subtotal_myr'],
                discount_pct=charge['discount_pct'],
                discount_myr=charge['discount_myr'],
                discount_reason=charge['discount_reason'],
                total_myr=charge['charged_myr'],
                issuer_snapshot=who.snapshot(),
                bill_to_snapshot=bill_to.snapshot(),
                issued_by_email=issued_by_email or '',
                override_reason=stored_override,
                replaces=replaces,
            )
            InvoiceLine.objects.bulk_create([
                InvoiceLine(invoice=invoice, position=i + 1, **ln) for i, ln in enumerate(lines)])
    except IntegrityError:
        # The one-live-invoice constraint: somebody issued the same month a moment ago.
        raise InvoiceRefused([_problem(
            'already_issued',
            f'{organisation.name} already has an invoice for {month_label(period_month)}.',
            False)])
    logger.info('invoicing: issued %s for org=%s month=%s total=RM%s%s',
                invoice.number, organisation.id, period_month, invoice.total_myr,
                ' (OVERRIDE)' if stored_override else '')
    return invoice


def issue_month(period_month=None, *, today=None):
    """The 15th's run: issue last month's invoice for every tenant that is ready.

    Never overrides. Returns a report; the caller logs it and alerts a person about refusals.
    Idempotent — a tenant already invoiced for the month is reported as skipped, never doubled.
    """
    from apps.courses.models import PartnerOrganisation

    from .models import Invoice

    today = _today(today)
    month = period_month or previous_month(today)
    report = {'month': month, 'issued': [], 'skipped': [], 'refused': []}
    for org in PartnerOrganisation.objects.tenants().order_by('name'):
        # Checked FIRST and on its own: an invoiced month still has whatever readiness warnings
        # it had when a super issued it past them, and re-reporting those every run would be an
        # alarm about a decision somebody already made.
        # org-fence: the monthly job walks every tenant by design; nothing here reaches a screen
        if Invoice.objects.filter(organisation=org, period_month=month,
                                  voided_at__isnull=True).exists():
            report['skipped'].append({'organisation': org.name})
            continue
        try:
            inv = issue_invoice(org, month, today=today)
            report['issued'].append({'organisation': org.name, 'number': inv.number,
                                     'total_myr': str(inv.total_myr)})
        except InvoiceRefused as exc:
            report['refused'].append({'organisation': org.name,
                                      'problems': [p['message'] for p in exc.problems]})
        except InvoicingError as exc:
            report['refused'].append({'organisation': org.name, 'problems': [exc.message]})
    return report


# ── After issue: send, void, receipts ────────────────────────────────────────

def send_invoice(invoice, *, sent_by_email=''):
    """Email the invoice PDF to the bill-to inboxes FROZEN on the invoice.

    ⚠ `sent_at` is written only AFTER the email went (the Vircle-alert lesson): marking it sent
    first would tell the tenant's screen, and the super, that a bill was delivered when the send
    failed. Re-sending is allowed — a lost email is ordinary — and updates the record.
    """
    from . import emails, invoice_pdf

    if invoice.voided_at:
        raise InvoicingError('invoice_void', 'A voided invoice cannot be sent.')
    to = [e for e in (invoice.bill_to_snapshot or {}).get('emails', []) if e]
    if not to:
        raise InvoicingError('no_recipients', 'This invoice has no billing email to send to.')
    pdf = invoice_pdf.invoice_pdf(invoice)
    if not emails.send_invoice_email(invoice, pdf, to):
        raise InvoicingError('send_failed', 'The email could not be sent. Nothing was marked sent.')
    invoice.sent_at = timezone.now()
    invoice.sent_by_email = sent_by_email or ''
    invoice.sent_to = to
    invoice.save(update_fields=['sent_at', 'sent_by_email', 'sent_to'])
    return invoice


def void_invoice(invoice, *, reason, voided_by_email=''):
    """Void an invoice. It is never edited; a replacement can then be issued for the month."""
    reason = (reason or '').strip()
    if not reason:
        raise InvoicingError('reason_required', 'Say why this invoice is being voided.')
    if invoice.voided_at:
        raise InvoicingError('invoice_void', 'This invoice is already void.')
    if invoice.receipts.exists():
        # Money has arrived against it. Voiding would leave a receipt pointing at a bill that no
        # longer exists; the money has to be dealt with first.
        raise InvoicingError('has_receipts',
                             'Payment has been recorded against this invoice, so it cannot be '
                             'voided.')
    invoice.voided_at = timezone.now()
    invoice.voided_by_email = voided_by_email or ''
    invoice.void_reason = reason
    invoice.save(update_fields=['voided_at', 'voided_by_email', 'void_reason'])
    logger.info('invoicing: voided %s (%s)', invoice.number, reason)
    return invoice


def _money(value):
    from decimal import InvalidOperation
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise InvoicingError('bad_amount', 'Enter the amount received, like 1552.50.')
    if amount != amount.quantize(TWO_PLACES) or amount <= 0:
        raise InvoicingError('bad_amount', 'Enter an amount above zero with at most two decimals.')
    return amount


def record_receipt(invoice, *, received_on, amount_myr, reference, method='bank_transfer',
                   note='', recorded_by_email='', today=None):
    """Record money that ARRIVED against an invoice, and number its receipt."""
    from .models import Invoice, InvoiceReceipt

    today = _today(today)
    reference = (reference or '').strip()
    if not reference:
        raise InvoicingError('reference_required',
                             'Enter the bank reference. A receipt records money that moved.')
    if method not in dict(InvoiceReceipt.METHOD_CHOICES):
        raise InvoicingError('bad_method', 'Choose how the money was paid.')
    if isinstance(received_on, str):
        try:
            received_on = date.fromisoformat(received_on)
        except ValueError:
            raise InvoicingError('bad_date', 'Enter the date the money arrived.')
    if not isinstance(received_on, date) or received_on > today:
        raise InvoicingError('bad_date', 'The date received cannot be in the future.')
    amount = _money(amount_myr)

    with transaction.atomic():
        # Lock the invoice so two receipts recorded at once cannot both fit under the balance.
        # org-fence: re-reads the invoice the fenced caller already resolved
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if locked.voided_at:
            raise InvoicingError('invoice_void', 'A voided invoice cannot take a payment.')
        balance = locked.balance()
        if amount > balance:
            raise InvoicingError(
                'overpayment',
                f'RM{amount} is more than the RM{balance} still owed on {locked.number}.')
        # org-fence: a receipt on the invoice locked above, never on another
        receipt = InvoiceReceipt.objects.create(
            number=next_number('RCP', received_on.year),
            invoice=locked, received_on=received_on, amount_myr=amount, method=method,
            reference=reference[:120], note=(note or '').strip(),
            recorded_by_email=recorded_by_email or '')
    logger.info('invoicing: receipt %s for %s RM%s', receipt.number, locked.number, amount)
    return receipt
