"""Sponsor comms — the sending layer (S3, 2026-07-28).

`sponsor_comms` decides what an email says and whether it may go. This puts it in an inbox, and
it is the ONLY module that can. The split mirrors `partner_comms` / `partner_notify` for the same
reason: a pure decision module can be tested without mocking SMTP, and a sender with no opinions
cannot quietly grow a second copy of the rules.

**Every path through `deliver` writes a log row** — sent, failed, no recipient, template off,
template never seeded. That is the rule the partner family arrived at the hard way: an
unreachable recipient and a happy one looked identical until the skips were logged too.

**Nothing here can raise into its caller.** These sends hang off registration, a vetting decision
and a credit countersignature; none of those may fail because an email did. Each entry point is
wrapped, and the wrap is the point rather than an afterthought.
"""
import logging

from . import sponsor_comms
from .emails import send_sponsor_email

logger = logging.getLogger(__name__)


def deliver(kind, sponsor, context=None, *, to_email=None):
    """Render and send ONE sponsor email of `kind`, logging whatever happens.

    `to_email` overrides the sponsor's own address — used only by `referral_invite`, which goes
    to a prospective sponsor who has no account yet. Returns True only on a successful send.
    """
    context = dict(context or {})
    recipient = (to_email or sponsor_comms.recipient_for(sponsor) or '').strip().lower()

    if not sponsor_comms.comms_enabled():
        sponsor_comms.log_attempt(kind, sponsor, [recipient] if recipient else [],
                                  note='platform_off')
        return False

    template = sponsor_comms.template_for(kind)
    if template is None:
        # Not seeded. Distinct from "switched off" on purpose: one is a decision, the other is a
        # deployment step nobody ran, and they need different fixes.
        sponsor_comms.log_attempt(kind, sponsor, [recipient] if recipient else [],
                                  note='no_template')
        return False
    if not template.enabled:
        sponsor_comms.log_attempt(kind, sponsor, [recipient] if recipient else [],
                                  note='disabled')
        return False
    if not recipient:
        sponsor_comms.log_attempt(kind, sponsor, [], note='no_recipient')
        return False

    context.setdefault('sponsor_name', getattr(sponsor, 'name', '') or '')
    subject, text_body, html_body = sponsor_comms.render(kind, template, context)

    ok = False
    note = ''
    try:
        ok = bool(send_sponsor_email(recipient, subject=subject,
                                     text_body=text_body, html_body=html_body))
        if not ok:
            note = 'send_failed'
    except Exception as exc:                       # noqa: BLE001 — logged, never raised on
        note = f'error: {exc.__class__.__name__}'  # a registration or a countersignature
        logger.warning('Sponsor email %s to %s failed', kind, recipient, exc_info=True)

    sponsor_comms.log_attempt(kind, sponsor, [recipient], subject=subject, ok=ok, note=note)
    return ok


def _safe(kind, sponsor, context=None, **kwargs):
    """`deliver`, with the last guard: bookkeeping must never break the caller."""
    try:
        return deliver(kind, sponsor, context, **kwargs)
    except Exception:                              # noqa: BLE001
        logger.warning('Sponsor email %s could not be attempted', kind, exc_info=True)
        return False


# ── the lifecycle sends ───────────────────────────────────────────────────────
# Five of these close a silence that has been live since Phase E1: a sponsor was vetted and
# never told the outcome, in either direction.

def send_welcome(sponsor):
    """They have registered; vetting is pending. The first thing we have ever said to them."""
    return _safe('welcome', sponsor)


def send_vetting_outcome(sponsor, status, *, previous_status=''):
    """Approved / not approved / suspended / reinstated — whichever this decision was.

    `reinstated` rather than `approved` when an approval LIFTS a suspension: the two read very
    differently to someone who was suspended, and the review endpoint uses one action for both.
    """
    if status == 'approved':
        kind = 'reinstated' if previous_status == 'suspended' else 'approved'
    elif status == 'rejected':
        kind = 'rejected'
    elif status == 'suspended':
        kind = 'suspended'
    else:
        return False
    return _safe(kind, sponsor)


