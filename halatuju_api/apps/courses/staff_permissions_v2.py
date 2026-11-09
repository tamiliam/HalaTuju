"""Team tables T5a (2026-11-03): the permission vocabulary v2 — one key per PAGE x TIER, in four groups —
the alias table from today's keys, and a READ-ONLY answer to "which v2 keys does this person effectively
hold today?".

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (T5, owner "approve all", rulings 1-8); evidence
pack: the lead's T5 investigation, sections A (page inventory) and F (catalogue + live shapes).

⚠ A GATE FOR THE ORGANISATION / ADMIN-WORK PAGE DOORS SINCE T5c (P1): `staff_tables.opens` reads
`effective_v2` (decisions.md "Team tables T5c", the door -> key table). ONLY `staff_tables` imports
this module (`test_permission_catalogue_v2.V2Importers`, an allowlist); a door module asks
`staff_tables.opens_door(admin, '<door>')`, whose keys are `staff_tables.DOOR_KEYS` (T5c P4a). The rest (review / QC / payments / spending / the
lead-only pages) still opens through `staff_permissions.resolve` / `has_perm` and role checks; T5d-T5f
convert them; T5g opens the editor (and `asked_set`) to v2 keys. Until then a stored `permissions` list
holds TODAY's keys only: the save door (`staff_permissions_admin.asked_set`) refuses a v2 key as
`unknown_permission`, and `staff_permissions.clean` drops one on read.

⚠ THIS IS A LEAF, like `staff_permissions` and `staff_tables`: it imports nothing from `apps.scholarship`.
The role-label grants below that live in scholarship code (the wallet-credit chain) are restated as
data, each with its source line, and `test_permission_catalogue_v2` asks the real code they restate.
"""
from . import staff_permissions as sp
from . import staff_tables

ORGANISATION, PROGRAMME, ENGAGEMENT, MONEY = 'organisation', 'programme', 'engagement', 'money'
#: In the order the Permissions tab will show them (owner ruling 1: per page, shown in groups).
GROUPS = (ORGANISATION, PROGRAMME, ENGAGEMENT, MONEY)
VIEW, EDIT, PREPARE, CHECK, APPROVE = 'view', 'edit', 'prepare', 'check', 'approve'
TIERS = (VIEW, EDIT, PREPARE, CHECK, APPROVE)

#: Owner ruling 3: the organisation admin's lead-only powers become keys, but NO PRESET GRANTS THEM —
#: only the org admin ticks them (T5g). Marked per row below.
LEAD_ONLY = True

#: key -> (group, page, tier, lead_only). In display order: group, then page, then tier.
#: ⚠ `team.edit` is NOT offered (ruling: not in T5); `manage_team` stays lead-tier only and is not v2.
CATALOGUE_V2 = {
    # ── Organisation ─────────────────────────────────────────────────────────────────────────────
    'invitations.view':      (ORGANISATION, 'invitations', VIEW, False),
    'invitations.edit':      (ORGANISATION, 'invitations', EDIT, LEAD_ONLY),
    'team.view':             (ORGANISATION, 'team', VIEW, False),       # Team tables + Mentors list
    'sources.view':          (ORGANISATION, 'sources', VIEW, False),
    'sources.edit':          (ORGANISATION, 'sources', EDIT, False),
    'sponsors.view':         (ORGANISATION, 'sponsors', VIEW, False),
    'sponsors.edit':         (ORGANISATION, 'sponsors', EDIT, False),   # terms, emails, record a credit
    'sponsors.check':        (ORGANISATION, 'sponsors', CHECK, False),  # the credit's middle check
    'sponsors.approve':      (ORGANISATION, 'sponsors', APPROVE, LEAD_ONLY),
    'billing.view':          (ORGANISATION, 'billing', VIEW, LEAD_ONLY),
    'billing.edit':          (ORGANISATION, 'billing', EDIT, LEAD_ONLY),
    'requests.view':         (ORGANISATION, 'requests', VIEW, LEAD_ONLY),
    'requests.edit':         (ORGANISATION, 'requests', EDIT, LEAD_ONLY),
    'requests.approve':      (ORGANISATION, 'requests', APPROVE, LEAD_ONLY),
    'settings.edit':         (ORGANISATION, 'settings', EDIT, LEAD_ONLY),
    # ── Programme ────────────────────────────────────────────────────────────────────────────────
    'students.view':         (PROGRAMME, 'students', VIEW, False),      # Applications (S1: not Scholars)
    # Sprint S1 (owner 2026-11-09): the Scholars page and every scholar's file — `scholars` (`ALIASES`).
    'scholars.view':         (PROGRAMME, 'scholars', VIEW, False),
    'students.edit':         (PROGRAMME, 'students', EDIT, LEAD_ONLY),  # assign (never self), nudge
    'students.approve':      (PROGRAMME, 'students', APPROVE, LEAD_ONLY),
    'contracts.view':        (PROGRAMME, 'contracts', VIEW, LEAD_ONLY),
    'contracts.edit':        (PROGRAMME, 'contracts', EDIT, LEAD_ONLY),
    # Ruling 2: gift configuration stays under Programme, with each gift ("Programme Settings").
    'programmes.edit':       (PROGRAMME, 'programme_settings', EDIT, LEAD_ONLY),
    # ── Engagement (each names every scholar: ruling 7, needs `students.view`) ──────────────────
    'announcements.view':    (ENGAGEMENT, 'announcements', VIEW, False),
    'announcements.edit':    (ENGAGEMENT, 'announcements', EDIT, False),
    'surveys.view':          (ENGAGEMENT, 'surveys', VIEW, False),
    'surveys.edit':          (ENGAGEMENT, 'surveys', EDIT, False),
    'development.view':      (ENGAGEMENT, 'development', VIEW, False),
    'development.edit':      (ENGAGEMENT, 'development', EDIT, False),
    # Lead ruling 2026-11-03 (T5a): the scholar MENTORING tab names scholars, so `team.view` must never
    # cover it — its own Engagement key.
    'mentoring.view':        (ENGAGEMENT, 'mentoring', VIEW, False),
    'mentoring.edit':        (ENGAGEMENT, 'mentoring', EDIT, False),
    # ── Money ────────────────────────────────────────────────────────────────────────────────────
    'payments.view':         (MONEY, 'payments', VIEW, False),
    'payments.prepare':      (MONEY, 'payments', PREPARE, False),
    'payments.check':        (MONEY, 'payments', CHECK, False),
    'payments.approve':      (MONEY, 'payments', APPROVE, False),
    'spending.view':         (MONEY, 'spending', VIEW, False),
    'spending.edit':         (MONEY, 'spending', EDIT, False),
}

