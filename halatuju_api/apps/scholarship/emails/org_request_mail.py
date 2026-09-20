"""The sponsor-interest admin note and the five tenant org-request mails.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from .shared import _P, logger


def send_sponsor_interest_admin_email(name, email, organisation, message):
    """Notify the admin that someone registered interest in sponsoring. English,
    to ``settings.ADMIN_NOTIFY_EMAIL``; skipped silently if unset. Best-effort."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    try:
        send_mail(
            subject='New sponsor interest registered',
            message=(
                f'{name} ({email}) has registered interest in sponsoring.\n'
                f'Organisation: {organisation or "—"}\n\n'
                f'Message:\n{message or "—"}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send sponsor-interest email for %s', email, exc_info=True)
        return False


# ── Requests space (Sprint 15) — best-effort, English, seam-compliant ─────────
# Owner-notify mail goes to settings.ADMIN_NOTIFY_EMAIL (the send_sponsor_interest pattern);
# requestee mail goes to the submitting org_admin's own email. All from _P.email_from, links
# built from _P.frontend_url — ZERO brand literals (the AST guard scans this module).

def _requests_owner_email():
    return (getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or '')


def _org_request_link(req):
    return f'{_P.frontend_url}/admin/requests/{req.pk}'


def _fmt_hours(value):
    """A tidy hours string: '10' not '10.0', '8.5' kept."""
    if value is None:
        return ''
    s = f'{value:.1f}'
    return s[:-2] if s.endswith('.0') else s


def send_org_request_submitted_email(req):
    """Owner notice that an organisation submitted a request. English, to ADMIN_NOTIFY_EMAIL."""
    to_email = _requests_owner_email()
    if not to_email:
        return False
    try:
        send_mail(
            subject=f'New request: {req.title}',
            message=(
                f'{req.submitted_by.name} ({req.organisation.name}) submitted a '
                f'{req.get_kind_display().lower()}.\n\n'
                f'Title: {req.title}\n\n{req.description}\n\n'
                f'Review it here:\n{_org_request_link(req)}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send org-request submitted email for %s', req.pk, exc_info=True)
        return False


def send_org_request_questions_email(req, questions):
    """Requestee notice that the AI reviewer asked a clarifying question (flows to them directly —
    no owner gate). To the submitting org_admin's email."""
    to_email = (getattr(req.submitted_by, 'email', '') or '').strip()
    if not to_email or not questions:
        return False
    qtext = '\n'.join(f'- {q}' for q in questions)
    try:
        EmailMessage(
            subject=f'A question about your request: {req.title}',
            body=(
                f'Hello {req.submitted_by.name},\n\n'
                f'To help us review your request "{req.title}", we have '
                f'{"a question" if len(questions) == 1 else "some questions"}:\n\n'
                f'{qtext}\n\n'
                f'Please reply here:\n{_org_request_link(req)}\n\n'
                f'Thank you,\nThe HalaTuju team'
            ),
            from_email=_P.email_from,
            to=[to_email],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send org-request questions email for %s', req.pk, exc_info=True)
        return False


def send_org_request_answered_email(req):
    """Owner notice that the requestee answered a clarifying question. To ADMIN_NOTIFY_EMAIL."""
    to_email = _requests_owner_email()
    if not to_email:
        return False
    try:
        send_mail(
            subject=f'Request updated: {req.title}',
            message=(
                f'{req.submitted_by.name} ({req.organisation.name}) answered a question on '
                f'"{req.title}".\n\nReview it here:\n{_org_request_link(req)}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send org-request answered email for %s', req.pk, exc_info=True)
        return False


def send_org_request_quote_email(req):
    """Requestee notice that the owner sent a quote (hours only, v1). To the submitting
    org_admin's email — never any other recipient."""
    to_email = (getattr(req.submitted_by, 'email', '') or '').strip()
    if not to_email:
        return False
    # The MARGIN IS NOT MENTIONED to the organisation (owner, 2026-07-30). `quote_hours` is the
    # figure they are asked to accept and the only one anything bills on — nothing in the codebase
    # multiplies by `quote_margin_pct`, so naming it disclosed our padding without changing the
    # number. It stays owner-side (OrgRequestOwnerSerializer + the quote form).
    note = (req.quote_note or '').strip()
    try:
        EmailMessage(
            subject=f'A quote for your request: {req.title}',
            body=(
                f'Hello {req.submitted_by.name},\n\n'
                f'We\'ve reviewed your request "{req.title}". Our estimate is '
                f'≈{_fmt_hours(req.quote_hours)} hours.\n\n'
                + (f'{note}\n\n' if note else '')
                + f'You can accept it, defer it for later, or ask to change your request here:\n'
                f'{_org_request_link(req)}\n\n'
                f'Thank you,\nThe HalaTuju team'
            ),
            from_email=_P.email_from,
            to=[to_email],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send org-request quote email for %s', req.pk, exc_info=True)
        return False


def send_org_request_accepted_email(req):
    """Owner notice that the requestee accepted a quote. To ADMIN_NOTIFY_EMAIL."""
    to_email = _requests_owner_email()
    if not to_email:
        return False
    try:
        send_mail(
            subject=f'Request accepted: {req.title}',
            message=(
                f'{req.submitted_by.name} ({req.organisation.name}) accepted the quote for '
                f'"{req.title}" (≈{_fmt_hours(req.quote_hours)} hours).\n\n'
                f'View it here:\n{_org_request_link(req)}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send org-request accepted email for %s', req.pk, exc_info=True)
        return False
