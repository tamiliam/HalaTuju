"""Per-gift referral sources — which organisations a gift's apply form lists (2026-10-08).

Owner's rulings (decisions.md, "A gift chooses its referral sources"): each gift (Programme)
chooses its own set, in that gift's Configuration; the screen offers every ACTIVE source —
`show_in_apply` AND `is_active`, never a tenant — each with an on/off switch. A source newly
switched on joins NO gift, and a new gift starts with NO sources. The three fixed choices
(Halatuju.xyz, Facebook / WhatsApp, Other) are on every form and are not rows here.

Sprint 1 (2026-10-08) landed the table, the Configuration card and the Sources-page count.
Sprint 2 (same day) put it in front of the student: the public intake serves the gift's offered
sources (`public_sources`), the apply form lists them followed by the fixed choices, and the
submit REFUSES a code the gift does not offer (`is_offered`) — owner's ruling. The legacy
`pushparani` / `govind` codes are gone from every form (courses migration 0077 moved them to
`other`).

Request #44 (2026-10-25, owner reversed "the fixed three are not toggles" for two of them): a gift
may switch off `social` (Facebook / WhatsApp) and `halatuju` (Halatuju.xyz) in its Configuration —
a partner-run gift wants its referrals attributed to its partners. `other` is never switchable.
ONE definition of what a gift offers, `offered_fixed_codes`, read by `is_offered` (the submit), the
public intake (`fixed_sources`) and the Configuration (`fixed_sources_for`, `resolve_fixed_changes`).

Sources-and-referrals Sprint B (2026-10-18): a source is its own row (`ReferralSource`) OWNED BY AN
ORGANISATION, and every list here is read INSIDE the gift's own organisation — a gift can only ever
offer, list or be switched to its own organisation's sources. A code is unique per organisation, so
a source is never looked up by its code alone.

⚠ NOT ACCESS CONTROL. A referral source is an ATTRIBUTION relationship, never a scope; nothing
here decides who may see what. The org fence is the caller's (`_AdminBase`).

Pure reads and validated writes only. The view that calls `apply_changes` writes the audit line,
so every `AUDIT` line stays on the `views_admin` package logger.
"""
from django.db.models import Count, Q

from .models import ProgrammeReferralSource, ReferralSource

#: The three fixed choices, after the gift's own sources (owner, 2026-10-08) — never rows here. The
#: web holds the same three for their labels (drift-tested by `src/lib/__tests__/referralSources.test.ts`).
#: A past answer naming any of them keeps its label everywhere, offered today or not.
FIXED_CODES = ('halatuju', 'social', 'other')

#: The fixed choices a GIFT may switch off (request #44) -> the Programme column holding the switch.
#: `other` is deliberately absent: it is on every form, always.
SWITCHABLE_FIXED = {'halatuju': 'offers_halatuju', 'social': 'offers_social'}


class GiftSourceError(Exception):
    """A refused change, with the code the screen renders and the source code it named."""

    def __init__(self, code, source=''):
        super().__init__(code)
        self.code = code
        self.source = source


def active_sources(organisation_id):
    """Every source a gift of THIS organisation may offer: owned by it, switched on in Sources, and
    not suspended. Since Sprint B a tenant can never be one (sources are their own table), and an
    organisation-less caller (`None`) gets none, never everybody's."""
    return ReferralSource.objects.owned_by(organisation_id).filter(show_in_apply=True,
                                                                   is_active=True)


def sources_for(programme):
    """`[{code, name, on}]` for the gift's Configuration — its organisation's active sources only,
    by name."""
    on = set(ProgrammeReferralSource.objects.filter(programme=programme)
             .values_list('source_id', flat=True))
    return [{'code': s.code, 'name': s.name, 'on': s.id in on}
            for s in active_sources(programme.organisation_id).order_by('name', 'code')]


def offered_sources(programme):
    """The sources THIS gift's apply form lists: its switched-on links whose source is still
    active (`show_in_apply`, `is_active`) and belongs to the gift's own organisation. A link whose
    source was switched off in Sources stays in the table but is not offered. No gift → nothing."""
    if programme is None:
        return ReferralSource.objects.none()
    return (active_sources(programme.organisation_id)
            .filter(gift_links__programme=programme).order_by('name', 'code'))


def public_sources(programme):
    """What the PUBLIC intake serves: `[{code, name}]` and NOTHING else — never a contact
    person, email or phone (`test_gift_sources_public.py` plants them and asserts they stay out)."""
    return [{'code': s.code, 'name': s.name} for s in offered_sources(programme)]


def offered_fixed_codes(programme):
    """The fixed choices THIS gift's apply form offers, in form order — `other` always, `halatuju`
    and `social` unless the gift switched them off (request #44). No gift → all three (nothing can
    have switched them off)."""
    return [code for code in FIXED_CODES
            if programme is None or code not in SWITCHABLE_FIXED
            or getattr(programme, SWITCHABLE_FIXED[code])]


