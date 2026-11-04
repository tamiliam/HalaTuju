"""Team tables T1 (2026-11-03): the TABLES a person sits in — Admins, Reviewers, Mentors — and the ONE
page gate that reads them.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (APPROVED 2026-11-01). The owner: *"A person could
wear all three hats, or just one, or two. Once they wear a particular hat, they should sit in that table.
And each table has its own set of permissions."*

⚠ DERIVED, NEVER STORED (the 0123 / no-backfill lesson). A person's tables are read from what the row
already says — the lead tier, the preset label (`role`), the RESOLVED keys (`staff_permissions.resolve`)
and the mentor link (`PartnerAdmin.mentors_now`). There is no column to keep in step, so a new invitee,
a changed key and a stopped mentor are all answered the moment they happen.

THE DERIVATION (decisions.md 2026-11-03, "Team tables T1"):
  Admins    — the lead tier (`org_admin`) or a super; the preset labels `admin` / `finance`; or a TEAM
              member holding an ADMIN KEY (`ADMIN_KEYS`). ⚠ `see_all` held ALONGSIDE `qc` is what
              `qc` itself brings (`staff_permissions.IMPLIES`, T5b; a dependency before), not an admin
              hat: the QC preset holds `see_all` + `qc`, a saved `['qc']` reads the same, and both are
              Reviewers (owner ruling 8: "a QC person is a Reviewer with qc").
  Reviewers — the preset labels `reviewer` / `qc`; or a TEAM member holding `review` or `qc`. The lead
              tier holds `qc` but is NOT a Reviewer by it (owner 2026-10-19); since T2 an organisation
              admin sits here once Team -> Reviewers -> Add gave them `review`
              (`staff_permissions.lead_reviews`, owner ruling 5).
  Mentors   — `mentors_now` (7d), unchanged.
  Nobody else: a referral `partner`, a `source_partner`, a sponsor, a revoked (inactive) row and an
  unknown role sit in NO table.

Team tables T5c (P1): the page gate is `opens(admin, *v2_keys)` — v2 page keys, read through
`staff_permissions_v2.effective_v2`. The T1 `admits` (role list, widened by an admin key) is gone; the
v2 set is DERIVED from the same tables and labels, so no access moved (`test_team_tables_t5c_doors`).

⚠ THIS IS A LEAF, like `staff_permissions`: it imports nothing from `apps.scholarship`.
"""
from . import staff_permissions as sp

ADMINS = 'admins'
REVIEWERS = 'reviewers'
MENTORS = 'mentors'
#: In the order the Team page will show them (owner ruling 1).
TABLES = (ADMINS, REVIEWERS, MENTORS)

#: The keys that put a TEAM member at the Admins table (owner ruling 2). `manage_team` is lead-tier only
#: (`LEAD_TIER_ONLY`) and never resolves for a team member; it is named for completeness.
ADMIN_KEYS = ('see_all', 'spending', 'payments_prepare', 'payments_check', 'payments_approve', 'manage_team')
#: The keys that put a TEAM member at the Reviewers table.
REVIEWER_KEYS = ('review', 'qc')
#: The preset labels that ARE a table by themselves (whatever a custom set later says).
ADMIN_ROLES = ('admin', 'finance')
REVIEWER_ROLES = ('reviewer', 'qc')


def _team_member(admin):
    """A live team member: an active row whose role is a team preset (never a super, never the lead)."""
    return (admin is not None and getattr(admin, 'is_active', True) and not admin.is_super
            and admin.role in sp.TEAM_ROLES)


def admin_keys(admin):
    """The ADMIN keys a team member holds, `see_all` dropped when `qc` is held (it is what `qc`
    brings, T5b `staff_permissions.IMPLIES` — so a `qc` holder can never hold it as an admin hat)."""
    held = set(sp.resolve(admin))
    if 'qc' in held:
        held.discard('see_all')
    return tuple(k for k in ADMIN_KEYS if k in held)


