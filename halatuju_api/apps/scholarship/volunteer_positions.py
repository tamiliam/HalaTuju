"""Request #69 (2026-11-17): "Our volunteers" on the sponsor's Trust & Transparency page — the share of an
organisation's team at each highest-position level, and NEVER anything about one person.

WHO COUNTS: the organisation's OWN team (`owning_organisation`), active (`is_active`) and not archived
(`archived_at` NULL), who have answered `StaffProfile.highest_position`. Every team role counts, a mentor
login and a "No group" member included; a super (platform-level, no organisation) never does, nor a
source user or a referral partner (`NOT_TEAM`: they are not the organisation's volunteers).

WHICH ORGANISATION: the one running the gifts the sponsor was ACCEPTED into (approved
`SponsorProgrammeMembership` rows), through `usage.sole_organisation_id` — exactly one organisation, or
no figures at all (a sponsor of none, or of two, gets None; the `sponsor_notify._sponsor_org_id` rule).

PRIVACY: below `MIN_ANSWERS` answers the summary is None, so the API sends no figures (the page leaves
the section off). Otherwise `{count, shares}` and nothing else: no ids, names or rows.

ROUNDING: largest remainder (Hamilton). Each share is floored to a whole percent; the points left over to
reach 100 go one each to the levels with the largest dropped fractions (ties: the higher level first,
the `KEYS` order). So the four shares always add up to exactly 100, and each is within one point of its
true value. The page's headline adds the two top shares as served.
"""
from django.db.models import Count

from . import usage
from .models import SponsorProgrammeMembership, StaffProfile

#: The four levels, highest first (the column's choice keys).
KEYS = tuple(k for k, _ in StaffProfile.HIGHEST_POSITIONS)
#: Fewer answers than this and no figures leave the server.
MIN_ANSWERS = 5
#: Roles that sign in but are not the organisation's team (a super is excluded by having no organisation).
NOT_TEAM = ('super', 'source_partner', 'partner')


def sponsor_organisation_id(sponsor):
    """The one organisation whose gifts the sponsor was accepted into, else None."""
    return usage.sole_organisation_id(
        SponsorProgrammeMembership.objects
        .filter(sponsor=sponsor, status='approved')
        .values_list('programme__organisation_id', flat=True).distinct())


def counts_for_organisation(org_id):
    """`{key: n}` for each level: the organisation's active, non-archived team who answered it."""
    rows = (StaffProfile.objects
            .filter(partner_admin__owning_organisation_id=org_id, partner_admin__is_active=True,
                    partner_admin__archived_at__isnull=True, highest_position__in=KEYS)
            .exclude(partner_admin__role__in=NOT_TEAM)
            .values('highest_position').annotate(n=Count('id')))
    found = {r['highest_position']: r['n'] for r in rows}
    return {k: found.get(k, 0) for k in KEYS}


def shares(counts):
    """Whole percentages summing to 100 (largest remainder; see the module docstring)."""
    total = sum(counts.values())
    exact = {k: counts[k] * 100 / total for k in KEYS}
    out = {k: int(exact[k]) for k in KEYS}
    order = sorted(KEYS, key=lambda k: (-(exact[k] - out[k]), KEYS.index(k)))
    for k in order[:100 - sum(out.values())]:
        out[k] += 1
    return out


def summary_for_organisation(org_id):
    """`{count, shares}` for the organisation, or None below `MIN_ANSWERS` (or with no organisation)."""
    if org_id is None:
        return None
    counts = counts_for_organisation(org_id)
    total = sum(counts.values())
    if total < MIN_ANSWERS:
        return None
    return {'count': total, 'shares': shares(counts)}


def summary_for_sponsor(sponsor):
    """The Trust page's `volunteers`: the sponsor's one organisation's summary, or None."""
    return summary_for_organisation(sponsor_organisation_id(sponsor))
