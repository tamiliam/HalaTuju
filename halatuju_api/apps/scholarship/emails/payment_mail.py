"""Payment-run mail: countersignature, the finance check and the run itself.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import EmailMessage
from .shared import _P, _PROG_EN, _TEAM_EN, logger


def _run_month_label(run):
    """The month a run pays for, e.g. 'July 2026' (falls back to the payment date's month)."""
    d = getattr(run, 'period_month', None) or getattr(run, 'payment_date', None)
    return d.strftime('%B %Y') if d else ''


def _run_totals(run):
    """(included-student count, total amount) for a run."""
    from decimal import Decimal
    included = [i for i in run.items.all() if i.included]
    return len(included), sum((i.amount for i in included), Decimal('0'))


def _rm_amount(v):
    """Whole-ringgit display: Decimal('200.00') → '200' (a genuine .50 is kept)."""
    try:
        return f'{v.normalize():f}'
    except Exception:
        return str(v)


def send_payment_countersign_email(run):
    """Payments (owner 2026-07-16): when the maker signs a run, tell the organisation admin(s)
    it awaits their countersignature. Internal officer email (English); best-effort — never
    raises, a failure never blocks the signature."""
    from apps.courses.models import PartnerAdmin
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    vircle_to = getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '')
    subject = f'Payment run {run.reference} awaits your countersignature'
    sent = False
    approvers = PartnerAdmin.objects.filter(
        owning_organisation=run.organisation, role='org_admin', is_active=True)
    for approver in approvers:
        if not (approver.email or '').strip():
            continue
        body = (
            f'Dear {(approver.name or "").strip() or "Organisation Admin"},\n\n'
            f'{run.admin_signed_name} has signed payment run {run.reference}, paying the '
            f'{_PROG_EN} for {month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your countersignature. Once you countersign, the payment '
            f'instruction (with the payment file attached) will be emailed to Vircle at '
            f'{vircle_to}.\n\n'
            f'Review and countersign here: {link}\n\n'
            f'If anything looks wrong, do not countersign — editing the run returns it to '
            f'draft and clears the first signature, or ask {run.admin_signed_name} to '
            f'correct it.\n\n'
            f'The HalaTuju Team'
        )
        try:
            EmailMessage(subject=subject, body=body,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[approver.email]).send()
            sent = True
        except Exception:
            logger.warning('Failed to send countersign notification for run %s to %s',
                           run.reference, approver.email, exc_info=True)
    return sent


def send_payment_finance_check_email(run):
    """Payments / Sprint 14: when the maker signs a run in an organisation that HAS an active
    finance admin, the run goes to finance for the check before the approver ever sees it — so
    this email replaces the countersign one at that moment (``payments.sign`` picks). Internal
    officer email (English); best-effort — never raises, a failure never blocks the signature.

    Deliberately carries NO programme-name literal (conventions rule 2): it is addressed to the
    organisation's own finance staff about their own run, so the reference and the month say
    everything the recipient needs. (The sibling countersign email predates that rule.)"""
    from apps.courses.models import PartnerAdmin
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    subject = f'Payment run {run.reference} awaits your finance check'
    sent = False
    checkers = PartnerAdmin.objects.filter(
        owning_organisation=run.organisation, role='finance', is_active=True)
    for checker in checkers:
        if not (checker.email or '').strip():
            continue
        body = (
            f'Dear {(checker.name or "").strip() or "Finance Admin"},\n\n'
            f'{run.admin_signed_name} has signed payment run {run.reference}, covering '
            f'{month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your finance check. The run cannot be countersigned — and no money '
            f'moves — until you have checked it.\n\n'
            f'Review the list and the payment file, then sign here: {link}\n\n'
            f'If anything looks wrong, do not sign. Ask {run.admin_signed_name} to correct it; '
            f'editing the run returns it to draft and clears every signature collected so far, '
            f'including yours.\n\n'
            f'The HalaTuju Team'
        )
        try:
            EmailMessage(subject=subject, body=body,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[checker.email]).send()
            sent = True
        except Exception:
            logger.warning('Failed to send finance-check notification for run %s to %s',
                           run.reference, checker.email, exc_info=True)
    return sent


def send_payment_run_email(run):
    """Payments D7 — on countersignature, email Vircle the payment instruction with the run's
    CSV attached. Enabled when ``VIRCLE_PAYMENTS_EMAIL`` is set (default gokula@vircle.com);
    best-effort — a failure never breaks the completed run (the DB is the record)."""
    recipient = (getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '') or '').strip()
    if not recipient:
        return False
    from .. import sheets
    month = _run_month_label(run)
    n, total = _run_totals(run)
    body = (
        'Dear Vircle team,\n\n'
        f'Please find attached the payment instruction for the ' + _PROG_EN + ' '
        f'for {month}.\n\n'
        f'    Run reference:  {run.reference}\n'
        f'    Payment date:   {run.payment_date:%d/%m/%Y}\n'
        f'    Students:       {n}\n'
        f'    Total:          RM{_rm_amount(total)}\n\n'
        "The attached file lists each student's Wallet ID, NRIC, full name and the amount to "
        "credit. Kindly credit each student's Vircle wallet on the payment date, and reply "
        'to this email to confirm once the payments have been processed.\n\n'
        f'This run was signed by {run.admin_signed_name} and countersigned by '
        f'{run.org_admin_signed_name} of the ' + _PROG_EN + ' programme.\n\n'
        'Thank you,\n'
        + _TEAM_EN
    )
    # Owner 2026-07-17 (approver's ask): CC the countersigning org admin so the
    # organisation holds its own copy of exactly what was sent to Vircle.
    cc = [e for e in [(run.org_admin_signed_email or '').strip()] if e]
    try:
        msg = EmailMessage(
            subject=f'{_PROG_EN} — payment instruction {run.reference} ({month})',
            body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], cc=cc)
        msg.attach(f'{run.reference}.csv', sheets.payment_csv_text(run), 'text/csv')
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send the Vircle payment email for run %s',
                       run.reference, exc_info=True)
        return False