def in_admins(admin):
    if admin is None or not getattr(admin, 'is_active', True):
        return False
    if admin.is_super or sp.is_lead_tier(admin):
        return True
    if not _team_member(admin):
        return False
    return admin.role in ADMIN_ROLES or bool(admin_keys(admin))


def in_reviewers(admin):
    if admin is not None and getattr(admin, 'is_active', True) and sp.lead_reviews(admin):
        return True                       # T2: the org admin added to Reviewers (owner ruling 5)
    if not _team_member(admin):
        return False
    return admin.role in REVIEWER_ROLES or bool(set(REVIEWER_KEYS) & set(sp.resolve(admin)))


def in_mentors(admin):
    return admin is not None and bool(admin.mentors_now)


def tables(admin):
    """The tables `admin` sits in, as a tuple in `TABLES` order (served by `admin/role/` as `tables`)."""
    return tuple(t for t, rule in ((ADMINS, in_admins), (REVIEWERS, in_reviewers), (MENTORS, in_mentors))
                 if rule(admin))


def opens(admin, *keys):
    """THE PAGE GATE since Team tables T5c (P1): does `admin` hold EVERY v2 page key in `keys`
    (`staff_permissions_v2.effective_v2`, which reads the stored keys through the aliases, the Admins
    table and the role label — no migration)? A super holds every key. An inactive row holds none (the
    sign-in already refuses it: `views_admin.get_admin` reads `is_active=True`). The org fence stays the
    caller's (`_org_scoped` / `_org_allows`), untouched.

    ⚠ An unknown key RAISES (`v2_order`): a misspelt door must fail loudly, never stay shut quietly.
    Each door names its OWN page key (decisions.md "Team tables T5c", the door -> key table); the
    parity test `test_team_tables_t5c_doors` proves every door answers what its T1 role rule answered."""
    # Imported here, not at the top: `staff_permissions_v2` imports this module (a leaf pair, no cycle
    # at import time). Neither imports anything from `apps.scholarship`.
    from . import staff_permissions_v2 as v2
    wanted = v2.v2_order(keys)
    if admin is None or not wanted:
        return False
    held = set(v2.effective_v2(admin))
    return all(k in held for k in wanted)


# ── The two UNION gates (T1), now read from v2 keys (T5c P1). ─────────────────────────────────────────
# Each opens only for someone holding EVERY key of its page set — today exactly the people the T1 role
# rule opened (org_admin / admin / finance or the Admins table by a key; org_admin / admin). The pages
# that have their own door (`surface_gates`, `announcements`, `surveys`, `development`, `mentoring`, the
# sponsor terms and sponsor emails) no longer come through here; the callers still here (Sources, the
# team roster `admin/admins/`, the Mentors list, Team -> Emails -> Admin emails, the credit screens) move
# to their own keys in a later phase. ⚠ All-of, never any-of: holding ONE page key must never open a
# union of pages.


def may_read_org(admin):
    """The organisation READ pages (Organisation, Invitations, People, Sponsors + credits ledger):
    `staff_permissions_v2.ORG_READ_V2`, every one held."""
    from . import staff_permissions_v2 as v2
    return opens(admin, *v2.ORG_READ_V2)


def may_do_admin_work(admin):
    """The organisation WORK pages, never finance: `staff_permissions_v2.ADMIN_WORK_V2`, every one held."""
    from . import staff_permissions_v2 as v2
    return opens(admin, *v2.ADMIN_WORK_V2)


# ── Team tables T2: what an invitation STARTS a person at (owner ruling 4). ──────────────────────────
#: "No View-only admin and no separate Finance label: one Admin; a new admin starts at the absolute
#: minimum" — an invited Admin holds exactly `see_all`; payment keys are ticked afterwards on Team. Every
#: other role starts at its preset (NULL). An OLD pending invitation is untouched: its row was written
#: when it was sent, so it accepts onto today's preset.
INVITE_START = {'admin': ('see_all',)}


def invite_permissions(role):
    """The `permissions` value a NEW invitation's row is written with: a list, or None (the preset)."""
    start = INVITE_START.get(role)
    return list(start) if start is not None else None
