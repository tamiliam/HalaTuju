"""When a tenant invoice is OVERDUE — the ONE rule (staff nudges, sprint 3, 2026-11-09).

Brief `docs/plans/2026-11-08-staff-nudges.md`, owner decision 5. Before this, the only answer lived in
the browser (`halatuju-web/src/lib/invoices.ts` `statusChip`: a `sent` row whose due date had passed),
so the console's red banner and the billing page's chip would have been two rules. Now both read the
flag this module serves; the web keeps no copy.

An invoice is overdue when ALL of these hold:

  * it was SENT (`sent_at`) — an issued invoice has not reached the tenant, so it cannot be late;
  * it is not VOID;
  * something is still owed: `balance() > 0` (a fully discounted month owes nothing and is never
    late; a part-paid one still owes the rest and DOES count);
  * no tenant payment declaration is OPEN (`has_open_payment_declaration`): the tenant has said it
    paid and the owner has not yet looked at the bank, so it is "being checked", not late. This
    holds even when part of the money has already arrived (status `part_paid`);
  * today is AFTER `due_on`, today being the Malaysian date (`timezone.localdate()`, TD-209; the
    project's TIME_ZONE is Asia/Kuala_Lumpur). On the due date itself it is not yet overdue. No
    grace period.

Days overdue = today - due_on, in whole days (so 1 on the day after the due date).

⚠ Read-only and a LEAF: it imports no view and writes nothing. Audit sprint A4.5 builds on it; the
existing `invoicing.py` functions are deliberately untouched. `amount_paid` and the declaration check
walk PREFETCHED rows, so pass invoices with `receipts` and `payment_declarations` prefetched.
"""
from decimal import Decimal

from django.utils import timezone


def _today(today=None):
    # ⚠ `localdate`, never `now().date()` (TD-209): at 00:30 in Kuala Lumpur it is still yesterday
    # in UTC, and an invoice would turn red a day late — or, the other way round, a day early.
    return today or timezone.localdate()


def is_overdue(inv, today=None):
    """Is this invoice overdue today? See the module docstring for the rule, clause by clause."""
    if inv.sent_at is None or inv.voided_at is not None:
        return False
    if not inv.due_on or _today(today) <= inv.due_on:
        return False
    if inv.balance() <= Decimal('0.00'):
        return False
    return not inv.has_open_payment_declaration()


def days_overdue(inv, today=None):
    """Whole days past the due date (0 when not overdue)."""
    return (_today(today) - inv.due_on).days if is_overdue(inv, today) else 0


def org_summary(organisation_id, today=None):
    """The organisation's overdue invoices in one line, for the console's red banner.

    → None when nothing is overdue (or no organisation), else::

        {'invoice_id', 'number', 'currency', 'balance_myr' (a STRING), 'due_on' (ISO),
         'days_overdue', 'count', 'more'}

    `number`, `balance_myr` and `days_overdue` describe the OLDEST overdue invoice (earliest due
    date, then earliest issued, then lowest id); `count` is how many are overdue and `more` is
    `count - 1`, the banner's "and N more".
    """
    if not organisation_id:
        return None
    from . import money
    from .models import Invoice
    day = _today(today)
    candidates = (Invoice.objects  # org-fence: narrowed to ONE organisation, sent and live, below
                  .filter(organisation_id=organisation_id, sent_at__isnull=False,
                          voided_at__isnull=True, due_on__lt=day)
                  .prefetch_related('receipts', 'payment_declarations')
                  .order_by('due_on', 'issued_on', 'id'))
    overdue = [inv for inv in candidates if is_overdue(inv, day)]
    if not overdue:
        return None
    oldest = overdue[0]
    return {
        'invoice_id': oldest.id,
        'number': oldest.number,
        'currency': oldest.currency,
        'balance_myr': money.format_money(oldest.balance(), blank=None, blank_when=money.BLANK_NONE,
                                          quantize=False, coerce=False),
        'due_on': oldest.due_on.isoformat(),
        'days_overdue': (day - oldest.due_on).days,
        'count': len(overdue),
        'more': len(overdue) - 1,
    }
