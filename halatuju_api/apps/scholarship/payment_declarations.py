"""The tenant says it has paid; the owner checks the bank (2026-10-29).

Why this exists, in the owner's own words. They signed in as BrightPath's org_admin on
2026-10-29, read the billing page, and said:

    *"the status of the invoice is sent. I think it should be received or unpaid for the client.
    And, there doesn't seem to be a way for the client to enter anything to claim settlement.
    Perhaps a payment proof or date or sth.?"*

The first half was a wording fault and was fixed on the screen (`statusChip`). The second half is
this module: a customer who has paid had no way to say so, and so sat waiting for somebody to
notice.

⚠ **THE WHOLE DESIGN IS ONE RULE: A DECLARATION IS NOT MONEY.** The tenant's claim creates a
`InvoicePaymentDeclaration` and nothing else. A receipt — the document that says money arrived,
and the thing `Invoice.status` reads to decide `paid` — is still minted in exactly one place, by
a super, through `invoicing.record_receipt`, after somebody has looked at the bank statement. If a
declaration could mint a receipt, a customer could mark their own invoice paid.

⚠ **DATE AND BANK REFERENCE ONLY.** The owner's choice, asked and answered on 2026-10-29. No
amount: the invoice already states it, and a tenant-typed figure only invites an argument about
which number is right. No payment slip: a file is a thing to store, scan, serve and purge, and the
bank reference already identifies the transfer. Do not add either without asking again.

The flow:

    sent/unpaid  --declare-->  payment declared  --confirm-->  paid (a receipt exists)
                                       |
                                       +--------reject------>  back to unpaid, with a reason
"""
import logging
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from .invoicing import InvoicingError, _today, record_receipt

logger = logging.getLogger(__name__)


def open_declaration(invoice):
    """The one unsettled declaration on this invoice, or None.

    Reads the PREFETCHED rows when the caller has them, so a list of invoices does not fire one
    query per row. `is_open` is a plain property, not a filter, for exactly that reason.
    """
    for d in invoice.payment_declarations.all():
        if d.is_open:
            return d
    return None


def declare_payment(invoice, *, paid_on, reference, declared_by_email='', today=None):
    """The TENANT'S claim that this invoice has been paid. Creates no receipt and moves no money.

    Refused when there is nothing to declare against, so a claim never lands somewhere it will be
    quietly ignored:

    * a voided invoice — there is no bill any more;
    * an invoice that was never SENT — the tenant cannot see it, so the claim cannot be theirs;
    * an invoice already settled in full — the receipts say the money is in;
    * a second open claim — one at a time, else the owner is checking a queue of guesses.
    """
    from .models import Invoice, InvoicePaymentDeclaration

    today = _today(today)
    reference = (reference or '').strip()
    if not reference:
        # The same standing rule `record_receipt` applies to a receipt. A claim with no reference
        # gives the owner nothing to look up, which makes it a claim nobody can act on.
        raise InvoicingError(
            'reference_required',
            'Enter the bank reference for the transfer, so it can be found on the statement.')
    if isinstance(paid_on, str):
        try:
            paid_on = date.fromisoformat(paid_on)
        except ValueError:
            raise InvoicingError('bad_date', 'Enter the date the payment was made.')
    if not isinstance(paid_on, date) or paid_on > today:
        raise InvoicingError('bad_date', 'The payment date cannot be in the future.')
    if paid_on < invoice.issued_on:
        raise InvoicingError(
            'paid_before_issued',
            f'{invoice.number} is dated {invoice.issued_on.isoformat()}, so it cannot have been '
            f'paid on {paid_on.isoformat()}.')

    with transaction.atomic():
        # org-fence: re-reads the invoice the fenced caller already resolved
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if locked.voided_at:
            raise InvoicingError('invoice_void', 'This invoice has been cancelled.')
        if not locked.sent_at:
            raise InvoicingError('not_sent', 'This invoice has not been sent yet.')
        if locked.status == 'paid':
            raise InvoicingError('already_paid', f'{locked.number} is already settled in full.')
        if open_declaration(locked) is not None:
            raise InvoicingError(
                'already_declared',
                f'A payment has already been declared for {locked.number} and is being checked.')
        try:
            declaration = InvoicePaymentDeclaration.objects.create(
                invoice=locked, paid_on=paid_on, reference=reference[:120],
                declared_by_email=declared_by_email or '')
        except IntegrityError:
            # ⚠ THE CONSTRAINT IS THE REAL GUARD, not the check above. Two org_admins pressing the
            # button together both pass the read and one loses the write; the partial unique index
            # turns that race into this ordinary refusal rather than a second open claim.
            raise InvoicingError(
                'already_declared',
                f'A payment has already been declared for {locked.number} and is being checked.')
    logger.info('invoicing: payment declared for %s paid_on=%s by=%s',
                locked.number, paid_on, declared_by_email or '-')
    return declaration


