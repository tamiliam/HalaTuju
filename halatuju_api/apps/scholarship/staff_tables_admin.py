"""Team -> Admins / Reviewers -> **Add** and **Remove from** (Team tables T2, 2026-11-03).

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (owner rulings 3, 4, 5, 8); lead rulings Q1-Q4
2026-11-03 in docs/decisions.md ("Team tables T2"). The view (`views_admin/staff.py`
`AdminTeamTableView`) is the door: who may knock, the 404 fence, the AUDIT line. This module decides what
an Add or a Remove may be, what it would do, and writes it.

⚠ A TABLE IS STILL DERIVED (`apps/courses/staff_tables.py`); nothing here stores a table. An Add or a
Remove writes the person's KEYS (`PartnerAdmin.permissions`) and — only where the preset label would
otherwise keep them seated — their `role`:

  Add to Admins      keys + `see_all` and `scholars` (S1 ruling B: the same two keys an invited Admin starts
                     with). Role unchanged (a reviewer given them keeps role `reviewer`: option B, the
                     organisation READ pages only). A pure MENTOR login becomes role `admin` holding
                     exactly ['see_all', 'scholars'].
  Add to Reviewers   keys + `review`. Role unchanged. A pure MENTOR login becomes role `reviewer` (the
                     preset, `review`). An ORGANISATION ADMIN stores ['review'] (`staff_permissions.
                     LEAD_MAY_ADD`) — the lead tier itself never changes.
  Remove from Admins the person's admin keys go (`staff_tables.admin_keys`; `see_all` stays when `qc`
                     brings it, T5b `staff_permissions.IMPLIES`). Role `admin` / `finance` moves to `qc`
                     (if `qc` stays) or
                     `reviewer`. Refused for the organisation admin (the lead tier is fixed).
  Remove from Reviewers `review` and `qc` go (and the `see_all` that only served `qc`): the keys left
                     are exactly the Admins table's. Role `reviewer` / `qc` moves to `admin` (lead ruling
                     Q2b: one Admin, the same as an invited Admin — they OPEN the admin work pages). The org
                     admin's stored ['review'] goes back to NULL. Refused while they hold open cases.

⚠ A KEY SET EQUAL TO THE (new) ROLE'S PRESET IS STORED AS NULL, as the editor stores it, so "custom" stays
derivable. A preset row is MATERIALISED before a key is added, so nobody loses anything by an Add.

⚠ REFUSED: the person's LAST table ("revoke instead"); an Add for a revoked or inactive row (since M2c, owner
R3, a suspended person may be REMOVED, under the same work checks, planned on the groups a Restore gives
back: `staff_tables.seated`); a super; anyone outside the caller's remit (the view answers 404 for those).

⚠ TEAM TABLES T3 (2026-11-03): THE LAST STAFF TABLE WHEN THEY STILL MENTOR. T2 refused it ("only Mentors
would be left", until T3). It is now accepted ONLY where the shape is already one 7a / 7d support — a
MENTOR LOGIN (role `mentor`, the link kept, permissions NULL): the person keeps their sign-in, their mentor
record and every scholar, and from then on sees My students and their Profile only (`may_become_mentor`:
an admin, reviewer or QC — never the organisation admin, who never leaves Admins, and never finance, who
cannot mentor — who mentors NOW, HAS SIGNED IN, and holds no open case). Anyone else is still refused
`mentors_only` ("revoke, or stop mentoring"). The reverse door is T2's (a mentor login added to a table
becomes staff). No email; the sign-in untouched; no stored field.

⚠ SPRINT M1a (2026-11-10, owner O5/O6): with ``to_no_group`` a Remove of the LAST group (nobody mentoring
now: T3 above still decides those) lands on "No group" — role `member`, NULL keys, sign-in kept — instead of
`last_table`, once they have signed in. A member joins a group with that group's preset. A Remove from Admins
is refused while anything waits on them as an admin (`staff_work.ADMIN_WAITING`: `run_in_progress` today).

⚠ WHO MAY: whoever may edit permissions on Team today — a super, or an organisation admin on their own
organisation's TEAM members (`_staff_target_manageable`) — PLUS (lead ruling Q4) an organisation admin
on THEIR OWN row, for the Reviewers table only. Never a fellow organisation admin; `manage_team` is
never a door (no team member holds it).
"""
from django.db import transaction

from apps.courses.staff_tables import ADMIN_KEYS

