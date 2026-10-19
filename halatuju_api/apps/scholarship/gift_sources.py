"""Per-gift referral sources — which organisations a gift's apply form lists (2026-10-08).

Owner's rulings (decisions.md, "A gift chooses its referral sources"): each gift (Programme)
chooses its own set, in that gift's Configuration; the screen offers every ACTIVE source —
`show_in_apply` AND `is_active`, never a tenant — each with an on/off switch. A source newly
switched on joins NO gift, and a new gift starts with NO sources. The three fixed choices
(Halatuju.xyz, Facebook / WhatsApp, Other) are on every form and are not rows here.

Sprint 1 (2026-10-08) landed the table, the Configuration card and the Sources-page count.
Sprint 2 (same day) put it in front of the student: the public intake serves the gift's offered
sources (`public_sources`), the apply form lists them followed by the three fixed choices, and the
submit REFUSES a code the gift does not offer (`is_offered`) — owner's ruling. The legacy
`pushparani` / `govind` codes are gone from every form (courses migration 0077 moved them to
`other`).

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

#: The three choices on EVERY apply form, after the gift's own sources (owner, 2026-10-08) — never
#: rows here, never switches. The web holds the same three for their labels (drift-tested by
#: `src/lib/__tests__/referralSources.test.ts`).
FIXED_CODES = ('halatuju', 'social', 'other')


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


def is_offered(programme, code):
    """May a student submit `code` as who referred them, on this gift? Blank (not answered) and
    the three fixed choices always; otherwise only a source this gift offers right now."""
    # Exact match, no trimming: the code checked is the code the profile will store.
    code = code or ''
    if not code or code in FIXED_CODES:
        return True
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


def gift_counts(sources_qs, programmes_qs):
    """Annotate sources with `gift_count`: links on the ACTIVE gifts in `programmes_qs` (the
    caller's own scope). ONE query for the whole list — never one per row."""
    scope = programmes_qs.filter(is_active=True).values('pk')
    return sources_qs.annotate(gift_count=Count(
        'gift_links', filter=Q(gift_links__programme__in=scope), distinct=True))
