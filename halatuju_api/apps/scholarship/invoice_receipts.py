"""Receipts: money that ARRIVED, and telling the customer about it (2026-10-29).

Moved here VERBATIM from `invoicing.py` (moves only, when that file passed the 600-line standard
after `email_receipt` was added). Not a line of the bodies below was reworded; the names are
re-exported from `invoicing`, so every existing `invoicing.record_receipt` caller and every
`mock.patch.object(invoicing, ...)` keeps working.

The pair belongs together and apart from issuing: `record_receipt` is the ONE place a receipt is
ever minted, and `email_receipt` is deliberately NOT part of it — see its docstring.

⚠ `InvoicingError` and the logger are imported INSIDE each function, not at the top. `invoicing`
imports this module at ITS top so the names can be re-exported, and a module-level import back the
other way would close that circle at import time. The same shape `org_requests_ai.py` uses.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from . import money
from .invoice_dates import _today, next_number

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
    from .invoicing import InvoicingError

    try:
        return money.parse_money(value, places_exact=True, allow_zero=False,
                                 allow_negative=False)
    except money.MoneyError as exc:
        raise InvoicingError('bad_amount', _RECEIPT_UNREADABLE if exc.reason == 'syntax'
                             else _RECEIPT_OUT_OF_RANGE)


def record_receipt(invoice, *, received_on, amount_myr, reference, method='bank_transfer',
                   note='', recorded_by_email='', today=None):
    """Record money that ARRIVED against an invoice, and number its receipt."""
    from .invoicing import InvoicingError, logger
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


def email_receipt(receipt):
    """Send the receipt to the bill-to inboxes FROZEN on its invoice. Best-effort → bool.

    ⚠ **DELIBERATELY NOT PART OF `record_receipt`.** It must run AFTER the money is committed, and
    `record_receipt` is itself called from inside another transaction by
    `payment_declarations.confirm_payment` — emailing from in there would tell a customer their
    money arrived and then roll the receipt back if anything later failed. Keeping it a separate
    call makes the ordering visible at each door instead of hidden two layers down.

    ⚠ **A FAILURE NEVER UNDOES THE RECEIPT.** Money recorded is money recorded. `emailed_at` is
    stamped only when the send succeeded, so a blank one means exactly what it says — it was not
    sent — and the screen can offer the PDF instead of implying it is on its way.

    There are two doors into this and a test for each: the super's Record payment, and the owner
    confirming a tenant's declaration.
    """
    from . import emails, invoice_pdf
    from .invoicing import logger

    to = [e for e in (receipt.invoice.bill_to_snapshot or {}).get('emails', []) if e]
    if not to:
        return False
    try:
        pdf = invoice_pdf.receipt_pdf(receipt)
    except Exception:
        logger.warning('Could not render receipt %s to email it', receipt.number, exc_info=True)
        return False
    if not emails.send_receipt_email(receipt, pdf, to):
        return False
    receipt.emailed_at = timezone.now()
    receipt.emailed_to = to
    receipt.save(update_fields=['emailed_at', 'emailed_to'])
    logger.info('invoicing: receipt %s emailed to %s', receipt.number, ', '.join(to))
    return True
