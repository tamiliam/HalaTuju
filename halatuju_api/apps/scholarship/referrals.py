"""B40 Phase E/F (F4) — sponsor referral / invitation.

A sponsor invites a prospective sponsor to the F1 landing. The full guest-book
model (owner decision 2026-06-09): each invite is a ``SponsorReferral`` row, so the
inviter sees their invitations + conversion. The invitee's email is PII for someone
who has not consented, so ``purge_expired_referrals`` scrubs it after 60 days.

Writes live here; the invite email is best-effort (a mail failure never blocks the
record). Import direction: this module imports ``emails`` + ``models`` only.
"""
import re
import secrets
from datetime import timedelta

from django.utils import timezone

from .emails import send_sponsor_referral_invite
from .models import SponsorReferral

RETENTION_DAYS = 60   # owner decision 2026-06-09: purge unconverted invitee PII after 60 days

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


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
    send_sponsor_referral_invite(
        to_email=email, inviter_name=inviter.name,
        note=referral.note, code=code, lang='en',
    )
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
    referral.registered_sponsor = new_sponsor
    referral.status = 'joined'
    referral.joined_at = timezone.now()
    referral.save(update_fields=['registered_sponsor', 'status', 'joined_at'])
    return referral


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
