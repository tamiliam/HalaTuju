"""Sponsor comms (S3) — what a sponsor hears, and who decides the wording.

The problem this closes: a sponsor registered, was vetted, was approved — and was told none of
it. `AdminSponsorReviewView` flipped a status field and returned. Eight people on production were
approved in silence, and the only mail a sponsor has ever had from us is a new-student alert.

**The architecture is the partner-comms one, deliberately** (`partner_comms.py`, 2026-07-26): one
switch per EMAIL rather than per recipient, wording editable by an org_admin, a two-gate dark
launch, every attempt logged including the skips, and a per-kind placeholder allowlist. The
block-splitting mechanics are shared with that family via `email_templates` — extracted when this
became the second family, so there is one renderer and not two drifting copies.

This module stays PURE: it decides what an email should say and whether it may be sent. It never
touches SMTP. `sponsor_notify` does the sending, and nothing here can put a message in an inbox.
"""
from decimal import Decimal

from django.conf import settings

from . import email_templates
from .models import SponsorEmailLog, SponsorEmailTemplate

# ── the nine kinds ────────────────────────────────────────────────────────────
#
# NOT eleven: `low_balance` and `annual_statement` were deferred by the owner (2026-07-28).
# Both edge from transactional account mail into marketing, and what a sponsor actually agreed to
# at registration is a version STRING with no stored wording behind it (TD-186) — so there is no
# way to check whether their consent covers being marketed to. They are absent from the model's
# choices too, so a template for them cannot exist.

KINDS = tuple(k for k, _ in SponsorEmailTemplate.KIND_CHOICES)

# Kinds sent to somebody who is NOT the sponsor row's own account holder.
NON_ACCOUNT_KINDS = ('referral_invite',)

# Per-kind placeholder allowlist. A template saved with anything else is refused: an unknown token
# renders literally into a donor's inbox as `{whatever}`.
#
# It is also a PRIVACY control, and that is the more important half. Sponsor-facing payloads are
# allowlists by construction with planted-identifier leak tests behind them; an editable template
# is a new way in. No token here resolves to a student's name, school, address or contact — the
# only student content available is `{student_cards}`, which renders the same anonymised card the
# pool serializer already produces.
PLACEHOLDERS = {
    'welcome':          {'sponsor_name', 'programme_name', 'team_signoff'},
    'approved':         {'sponsor_name', 'programme_name', 'portal_link', 'team_signoff'},
    'rejected':         {'sponsor_name', 'programme_name', 'team_signoff'},
    'suspended':        {'sponsor_name', 'programme_name', 'team_signoff'},
    'reinstated':       {'sponsor_name', 'programme_name', 'portal_link', 'team_signoff'},
    'credit_confirmed': {'sponsor_name', 'programme_name', 'amount', 'bank_ref', 'available',
                         'portal_link', 'team_signoff'},
    'new_students':     {'sponsor_name', 'programme_name', 'count', 'student_cards',
                         'portal_link', 'team_signoff'},
    'weekly_digest':    {'sponsor_name', 'programme_name', 'count', 'student_cards',
                         'portal_link', 'team_signoff'},
    'referral_invite':  {'inviter_name', 'invitee_name', 'note', 'invite_link',
                         'programme_name', 'team_signoff'},
}

# The one structural token this family adds: the rich per-student cards.
STRUCTURAL_TOKENS = ('student_cards',)

# How many cards a body renders before it says so. The pre-template email capped at five
# SILENTLY; a cap that does not announce itself reads as "that is everyone" (the chase table
# learned this the same way).
MAX_CARDS = 5

NO_NAME_GREETING = 'there'


# ── the voice guard ───────────────────────────────────────────────────────────
#
# Partner comms bans conduit phrasing because a partner co-owns the bursary. The sponsor risks are
# different and, in one case, legal:
#
#   * TAX STATUS — HalaTuju holds no LHDN s44(6) approval, and the entity question behind it is
#     still open. "Tax deductible" in a donor email is a false statement about someone's tax
#     position, and it is the one line here that could cost a donor money.
#   * OWNERSHIP — a sponsor funds a student; they do not acquire one. "Your student" also cuts
#     against the anonymity the whole pool design rests on.
#   * URGENCY — consent taken at registration covers transactional account mail. Pressure copy
#     turns that mail into marketing, which is exactly the boundary `low_balance` and
#     `annual_statement` were deferred over.
#
# The tax and urgency entries moved to `email_templates.UNIVERSAL_BANNED` on 2026-08-04 and are
# folded back in here unchanged — nothing this family refuses has changed. They moved because they
# were needed by the partner family too, once an organisation's sponsor invitation started living
# in that table; keeping a second copy here is how the two would drift.
BANNED_PHRASES = email_templates.UNIVERSAL_BANNED + (
    'your student', 'your students', 'your child', 'your children',
)


def unknown_placeholders(kind, *parts):
    """Tokens this kind does not supply, sorted. Empty means the template is safe to save."""
    return email_templates.unknown_placeholders(PLACEHOLDERS.get(kind, set()), *parts)


def banned_phrases(*parts):
    """Refused phrasings present in `parts`, sorted. Empty means the copy is clean."""
    return email_templates.banned_phrases(BANNED_PHRASES, *parts)


# ── the gates ─────────────────────────────────────────────────────────────────

