"""Award-withdrawal staff mail (A1.13b maker and checker, owner ruling 2026-11-08).

Two internal English emails, like the payment-run mail (`payment_mail`):

  * ``send_withdrawal_requested_email`` — a request is waiting: to every ELIGIBLE checker (signed in,
    active, holds `award_withdraw_approve`, in the case's organisation, never the maker, never a super);
  * ``send_withdrawal_outcome_email`` — the request was approved or refused: to the maker.

⚠ LINK ONLY, NO STUDENT DATA: no name, no IC, no amount, no explanation and no note — the reader opens
the case behind sign-in. ⚠ BEST-EFFORT: each is sent AFTER COMMIT by `award_withdrawal_chain`, and a
failure is logged, never raised, so it can never block or undo the action.
"""
from django.conf import settings
from django.core.mail import EmailMessage

from .shared import _P, logger


def _link(request_row):
    return f'{_P.frontend_url}/admin/scholarship/{request_row.application_id}'


def _send(to, subject, body, request_row):
    try:
        EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[to]).send()
        return True
    except Exception:
        logger.warning('Failed to send award-withdrawal mail for request %s to %s',
                       request_row.pk, to, exc_info=True)
        return False


def send_withdrawal_requested_email(request_row, checkers):
    """Tell each eligible checker that a withdrawal request waits for a decision. Returns whether any
    email went."""
    sent = False
    who = (request_row.requested_by_name or '').strip() or 'A colleague'
    for checker in checkers:
        to = (getattr(checker, 'email', '') or '').strip()
        if not to:
            continue
        body = (
            f'Dear {(checker.name or "").strip() or "Colleague"},\n\n'
            f'{who} has asked for an award to be withdrawn (request {request_row.pk}). Nothing changes '
            f'until another person approves it.\n\n'
            f'Please open the case, read the explanation, and approve or refuse it:\n{_link(request_row)}\n\n'
            f'A request that nobody decides within 14 days expires.\n\n'
            f'The HalaTuju Team'
        )
        sent = _send(to, 'An award withdrawal awaits your decision', body, request_row) or sent
    return sent


def send_withdrawal_outcome_email(request_row):
    """Tell the maker their request was approved (the award is withdrawn) or refused."""
    to = (request_row.requested_by_email or '').strip()
    if not to:
        return False
    approved = request_row.status == 'approved'
    outcome = 'approved: the award has been withdrawn' if approved else 'refused: the award stands'
    body = (
        f'Dear {(request_row.requested_by_name or "").strip() or "Colleague"},\n\n'
        f'Your award withdrawal request {request_row.pk} was {outcome}.\n\n'
        f'Open the case to see the decision:\n{_link(request_row)}\n\n'
        f'The HalaTuju Team'
    )
    subject = 'Your award withdrawal request was ' + ('approved' if approved else 'refused')
    return _send(to, subject, body, request_row)