from .staff_permissions_admin import PermissionChangeRefused

ADMINS = 'admins'
REVIEWERS = 'reviewers'
TABLES = (ADMINS, REVIEWERS)

#: Each table's OWN keys — what its chips show and its editor edits (owner ruling 2). M1a (brief addendum
#: item 1): DERIVED from the ONE list of keys that seat a person in Admins (`staff_tables.ADMIN_KEYS`), so a
#: future key follows on its own and a Remove from Admins strips it. `manage_team` is never a table key:
#: the lead tier's alone (owner O15), never granted, so no chip shows it.
ADMIN_TABLE_KEYS = tuple(k for k in ADMIN_KEYS if k != 'manage_team')
REVIEWER_TABLE_KEYS = ('review', 'qc')

#: The keys an Add gives. Admins: BOTH keys, the same as an invited Admin (`staff_tables.INVITE_START`;
#: S1 owner ruling B, 2026-11-10) — Applications and Scholars.
ADD_KEYS = {ADMINS: ('see_all', 'scholars'), REVIEWERS: ('review',)}

#: Refusal codes the screen words (`admin.team.refused.<code>`).
LAST_TABLE = 'last_table'
MENTORS_ONLY = 'mentors_only'
HAS_OPEN_CASES = 'has_open_cases'
LEAD_FIXED = 'lead_fixed'
QC_SEES_ALL = 'qc_sees_all'
NOT_ARRIVED = 'not_arrived'       # M1a: "No group" only for somebody who has signed in (Invitations has the rest)

#: T3: the staff roles that may leave their last STAFF table and stay on as a mentor login. Never
#: `org_admin` (the lead never leaves Admins), never `finance` (it cannot mentor: `mentors_now` is false).
TO_MENTOR_ROLES = ('admin', 'reviewer', 'qc')

Refused = PermissionChangeRefused


# ── who ─────────────────────────────────────────────────────────────────────────────────────────────
def _pure_mentor_ready(target):
    """A MENTOR's own login that has signed in and mentors now — a team member at the Mentors table only."""
    return (target.is_mentor and target.is_active and target.first_seen_at is not None
            and target.mentors_now)


def may_act(caller, target, table):
    """May ``caller`` add ``target`` to, or remove them from, ``table``? False → the view's 404."""
    from apps.courses import staff_permissions as sp
    from apps.courses.views_admin import _staff_target_manageable
    if caller is None or target is None or table not in TABLES:
        return False
    if target.is_super or target.is_archived:   # M1a: an archived row is out of reach by id
        return False
    if target.role == sp.LEAD_ROLE:
        # Lead ruling Q4: a super, or the organisation admin on their OWN row — Reviewers only (the lead
        # tier's seat at Admins is fixed). Never a fellow organisation admin.
        if table != REVIEWERS:
            return False
        return caller.is_super or (caller.role == sp.LEAD_ROLE and caller.pk == target.pk)
    if target.is_mentor:
        # A pure mentor login: the 7a actors (a super, or its own organisation's admin).
        if caller.is_super:
            return True
        return (caller.role == sp.LEAD_ROLE and caller.owning_organisation_id is not None
                and target.owning_organisation_id == caller.owning_organisation_id)
    return _staff_target_manageable(caller, target)


# ── what ────────────────────────────────────────────────────────────────────────────────────────────
def table_keys(target, table):
    """The keys ``target`` holds that ``table`` shows (its chips; what a Remove takes away)."""
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    if sp.is_lead_tier(target):
        return ['review'] if table == REVIEWERS and sp.lead_reviews(target) else []
    if table == ADMINS:
        return [k for k in staff_tables.admin_keys(target) if k in ADMIN_TABLE_KEYS]
    held = sp.resolve(target)
    return [k for k in REVIEWER_TABLE_KEYS if k in held]


def table_presets(target):
    """`{admins: [...], reviewers: [...]}` — each table's PRESET for ``target``, what the person page's
    Permissions tab compares a table's keys with ("Custom", owner O12; M1b draws one table's section).
    The role label's preset as that table shows it; where the label gives that table nothing (a reviewer
    seated at Admins), what an Add to that table gives (`ADD_KEYS`). Lead (M1a addendum). M2b D7/D9: the
    Admins preset ends with its v2 page keys — the label's (`V2_PRESETS`), else what an Add stores."""
    from apps.courses import staff_permissions as sp
    from . import staff_permissions_admin as spa
    v2 = spa._v2()
    shown = {ADMINS: ADMIN_TABLE_KEYS, REVIEWERS: REVIEWER_TABLE_KEYS}
    preset = sp.preset_for(target.role)
    out = {}
    for table, keys in shown.items():
        mine = [k for k in preset if k in keys]
        out[table] = mine or [k for k in ADD_KEYS[table] if k in keys]
    out[ADMINS] += list(v2.V2_PRESETS.get(target.role, v2.ADMIN_PRESET_V2))
    return out