def comms_enabled():
    """The PLATFORM gate. Unset by default, so this whole feature ships dark.

    Read live from settings at every call rather than captured at import: flipping the env var is
    an `--update-env-vars`, not a deploy, and a value frozen at import would ignore it.
    """
    return bool(getattr(settings, 'SPONSOR_COMMS_ENABLED', False))


def template_for(kind):
    """The stored template for `kind`, or None if it has not been seeded."""
    return SponsorEmailTemplate.objects.filter(kind=kind).first()


def is_enabled(kind):
    """BOTH gates: the platform flag AND this template's own switch.

    Two independent gates, because they answer different questions — "is this feature live at
    all" belongs to whoever deploys, "should sponsors hear this particular thing" belongs to the
    org_admin. Either one off means nothing sends.
    """
    if not comms_enabled():
        return False
    template = template_for(kind)
    return bool(template and template.enabled)


def recipient_for(sponsor):
    """The one address a sponsor email goes to: the account's own, normalised. '' if none.

    Deliberately narrow. There is no CC, no fallback to an admin, and no second address — a
    sponsor email is account correspondence, and the partner family already learned what happens
    when a "sensible fallback" recipient turns out to be the wrong audience.
    """
    return (getattr(sponsor, 'email', '') or '').strip().lower()


# ── rendering ─────────────────────────────────────────────────────────────────

def _money(value):
    """Money as a 2-decimal string, matching `sponsorship._money`, so a figure in an email and
    the same figure on the screen can never render two different ways."""
    if value in (None, ''):
        return ''
    return str(Decimal(str(value)).quantize(Decimal('0.01')))


def student_cards_blocks(cards, lang='en'):
    """The `{student_cards}` block as `(html, text)`, reusing the SAME card builders the
    pre-template emails used — the artwork thumbnail, programme, institution, facts and blurb.

    Imported inside the function on purpose: `emails` is the sending layer, and a module-level
    import would tie this pure module to it (and invite a cycle the first time `emails` wants
    something from here).

    Capped at `MAX_CARDS`, and the cap SAYS SO. The old email truncated at five in silence.
    """
    from .emails import _sponsor_card_html, _sponsor_card_text, _tax_name_map, _P

    rows = list(cards or [])
    shown, dropped = rows[:MAX_CARDS], max(0, len(rows) - MAX_CARDS)
    frontend, tax = _P.frontend_url, _tax_name_map()

    html = ''.join(_sponsor_card_html(c, lang, frontend, tax) for c in shown)
    text = '\n\n'.join(_sponsor_card_text(c, lang, frontend, tax) for c in shown)
    if dropped:
        more = f'… and {dropped} more waiting on the site.'
        html += ('<p style="margin:0 0 12px;font-size:12.5px;color:#6b7280;">'
                 + email_templates.esc(more) + '</p>')
        text += '\n\n' + more
    return html, text


def _blocks_for(context):
    """`{token: (html, text)}` for the structural tokens this context supplies."""
    if 'cards' not in context:
        return {}
    return {'student_cards': student_cards_blocks(context['cards'], context.get('lang', 'en'))}


def _scalars(context):
    """`{token: value}` for the plain tokens, with branding and the greeting fallback filled in."""
    from . import branding
    platform = branding.platform()
    frontend = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    name = (context.get('sponsor_name') or '').strip() or NO_NAME_GREETING
    return {
        'sponsor_name': name,
        'programme_name': context.get('programme_name') or platform.programme_name('en'),
        'team_signoff': context.get('team_signoff') or platform.team_signoff('en'),
        'portal_link': context.get('portal_link') or f'{frontend}/sponsor',
        'count': context.get('count', ''),
        'amount': _money(context.get('amount')),
        'available': _money(context.get('available')),
        'bank_ref': context.get('bank_ref', ''),
        'inviter_name': context.get('inviter_name', ''),
        'invitee_name': (context.get('invitee_name') or '').strip() or NO_NAME_GREETING,
        'note': context.get('note', ''),
        'invite_link': context.get('invite_link', ''),
    }


def render(kind, template, context):
    """A stored template + one recipient's data → `(subject, text_body, html_body)`.

    `html_body` is the INNER html; the sender wraps it in the shared email shell. The mechanics
    live in `email_templates.render`; what stays here is the sponsor vocabulary.
    """
    return email_templates.render(
        template.subject, template.body, _scalars(context), _blocks_for(context))


# ── the log ───────────────────────────────────────────────────────────────────

def log_attempt(kind, sponsor, recipients, subject='', ok=False, note=''):
    """Record an attempt — INCLUDING a skip.

    Every path writes a row: sent, failed, no recipient, template off. Silence that leaves no
    trace is indistinguishable from success, and on the partner side that distinction is what
    told us nine organisations could not be reached at all.
    """
    return SponsorEmailLog.objects.create(
        kind=kind, sponsor=sponsor,
        recipients=list(recipients or []),
        subject=(subject or '')[:255], ok=bool(ok), note=(note or '')[:200],
    )


def last_sent(kind, sponsor=None):
    """The most recent SUCCESSFUL attempt for a kind (optionally for one sponsor), or None."""
    qs = SponsorEmailLog.objects.filter(kind=kind, ok=True)
    if sponsor is not None:
        qs = qs.filter(sponsor=sponsor)
    return qs.first()