#: The Reviewer-table hats keep today's names and meaning in v2 (`review` = assigned cases, `qc` = the
#: QC gate). They are both vocabularies at once; T5b made `qc` self-sufficient (`HAT_IMPLIES`).
HATS = ('review', 'qc')

#: Every v2 key, in display order: the page keys, then the hats.
V2_KEYS = (*CATALOGUE_V2, *HATS)


def _page_view(key):
    tier = CATALOGUE_V2[key][2]
    view = f'{key.rsplit(".", 1)[0]}.view'
    return view if tier != VIEW and view in CATALOGUE_V2 else None


#: Rules as data: every non-view tier implies its page's view, where the page has one (`edit`,
#: `prepare`, `check`, `approve` => `view`). ⚠ `approve` NEVER implies `edit` (nor `check`).
IMPLIES = {k: (_page_view(k),) for k in CATALOGUE_V2 if _page_view(k)}

#: Team tables T5b (owner 2026-11-03, "QC is self-sufficient"): the `qc` HAT implies `students.view` —
#: the v2 spelling of `staff_permissions.IMPLIES` (`qc` brings `see_all`). Kept apart from `IMPLIES`, whose
#: rows are page tiers. ⚠ STILL NOT A GATE: QC opens through `resolve` / `_b40_scope`, as before.
HAT_IMPLIES = {'qc': ('students.view',)}

#: Dependencies as data (ruling 7): the Engagement pages name every scholar, so each needs
#: `students.view` — as `qc` needed `see_all` in the old vocabulary until T5b (now `qc` brings it).
DEPENDS_ON_V2 = {k: ('students.view',) for k, row in CATALOGUE_V2.items() if row[0] == ENGAGEMENT}

#: Old key -> the v2 keys it MEANS. `manage_team` maps to nothing: it is lead-tier only, and the lead
#: holds every v2 key anyway.
ALIASES = {
    'review':           ('review',),
    'see_all':          ('students.view',),
    'scholars':         ('scholars.view',),     # S1
    'qc':               ('qc',),
    'spending':         ('spending.view', 'spending.edit'),
    'payments_prepare': ('payments.view', 'payments.prepare'),
    'payments_check':   ('payments.view', 'payments.check'),
    # TD-475 (A1.10a): `payments_approve` IS the wallet credit's checker seat (`credit_steps.CHECKER_KEY`),
    # so it means the credit's middle check too (was the `finance` LABEL's grant).
    'payments_approve': ('payments.view', 'payments.approve', 'sponsors.check'),
    'manage_team':      (),
    # A1.13b: the award-withdrawal seats have no v2 key yet (like `manage_team`).
    'award_withdraw_request': (),
    'award_withdraw_approve': (),
}

