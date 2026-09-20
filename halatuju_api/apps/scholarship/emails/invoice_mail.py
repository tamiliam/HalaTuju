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
