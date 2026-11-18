"""Request #69 (2026-11-17): "Our volunteers" on the sponsor's Trust & Transparency page — the share of an
organisation's team at each highest-position level, and NEVER anything about one person.

WHO IS ASKED (`asked`, the ONE rule; owner 2026-11-17): every team kind, and never a super (platform
level, no organisation; review round 3), a source user or a referral partner (`NOT_ASKED`: they are not
the organisation's volunteers). The completion item, the console's banner question and the My Profile
field all follow it; `PATCH admin/me/` refuses the field from anybody else (`bad_highest_position`).

WHO COUNTS: the organisation's OWN team (`owning_organisation`), active (`is_active`) and not archived
(`archived_at` NULL), who have answered `StaffProfile.highest_position`. Every asked kind counts, a
mentor login and a "No group" member included, and a PAUSED reviewer too (paused is not gone); a super
and a `NOT_ASKED` kind never do. `is_active` is the ONLY "switched off" test: a SUSPENDED mentor is out
because Suspend turns their login off (`mentor_invite._switch_off`). ⚠ NEVER filter on
`Mentor.deactivated_at` (review round 3): an ACTIVE person keeps a deactivated mentor link after they
stop mentoring (`staff_mentor.stop`), leave Mentors for "No group" (`staff_mentor.remove_mentor_login`)
or hold a legacy Finance row (Admin -> Finance before that label was retired), and they are still the
organisation's team. A RESTORED (re-invited) person counts with the answer they kept, before signing in again.

WHICH ORGANISATION: the one running the gifts the sponsor was ACCEPTED into (approved
`SponsorProgrammeMembership` rows), through `usage.sole_organisation_id` — exactly one organisation, or
no figures at all (a sponsor of none, or of two, gets None; the `sponsor_notify._sponsor_org_id` rule).

PRIVACY (owner 2026-11-17):
- below `MIN_ANSWERS` answers the summary is None, so the API sends no figures (the page leaves the
  section off);
- the exact count NEVER leaves the server: `count_at_least` is the largest of `BANDS` at or below it;
- the four `shares` are sent only when no level holds every answer and no level holds exactly one
  person (either could single somebody out); otherwise `shares` is None and the page shows only the
  headline and the footnote;
- no ids, names or rows, ever.

ROUNDING: largest remainder (Hamilton). Each share is floored to a whole percent; the points left over to
reach 100 go one each to the levels with the largest dropped fractions (ties: the higher level first,
the `KEYS` order). So the four shares always add up to exactly 100, and each is within one point of its
true value. `senior_pct` (the headline) is worked out from the exact counts the same way, ALWAYS: the
top two levels' largest-remainder shares added together — so when the bars are shown, the headline is
exactly the sum of the two top bars, and when they are withheld it is the same number.
"""
from django.db.models import Count

from . import usage
from .models import SponsorProgrammeMembership, StaffProfile

#: The four levels, highest first (the column's choice keys).
KEYS = tuple(k for k, _ in StaffProfile.HIGHEST_POSITIONS)
#: The headline's levels: "a senior manager role or above".
SENIOR = ('c_level', 'head')
#: Fewer answers than this and no figures leave the server.
MIN_ANSWERS = 5
#: The count is sent as the largest of these at or below it, never exactly.
BANDS = (5, 10, 20, 50, 100, 200, 500)
#: Kinds that sign in but are not the organisation's team: never asked, never counted.
NOT_ASKED = ('source_partner', 'partner')
#: Never counted (a super is excluded by having no organisation, and by its role).
NOT_TEAM = ('super', *NOT_ASKED)


def asked(admin):
    """True when this person is asked their highest position (see the module docstring): never a super."""
    return admin is not None and not admin.is_super and admin.role not in NOT_ASKED


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


def band(total):
    """The largest of `BANDS` at or below `total` (None below the first)."""
    below = [b for b in BANDS if b <= total]
    return below[-1] if below else None


def bars_safe(counts):
    """False when a level holds every answer or exactly one person (see the module docstring)."""
    total = sum(counts.values())
    return all(counts[k] != total and counts[k] != 1 for k in KEYS)


def summary_for_organisation(org_id):
    """`{count_at_least, senior_pct, shares}` for the organisation, or None below `MIN_ANSWERS` (or with no
    organisation). `shares` is None when `bars_safe` says no."""
    if org_id is None:
        return None
    counts = counts_for_organisation(org_id)
    total = sum(counts.values())
    if total < MIN_ANSWERS:
        return None
    split = shares(counts)
    return {'count_at_least': band(total), 'senior_pct': sum(split[k] for k in SENIOR),
            'shares': split if bars_safe(counts) else None}


def summary_for_sponsor(sponsor):
    """The Trust page's `volunteers`: the sponsor's one organisation's summary, or None."""
    return summary_for_organisation(sponsor_organisation_id(sponsor))
