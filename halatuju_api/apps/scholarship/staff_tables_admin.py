"""Team -> Admins / Reviewers -> **Add** and **Remove from** (Team tables T2, 2026-11-03).

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (owner rulings 3, 4, 5, 8); lead rulings Q1-Q4
2026-11-03 in docs/decisions.md ("Team tables T2"). The view (`views_admin/staff.py`
`AdminTeamTableView`) is the door: who may knock, the 404 fence, the AUDIT line. This module decides what
an Add or a Remove may be, what it would do, and writes it.

⚠ A TABLE IS STILL DERIVED (`apps/courses/staff_tables.py`); nothing here stores a table. An Add or a
Remove writes the person's KEYS (`PartnerAdmin.permissions`) and — only where the preset label would
otherwise keep them seated — their `role`:

  Add to Admins      keys + `see_all` (the absolute minimum admin key). Role unchanged (a reviewer
                     given `see_all` keeps role `reviewer`: option B, the organisation READ pages only).
                     A pure MENTOR login becomes role `admin` holding exactly ['see_all'].
  Add to Reviewers   keys + `review`. Role unchanged. A pure MENTOR login becomes role `reviewer` (the
                     preset, `review`). An ORGANISATION ADMIN stores ['review'] (`staff_permissions.
                     LEAD_MAY_ADD`) — the lead tier itself never changes.
  Remove from Admins the person's admin keys go (`staff_tables.admin_keys`; `see_all` stays when it is
                     `qc`'s dependency). Role `admin` / `finance` moves to `qc` (if `qc` stays) or
                     `reviewer`. Refused for the organisation admin (the lead tier is fixed).
  Remove from Reviewers `review` and `qc` go (and the `see_all` that only served `qc`): the keys left
                     are exactly the Admins table's. Role `reviewer` / `qc` moves to `admin` (lead ruling
                     Q2b: one Admin, the same as an invited Admin — they keep the admin pages). The org
                     admin's stored ['review'] goes back to NULL. Refused while they hold open cases.

⚠ A KEY SET EQUAL TO THE (new) ROLE'S PRESET IS STORED AS NULL, as the editor stores it, so "custom" stays
derivable. A preset row is MATERIALISED before a key is added, so nobody loses anything by an Add.

⚠ REFUSED: the person's LAST table ("revoke instead"); the last STAFF table when only Mentors would be
left (until T3: "revoke, or stop mentoring"); a revoked or inactive row; a super; anyone outside the
caller's remit (the view answers 404 for those).

⚠ WHO MAY: whoever may edit permissions on Team today — a super, or an organisation admin on their own
organisation's TEAM members (`_staff_target_manageable`) — PLUS (lead ruling Q4) an organisation admin
on THEIR OWN row, for the Reviewers table only. Never a fellow organisation admin; `manage_team` is
never a door (no team member holds it).
"""
from django.db import transaction

from .staff_permissions_admin import PermissionChangeRefused

ADMINS = 'admins'
REVIEWERS = 'reviewers'
TABLES = (ADMINS, REVIEWERS)

#: Each table's OWN keys — what its chips show and its editor edits (owner ruling 2).
ADMIN_TABLE_KEYS = ('see_all', 'spending', 'payments_prepare', 'payments_check', 'payments_approve')
REVIEWER_TABLE_KEYS = ('review', 'qc')

#: The key an Add gives.
ADD_KEY = {ADMINS: 'see_all', REVIEWERS: 'review'}

#: Refusal codes the screen words (`admin.team.refused.<code>`).
LAST_TABLE = 'last_table'
MENTORS_ONLY = 'mentors_only'
HAS_OPEN_CASES = 'has_open_cases'
LEAD_FIXED = 'lead_fixed'
QC_SEES_ALL = 'qc_sees_all'

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
    if target.is_super or target.is_super_admin:
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


def _in(target, table):
    from apps.courses import staff_tables
    return staff_tables.in_admins(target) if table == ADMINS else staff_tables.in_reviewers(target)


def _other(table):
    return REVIEWERS if table == ADMINS else ADMINS