def _in(target, table):
    from apps.courses import staff_tables
    return staff_tables.in_admins(target) if table == ADMINS else staff_tables.in_reviewers(target)


def _other(table):
    return REVIEWERS if table == ADMINS else ADMINS


def may_become_mentor(target, open_n):
    """T3: may ``target``, leaving their last STAFF table, stay on as a mentor login? (See the module
    docstring.) ``open_n`` is their open-case count (`staff_lifecycle.open_cases`)."""
    from apps.courses import staff_tables
    return (target.role in TO_MENTOR_ROLES and target.is_active and staff_tables.in_mentors(target)
            and target.first_seen_at is not None and not open_n)


def _refuse_basic(target, remove=False):
    """``remove`` (M2c, owner R3): a suspended person may still be REMOVED from a group, under the same work
    checks; an Add (and the permission editor's own `_refuse_target`) still refuses `not_active`."""
    from apps.courses import staff_permissions as sp
    if target.is_super or not (target.role in sp.TEAM_ROLES or target.role == sp.LEAD_ROLE
                               or target.is_mentor or target.is_member):   # M1a: "No group" joins one
        raise Refused('not_eligible', 400, 'Only a member of this organisation’s team can sit in a table.')
    if not target.is_active and not remove:
        raise Refused('not_active', 400,
                      f"{target.name}'s access is revoked. Restore them before changing their tables.")


def _stored_set(role, after):
    from apps.courses import staff_permissions as sp
    return None if tuple(after) == sp.preset_for(role) else list(after)


def _plan_add(target, table):
    from apps.courses import staff_permissions as sp
    if target.is_mentor:
        if not _pure_mentor_ready(target):
            raise Refused('not_eligible', 400,
                          f'{target.name} has not signed in as a mentor yet, or no longer mentors.')
        if table == ADMINS:
            keys = list(ADD_KEYS[ADMINS])
            return {'role': 'admin', 'before': [], 'after': keys, 'stored': keys}
        return {'role': 'reviewer', 'before': [], 'after': ['review'], 'stored': None}
    if target.is_member:
        # M1a (brief §2 item 7): "No group" joins Admins with the `admin` preset, Reviewers with `reviewer`'s.
        role = 'admin' if table == ADMINS else 'reviewer'
        return {'role': role, 'before': [], 'after': list(sp.preset_for(role)), 'stored': None}
    if _in(target, table):
        raise Refused('already_in', 400, f'{target.name} is already in this table.')
    before = list(sp.resolve(target))
    if sp.is_lead_tier(target):            # Reviewers only (may_act / _in keep Admins away)
        # M3a (A6): `review` is ADDED to their stored list; every other key they store is kept.
        from . import staff_permissions_admin as spa
        return {'role': target.role, 'before': before,
                'after': list(sp._ordered((*before, sp.LEAD_MAY_ADD))),
                'stored': spa._v2().org_admin_list(target, review=True), 'lead': True}
    keys = ADD_KEYS[table]
    if keys[0] in before:
        # Only `see_all` can be here: brought by `qc` (T5b IMPLIES), it seats nobody at Admins. Refused as
        # in T2 (a deviation): the Add stays the invite's two keys, and Quality check alone never brings
        # Scholars (S1 owner ruling, 2026-11-10) — so an Add never seats a QC holder through the back door.
        raise Refused(QC_SEES_ALL, 400,
                      f'{target.name} already sees every student through Quality check, so they are not '
                      'added to Admins. Remove them from Reviewers first, or ask HalaTuju support.')
    after = sp._ordered((*before, *keys))    # the preset MATERIALISED, then the keys added
    return {'role': target.role, 'before': before, 'after': list(after),
            'stored': _stored_set(target.role, after)}