def fixed_sources_for(programme):
    """`[{code, on, switchable}]` for the gift's Configuration — all three, in form order."""
    offered = offered_fixed_codes(programme)
    return [{'code': code, 'on': code in offered, 'switchable': code in SWITCHABLE_FIXED}
            for code in FIXED_CODES]


def is_offered(programme, code):
    """May a student submit `code` as who referred them, on this gift? Blank (not answered) always;
    a fixed choice when this gift offers it; otherwise only a source this gift offers right now."""
    # Exact match, no trimming: the code checked is the code the profile will store.
    code = code or ''
    if not code:
        return True
    if code in FIXED_CODES:
        return code in offered_fixed_codes(programme)
    return offered_sources(programme).filter(code=code).exists()


def submitted_source(organisation_id, code):
    """The SOURCE an application's answer names (sources Sprint C, 2026-10-19): the source with
    that code owned by the APPLICATION'S organisation — switched on or not, because this records
    what was answered — or None for blank, a fixed choice, or a code that organisation has no source
    for. The submit (`services/intake.create_application`) and scholarship 0174's backfill use this
    one rule, so an application can never be attributed to another organisation's source."""
    if not code or code in FIXED_CODES:
        return None
    return ReferralSource.objects.owned_by(organisation_id).filter(code=code).first()


def resolve_changes(raw, programme):
    """Validate a PUT's `sources` map — `{<code>: true|false}` — BEFORE anything is written.

    Returns `{ReferralSource: bool}`. Refuses the WHOLE map on the first bad entry:
    `bad_sources` (not a map), `bad_source_value` (not a boolean), `unknown_source` (no such
    code IN THIS GIFT'S ORGANISATION, switched off, or suspended — the screen never offers any of
    those; another organisation's source reads exactly like one that does not exist).
    A FIXED code in the same map is skipped here — `resolve_fixed_changes` owns it (request #44).
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GiftSourceError('bad_sources')
    by_code = {s.code: s for s in active_sources(programme.organisation_id)
               .filter(code__in=[str(k) for k in raw])}
    resolved = {}
    for code, value in raw.items():
        if not isinstance(value, bool):
            raise GiftSourceError('bad_source_value', str(code))
        if str(code) in FIXED_CODES:
            continue
        source = by_code.get(str(code))
        if source is None:
            raise GiftSourceError('unknown_source', str(code))
        resolved[source] = value
    return resolved


def apply_changes(programme, resolved):
    """Write only the rows that change. Returns `[(source, was, now)]` for the caller to audit."""
    have = set(ProgrammeReferralSource.objects.filter(
        programme=programme, source__in=list(resolved)).values_list('source_id', flat=True))
    changed = []
    for source, want in resolved.items():
        was = source.id in have
        if was == want:
            continue
        if want:
            ProgrammeReferralSource.objects.get_or_create(programme=programme, source=source)
        else:
            ProgrammeReferralSource.objects.filter(programme=programme, source=source).delete()
        changed.append((source, was, want))
    return changed


def resolve_fixed_changes(raw):
    """The FIXED codes in a PUT's `sources` map (request #44) → `{code: bool}`, validated before
    anything is written. `other` (or any fixed code without a switch) → `fixed_source_locked`; the
    map's shape and its values are refused exactly as `resolve_changes` refuses them."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GiftSourceError('bad_sources')
    resolved = {}
    for code, value in raw.items():
        code = str(code)
        if code not in FIXED_CODES:
            continue
        if not isinstance(value, bool):
            raise GiftSourceError('bad_source_value', code)
        if code not in SWITCHABLE_FIXED:
            raise GiftSourceError('fixed_source_locked', code)
        resolved[code] = value
    return resolved


def apply_fixed_changes(programme, resolved):
    """Write only the switches that change. Returns `[(code, was, now)]` for the caller to audit."""
    changed, fields = [], []
    for code, want in resolved.items():
        field = SWITCHABLE_FIXED[code]
        was = getattr(programme, field)
        if was == want:
            continue
        setattr(programme, field, want)
        fields.append(field)
        changed.append((code, was, want))
    if fields:
        programme.save(update_fields=fields)
    return changed


def gift_counts(sources_qs, programmes_qs):
    """Annotate sources with `gift_count`: links on the ACTIVE gifts in `programmes_qs` (the
    caller's own scope). ONE query for the whole list — never one per row."""
    scope = programmes_qs.filter(is_active=True).values('pk')
    return sources_qs.annotate(gift_count=Count(
        'gift_links', filter=Q(gift_links__programme__in=scope), distinct=True))
