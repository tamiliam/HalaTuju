"""Payment-run mail: the approval, the finance check and the run itself.

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
    """Payments: when a run is ready for its FINAL signature, tell whoever approves it. Internal
    officer email (English); best-effort — never raises, a failure never blocks the signature.

    ⚠ ROUTED BY PERMISSION since #39 Sprint 2 (owner, 2026-10-19: Finance approves runs): the
    organisation's active `payments_approve` holders who have not signed this run
    (`payments.eligible_approvers` — Finance, today); ELSE, under the fallback, its organisation
    admins who have not signed it (`payments.fallback_approvers`), as before the change. The
    function keeps its old name so the sign service and its tests address it as they did."""
    from .. import payments
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    vircle_to = getattr(settings, 'VIRCLE_PAYMENTS_EMAIL', '')
    subject = f'Payment run {run.reference} awaits your approval'
    sent = False
    approvers = payments.eligible_approvers(run) or payments.fallback_approvers(run)
    for approver in approvers:
        if not (approver.email or '').strip():
            continue
        body = (
            f'Dear {(approver.name or "").strip() or "Approver"},\n\n'
            f'{run.admin_signed_name} has prepared and signed payment run {run.reference}, '
            f'paying the {_PROG_EN} for {month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your approval. Once you approve it, the payment '
            f'instruction (with the payment file attached) will be emailed to Vircle at '
            f'{vircle_to}.\n\n'
            f'Review and approve here: {link}\n\n'
            f'If anything looks wrong, do not approve — editing the run returns it to '
            f'draft and clears every signature collected so far, or ask '
            f'{run.admin_signed_name} to correct it.\n\n'
            f'The HalaTuju Team'
        )
        try:
            EmailMessage(subject=subject, body=body,
                         from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[approver.email]).send()
            sent = True
        except Exception:
            logger.warning('Failed to send approval notification for run %s to %s',
                           run.reference, approver.email, exc_info=True)
    return sent


def send_payment_finance_check_email(run):
    """Payments / Sprint 14: when the maker signs a run whose chain has the CHECK armed, the run
    goes to the checkers before the approver ever sees it — so this email replaces the approval
    one at that moment (``payments.sign`` picks). Since #39 Sprint 2 the checkers are the active
    `payments_check` holders who have not signed the run (`payments.eligible_checkers`); no preset
    holds that key, so this stays dormant until somebody is given it. Internal officer email
    (English); best-effort — never raises, a failure never blocks the signature.

    Deliberately carries NO programme-name literal (conventions rule 2): it is addressed to the
    organisation's own finance staff about their own run, so the reference and the month say
    everything the recipient needs. (The sibling countersign email predates that rule.)"""
    from .. import payments
    frontend = _P.frontend_url
    link = f'{frontend}/admin/payments/{run.id}'
    month = _run_month_label(run)
    n, total = _run_totals(run)
    subject = f'Payment run {run.reference} awaits your finance check'
    sent = False
    checkers = payments.eligible_checkers(run)
    for checker in checkers:
        if not (checker.email or '').strip():
            continue
        body = (
            f'Dear {(checker.name or "").strip() or "Checker"},\n\n'
            f'{run.admin_signed_name} has signed payment run {run.reference}, covering '
            f'{month}:\n\n'
            f'    Students:      {n}\n'
            f'    Total:         RM{_rm_amount(total)}\n'
            f'    Payment date:  {run.payment_date:%d/%m/%Y}\n\n'
            f'It now needs your finance check. The run cannot be approved — and no money '
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


def _instruction_cc(run):
    """Who is copied on the Vircle instruction: the approver, then the organisation's active org
    admins, each address once (case-insensitive), in that order."""
    from apps.courses.models import PartnerAdmin
    emails = [(run.org_admin_signed_email or '').strip()]
    emails += list(PartnerAdmin.objects.filter(
        owning_organisation_id=getattr(run, 'organisation_id', None), role='org_admin',
        is_active=True, is_super_admin=False).order_by('id').values_list('email', flat=True))
    seen, cc = set(), []
    for e in emails:
        e = (e or '').strip()
        if e and e.casefold() not in seen:
            seen.add(e.casefold())
            cc.append(e)
    return cc


def send_payment_run_email(run):
    """Payments D7 — on the approval, email Vircle the payment instruction with the run's
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
        f'This run was prepared by {run.admin_signed_name} and approved by '
        f'{run.org_admin_signed_name} of the ' + _PROG_EN + ' programme.\n\n'
        'Thank you,\n'
        + _TEAM_EN
    )
    # Owner 2026-07-17 (approver's ask): CC the APPROVER — the final signer, Finance since #39
    # Sprint 2 (the org admin under the fallback) — so the organisation holds its own copy of
    # exactly what was sent to Vircle. Owner 2026-10-19 (#39 S2 review item 3, option A): ALSO the
    # organisation's ACTIVE org admins, for information — they no longer sign the run, and they
    # fund Vircle. Deduplicated case-insensitively (an org admin approving under the fallback is
    # copied once); never an inactive account.
    cc = _instruction_cc(run)
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
