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

⚠ NOT ACCESS CONTROL. A referral source is an ATTRIBUTION relationship, never a scope; nothing
here decides who may see what. The org fence is the caller's (`_AdminBase`).

Pure reads and validated writes only. The view that calls `apply_changes` writes the audit line,
so every `AUDIT` line stays on the `views_admin` package logger.
"""
from django.db.models import Count, Q

from .models import ProgrammeReferralSource

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


def active_sources():
    """Every source a gift's Configuration may offer: switched on in Sources, not suspended, and
    never a tenant organisation (the table is dual-role — see `PartnerOrganisationQuerySet`)."""
    from apps.courses.models import PartnerOrganisation
    return (PartnerOrganisation.objects
            .filter(show_in_apply=True, is_active=True)
            .exclude(pk__in=PartnerOrganisation.objects.tenants().values('pk')))


def sources_for(programme):
    """`[{code, name, on}]` for the gift's Configuration — active sources only, by name."""
    on = set(ProgrammeReferralSource.objects.filter(programme=programme)
             .values_list('source_id', flat=True))
    return [{'code': s.code, 'name': s.name, 'on': s.id in on}
            for s in active_sources().order_by('name', 'code')]


def offered_sources(programme):
    """The sources THIS gift's apply form lists: its switched-on links whose source is still
    active (`show_in_apply`, `is_active`, not a tenant). A link whose source was switched off in
    Sources stays in the table but is not offered. No gift → nothing."""
    if programme is None:
        return active_sources().none()
    return active_sources().filter(gift_links__programme=programme).order_by('name', 'code')


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


def resolve_changes(raw):
    """Validate a PUT's `sources` map — `{<code>: true|false}` — BEFORE anything is written.

    Returns `{PartnerOrganisation: bool}`. Refuses the WHOLE map on the first bad entry:
    `bad_sources` (not a map), `bad_source_value` (not a boolean), `unknown_source` (no such
    code, switched off, suspended, or a tenant — the screen never offers any of those).
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise GiftSourceError('bad_sources')
    by_code = {s.code: s for s in active_sources().filter(code__in=[str(k) for k in raw])}
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
