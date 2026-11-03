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


def admits(admin, *, roles, admin_keys_any=()):
    """THE PAGE GATE for admin work: may `admin` open a page whose rule is `roles` (the preset labels
    that open it today) and, for somebody at the Admins table, `admin_keys_any` (holding ANY opens it)?

    ⚠ ALWAYS A UNION WITH TODAY'S ROLE RULE, so nobody can lose a page they have; and the key half
    admits ONLY a person at the Admins table, through keys they already hold. A super passes, as
    `has_role` passes a super. The org fence is the caller's (`_org_scoped` / `_org_allows`), untouched.

    A future admin key (`team_view`, `requests`, …) opens a page by being added to that page's
    `admin_keys_any` — and to the catalogue — never by another rewrite."""
    if admin is None:
        return False
    if admin.is_super or admin.role in roles:
        return True
    if not admin_keys_any or not in_admins(admin):
        return False
    held = admin_keys(admin)
    return any(k in held for k in admin_keys_any)


# ── The page gates (T1). Each is today's role rule, widened ONLY to the Admins table by a key. ────────

#: The organisation pages an Admin READS: Organisation, Invitations, People, Sponsors (+ the sponsor
#: detail, the sponsorships list, the wallet-credit screens). Today super / org_admin / admin / finance;
#: any admin key opens them for a person at the Admins table — which reproduces both presets.
ORG_READ_ROLES = ('org_admin', 'admin', 'finance')
ORG_READ_KEYS = ADMIN_KEYS


def may_read_org(admin):
    return admits(admin, roles=ORG_READ_ROLES, admin_keys_any=ORG_READ_KEYS)


#: The organisation work an Admin DOES, never finance: Sources (manage) and the witness override, the
#: Mentors page (read), the team roster (`admin/admins/`), Announcements, Surveys, Development, the sponsor
#: terms and the sponsor / partner emails. Today super / org_admin / admin.
#: ⚠ `ADMIN_WORK_KEYS` IS EMPTY ON PURPOSE (T1, conservative reading — decisions.md 2026-11-03): these
#: pages WRITE, and the only admin key that separates the `admin` preset from `finance` is `see_all`, a
#: READ key. Opening writes on a read key would make "see everything" mean "post, edit and assign", so a
#: person seated at the Admins table by keys does not reach them yet. A future key (e.g. `announcements`,
#: `sources`) opens them by being named here — `('see_all',)` would reproduce the presets exactly too.
ADMIN_WORK_ROLES = ('org_admin', 'admin')   # THE one home (announcements / surveys / development read it)
ADMIN_WORK_KEYS = ()


def may_do_admin_work(admin):
    return admits(admin, roles=ADMIN_WORK_ROLES, admin_keys_any=ADMIN_WORK_KEYS)


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