def _plan_remove(target, table, open_n, to_no_group=False):
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    from . import staff_lifecycle, staff_work
    if sp.is_lead_tier(target) and table == ADMINS:
        raise Refused(LEAD_FIXED, 400, 'The organisation admin always sits in Admins; that cannot change.')
    if not _in(target, table):
        raise Refused('not_in', 400, f'{target.name} is not in this table.')
    if table == ADMINS:
        # M1a (owner O5): refused while anything is still waiting on them as an admin (the per-key
        # registry `staff_work.ADMIN_WAITING`; every entry counts, held key or not — lead).
        for entry, n in staff_work.admins_waiting(target):
            raise Refused(entry.code, 409, entry.message(target.name, n), **{entry.field: n})
    other = _other(table)
    to_mentor = to_member = False
    if not _in(target, other):
        if not staff_tables.in_mentors(target):
            if not to_no_group:
                raise Refused(LAST_TABLE, 400,
                              f'This is the only table {target.name} is in. Revoke their access instead.')
            to_member = _refuse_no_group(target, table, open_n)
        else:
            to_mentor = _refuse_to_mentor(target, open_n)
    if table == REVIEWERS and not (to_mentor or to_member):
        n = staff_lifecycle.open_cases(target) if open_n is None else open_n
        if n:
            raise Refused(HAS_OPEN_CASES, 409,
                          f'{target.name} has {n} open case(s) assigned. Reassign their cases first.',
                          open_cases=n)
    before = list(sp.resolve(target))
    if to_mentor:
        # A mentor login holds no staff key; its row stores NULL (the 7a shape).
        from apps.courses.models import PartnerAdmin
        return {'role': PartnerAdmin.MENTOR_ROLE, 'before': before, 'after': [], 'stored': None,
                'to_mentor': True}
    if to_member:
        # M1a (owner O6): their last group goes; they stay on the Staff list as "No group" — sign-in kept,
        # no key (NULL), any mentor link kept with its Mentor already deactivated (`in_mentors` is false).
        from apps.courses.models import PartnerAdmin
        return {'role': PartnerAdmin.MEMBER_ROLE, 'before': before, 'after': [], 'stored': None,
                'to_member': True}
    if sp.is_lead_tier(target):
        # M3a (A6): only `review` comes off their stored list; every other key they store is kept (was
        # NULL, which read as the fixed tier before M3a).
        from . import staff_permissions_admin as spa
        return {'role': target.role, 'before': before,
                'after': [k for k in before if k != sp.LEAD_MAY_ADD],
                'stored': spa._v2().org_admin_list(target, review=False), 'lead': True}
    if table == REVIEWERS:
        after = table_keys(target, ADMINS)        # exactly the Admins table's keys
        role = 'admin' if target.role in ('reviewer', 'qc') else target.role
    else:
        gone = set(table_keys(target, ADMINS))
        after = [k for k in before if k not in gone]
        role = target.role
        if target.role in ('admin', 'finance'):
            role = 'qc' if 'qc' in after else 'reviewer'
    after = list(sp._ordered(after))
    return {'role': role, 'before': before, 'after': after, 'stored': _stored_set(role, after)}


def _v2_part(target, table, action, out):
    """M2b D8: the stored v2 page keys a table change leaves, appended to the plan's `before` / `after`
    (and so to its `stored` list and history). An Add to Admins, or a change that makes them `admin`,
    adds `ADMIN_PRESET_V2`; leaving Admins (a Remove from it, or becoming a mentor login / "No group")
    strips every v2 key; anything else keeps them. The lead tier stores none. NULL only when the old
    part is the new role's preset and no v2 key is left (`asked_set`'s rule). True when the admin work
    pages become stored (the confirm's `opens_admin_pages`)."""
    from apps.courses import staff_permissions as sp
    from . import staff_permissions_admin as spa
    v2 = spa._v2()
    if out.get('lead'):
        return False
    before_v2 = [] if (target.is_mentor or target.is_member) else list(v2.stored_v2(target))
    if out.get('to_mentor') or out.get('to_member') or (action == 'remove' and table == ADMINS):
        after_v2 = []
    elif (action == 'add' and table == ADMINS) or (out['role'] == 'admin' and out['role'] != target.role):
        after_v2 = list(v2.v2_order({*before_v2, *v2.ADMIN_PRESET_V2}))
    else:
        after_v2 = before_v2
    old_after = tuple(out['after'])
    out['before'], out['after'] = [*out['before'], *before_v2], [*old_after, *after_v2]
    out['stored'] = None if old_after == sp.preset_for(out['role']) and not after_v2 else list(out['after'])
    work = set(v2.ADMIN_WORK_V2)
    return work <= set(after_v2) and not work <= set(before_v2)