def confirm_payment(declaration, *, amount_myr, received_on=None, reference='',
                    method='bank_transfer', note='', confirmed_by_email='', today=None):
    """The OWNER found the money. Mints the receipt and closes the claim, in one transaction.

    ⚠ **THE OWNER'S FIGURES WIN, not the tenant's.** `amount_myr` is required and comes from the
    bank statement; the tenant was never asked for one. `received_on` and `reference` default to
    what the tenant declared, because that is usually right and re-typing a reference invites a
    typo — but either may be corrected here, and the correction goes on the receipt, which is the
    document that counts.

    Every refusal `record_receipt` can raise (overpayment, a voided invoice, a date before the
    invoice) still applies and is raised from here unchanged. The receipt is minted FIRST so that
    a refused payment leaves the claim open rather than closing it against nothing.
    """
    from .models import InvoicePaymentDeclaration

    if not declaration.is_open:
        raise InvoicingError('declaration_settled',
                             'This declaration has already been dealt with.')
    invoice = declaration.invoice
    with transaction.atomic():
        # ⚠ LOCKED AND RE-READ INSIDE THE TRANSACTION, not trusted from the check above. Two
        # supers confirming the same claim at once both pass that check, and the second would
        # mint a SECOND receipt — which `record_receipt` only catches when the first already
        # covered the whole balance. A partial confirmation would be recorded twice.
        # org-fence: the same row the fenced caller already resolved
        locked = (InvoicePaymentDeclaration.objects
                  .select_for_update().filter(pk=declaration.pk).first())
        if locked is None or not locked.is_open:
            raise InvoicingError('declaration_settled',
                                 'This declaration has already been dealt with.')
        receipt = record_receipt(
            invoice,
            received_on=received_on or declaration.paid_on,
            amount_myr=amount_myr,
            reference=(reference or '').strip() or declaration.reference,
            method=method, note=note, recorded_by_email=confirmed_by_email, today=today)
        locked.receipt = receipt
        locked.confirmed_at = timezone.now()
        locked.confirmed_by_email = confirmed_by_email or ''
        locked.save(update_fields=['receipt', 'confirmed_at', 'confirmed_by_email'])
    # The caller still holds the object it passed in, so bring it up to date rather than leaving
    # it reading "open" on a claim that is now closed.
    declaration.refresh_from_db()
    logger.info('invoicing: payment declaration confirmed for %s as receipt %s',
                invoice.number, receipt.number)
    return receipt


def reject_declaration(declaration, *, reason, rejected_by_email=''):
    """The OWNER could not find the money. Closes the claim and tells the tenant why.

    ⚠ The reason is REQUIRED and is shown to the tenant. "Not found" with no reason leaves a
    customer guessing at their own bank, which is the position this whole module exists to end.
    The invoice falls back to unpaid and the tenant may declare again with the right reference.
    """
    from .models import InvoicePaymentDeclaration

    reason = (reason or '').strip()
    if not reason:
        raise InvoicingError(
            'reason_required',
            'Say why the payment could not be matched. The organisation is shown this.')
    if not declaration.is_open:
        raise InvoicingError('declaration_settled',
                             'This declaration has already been dealt with.')
    with transaction.atomic():
        # Locked for the same reason as `confirm_payment`: a reject racing a confirm must not be
        # able to stamp a claim that now has a receipt against it.
        # org-fence: the same row the fenced caller already resolved
        locked = (InvoicePaymentDeclaration.objects
                  .select_for_update().filter(pk=declaration.pk).first())
        if locked is None or not locked.is_open:
            raise InvoicingError('declaration_settled',
                                 'This declaration has already been dealt with.')
        locked.rejected_at = timezone.now()
        locked.rejected_by_email = rejected_by_email or ''
        locked.reject_reason = reason
        locked.save(update_fields=['rejected_at', 'rejected_by_email', 'reject_reason'])
    declaration.refresh_from_db()
    logger.info('invoicing: payment declaration rejected for %s by=%s',
                declaration.invoice.number, rejected_by_email or '-')
    return declaration
