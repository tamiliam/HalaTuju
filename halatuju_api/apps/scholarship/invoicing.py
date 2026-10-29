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

from . import money
# ── Months, dates and numbering: lifted whole into `invoice_dates.py` ────────
# Moves only, when this file passed the 600-line standard. RE-EXPORTED rather than left behind,
# because `invoicing.month_label`, `invoicing.previous_month`, `invoicing.MONTH_RE` and
# `invoicing.next_number` are read from a dozen modules and tests: a split is not a rename.
from .invoice_dates import (  # noqa: F401  (re-export: see above)
    DAY_RE, ISSUE_DAY, MONTH_NAMES, MONTH_RE, _refuse_out_of_order, _today, issue_date_for,
    month_label, month_of, next_number, previous_month, shift_month,
)

logger = logging.getLogger(__name__)

#: The marker `platform_cost.request_module_tag` writes at the front of an `OrgBuildHours.module`.
_REQUEST_TAG_RE = re.compile(r'^\s*\[REQ-\d+\]\s*')


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

    # ⚠ ABSOLUTE, not overridable (owner, 2026-10-29): *"Make sure every feature has a quote and
    # acceptance from BrightPath."* A feature is priced work, so one the organisation never agreed
    # to is a charge for something nobody ordered. There IS a remedy — quote it and have it
    # accepted — so "issue it anyway" must not be on offer. Bugs and hand-typed hours are outside
    # this; see `request_hours.consent_gaps` for why.
    for gap in platform_cost.consent_gaps(organisation, period_month):
        problems.append(_problem(
            'feature_not_accepted',
            f'Request {gap["request_id"]} ("{gap["title"][:80]}") is billed as a feature in '
            f'{label} but is missing {gap["missing"]} from {organisation.name}.', False))

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


def printable_module(text):
    """What a development line SAYS on the invoice, from what the hours row STORES.

    ⚠ The stored `module` carries `[REQ-12]` at the front, and that tag is the only thing that lets
    `platform_cost.unbilled_request_hours` know the request has been billed — so it must stay in
    the database, untouched. It must not reach the paper. The owner read August's preview on
    2026-10-28 and the lines read like a bug tracker: *"[REQ-12] show year SPM was taken"*. The tag
    is stripped HERE, in the one place a frozen description is written, and nowhere else.

    The rest is whatever a super typed on the build-hours screen, so the wording is already theirs
    to edit; this removes only the part no customer should have to read.
    """
    return _REQUEST_TAG_RE.sub('', text or '').strip()


def _sub_description(detail, label):
    """What one request says as a sub-item: its own wording, then its request number in brackets.

    Owner, 2026-10-29: *"each feature request, too, include the req no in brackets."* The number
    comes back to the paper here — but at the END and in round brackets, which reads as a
    reference, rather than at the front in square ones, which read like a bug tracker and is what
    `printable_module` strips. The two are not in conflict: the stored `[REQ-12]` prefix is still
    never printed, and the suffix is composed from the id rather than from the stored text.

    The suffix is measured FIRST and the wording truncated around it, so a very long title can
    never push the number off the end of a 300-character column.
    """
    words = printable_module(detail['module']) or f'Development, {label}'
    if detail.get('request_id') is None:
        return words[:300]
    suffix = f' (REQ-{detail["request_id"]})'
    return f'{words[:300 - len(suffix)]}{suffix}'