def _refuse_to_mentor(target, open_n):
    """T3: only Mentors would be left — accepted as a mentor login where that shape is safe. True, or
    `Refused`."""
    from . import staff_lifecycle
    n = staff_lifecycle.open_cases(target) if open_n is None else open_n
    if n:
        raise Refused(HAS_OPEN_CASES, 409,
                      f'{target.name} has {n} open case(s) assigned. Reassign their cases first.',
                      open_cases=n)
    if not may_become_mentor(target, n):
        raise Refused(MENTORS_ONLY, 400,
                      f'{target.name} would be left only in Mentors, which is possible only for an '
                      'admin, reviewer or QC who has signed in. Revoke their access, or stop their '
                      'mentoring, instead.')
    return True


def _refuse_no_group(target, table, open_n):
    """M1a (owner O6): may ``target`` leave their LAST group and stay on as "No group"? Only once they have
    signed in (before that they live on Invitations, owner O1 — lead), and, from Reviewers, holding no
    open case. True, or `Refused`."""
    from . import staff_lifecycle
    if target.first_seen_at is None:
        raise Refused(NOT_ARRIVED, 400, f'{target.name} has not signed in yet. Cancel their invitation '
                                        'instead.')
    n = 0
    if table == REVIEWERS:
        n = staff_lifecycle.open_cases(target) if open_n is None else open_n
    if n:
        raise Refused(HAS_OPEN_CASES, 409,
                      f'{target.name} has {n} open case(s) assigned. Reassign their cases first.',
                      open_cases=n)
    return True


def plan_table_change(target, table, action, *, open_n=None, to_no_group=False):
    """What adding / removing would do, or `Refused`. Read-only apart from the work counts.
    ``to_no_group`` (M1a, owner O6): a Remove of the LAST group lands on "No group" (role `member`)
    instead of `last_table`. Without it, today's answer."""
    from apps.courses import staff_tables
    from . import staff_lifecycle, staff_permissions_admin as spa
    if table not in TABLES or action not in ('add', 'remove'):
        raise Refused('bad_request', 400, 'table must be admins or reviewers; action add or remove.')
    _refuse_basic(target, remove=action == 'remove')
    live = target.is_active
    # M2c (owner R3): a suspended person's Remove is planned on their groups as a Restore gives them back.
    target = staff_tables.seated(target) if action == 'remove' else target
    out = (_plan_add(target, table) if action == 'add'
           else _plan_remove(target, table, open_n, to_no_group))
    opens_admin_pages = _v2_part(target, table, action, out)
    out['role_from'] = target.role
    out['role_changed'] = out['role'] != target.role
    lead = out.pop('lead', False)
    # T3: they leave their last staff table and stay on as a mentor login — said on the confirm.
    out['becomes_mentor'] = out.pop('to_mentor', False)
    out['becomes_member'] = out.pop('to_member', False)    # M1a: "No group", said on the confirm
    if not lead and not target.is_mentor:
        # The editor's own stranding rule (a Remove from Admins taking `see_all` from somebody who
        # reaches assigned cases only through it) — the same check, the same words.
        spa._refuse_stranding(target, out['before'], out['after'])
    out['consequences'] = (spa.consequences(target, out['before'], out['after'])
                           if not target.is_mentor else [])
    # TD-475 (A1.10a): the wallet-credit check turns on the KEY `payments_approve` (`credit_steps.
    # CHECKER_KEY`), so it goes off when this change takes the key from the organisation's last active
    # holder — whatever their label (was: leaving the Finance LABEL).
    from .credit_steps import CHECKER_KEY
    out['finance_check_off'] = bool(live and CHECKER_KEY in out['before'] and CHECKER_KEY not in out['after']
                                    and target.owning_organisation_id is not None
                                    and not staff_lifecycle.other_active_checker(target))
    # Lead ruling Q2b: said in plain words on the confirm. M2b: the change STORES the admin work pages
    # (`_v2_part`) — an Add to Admins, a Remove from Reviewers that makes them `admin` (Q2b), a mentor
    # login added to Admins. It can be a GAIN, so the confirm says so in plain words.
    out['opens_admin_pages'] = opens_admin_pages
    out['added'] = [k for k in out['after'] if k not in out['before']]
    out['removed'] = [k for k in out['before'] if k not in out['after']]
    return out


