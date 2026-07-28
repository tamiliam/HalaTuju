"""B40 Phase E/F (F4) — sponsor referral / invitation.

A sponsor invites a prospective sponsor to the F1 landing. The full guest-book
model (owner decision 2026-06-09): each invite is a ``SponsorReferral`` row, so the
inviter sees their invitations + conversion. The invitee's email is PII for someone
who has not consented, so ``purge_expired_referrals`` scrubs it after 60 days.

Writes live here; the invite email is best-effort (a mail failure never blocks the
record). Import direction: ``models`` at module scope; the SENDING layer (``sponsor_notify``)
is imported inside the function, so the invite can route through an editable template without
this module depending on the email stack.
"""
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import SponsorReferral

RETENTION_DAYS = 60   # owner decision 2026-06-09: purge unconverted invitee PII after 60 days

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _frontend():
    return (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')


class ReferralError(Exception):
    """Raised for an invalid referral action. Carries a short ``code`` for the view."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _new_code():
    """An opaque, URL-safe, non-guessable invite code (unique-checked by the caller)."""
    return secrets.token_urlsafe(9)   # ~12 chars


def create_referral(inviter, *, invitee_email, invitee_name='', note=''):
    """Record an invite + send the invite email (best-effort). Validates the email
    shape (``bad_email``). A still-pending invite from the SAME inviter to the SAME
    email is returned as-is (idempotent — no duplicate row, no second email)."""
    email = (invitee_email or '').strip().lower()
    if not _EMAIL_RE.match(email):
        raise ReferralError('bad_email')

    existing = inviter.referrals_sent.filter(invitee_email=email, status='invited').first()
    if existing:
        return existing

    # Generate a unique code (retry on the vanishingly-rare collision).
    code = _new_code()
    while SponsorReferral.objects.filter(code=code).exists():
        code = _new_code()

    referral = SponsorReferral.objects.create(
        inviter=inviter, invitee_email=email,
        invitee_name=(invitee_name or '').strip()[:200],
        note=(note or '').strip()[:500], code=code, status='invited',
    )
    # S3: goes through the template path when `referral_invite` is switched on, and through the
    # original hardcoded invite while it is dark — this email is LIVE, so it must not stop.
    from . import sponsor_notify
    sponsor_notify.send_referral_invite(
        referral, inviter_name=inviter.name,
        invite_link=f'{_frontend()}/sponsor?ref={code}',
    )
    return referral


def _mark_joined(referral, new_sponsor, when=None):
    """Close one still-``invited`` row against the account that registered.

    ``when`` exists for the backfill, which knows the real join moment (the sponsor's own
    registration date) and should not stamp all of history with today's date.
    """
    referral.registered_sponsor = new_sponsor
    referral.status = 'joined'
    referral.joined_at = when or timezone.now()
    referral.save(update_fields=['registered_sponsor', 'status', 'joined_at'])
    return referral


def attribute_referral(code, new_sponsor):
    """When a sponsor registers via a ``/sponsor?ref=<code>`` link, attribute it:
    flip the matching still-``invited`` referral to ``joined`` and link the account.
    Idempotent + safe — a missing/already-used code or a self-referral is a no-op.
    Returns the referral when attributed, else None."""
    if not code or new_sponsor is None:
        return None
    referral = SponsorReferral.objects.filter(code=code, status='invited').first()
    if referral is None or referral.inviter_id == new_sponsor.id:
        return None
    return _mark_joined(referral, new_sponsor)


def attribute_referral_by_email(new_sponsor):
    """Close an invitation when the person we invited registers DIRECTLY.

    ``attribute_referral`` fires only if they come back through the ``?ref=<code>`` link,
    and most people don't — they read the invite, then go to the site and sign up. Every
    such invitation stayed ``invited`` for ever, so a real conversion read as none. The
    invitee's own email is the join key, and it is the one thing the invite and the
    registration are guaranteed to share.

    Same rules as the code path: a still-``invited`` row only, never a self-referral, and
    the row is closed exactly once. The OLDEST invitation wins when two sponsors invited
    the same person, so the one who actually introduced them is credited.

    Returns the referral when attributed, else None. Never raises — attribution must not
    be able to fail a registration.
    """
    if new_sponsor is None:
        return None
    email = (new_sponsor.email or '').strip().lower()
    if not email:
        return None
    referral = (SponsorReferral.objects
                .filter(invitee_email=email, status='invited')
                .exclude(inviter_id=new_sponsor.id)
                .order_by('created_at', 'id')
                .first())
    if referral is None:
        return None
    return _mark_joined(referral, new_sponsor)


def purge_expired_referrals(now=None, days=RETENTION_DAYS):
    """PDPA: scrub the invitee PII from still-``invited`` referrals older than ``days``
    and mark them ``expired``. The row stays (the inviter's count survives) but carries
    no personal data. Returns the number purged. Run daily via the cron endpoint."""
    cutoff = (now or timezone.now()) - timedelta(days=days)
    stale = SponsorReferral.objects.filter(status='invited', created_at__lt=cutoff)
    return stale.update(invitee_email='', invitee_name='', status='expired')


def sponsor_referrals(inviter):
    """The inviter's own invitations (latest first), for their 'your invitations' list."""
    return inviter.referrals_sent.all()
