"""When an invoice is dated, and what it is numbered (2026-10-28).

Lifted out of `invoicing.py`, moves only, when that file passed the 600-line standard while the
back-issue rules were being added. The guard asks for a SPLIT, not for prose to be trimmed until
the number passes (docs/lessons.md).

One subject, and the two halves are the same subject: **the number follows the date.**
`Invoice.number` is *"numbered by the year of issue"*, so the moment the printed date became
settable (owner, 2026-10-28, back-issuing July and August) every rule about which date is allowed
became a rule about which run of numbers is opened. They are read together or not at all.

⚠ TD-209 runs through all of it: `timezone.localdate()`, never `now().date()`. Stored times are
UTC; at 00:30 on 15 October in Malaysia it is still 14 October in UTC, and the monthly job would
bill the wrong month's cut-off.

Imports `InvoicingError` lazily, at the point each refusal is raised, so this module stays a LEAF
and `invoicing` can import it at the top of the file.
"""
import re
from datetime import date, datetime, timedelta

from django.db import transaction
from django.utils import timezone


MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
               'September', 'October', 'November', 'December')

#: A real calendar month. `2026-00` must not slip through: index -1 would print it as December.
MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

#: The day of the month the previous month's invoices are issued (owner, 2026-09-14). The Cloud
#: Scheduler job fires on this day; `readiness` warns about any earlier issue of that month.
ISSUE_DAY = 15

#: A date as the issue-date box sends it. Deliberately stricter than `date.fromisoformat`, which
#: since Python 3.11 also accepts a full ISO timestamp — and a timestamp is exactly the input
#: TD-209 exists to keep out of a date field.
DAY_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

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


def issue_date_for(period_month, issued_on, today):
    """The date to PRINT as the issue date, checked against the month it bills.

    Normally today: the 15th's run and a super pressing Issue both bill the month that has just
    closed, so the two dates are days apart. BACK-ISSUING is the exception (owner, 2026-10-28:
    *"I want to issue Invoice from the the month of July onwards, issued on the 15 of the following
    month"*). July's invoice has to say **15 August**, the day it should have gone out, not the day
    somebody finally pressed the button — otherwise a July bill carries a November due date.

    Three bounds, and none is arguable:

      * never after today — an invoice dated in the future is a document that did not exist yet;
      * never on or before the last day of the billed month — a bill cannot predate the thing it
        bills, and the suppliers' own figures are not in until after the month has closed;
      * **never in a previous CALENDAR YEAR.** Adversarial review, 2026-10-28: the first two bounds
        alone let the screen's own twelve-month picker reach November 2025, prefill 15 December
        2025 and pass every check — and because the NUMBER follows the printed year, that mints
        `INV-2025-0001` and reopens a closed, filed series, today, irreversibly. A back-date is for
        a month that slipped past this year; a month that slipped past a year-end is an accounting
        decision, not a keystroke.

    Everything else follows from the answer: `due_on` is this date plus the payment terms, so a
    back-dated invoice carries the due date it would have had, and the NUMBER is drawn from this
    year, because `Invoice.number` is *"numbered by the year of issue"*.

    ⚠ **WHAT A BACK-DATED INVOICE DOES NOT CARRY: the issuer, the bill-to and the payment terms as
    they were on the printed date.** None of the three is versioned, so all three are snapshotted
    from TODAY's rows. The money is the billed month's (rates and discounts are month-keyed) but
    the bank account, the address and the terms are the current ones. That is a limitation to state
    rather than a bug to hide: the day any of them changes, a back-dated invoice misstates it.
    """
    from . import platform_cost
    from .invoicing import InvoicingError

    if issued_on in (None, ''):
        return today
    if isinstance(issued_on, str):
        if not DAY_RE.match(issued_on.strip()):
            raise InvoicingError('bad_issue_date', 'Enter the issue date as YYYY-MM-DD.')
        try:
            issued_on = date.fromisoformat(issued_on.strip())
        except ValueError:
            raise InvoicingError('bad_issue_date', 'Enter the issue date as YYYY-MM-DD.')
    # ⚠ `datetime` is a SUBCLASS of `date`, so a plain isinstance check would let a timestamp
    # through and silently drop its time — in whichever zone it happened to carry (TD-209).
    if isinstance(issued_on, datetime) or not isinstance(issued_on, date):
        raise InvoicingError('bad_issue_date', 'Enter the issue date as YYYY-MM-DD.')
    if issued_on > today:
        raise InvoicingError('issue_date_future',
                             'An invoice cannot be dated in the future.')
    if issued_on.year < today.year:
        raise InvoicingError(
            'issue_date_last_year',
            f'An invoice cannot be dated in {issued_on.year}: {today.year} is the open year, and '
            f'a {issued_on.year} date would start a new run of {issued_on.year} invoice numbers.')
    ended = platform_cost.month_end(period_month)
    if issued_on <= ended:
        first = ended + timedelta(days=1)
        raise InvoicingError(
            'issue_date_before_month_end',
            f'{month_label(period_month)} ends on {ended.isoformat()}, so its invoice cannot be '
            f'dated earlier than {first.isoformat()}.')
    return issued_on


# ── Numbering ────────────────────────────────────────────────────────────────

def next_number(kind, year):
    """The next gap-free number for a document kind in a year, e.g. 'INV-2026-0007'.

    MUST be called inside the transaction that creates the document: the counter row is locked
    with `select_for_update`, so a rolled-back issue rolls the counter back and never burns a
    number, and two concurrent issues cannot draw the same one.
    """
    from .invoicing import InvoicingError
    from .models import BillingSequence

    if not transaction.get_connection().in_atomic_block:
        raise InvoicingError('numbering_outside_transaction',
                             'A document number must be drawn inside the issuing transaction.')
    seq, _ = BillingSequence.objects.get_or_create(kind=kind, year=year)
    seq = BillingSequence.objects.select_for_update().get(pk=seq.pk)
    seq.last += 1
    seq.save(update_fields=['last'])
    return f'{kind}-{year:04d}-{seq.last:04d}'


def _refuse_out_of_order(issued):
    """Refuse a printed date EARLIER than the last one already numbered in that year.

    ⚠ **THE SERIES AND THE CALENDAR MUST AGREE.** `next_number` is gap-free and counts in keypress
    order; `issued_on` is now chosen freely. Issue September, then August, then July — the obvious
    order to work in when catching up, and the one the month picker defaults to — and the numbers
    ascend while the dates descend. For a numbered tax-document series that is the classic audit
    finding, and adversarial review on 2026-10-28 pointed out it would happen on the owner's very
    first sitting.

    Nothing else enforces it: the one-live-per-month constraint is about months, not dates, and the
    sequence only guarantees uniqueness. So the rule is stated here — issue the OLDEST month first.

    A voided invoice still counts. Its number was drawn and filed; pretending otherwise would let a
    void-and-reissue walk the series backwards one step at a time.
    """
    from .invoicing import InvoicingError
    from .models import Invoice

    # org-fence: the series is platform-wide by design — one issuer, one run of numbers a year —
    # and this is reachable only by a super or the monthly job.
    last = (Invoice.objects.filter(issued_on__year=issued.year)
            .order_by('-issued_on', '-id').first())
    if last is not None and issued < last.issued_on:
        raise InvoicingError(
            'issue_date_out_of_order',
            f'{last.number} is already dated {last.issued_on.isoformat()}, so an invoice numbered '
            f'after it cannot be dated {issued.isoformat()}. Issue the oldest month first.')