#: The organisation READ pages (Organisation, Invitations, Team, Sponsors + credits ledger). A team
#: member at the ADMINS table (`staff_tables.in_admins`: the `admin` / `finance` label, or an admin key
#: — T1) holds them (`TABLE_GRANTS`); `staff_tables.may_read_org` opens on all of them (T5c).
#: T5c P4a: the one spelling is `staff_tables.DOOR_KEYS` (the door -> key table); read from there.
ORG_READ_V2 = staff_tables.DOOR_KEYS['org_read']

#: The organisation WORK pages, never finance: Sources and the witness override, Mentors read and the
#: roster, Announcements, Surveys, Development, sponsor terms and sponsor / partner emails, and on a
#: scholar the mentoring tab (`mentoring.py`), scholar growth (`development.py`) and scholar surveys
#: (`surveys.py`). The `admin` LABEL holds them (`LABEL_GRANTS`; T1's `ADMIN_WORK_ROLES` was
#: org_admin / admin, and the lead tier holds every key); `staff_tables.may_do_admin_work` opens on all.
ADMIN_WORK_V2 = staff_tables.DOOR_KEYS['admin_work']

#: What a TABLE seat grants (T1 derivation, `staff_tables`). Only the Admins table grants page keys.
TABLE_GRANTS = {staff_tables.ADMINS: ORG_READ_V2}

#: What a ROLE LABEL still grants by itself today. `admin`: the admin-work pages (above), and it records,
#: maker-signs and voids a wallet credit (`sponsorship.py`, `credit_steps.step_refusal`) — scholarship
#: code this leaf cannot import. TD-475 (A1.10a): `finance` grants nothing by itself any more — the
#: credit's middle check is the KEY `payments_approve` (`ALIASES`), and `sponsors.view` comes with the
#: Admins table seat the label (or the key) already gives (`TABLE_GRANTS`).
LABEL_GRANTS = {
    'admin': (*ADMIN_WORK_V2,),
}


def v2_order(keys):
    """`keys` in `V2_KEYS` order, as a tuple. Raises on a key v2 does not have."""
    held = set(keys)
    unknown = held - set(V2_KEYS)
    if unknown:
        raise KeyError(f'unknown v2 permission(s) {sorted(unknown)!r}')
    return tuple(k for k in V2_KEYS if k in held)


def with_implied_views(keys):
    """`keys` plus every view an `edit` / `prepare` / `check` / `approve` implies (never the reverse),
    and `students.view` for the `qc` hat (`HAT_IMPLIES`, T5b)."""
    held = set(keys)
    for key in list(held):
        held.update(IMPLIES.get(key, ()))
        held.update(HAT_IMPLIES.get(key, ()))
    return v2_order(held)


def dependency_gaps(keys):
    """``{key: missing}`` for each held key whose ruling-7 dependency is not held. Empty = consistent."""
    held = set(keys)
    return {k: tuple(n for n in needs if n not in held)
            for k, needs in DEPENDS_ON_V2.items() if k in held and not all(n in held for n in needs)}


def through_aliases(old_keys):
    """Today's keys read through `ALIASES`, as a v2 tuple."""
    return v2_order(k for old in old_keys for k in ALIASES[old])


def lead_v2(admin):
    """The lead tier's v2 set: every page key, the `qc` hat (the lead tier holds `qc`), and `review`
    when Team -> Reviewers added them (T2, `staff_permissions.lead_reviews`)."""
    hats = ('qc', 'review') if sp.lead_reviews(admin) else ('qc',)
    return v2_order((*CATALOGUE_V2, *hats))


def effective_v2(admin):
    """The v2 keys `admin` EFFECTIVELY holds: their resolved old keys through `ALIASES`, plus what their
    T1 table and their role LABEL open (`TABLE_GRANTS`, `LABEL_GRANTS`).

      super            -> every v2 key (as `resolve` answers every old key)
      org_admin        -> `lead_v2`
      inactive row     -> nothing (sign-in refuses it: `views_admin.get_admin` reads `is_active=True`)
      team member      -> as above
      anyone else      -> nothing (a referral partner, a source user, a mentor login)

    ⚠ A GATE SINCE T5c (P1): `staff_tables.opens` reads it for the page doors. So it must NEVER ask a
    door (`staff_tables.may_*`) — it reads the tables and labels those doors were built from. It does NOT
    drop a key whose ruling-7 dependency is missing (`dependency_gaps` reports that; T5d decides)."""
    if admin is None:
        return ()
    if admin.is_super:
        return V2_KEYS
    if not getattr(admin, 'is_active', True):
        return ()
    if admin.role == sp.LEAD_ROLE:
        return lead_v2(admin)
    if admin.role not in sp.TEAM_ROLES:
        return ()
    held = set(through_aliases(sp.resolve(admin)))
    if staff_tables.in_admins(admin):     # the one table that grants page keys (no mentor query)
        held.update(TABLE_GRANTS[staff_tables.ADMINS])
    held.update(LABEL_GRANTS.get(admin.role, ()))
    return with_implied_views(held)