def _cheap_refusal(target, table, open_n, to_no_group=False, runs_n=None):
    """The refusal a Remove would meet, read WITHOUT a query (open cases and unfinished runs counted once
    for the page): the same rules `_plan_remove` applies first, in its order. The rarer stranding refusal
    (a Remove from Admins taking `see_all` from somebody who reaches cases only through it) is the
    endpoint's to say. ``runs_n`` (M1b, TD-606): their unfinished payment runs, M1a's Admins "waiting on
    them" refusal (`staff_work.ADMIN_WAITING`, `run_in_progress`); None = not counted (the endpoint says
    it). ⚠ A new `ADMIN_WAITING` entry (M3/M4) needs its page count here too."""
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    if not target.is_active:
        return 'not_active'
    if sp.is_lead_tier(target) and table == ADMINS:
        return LEAD_FIXED
    if not _in(target, table):
        return 'not_in'
    if table == ADMINS and runs_n:
        from .staff_work import ADMIN_WAITING
        return ADMIN_WAITING['payments_prepare'].code
    if not _in(target, _other(table)):
        if not staff_tables.in_mentors(target):
            if not to_no_group:
                return LAST_TABLE
            if target.first_seen_at is None:          # M1a: `_refuse_no_group`, in its order
                return NOT_ARRIVED
            return HAS_OPEN_CASES if table == REVIEWERS and open_n else None
        if open_n:
            return HAS_OPEN_CASES
        return None if may_become_mentor(target, open_n) else MENTORS_ONLY   # T3
    if table == REVIEWERS and open_n:
        return HAS_OPEN_CASES
    return None


def row_refusal(target, table, open_n, runs_n=None):
    """A row's `remove` code (TD-606): the answer the screen's Remove meets, as the screen sends it — as it
    is, and where that is `last_table`, again WITH `to_no_group` (the web sends it exactly then). So a last
    group they may leave for No group stays `last_table` (the web's cue); one they may not reads that
    refusal (`not_arrived`, then `has_open_cases`: `_refuse_no_group`'s order), never `last_table`. A
    `run_in_progress` (``runs_n``) comes before all of those, as in `_plan_remove`."""
    code = _cheap_refusal(target, table, open_n, runs_n=runs_n)
    if code == LAST_TABLE:
        return _cheap_refusal(target, table, open_n, to_no_group=True) or LAST_TABLE
    return code


def open_case_counts(admin_ids):
    """`{admin_id: open cases}` in ONE query — `staff_lifecycle.open_cases`'s rule, for a page of rows."""
    from django.db.models import Count, Q
    from .models import ScholarshipApplication
    from .staff_lifecycle import OPEN_CASE_STATUSES
    ids = [i for i in admin_ids if i is not None]
    if not ids:
        return {}
    rows = (ScholarshipApplication.objects.filter(assigned_to_id__in=ids)
            .filter(Q(status__in=OPEN_CASE_STATUSES) | Q(decision_reopened_at__isnull=False))
            .values('assigned_to_id').annotate(n=Count('id')))
    return {r['assigned_to_id']: r['n'] for r in rows}


def row_fields(caller, admins, *, open_counts=None, runs=None):
    """`{admin_id: {...}}` — what the Team tables need per row, served on both lists so the screen shows
    a Remove only where the endpoint will accept it:
      `tables`        the tables the person sits in (`staff_tables.tables`)
      `lead`          the organisation admin ("Admin (lead)", never editable at Admins)
      `admin_keys` / `reviewer_keys`  each table's OWN chips
      `remove`        `{admins|reviewers: None | code}` for a table they sit in and the caller may act
                      on: None = Remove is accepted; `last_table` = accepted as a move to No group (send
                      `to_no_group`); another code = why not (`row_refusal`). Absent = no link at all
                      (not in that table, or not the caller's to act on).
      `runs_in_progress`  only when ``runs`` is given (`staff_work.runs_counts`, one query for the page;
                      M1b, TD-606): their unfinished payment runs, and the Admins Remove reads
                      `run_in_progress` while it is above 0. The Admins list passes it; the Reviewers list
                      does not (its query budget is frozen, and its screen reads only `remove.reviewers`)."""
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    rows = list(admins)
    # The Reviewers list counts them in its own workload query (`open_counts`); else one query here.
    counts = open_counts if open_counts is not None else open_case_counts([a.pk for a in rows])
    out = {}
    for a in rows:
        remove, seat = {}, staff_tables.seated(a)     # M2c (owner R3): a suspended row's Remove too
        for table in TABLES:
            if _in(seat, table) and may_act(caller, a, table):
                remove[table] = row_refusal(seat, table, counts.get(a.pk, 0),
                                            None if runs is None else runs.get(a.pk, 0))
        out[a.pk] = {'tables': list(staff_tables.tables(a)), 'lead': sp.is_lead_tier(a),
                     'admin_keys': table_keys(a, ADMINS), 'reviewer_keys': table_keys(a, REVIEWERS),
                     'remove': remove, **({} if runs is None else {'runs_in_progress': runs.get(a.pk, 0)})}
    return out


