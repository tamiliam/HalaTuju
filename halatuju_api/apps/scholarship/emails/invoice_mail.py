"""Invoice delivery and the invoicing alert.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import EmailMessage
from .shared import logger


def send_invoice_email(invoice, pdf_bytes, to):
    """Deliver a tenant invoice with its PDF attached. Best-effort → bool.

    ⚠ **FROM THE PLATFORM, NOT FROM THE PROGRAMME.** Almost every email in this module speaks as
    the tenant's programme (`_PROG_EN`, `_TEAM_EN` — "The BrightPath Bursary Team"). An invoice is
    the one message that goes the OTHER way: the platform billing the tenant. Signing it as the
    tenant's own team would have BrightPath invoicing BrightPath. So it names the issuer frozen on
    the invoice, and replies go to the issuer's address.

    Called only by `invoicing.send_invoice`, which marks the invoice sent AFTER this returns True.
    """
    from .. import invoicing
    who = invoice.issuer_snapshot or {}
    issuer_name = who.get('legal_name') or 'HalaTuju'
    bill_to = (invoice.bill_to_snapshot or {}).get('bill_to_name') or invoice.organisation.name
    month = invoicing.month_label(invoice.period_month)
    body = (
        f'Dear {bill_to},\n\n'
        f'Please find attached invoice {invoice.number} for {month}.\n\n'
        f'    Invoice:    {invoice.number}\n'
        f'    Amount due: RM{invoice.total_myr:,.2f}\n'
        f'    Due by:     {invoice.due_on:%d %B %Y}\n\n'
        'Payment details are printed on the invoice. Please quote the invoice number as your '
        'payment reference.\n\n'
        'If anything on it looks wrong, reply to this email and we will look into it.\n\n'
        'Thank you,\n'
        f'{issuer_name}\n'
    )
    reply_to = [who['email']] if who.get('email') else None
    try:
        msg = EmailMessage(
            subject=f'Invoice {invoice.number} from {issuer_name} ({month})',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=list(to), reply_to=reply_to)
        msg.attach(f'{invoice.number}.pdf', pdf_bytes, 'application/pdf')
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send invoice %s', invoice.number, exc_info=True)
        return False


def send_receipt_email(receipt, pdf_bytes, to):
    """Deliver a receipt with its PDF attached. Best-effort → bool.

    ⚠ **THE CUSTOMER IS TOLD THEIR MONEY ARRIVED.** Until 2026-10-29 a receipt was raised, stored
    and shown on the billing page, and nothing was sent — so the organisation had to come and look
    for it. The screen already promises *"we will check it against our account and raise your
    receipt"*; this is the half that makes the promise true.

    ⚠ **BEST-EFFORT, AND THE RECEIPT IS ALREADY SAVED BEFORE THIS RUNS.** Money recorded is money
    recorded: a mail outage must never undo it, and `invoicing.email_receipt` stamps the receipt
    only when this returns True, so the screen can say plainly that it did not go.

    Speaks as the PLATFORM, not as the tenant's programme, for the same reason `send_invoice_email`
    does: this message goes the other way round.
    """
    who = receipt.invoice.issuer_snapshot or {}
    issuer_name = who.get('legal_name') or 'HalaTuju'
    invoice = receipt.invoice
    bill_to = (invoice.bill_to_snapshot or {}).get('bill_to_name') or invoice.organisation.name
    body = (
        f'Dear {bill_to},\n\n'
        f'Thank you — we have received your payment. Receipt {receipt.number} is attached.\n\n'
        f'    Receipt:   {receipt.number}\n'
        f'    Received:  {receipt.received_on:%d %B %Y}\n'
        f'    Amount:    RM{receipt.amount_myr:,.2f}\n'
        f'    Reference: {receipt.reference}\n'
        f'    Invoice:   {invoice.number}\n\n'
        + (f'Balance still outstanding on {invoice.number}: RM{invoice.balance():,.2f}.\n\n'
           if invoice.balance() > 0 else
           f'{invoice.number} is now settled in full.\n\n')
        + 'If anything on it looks wrong, reply to this email and we will look into it.\n\n'
          'Thank you,\n'
        + f'{issuer_name}\n'
    )
    reply_to = [who['email']] if who.get('email') else None
    try:
        msg = EmailMessage(
            subject=f'Receipt {receipt.number} from {issuer_name} ({invoice.number})',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=list(to), reply_to=reply_to)
        msg.attach(f'{receipt.number}.pdf', pdf_bytes, 'application/pdf')
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send receipt %s', receipt.number, exc_info=True)
        return False


def send_payment_declared_email(declaration):
    """Tell the owner a tenant says it has paid. Best-effort → bool.

    ⚠ **WITHOUT THIS, THE FEATURE SOLVES HALF THE PROBLEM.** The owner's complaint on 2026-10-29
    was that a customer who had paid could only wait for somebody to notice. A declaration nobody
    is told about leaves the same wait, pointed the other way: the claim sits on the billing page
    until the owner happens to open it.

    ⚠ **IT CARRIES NO AMOUNT**, because none was asked for and none is known. The figure the owner
    acts on is the one on their own bank statement; printing the invoice total here would read as
    "this much arrived", which is exactly the confusion `payment_declarations` exists to prevent.

    Best-effort on purpose: the claim is already recorded and already on the screen, so a mail
    failure must not undo it. Sent AFTER the row is committed, never inside its transaction.
    """
    recipient = (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '').strip()
    if not recipient:
        return False
    from .. import invoicing
    invoice = declaration.invoice
    month = invoicing.month_label(invoice.period_month)
    who = declaration.declared_by_email or invoice.organisation.name
    body = (
        f'{invoice.organisation.name} says it has paid invoice {invoice.number} ({month}).\n\n'
        f'    Declared by: {who}\n'
        f'    Date paid:   {declaration.paid_on:%d %B %Y}\n'
        f'    Reference:   {declaration.reference}\n'
        f'    Invoice:     {invoice.number}, RM{invoice.total_myr:,.2f}, '
        f'due {invoice.due_on:%d %B %Y}\n\n'
        'Nothing has been recorded as received. Check the bank for that reference, then open '
        'Billing & usage and either confirm it — which raises the receipt — or say it could not '
        'be matched, with a reason the organisation is shown.\n'
    )
    try:
        EmailMessage(
            subject=f'{invoice.organisation.name} says it has paid {invoice.number}',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient]).send()
        return True
    except Exception:
        logger.warning('Failed to send the payment-declared email for %s',
                       invoice.number, exc_info=True)
        return False


def send_invoicing_alert_email(report):
    """Tell a person the 15th's run could not issue something. Best-effort → bool.

    Sent ONLY when something was refused — the same "no weekly all-clear" rule as the spending
    alert. Names organisations and reasons; carries no costs and no margins, because this mail
    gets forwarded.
    """
    recipient = (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '').strip()
    refused = report.get('refused') or []
    if not recipient or not refused:
        return False
    from .. import invoicing
    month = invoicing.month_label(report['month'])
    lines = []
    for r in refused:
        lines.append(f"{r['organisation']}:")
        lines.extend(f'  - {p}' for p in r['problems'])
    issued = report.get('issued') or []
    body = (
        f'The monthly invoice run for {month} could not issue every invoice.\n\n'
        + '\n'.join(lines)
        + ('\n\nIssued: ' + ', '.join(f"{i['organisation']} {i['number']}" for i in issued)
           if issued else '')
        + '\n\nFix the problems above and issue from Billing & usage, or issue anyway there with '
          'a reason. Nothing has been sent to any organisation.\n'
    )
    try:
        EmailMessage(
            subject=f'Invoices for {month} need attention',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient]).send()
        return True
    except Exception:
        logger.warning('Failed to send the invoicing alert email', exc_info=True)
        return False