def _refuse_basic(target):
    from apps.courses import staff_permissions as sp
    if target.is_super or not (target.role in sp.TEAM_ROLES or target.role == sp.LEAD_ROLE
                               or target.is_mentor):
        raise Refused('not_eligible', 400, 'Only a member of this organisation’s team can sit in a table.')
    if not target.is_active:
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
            return {'role': 'admin', 'before': [], 'after': ['see_all'], 'stored': ['see_all']}
        return {'role': 'reviewer', 'before': [], 'after': ['review'], 'stored': None}
    if _in(target, table):
        raise Refused('already_in', 400, f'{target.name} is already in this table.')
    before = list(sp.resolve(target))
    if sp.is_lead_tier(target):            # Reviewers only (may_act / _in keep Admins away)
        return {'role': target.role, 'before': before,
                'after': list(sp._ordered((*before, sp.LEAD_MAY_ADD))),
                'stored': [sp.LEAD_MAY_ADD], 'lead': True}
    key = ADD_KEY[table]
    if key in before:
        # Only `see_all` can be here: held as `qc`'s dependency, it seats nobody at Admins. Giving
        # another admin key instead would give MORE than the minimum, so it is refused (T2 deviation).
        raise Refused(QC_SEES_ALL, 400,
                      f'{target.name} already sees every student through Quality check, so the starting '
                      'admin permission adds nothing. Remove them from Reviewers first, or ask HalaTuju '
                      'support.')
    after = sp._ordered((*before, key))      # the preset MATERIALISED, then the key added
    return {'role': target.role, 'before': before, 'after': list(after),
            'stored': _stored_set(target.role, after)}


def _plan_remove(target, table, open_n):
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    from . import staff_lifecycle
    if sp.is_lead_tier(target) and table == ADMINS:
        raise Refused(LEAD_FIXED, 400, 'The organisation admin always sits in Admins; that cannot change.')
    if not _in(target, table):
        raise Refused('not_in', 400, f'{target.name} is not in this table.')
    other = _other(table)
    if not _in(target, other):
        if staff_tables.in_mentors(target):
            raise Refused(MENTORS_ONLY, 400,
                          f'{target.name} would be left only in Mentors. Revoke their access, or stop '
                          'their mentoring, instead.')
        raise Refused(LAST_TABLE, 400,
                      f'This is the only table {target.name} is in. Revoke their access instead.')
    if table == REVIEWERS:
        n = staff_lifecycle.open_cases(target) if open_n is None else open_n
        if n:
            raise Refused(HAS_OPEN_CASES, 409,
                          f'{target.name} has {n} open case(s) assigned. Reassign their cases first.',
                          open_cases=n)
    before = list(sp.resolve(target))
    if sp.is_lead_tier(target):
        return {'role': target.role, 'before': before, 'after': list(sp.preset_for(target.role)),
                'stored': None, 'lead': True}
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


def plan_table_change(target, table, action, *, open_n=None):
    """What adding / removing would do, or `Refused`. Read-only apart from the open-case count."""
    from . import staff_lifecycle, staff_permissions_admin as spa
    if table not in TABLES or action not in ('add', 'remove'):
        raise Refused('bad_request', 400, 'table must be admins or reviewers; action add or remove.')
    _refuse_basic(target)
    out = _plan_add(target, table) if action == 'add' else _plan_remove(target, table, open_n)
    out['role_from'] = target.role
    out['role_changed'] = out['role'] != target.role
    lead = out.pop('lead', False)
    if not lead and not target.is_mentor:
        # The editor's own stranding rule (a Remove from Admins taking `see_all` from somebody who
        # reaches assigned cases only through it) — the same check, the same words.
        spa._refuse_stranding(target, out['before'], out['after'])
    out['consequences'] = (spa.consequences(target, out['before'], out['after'])
                           if not target.is_mentor else [])
    # Leaving the Finance LABEL moves the wallet-credit check (a finance-ROLE rule, staff_lifecycle).
    out['finance_check_off'] = bool(out['role_changed'] and target.role == 'finance'
                                    and target.owning_organisation_id is not None
                                    and not staff_lifecycle._other_active_finance(target))
    # Lead ruling Q2b: said in plain words on the confirm.
    out['keeps_admin_pages'] = bool(action == 'remove' and table == REVIEWERS and out['role'] == 'admin'
                                    and out['role_changed'])
    out['added'] = [k for k in out['after'] if k not in out['before']]
    out['removed'] = [k for k in out['before'] if k not in out['after']]
    return out


