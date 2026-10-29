"""The two money terms applied AFTER a month's subtotal: the discount, and corrections.

Moves only, split out of `platform_cost.py` on 2026-10-29 because that file reached 646 lines
against the 600-line standard — and it had just LEFT the oversize ledger earlier the same day, so
re-adding it was not on offer (`docs/lessons.md`, TD-413). The standard asks for a split.

⚠ **THE ORDER THESE APPLY IN IS THE WHOLE REASON THEY LIVE TOGETHER.** A month reads:

    subtotal -> discount -> corrections -> charged

A discount is a PERCENTAGE of this month's work. A correction is a FIXED SUM putting right a bill
already sent (owner, 2026-10-29: *"When we have overcharged or undercharged, this should be
deducted or added (or written off) in the following month."*). So a correction must not be
discounted: doing so would quietly shrink a refund we already owe, and July's 100% discount would
have erased one entirely. Keeping both here makes that order one thing to read rather than two.

`platform_cost` imports this module and re-exports every name, so `platform_cost.charge_for` and
every existing `platform_cost.<name>` caller keep working unchanged.
"""
from decimal import Decimal


def corrections_for(organisation, period_month):
    """Corrections of EARLIER months that this month's invoice carries. Oldest first.

    ⚠ The owner's rule, 2026-10-29: *"When we have overcharged or undercharged, this should be
    deducted or added (or written off) in the following month."* An invoice already sent is never
    rewritten, so a mistake travels forward as its own line. `period_month` on the row is the month
    that CARRIES it, not the month that was wrong.
    """
    from .models import OrgBillingCorrection

    return (OrgBillingCorrection.objects
            .filter(organisation=organisation, period_month=period_month)
            .select_related('corrects_invoice')
            .order_by('id'))


def discount_block(subtotal, organisation, period_month):
    """The discount agreed for this month, as ``(pct, amount, reason, set_by)``.

    Extracted from `charge_for` beside `correction_block`, and for the same reason. Kept as a pair
    with it so the two money terms read alike at the call site and their ORDER is visible there:
    subtotal -> discount -> corrections -> charged.

    No discount reads as 0% and RM0.00 with an empty reason — never as a missing key, because the
    screen prints the line from the percentage and a month with none still has to render.
    """
    adj = adjustment_for(organisation, period_month)
    pct = adj.discount_pct if adj else Decimal('0.00')
    amount = (subtotal * pct / Decimal('100')).quantize(Decimal('0.01'))
    return pct, amount, (adj.reason if adj else ''), (adj.set_by_email if adj else '')


def correction_block(organisation, period_month):
    """The corrections this month carries, as ``(rows, signed_total)``.

    Extracted from `charge_for` on 2026-10-29 because that function reached 161 lines against a
    150-line limit, and the long-function ledger is frozen at what code health H4 found and may
    only shrink — so the standard asks for a named helper rather than a ledger entry.

    ⚠ **EACH CORRECTION KEEPS ITS OWN WORDS**, because each one goes on the tenant's invoice as
    its own line. A single netted figure would be a number nobody can explain six months later.
    The total is returned beside them so the caller does not re-derive it from the rows and get a
    different answer.

    ⚠ `set_by` is in these rows and must NOT reach a tenant. It is read by the super-only costs
    screen; `invoicing` freezes only `amount_myr`, `reason` and `corrects_invoice` onto the
    invoice, which is what both audiences read.
    """
    rows = list(corrections_for(organisation, period_month))
    payload = [{'id': c.id, 'amount_myr': c.amount_myr, 'reason': c.reason,
                'corrects_invoice': (c.corrects_invoice.number if c.corrects_invoice_id else ''),
                'set_by': c.set_by_email} for c in rows]
    return payload, sum((c.amount_myr for c in rows), Decimal('0.00'))


def adjustment_for(organisation, period_month):
    """The discount agreed for this organisation and this month, or None."""
    from .models import OrgBillingAdjustment

    return (OrgBillingAdjustment.objects
            .filter(organisation=organisation, period_month=period_month)
            .first())