def build_lines(charge, period_month):
    """The frozen, tenant-safe lines for a charge. Carries NO cost and NO margin.

    Development work is GROUPED (owner, 2026-10-29): a *"Feature requests"* parent carrying the
    group's hours, rate and amount, with one sub-item per request under it; and, when there were
    any, a *"Bug reports"* line carrying its hours at a rate of RM0.00 and no sub-items at all —
    *"these need not be itemised"*. Bugs are free because the 15% development margin already pays
    for them; see `platform_cost.development_charge`.

    ⚠ Checks its own arithmetic before returning, the way `invoice_parsers.ParsedInvoice` refuses
    to exist unless its lines reach the printed total: if the lines do not add up to the charge's
    subtotal, an invoice that does not add up must not be issued. Sub-items are summed TOO, even
    though each is RM0.00 by construction — the check is there to catch the day that stops being
    true, and skipping them would make a double-counted group invisible to it.
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
            detail = ln.get('detail', [])
            features = [d for d in detail if d.get('kind') != 'bug']
            bugs = [d for d in detail if d.get('kind') == 'bug']
            if features:
                out.append({
                    'category': cat,
                    'quantity': ln.get('feature_hours'),
                    'unit_amount_myr': ln['billed_rate_myr'],
                    'description': f'Feature requests, {label}'[:300],
                    'amount_myr': sum((Decimal(d['amount_myr']) for d in features),
                                      Decimal('0.00')),
                    # ⚠ A child's money is 0.00, always. The parent above carries the group's
                    # whole amount, so the Amount column still adds up to the subtotal.
                    '_children': [{'category': cat, 'quantity': d['hours'],
                                   'unit_amount_myr': None,
                                   'description': _sub_description(d, label),
                                   'amount_myr': Decimal('0.00')} for d in features],
                })
    # ⚠ THE BUG LINE IS COUNTED, AND IT SITS OUTSIDE THE LOOP ABOVE. Two reasons, both found by
    # the owner comparing the first invoice against the request list on 2026-10-29:
    #
    #   1. A bug is free, so nobody quotes one, so no hours row is ever recorded against it. A
    #      line that summed HOURS showed "2.0" for an August in which six bug reports were fixed.
    #      It now shows the COUNT, which is the thing we actually know.
    #   2. A month can have bug fixes and NO billable hours at all (July 2026). Inside the loop
    #      this line would never render for exactly those months.
    #
    # Hours and rate are left BLANK rather than printed as zero: we do not know the hours, and a
    # rate column on a line with no quantity says nothing. The RM0.00 in the amount is the point.
    fixed = charge.get('bug_reports_fixed') or {}
    count = int(fixed.get('count') or 0)
    if count:
        # ⚠ The hours go in the HOURS column only when they are known. October 2026 has ten fixed
        # bugs and no estimate on any of their current analyses: printing 0.0 there would read as
        # "ten bugs took no time", which is a confident lie. A blank says "not measured".
        out.append({
            'category': 'development',
            'quantity': fixed.get('hours'),
            'unit_amount_myr': Decimal('0.00'),
            'description': (f'Bug reports fixed, {label} — {count} '
                            f'{"report" if count == 1 else "reports"}, not charged')[:300],
            'amount_myr': Decimal('0.00'),
        })
    total = sum((Decimal(x['amount_myr']) for x in out), Decimal('0.00'))
    total += sum((Decimal(c['amount_myr']) for x in out for c in x.get('_children', [])),
                 Decimal('0.00'))
    if total != Decimal(charge['subtotal_myr']):
        raise InvoicingError(
            'lines_do_not_add_up',
            f'The invoice lines add up to RM{total} but the charge is RM{charge["subtotal_myr"]}.')
    return out


def issue_invoice(organisation, period_month, *, issued_by_email='', override_reason='',
                  issued_on=None, today=None):
    """Issue ONE invoice, or raise `InvoiceRefused` with every reason it cannot be.

    `override_reason` lets a super issue past the overridable problems; it is refused when blank
    and it is stored on the invoice together with the warnings it overrode.

    `issued_on` back-dates the printed issue date — see `issue_date_for` for the three bounds. It
    is checked EARLY and on its own: a mistyped date is one correction, and burying it under a list
    of readiness warnings would hide the only thing the person has to fix. Left out (the monthly
    job, and every ordinary Issue) it is today.

    ⚠ ONE READINESS PROBLEM IS CHECKED BEFORE THE DATE: a month that has not closed. Every date is
    'before the end of this month' while the month is still running, so the date check would answer
    *"October ends on the 31st"* — a correctable-looking sentence — in front of the real, absolute
    reason, which is that October's cost is not known yet.
    """
    from . import platform_cost
    from .models import Invoice, InvoiceLine

    today = _today(today)
    if period_month >= month_of(today):
        raise InvoiceRefused([p for p in readiness(organisation, period_month, today=today)
                              if p['code'] == 'month_not_closed'] or
                             [_problem('month_not_closed',
                                       f'{month_label(period_month)} has not ended, so its cost '
                                       f'is not known yet.', False)])
    issued = issue_date_for(period_month, issued_on, today)
    _refuse_out_of_order(issued)
    problems = readiness(organisation, period_month, today=today)
    absolute = [p for p in problems if not p['overridable']]
    overridable = [p for p in problems if p['overridable']]
    override_reason = (override_reason or '').strip()
    if absolute or (overridable and not override_reason):
        raise InvoiceRefused(problems)

    charge = platform_cost.charge_for(organisation, period_month)
    lines = build_lines(charge, period_month)
    if Decimal(charge['subtotal_myr']) <= 0:
        # ⚠ `build_lines` CANNOT catch this, and it is the SUBTOTAL that has to be tested, not the
        # lines and not the total:
        #   * an empty line list sums to zero, which equals the zero subtotal of a month with
        #     nothing in the ledger, so the lines-add-up self-check passes;
        #   * a month with no costs still produces two lines, each RM0.00 — a document that says
        #     "Platform infrastructure, August 2026 … RM0.00", which is not a bill either;
        #   * and the TOTAL is zero for July, which IS a real bill: it carries its lines in full
        #     and is reduced by a discount row that says so. That is the owner's July requirement
        #     and must keep working.
        # So: a real bill has something on it before any discount. Without this a super overriding
        # `no_costs` would mint a numbered, frozen, permanent document with nothing on it.
        raise InvoicingError(
            'nothing_to_bill',
            f'{month_label(period_month)} has nothing to bill — no costs and no hours — so there '
            f'is no invoice to issue.')
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
                # ⚠ The YEAR OF ISSUE, which for a back-dated invoice is the year printed on it,
                # not the year somebody pressed the button. January's invoice back-issued in a new
                # year must not carry the new year's sequence.
                number=next_number('INV', issued.year),
                organisation=organisation,
                period_month=period_month,
                issued_on=issued,
                due_on=issued + timedelta(days=int(who.payment_terms_days or 0)),
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
            # ⚠ Created one at a time, NOT bulk_create: a sub-item needs its parent's primary
            # key, and `bulk_create` only fills those in on some backends. `position` keeps
            # counting across both levels, so the document's order is held by one number and a
            # child always sorts straight after its parent.
            position = 0
            for ln in lines:
                children = ln.pop('_children', [])
                position += 1
                parent = InvoiceLine.objects.create(
                    invoice=invoice, position=position, **ln)
                for child in children:
                    position += 1
                    InvoiceLine.objects.create(
                        invoice=invoice, position=position, parent=parent, **child)
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


#: The two sentences the receipt box shows. One code, two messages: "that is not a number" and
#: "that number is not allowed" need different corrections, and the message is the only part of a
#: 400 the person reads.
_RECEIPT_UNREADABLE = 'Enter the amount received, like 1552.50.'
_RECEIPT_OUT_OF_RANGE = 'Enter an amount above zero with at most two decimals.'


def _receipt_amount(value):
    """Money that ARRIVED, as typed into the receipt box → `Decimal`. Above zero, at most two
    decimal places, and not rounded to get there — a receipt records a figure that moved through
    a bank, so a third decimal place is a typo to correct rather than a number to round.

    Was `_money` until code health H7; the mechanics moved to `money.parse_money`, which this
    hands its own code and its own two sentences."""
    try:
        return money.parse_money(value, places_exact=True, allow_zero=False,
                                 allow_negative=False)
    except money.MoneyError as exc:
        raise InvoicingError('bad_amount', _RECEIPT_UNREADABLE if exc.reason == 'syntax'
                             else _RECEIPT_OUT_OF_RANGE)


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
    if received_on < invoice.issued_on:
        # ⚠ Money cannot arrive before the bill exists. This was unreachable while every invoice
        # was dated the day it was issued; back-dating (2026-10-28) is what opens it, because the
        # owner is now recording July, August and September money against invoices that carry
        # July, August and September dates, where a month-out typo no longer looks absurd.
        raise InvoicingError(
            'received_before_issued',
            f'{invoice.number} is dated {invoice.issued_on.isoformat()}, so it cannot have been '
            f'paid on {received_on.isoformat()}.')
    amount = _receipt_amount(amount_myr)

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