# ── the write ───────────────────────────────────────────────────────────────────────────────────────
def change(target_id, table, action, *, by, dry_run=False, to_no_group=False):
    """Plan, and unless ``dry_run`` apply. Returns ``(target, plan)``. The row is LOCKED for the plan and
    the write (the editor's lock, which `assign_reviewer` also takes), and the UPDATE carries the role and
    the active flag it planned against."""
    from apps.courses.models import PartnerAdmin
    from . import invitations, staff_permissions_admin as spa
    from .models import Invitation
    with transaction.atomic():
        # ⚠ T3 review: this LOGIN-row lock is the one `staff_mentor.stop` takes too, so a Stop mentoring and
        # a Remove that would make a mentor login serialise: whichever commits second re-reads the first's.
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id).first()
        # Review 2026-11-03: the caller's right is judged AGAIN on the LOCKED row — the view's check read
        # it before the lock, and a role or organisation change landing in between must not slip through.
        if target is None or not may_act(by, target, table):
            raise Refused('not_found', 404, 'Admin not found')
        p = plan_table_change(target, table, action, to_no_group=to_no_group)
        if dry_run:
            return target, p
        fields = {'permissions': p['stored']}
        if p['role_changed']:
            fields['role'] = p['role']
        rows = PartnerAdmin.objects.filter(pk=target.pk, role=p['role_from'], is_active=target.is_active)
        if p['becomes_mentor']:
            # T3: the mentor link and the mentor record must still be live as the row is written (the
            # lock above holds the login; a Stop mentoring racing this one stamps the mentor first).
            rows = rows.filter(mentor__isnull=False, mentor__deactivated_at__isnull=True)
        done = rows.update(**fields)
        if not done:
            raise Refused('changed', 409, 'Somebody changed this person a moment ago. Reload and try again.')
        if p['role_changed'] and not target.is_mentor and not (p['becomes_mentor'] or p['becomes_member']):
            # As `change_role` does: an OPEN staff invitation carries the role the Invitations page shows.
            invitations.open_only(Invitation.objects.filter(
                audience='staff', partner_admin=target)).update(role=p['role'])
        for k, v in fields.items():
            setattr(target, k, v)
        if p['before'] != p['after']:
            spa.record(target, p['before'], p['after'], by=by, kind='edit')
    return target, p


# ── the Add sheet ───────────────────────────────────────────────────────────────────────────────────
def candidates(caller, table, organisation_id):
    """The people the Add sheet offers: ACTIVE members of ``organisation_id`` the caller may act on, not
    in ``table``, whom an Add would accept. Name order."""
    from apps.courses.models import PartnerAdmin
    qs = (PartnerAdmin.objects.filter(is_active=True)
          .exclude(role='super').select_related('mentor').order_by('name', 'id'))
    if organisation_id is not None:
        qs = qs.filter(owning_organisation_id=organisation_id)
    out = []
    for a in qs:
        if not may_act(caller, a, table):
            continue
        try:
            plan_add = _plan_add_safe(a, table)
        except Refused:
            continue
        out.append((a, plan_add))
    return out


def addable_tables(caller, target):
    """Sprint T3 (D8): the staff tables (Admins, Reviewers) ``caller`` could add ``target`` to right now —
    exactly where `candidates` would offer them (`may_act`, then the Add's own plan). The pure mentor's
    person page offers the Add path only for these; the Add endpoint still decides."""
    out = []
    for table in (ADMINS, REVIEWERS):
        if not may_act(caller, target, table):
            continue
        try:
            _plan_add_safe(target, table)
        except Refused:
            continue
        out.append(table)
    return out


def _plan_add_safe(target, table):
    _refuse_basic(target)
    return _plan_add(target, table)