def _cheap_refusal(target, table, open_n):
    """The refusal a Remove would meet, read WITHOUT a query (open cases counted once for the page):
    the same rules `_plan_remove` applies first, in its order. The rarer stranding refusal (a Remove from
    Admins taking `see_all` from somebody who reaches cases only through it) is the endpoint's to say."""
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    if not target.is_active:
        return 'not_active'
    if sp.is_lead_tier(target) and table == ADMINS:
        return LEAD_FIXED
    if not _in(target, table):
        return 'not_in'
    if not _in(target, _other(table)):
        return MENTORS_ONLY if staff_tables.in_mentors(target) else LAST_TABLE
    if table == REVIEWERS and open_n:
        return HAS_OPEN_CASES
    return None


def open_case_counts(admin_ids):
    """`{admin_id: open cases}` in ONE query — `staff_lifecycle.open_cases`'s rule, for a page of rows."""
    from django.db.models import Count, Q
    from .models import ScholarshipApplication
    from .services.apply_gate import IN_PLAY_STATUSES
    ids = [i for i in admin_ids if i is not None]
    if not ids:
        return {}
    rows = (ScholarshipApplication.objects.filter(assigned_to_id__in=ids)
            .filter(Q(status__in=IN_PLAY_STATUSES) | Q(decision_reopened_at__isnull=False))
            .values('assigned_to_id').annotate(n=Count('id')))
    return {r['assigned_to_id']: r['n'] for r in rows}


def row_fields(caller, admins, *, open_counts=None):
    """`{admin_id: {...}}` — what the Team tables need per row, served on both lists so the screen shows
    a Remove only where the endpoint will accept it:
      `tables`        the tables the person sits in (`staff_tables.tables`)
      `lead`          the organisation admin ("Admin (lead)", never editable at Admins)
      `admin_keys` / `reviewer_keys`  each table's OWN chips
      `remove`        `{admins|reviewers: None | code}` for a table they sit in and the caller may act
                      on: None = Remove is accepted; a code = why not (the screen's note). Absent = no
                      link at all (not in that table, or not the caller's to act on)."""
    from apps.courses import staff_permissions as sp
    from apps.courses import staff_tables
    rows = list(admins)
    # The Reviewers list counts them in its own workload query (`open_counts`); else one query here.
    counts = open_counts if open_counts is not None else open_case_counts([a.pk for a in rows])
    out = {}
    for a in rows:
        remove = {}
        for table in TABLES:
            if a.is_active and _in(a, table) and may_act(caller, a, table):
                remove[table] = _cheap_refusal(a, table, counts.get(a.pk, 0))
        out[a.pk] = {'tables': list(staff_tables.tables(a)), 'lead': sp.is_lead_tier(a),
                     'admin_keys': table_keys(a, ADMINS), 'reviewer_keys': table_keys(a, REVIEWERS),
                     'remove': remove}
    return out


# ── the write ───────────────────────────────────────────────────────────────────────────────────────
def change(target_id, table, action, *, by, dry_run=False):
    """Plan, and unless ``dry_run`` apply. Returns ``(target, plan)``. The row is LOCKED for the plan and
    the write (the editor's lock, which `assign_reviewer` also takes), and the UPDATE carries the role and
    the active flag it planned against."""
    from apps.courses.models import PartnerAdmin
    from . import invitations, staff_permissions_admin as spa
    from .models import Invitation
    with transaction.atomic():
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id).first()
        if target is None:
            raise Refused('not_found', 404, 'Admin not found')
        p = plan_table_change(target, table, action)
        if dry_run:
            return target, p
        fields = {'permissions': p['stored']}
        if p['role_changed']:
            fields['role'] = p['role']
            fields['is_super_admin'] = False
        done = PartnerAdmin.objects.filter(pk=target.pk, role=p['role_from'], is_active=True).update(**fields)
        if not done:
            raise Refused('changed', 409, 'Somebody changed this person a moment ago. Reload and try again.')
        if p['role_changed'] and not target.is_mentor:
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
    qs = (PartnerAdmin.objects.filter(is_active=True, is_super_admin=False)
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


def _plan_add_safe(target, table):
    _refuse_basic(target)
    return _plan_add(target, table)