def send_credit_confirmed(credit):
    """A wallet credit has reached `confirmed` — the step that makes the money spendable.

    **Fires on `confirmed` and nothing earlier.** A draft or admin-signed credit is money we have
    not agreed we hold; telling a donor we hold it is the one mistake on this path that cannot be
    taken back. The guard is here AND the caller only calls on confirmation — belt and braces,
    because the cost of being wrong is a false statement about someone's money.
    """
    from .models import Donation
    if credit is None or credit.status != Donation.STATUS_CONFIRMED:
        return False
    from . import sponsorship as sponsorship_service
    programme = credit.programme
    available = (sponsorship_service.sponsor_balance(credit.sponsor, programme)
                 if programme is not None else None)
    return _safe('credit_confirmed', credit.sponsor, {
        'programme_name': getattr(programme, 'name_en', '') or '',
        'amount': credit.amount,
        'bank_ref': credit.external_reference or '',
        'available': available,
    })


# ── the three ADOPTED sends ───────────────────────────────────────────────────
#
# `referral_invite`, `new_students` and `weekly_digest` are NOT new — they are live on production
# today as hardcoded emails, with the cron jobs that drive them enabled. Each therefore keeps its
# pre-S3 sender for exactly as long as the PLATFORM gate is shut.
#
# **The fallback keys on `comms_enabled()`, NOT on `is_enabled(kind)`, and the difference is the
# whole safety property.** Before the flip we are in the pre-S3 world: templates are inert and
# these three send as they always have. After the flip the templates govern completely — so an
# org_admin switching one OFF genuinely stops it. Keying the fallback on the template's own
# switch would have made "off" unenforceable on precisely the three emails that already reach
# people: the owner would tick a switch off, the legacy sender would carry on regardless, and the
# screen would say one thing while the system did another.
#
# These three are SEEDED ON (owner, 2026-07-28: *"many are already active. Keep them activated.
# Only the new ones can be inactive and subject to review."*), so flipping the platform gate
# changes nothing about what sponsors receive — it only moves them onto editable wording.

def send_referral_invite(referral, *, inviter_name='', invite_link='', lang='en'):
    """The invitation to a prospective sponsor.

    Goes to somebody with no account, so the log row carries the INVITER as its sponsor and the
    invitee's address as the recipient. Uses the pre-S3 hardcoded invite until the PLATFORM gate
    opens; after that the template governs, switch and all.
    """
    if not sponsor_comms.comms_enabled():
        from .emails import send_sponsor_referral_invite
        return send_sponsor_referral_invite(
            to_email=referral.invitee_email,
            inviter_name=inviter_name or getattr(referral.inviter, 'name', '') or '',
            note=referral.note or '', code=referral.code, lang=lang)
    return _safe('referral_invite', referral.inviter, {
        'inviter_name': inviter_name or getattr(referral.inviter, 'name', '') or '',
        'invitee_name': referral.invitee_name or '',
        'note': referral.note or '',
        'invite_link': invite_link,
        'sponsor_name': referral.invitee_name or '',
    }, to_email=referral.invitee_email)


def send_student_alert(sponsor, cards, *, weekly=False, lang='en'):
    """The new-student alert (`new_students`) or the Monday digest (`weekly_digest`).

    Uses the pre-S3 hardcoded email until the PLATFORM gate opens — see the note above. After
    that the template governs, so switching it off really does stop it.
    """
    if not cards:
        return False
    kind = 'weekly_digest' if weekly else 'new_students'
    if not sponsor_comms.comms_enabled():
        from .emails import send_sponsor_digest_email, send_sponsor_new_student_email
        sender = send_sponsor_digest_email if weekly else send_sponsor_new_student_email
        return bool(sender(sponsor.email, cards, name=sponsor.name))
    return _safe(kind, sponsor, {
        'cards': list(cards),
        'count': len(cards),
        'lang': lang,
    })
