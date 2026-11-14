"""Team tables T5a (2026-11-03): the permission vocabulary v2 — one key per PAGE x TIER, in four groups —
the alias table from today's keys, and a READ-ONLY answer to "which v2 keys does this person effectively
hold today?".

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (T5, owner "approve all", rulings 1-8); evidence
pack: the lead's T5 investigation, sections A (page inventory) and F (catalogue + live shapes).

⚠ A GATE FOR THE ORGANISATION / ADMIN-WORK PAGE DOORS SINCE T5c (P1): `staff_tables.opens` reads
`effective_v2` (decisions.md "Team tables T5c", the door -> key table). Only the allowlisted modules
import this one (`test_permission_catalogue_v2.V2Importers`); a door module asks
`staff_tables.opens_door(admin, '<door>')`, whose keys are `staff_tables.DOOR_KEYS` (T5c P4a). The rest
(review / QC / payments / spending / the lead-only pages) still opens through `staff_permissions.resolve`
/ `has_perm` and role checks.

Sprint M2b (2026-11-12, decisions.md "M2b"): the GRANTABLE v2 page keys are STORED in the same
`permissions` list as today's keys (`stored_v2`), saved by the editor (`staff_permissions_admin.asked_set`)
and seeded by migration 0097. The `admin` role LABEL no longer grants anything by itself (`LABEL_GRANTS`
is gone). `staff_permissions.clean` still drops every v2 key, so the old-key readers (`resolve`,
`holders`, the payment chain) never see one.

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

#: Dependencies as data (ruling 7): the Engagement pages name every scholar (survey answers, module
#: progress, mentoring), so each needs the key that reads every scholar's file. Since sprint S1 that is
#: `scholars.view`; `students.view` is Applications only. Data, not a gate (`dependency_gaps`; T5d).
DEPENDS_ON_V2 = {k: ('scholars.view',) for k, row in CATALOGUE_V2.items() if row[0] == ENGAGEMENT}

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
#: member at the ADMINS table (`staff_tables.in_admins`: an admin key, or since M2b a stored v2 key)
#: holds them (`TABLE_GRANTS`); `staff_tables.may_read_org` opens on all of them (T5c).
#: T5c P4a: the one spelling is `staff_tables.DOOR_KEYS` (the door -> key table); read from there.
ORG_READ_V2 = staff_tables.DOOR_KEYS['org_read']

#: The organisation WORK pages, never finance: Sources and the witness override, Mentors read and the
#: roster, Announcements, Surveys, Development, sponsor terms and sponsor / partner emails, and on a
#: scholar the mentoring tab (`mentoring.py`), scholar growth (`development.py`) and scholar surveys
#: (`surveys.py`). Since M2b a person holds them by STORED keys (`ADMIN_PRESET_V2`, migration 0097);
#: `staff_tables.may_do_admin_work` opens on all.
ADMIN_WORK_V2 = staff_tables.DOOR_KEYS['admin_work']

#: What a TABLE seat grants (T1 derivation, `staff_tables`). Only the Admins table grants page keys.
TABLE_GRANTS = {staff_tables.ADMINS: ORG_READ_V2}

#: M2b D4: the v2 page keys an Admin starts with — what the `admin` LABEL and its Admins seat opened
#: before M2b, derived from the two door sets (never retyped), in `CATALOGUE_V2` order. No money key, no
#: lead-only key (`test_m2b_stored_v2`).
ADMIN_PRESET_V2 = tuple(k for k in CATALOGUE_V2 if k in {*ORG_READ_V2, *ADMIN_WORK_V2})

#: M2b: each label's v2 part — what migration 0097 stored for it, what `preset_diff` / `table_presets`
#: compare a stored v2 part with. `finance` read the organisation through its Admins seat, nothing more.
V2_PRESETS = {'admin': ADMIN_PRESET_V2, 'finance': ORG_READ_V2}

#: M2b D3: never offered to anyone but the lead tier, not even after M3 (refused with its own code).
#: `manage_team` (an old key) is lead-tier only already (`staff_permissions.LEAD_TIER_ONLY`).
NEVER_GRANTABLE = ('billing.edit', 'requests.approve')

#: The v2 keys an old key already MEANS (`ALIASES`): money, Applications, Scholars and the credit check.
#: They are ticked through the old key, so the editor never stores their v2 spelling (M2b): a stored
#: alias would do nothing today and silently start to count when M4 converts those gates.
ALIAS_V2 = tuple(k for k in CATALOGUE_V2 if any(k in keys for keys in ALIASES.values()))

#: The v2 page keys the editor may STORE (M2b): neither lead-only (M3) nor an alias. Today this is
#: exactly `ADMIN_PRESET_V2` (`test_m2b_stored_v2` pins it).
GRANTABLE_V2 = tuple(k for k in CATALOGUE_V2 if not CATALOGUE_V2[k][3] and k not in ALIAS_V2)

# ── Sprint M3a (2026-11-14, decisions.md "M3a"): the organisation admin's powers as STORED keys. ──────
#: A1: the v2 page keys an organisation admin's row stores (migration 0098): every catalogue key that is
#: neither NEVER_GRANTABLE (held by role, below) nor an alias (held through the old keys they store, or
#: by role until M4, below). In `CATALOGUE_V2` order. The 11 lead-only keys are among them, and stay
#: unassignable to a team member until M3c (A5).
ORG_ADMIN_V2 = tuple(k for k in CATALOGUE_V2 if k not in NEVER_GRANTABLE and k not in ALIAS_V2)

#: The whole list an organisation admin's row stores (`review` comes on top only through Team ->
#: Reviewers): the old part (`staff_permissions.ORG_ADMIN_KEYS`), then the v2 part. Migration 0098 holds
#: a frozen copy (`test_m3_migration_0098`). It lives here, not in `staff_permissions`, because that leaf
#: cannot import this one at load time.
ORG_ADMIN_SET = (*sp.ORG_ADMIN_KEYS, *ORG_ADMIN_V2)

#: A2 (owner O15): the two v2 keys an active organisation admin holds BY ROLE — never stored, never
#: assignable (`NEVER_GRANTABLE`). The third of the O15 three is the old key `manage_team`
#: (`staff_permissions.LEAD_BY_ROLE`).
LEAD_BY_ROLE_V2 = NEVER_GRANTABLE

#: A3 (TD-620): the MONEY CARRY-OVER, held by an active organisation admin BY ROLE until M4. No gate
#: reads these v2 keys yet; storing their old-key spellings would arm or disarm the payment chain
#: (`staff_permissions.holders`, the run's fallback), which is M4's. The one implicit grant left: M4
#: removes it.
LEAD_MONEY_UNTIL_M4 = ('payments.view', 'payments.prepare', 'payments.check', 'payments.approve',
                       'sponsors.check')


def refusal_reason(key):
    """Why the editor may not store the v2 page key `key`: 'never_grantable', 'lead_only', 'alias',
    or None when it may (`GRANTABLE_V2`)."""
    if key in NEVER_GRANTABLE:
        return 'never_grantable'
    if CATALOGUE_V2[key][3]:
        return 'lead_only'
    if key in ALIAS_V2:
        return 'alias'
    return None


def stored_v2(admin):
    """M2b D2: the GRANTABLE v2 page keys stored in `admin.permissions`, in `V2_KEYS` order. A NULL
    (or non-list) value stores none. A key the editor can never store (lead-only, never-grantable, an
    alias, unknown) is ignored, as `staff_permissions.clean` ignores an unknown old key; the hats
    `review` / `qc` are old keys and are read by `resolve`, never here. Says nothing about `is_active`
    (the callers do).

    M3a: an organisation admin's row answers NONE here: their stored v2 keys are read by
    `org_admin_v2`, and the editor's ticks for them (`v2_held`) stay empty, as before, until M3c makes
    their card editable."""
    stored = getattr(admin, 'permissions', None) if admin is not None else None
    if not isinstance(stored, (list, tuple)) or sp.is_lead_tier(admin):
        return ()
    held = {k for k in stored if isinstance(k, str)}
    return tuple(k for k in GRANTABLE_V2 if k in held)


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


def org_admin_v2(admin):
    """M3a (A1, A2): the v2 page keys an organisation admin's row STORES, in `V2_KEYS` order — read
    strictly (only `ORG_ADMIN_V2` keys count), or all of `ORG_ADMIN_V2` when the row is NULL or not a
    list (fail-safe: an invitation the old image wrote, read as the set migration 0098 writes)."""
    stored = getattr(admin, 'permissions', None)
    if not isinstance(stored, (list, tuple)):
        return ORG_ADMIN_V2
    held = {k for k in stored if isinstance(k, str)}
    return tuple(k for k in ORG_ADMIN_V2 if k in held)


def org_admin_list(admin, *, review):
    """M3a (A6): the list an organisation admin's row stores after Team -> Reviewers Add (``review``
    True) or Remove (False): their stored list — `ORG_ADMIN_SET` when NULL or not a list — with `review`
    put first or taken out, and every other entry KEPT as it stands, in its order."""
    stored = getattr(admin, 'permissions', None)
    base = list(stored) if isinstance(stored, (list, tuple)) else list(ORG_ADMIN_SET)
    rest = [k for k in base if k != sp.LEAD_MAY_ADD]
    return [sp.LEAD_MAY_ADD, *rest] if review else rest


def effective_v2(admin):
    """The v2 keys `admin` EFFECTIVELY holds: their resolved old keys through `ALIASES`, what their T1
    table opens (`TABLE_GRANTS`) and, since M2b, their STORED v2 keys (`stored_v2`). The role label
    grants nothing by itself any more (M2b D5; migration 0097 stored what it gave).

      super            -> every v2 key (as `resolve` answers every old key)
      inactive row     -> nothing (sign-in refuses it: `views_admin.get_admin` reads `is_active=True`)
      org_admin        -> M3a (A2, A3): as a team member — `resolve` through `ALIASES`, the Admins
                          table (their seat is by role, A4) and their stored v2 keys (`org_admin_v2`)
                          — plus `LEAD_BY_ROLE_V2` (O15) and `LEAD_MONEY_UNTIL_M4` (TD-620) by role.
                          For the set migration 0098 stores this is exactly the lead set before M3a
                          (every page key, the `qc` hat, and `review` when Team -> Reviewers added it)
      team member      -> as above
      anyone else      -> nothing (a referral partner, a source user, a mentor login)

    ⚠ A GATE SINCE T5c (P1): `staff_tables.opens` reads it for the page doors. So it must NEVER ask a
    door (`staff_tables.may_*`) — it reads the tables and keys those doors were built from. It does NOT
    drop a key whose ruling-7 dependency is missing (`dependency_gaps` reports that; T5d decides)."""
    if admin is None:
        return ()
    if admin.is_super:
        return V2_KEYS
    if not getattr(admin, 'is_active', True):
        return ()
    lead = sp.is_lead_tier(admin)
    if not lead and admin.role not in sp.TEAM_ROLES:
        return ()
    held = set(through_aliases(sp.resolve(admin)))
    if staff_tables.in_admins(admin):     # the one table that grants page keys (no mentor query)
        held.update(TABLE_GRANTS[staff_tables.ADMINS])
    if lead:
        held.update((*org_admin_v2(admin), *LEAD_BY_ROLE_V2, *LEAD_MONEY_UNTIL_M4))
    else:
        held.update(stored_v2(admin))
    return with_implied_views(held)
