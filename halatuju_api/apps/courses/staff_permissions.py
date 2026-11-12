"""Staff permissions: the catalogue, the presets, and the one door every read goes through.

Request #39 (owner, 2026-10-19): *"Can we change all to admin and control only access permission?
So, a reviewer is someone with review permission. A QC likewise is an admin with QC permission."*
The roadmap is `docs/plans/2026-10-19-staff-permissions-roadmap.md`; read it before changing this.

THE MODEL
- **Team members** (`admin`, `finance`, `qc`, `reviewer`) hold a SET of permission keys. `role` stays on
  the row as the PRESET LABEL (where they sit on People, which letter they were sent, which Guide
  chapter they open). `PartnerAdmin.permissions` NULL means "the preset of `role`", which is every
  person alive today and every future invitee — there is NO BACKFILL, on purpose (the 0123 lesson;
  the owner's own NULL-means-default pattern for `PartnerAdmin.programme`).
- **The organisation lead** (`org_admin`) is a FIXED TIER that nobody edits (`LEAD_TIER`).
- **Platform roles** sit outside: a `super` passes every key (as `has_role` passes every role); a
  referral `partner` holds nothing.

⚠ THE PRESETS REPRODUCE TODAY, EXCEPT THE PAYMENT CHAIN. `apps/courses/tests/test_permission_presets.py`
(the golden table) proves it gate by gate. Sprint 1 converted no gate and kept the old payment chain
(`finance` = the CHECK, `org_admin` = the APPROVAL). **Sprint 2 (owner ruling, 2026-10-19, option A:
"I would like the role to be able to approve payment — the work that Suresh does today") changed
exactly two rows here:** `finance` now holds `payments_approve`, and the lead tier no longer does —
the organisation admin approves a run only under the per-run FALLBACK, when nobody else can
(`apps/scholarship/payments_chain.py`). No preset holds `payments_check`: the middle check is dormant
until somebody is given it. The payment gates read these keys since Sprint 2; the student-file,
quality-check, assignment and Spending gates (Appendix A groups A-D) since Sprint 3.

⚠ THIS IS A LEAF. It imports nothing from `apps.scholarship` (the `courses → scholarship` ratchet is
at 17), and nothing from `models*` at import time — `PartnerAdmin.has_perm` lives on the model and
delegates here, so scholarship callers write `admin.has_perm('qc')` with no new import statement.
"""

#: The eleven keys, in the order the screen will group them (Students, then Money, then the team).
CATALOGUE = (
    'review',            # can be ASSIGNED cases; works on the cases assigned to them (files included)
    'see_all',           # "Applications": reads every APPLICATION in the organisation (no writes unless
                         # assigned). Sprint S1 (2026-11-09): no longer the Scholars door.
    # Sprint S1 (owner, 2026-11-09): reads every SCHOLAR's file in the organisation — the Scholars list,
    # every per-scholar endpoint and tab — and writes on it (result review, letters, activity notes).
    # In the admin preset and the lead tier; NOT in the reviewer or qc preset; nothing implies it.
    'scholars',
    'qc',                # the QC gate + working on any case in the organisation; IMPLIES `see_all` (T5b)
    'spending',          # the Spending page: named students' spending, flags, categories
    'payments_prepare',  # create / edit / cancel runs; signs as MAKER
    'payments_check',    # the optional middle signature (armed while an active member holds it)
    'payments_approve',  # the final signature, which completes the run and releases the money
    # A1.13b (owner ruling 2026-11-08): withdrawing an award is MAKER and CHECKER. NO preset holds either
    # key; the lead tier holds only the approve seat (`award_withdrawal_chain`). Never a super.
    'award_withdraw_request',  # asks for an award to be withdrawn, with an explanation (the MAKER)
    'award_withdraw_approve',  # approves or refuses somebody else's request (the CHECKER)
    'manage_team',       # invite / resend / revoke / restore / delete / change role (lead tier only)
)

#: A key that BRINGS another key with it (Team tables T5b, owner 2026-11-03: "QC implicitly sees ALL
#: students — QC self-sufficient, no `see_all` dependency"). A stored list naming `qc` is read WITH
#: `see_all` (`clean`), so `qc` alone reads exactly what `see_all + qc` reads: every `has_perm('see_all')`
#: reader, `_b40_scope`, the R1 assignment override and the web menus (which read the resolved list off
#: `admin/role/`) open by construction, with no reader to miss. Until T5b this was `DEPENDS_ON` — a stored
#: `qc` without `see_all` was DROPPED (read fail-closed) and the editor refused it (`qc_needs_see_all`).
#: ⚠ IT NEVER SEATS ANYBODY AT ADMINS: `staff_tables.admin_keys` still drops a `see_all` held beside `qc`.
#: ⚠ The QC gate's separation of duties is NOT here: `apps/scholarship/qc_separation.py`.
IMPLIES = {'qc': ('see_all',)}


def with_implied(keys):
    """`keys` plus every key they imply (`IMPLIES`), as a set. Never removes a key."""
    held = set(keys)
    for key, brings in IMPLIES.items():
        if key in held:
            held.update(brings)
    return held

#: Keys that are never granted to a team member in #39 (owner question 3: "Manage team" stays an
#: org-admin power). A stored list naming one is read without it.
LEAD_TIER_ONLY = frozenset({'manage_team'})

#: The roles that are team members — whose `permissions` may one day be edited.
TEAM_ROLES = ('admin', 'finance', 'qc', 'reviewer')

#: Each team role's preset: exactly what that role can do TODAY (proven by the golden table).
PRESETS = {
    'reviewer': ('review',),
    'qc': ('see_all', 'qc'),
    'admin': ('see_all', 'scholars', 'spending', 'payments_prepare'),   # S1: + scholars
    'finance': ('payments_approve',),    # Sprint 2 (owner, 2026-10-19): was payments_check
}

#: The organisation lead's fixed bundle. Never stored, never edited. Its other lead powers
#: (configuration, gifts, contracts, sponsors' acceptance, assigning cases, billing, requests, the
#: parent's contact, creating / editing / cancelling runs without signing as maker, and approving a
#: run under the FALLBACK when nobody else can) are not catalogue keys: they stay on
#: `role == 'org_admin'` (`is_lead_tier`).
LEAD_ROLE = 'org_admin'
LEAD_TIER = ('see_all', 'scholars', 'qc', 'spending', 'award_withdraw_approve', 'manage_team')   # Sprint 2:
# payments_approve removed; A1.13b: the withdrawal CHECKER seat added (the org admin approves, never
# requests); S1: `scholars` added

#: Team tables T2 (owner ruling 5, lead ruling 2026-11-03): the ONE key an organisation admin may hold
#: beyond the fixed tier — `review`, so they sit at the Reviewers table and can be assigned cases. It is
#: stored in the row's `permissions` column (an org_admin's column was never read before T2, and live
#: had no org_admin row with a value) and ONLY Team -> Reviewers -> Add / Remove writes it
#: (`apps/scholarship/staff_tables_admin.py`). ⚠ EVERY OTHER KEY IN THAT LIST IS IGNORED: the lead tier
#: stays fixed, and the generic permission editor still refuses the lead.
LEAD_MAY_ADD = 'review'


def lead_reviews(admin):
    """Has this ORGANISATION ADMIN joined the Reviewers table (`permissions` names `review`)?"""
    if admin is None or admin.is_super or admin.role != LEAD_ROLE:
        return False
    stored = getattr(admin, 'permissions', None)
    return isinstance(stored, (list, tuple)) and LEAD_MAY_ADD in stored


def _ordered(keys):
    """`keys` in catalogue order, as a tuple. One spelling of a set for every reader."""
    held = set(keys)
    return tuple(k for k in CATALOGUE if k in held)


def clean(keys):
    """A stored list read FAIL-CLOSED: unknown keys, lead-tier-only keys and duplicates are dropped.
    Returns a tuple in catalogue order.

    ⚠ The ONE key it adds is an implied one (`IMPLIES`, T5b): `qc` brings `see_all`. Before T5b a
    list naming `qc` without `see_all` lost `qc`; it now reads as `see_all + qc`, the QC preset."""
    if not isinstance(keys, (list, tuple)):
        return ()
    held = {k for k in keys if isinstance(k, str) and k in CATALOGUE and k not in LEAD_TIER_ONLY}
    return _ordered(with_implied(held))


def preset_for(role):
    """The preset of a role, a tuple in catalogue order. `org_admin` answers the lead tier; a
    platform or unknown role answers nothing."""
    if role == LEAD_ROLE:
        return _ordered(LEAD_TIER)
    return _ordered(PRESETS.get(role, ()))


def is_lead_tier(admin):
    """The organisation lead (never a super, who is platform-level)."""
    return admin is not None and not admin.is_super and admin.role == LEAD_ROLE


def resolve(admin):
    """THE ONE DOOR: the keys `admin` holds, as a tuple in catalogue order.

      super        → every key (a super passes every check; payments still lets them fill ONE slot)
      org_admin    → the lead tier, whatever `permissions` says (never editable) — plus `review`
                     when Team -> Reviewers added them (T2, `lead_reviews`); nothing else is read
      team member  → `permissions` cleaned, or the preset of `role` when it is NULL
      anyone else  → nothing (a referral partner, a SOURCE user — source sign-in S1 —, an unknown
                     role, None). A source user is never a team member, whatever `permissions` says.
    """
    if admin is None:
        return ()
    if admin.is_super:
        return CATALOGUE
    if admin.role == LEAD_ROLE:
        if lead_reviews(admin):
            return _ordered((*LEAD_TIER, LEAD_MAY_ADD))
        return preset_for(LEAD_ROLE)
    if admin.role not in PRESETS:
        return ()
    stored = getattr(admin, 'permissions', None)
    if stored is None:
        return preset_for(admin.role)
    return clean(stored)


def holds(admin, key):
    """Whether `admin` holds `key`. ⚠ An unknown key RAISES: a typo in a gate must turn a test red,
    never deny (or allow) quietly for ever."""
    if key not in CATALOGUE:
        raise KeyError(f'unknown staff permission {key!r}; the catalogue is {", ".join(CATALOGUE)}')
    return key in resolve(admin)


def is_custom(admin):
    """True when a team member's set was saved by hand (`permissions IS NOT NULL`). A list equal to
    the preset is stored as NULL by the editor (Sprint 4), so this is derivable, never stored.

    M2b D7: an `admin` whose OLD keys are the preset and whose stored v2 keys are exactly
    `ADMIN_PRESET_V2` holds the Admin preset (a list only because v2 keys cannot be NULL) — not custom."""
    if not (admin is not None and not admin.is_super and admin.role in PRESETS
            and getattr(admin, 'permissions', None) is not None):
        return False
    old, v2_held, v2_preset = _two_parts(admin)
    return not (admin.role == 'admin' and old == preset_for('admin') and v2_held == v2_preset)


def _two_parts(admin):
    """``(old keys, stored v2 keys, the role's v2 preset)`` — M2b compares each part to its own preset."""
    from . import staff_permissions_v2 as v2      # v2 imports this leaf: read lazily, no cycle
    return resolve(admin), v2.stored_v2(admin), v2.V2_PRESETS.get(admin.role, ())


def preset_diff(admin):
    """``(added, removed)``: the keys a team member holds BEYOND their preset, and the preset keys
    they do NOT hold — what People's permission chips show (Sprint 4). Both empty on the preset, and
    for anybody whose set is not editable (the lead tier, a super, a partner). M2b: the v2 part is
    compared with the role's v2 preset (`staff_permissions_v2.V2_PRESETS`), after the old."""
    if not is_custom(admin):
        return [], []
    held, v2_held, v2_preset = _two_parts(admin)
    preset = preset_for(admin.role)
    return ([k for k in held if k not in preset] + [k for k in v2_held if k not in v2_preset],
            [k for k in preset if k not in held] + [k for k in v2_preset if k not in v2_held])


def org_staff(organisation):
    """The organisation's ACTIVE staff, never a super, in id order — the ONE read `holders` filters.
    A caller asking for several keys of one organisation reads this once and passes it as `staff`."""
    from .models_staff import PartnerAdmin
    return list(PartnerAdmin.objects.filter(owning_organisation=organisation, is_active=True)
                .exclude(role='super').order_by('id'))


def holders(organisation, key, staff=None):
    """The organisation's ACTIVE staff who hold `key`, as a list. `staff`, when given, is that
    organisation's `org_staff` already read (A1.13b: one read for both payment keys).

    ⚠ IN PYTHON, NOT A QUERYSET LOOKUP, and on purpose: Django's JSONField `__contains` is not
    supported on SQLite, which the test suite runs on, so a lookup would pass on one database and
    fail on the other. An organisation has tens of staff and this runs on rare operations.

    ⚠ A SUPER IS NEVER A HOLDER, even one bound to the organisation. "An active member holds
    `payments_check`" arms the payment check (`payments.finance_check_required`), and "an active
    member holds `payments_approve`" turns the organisation admin's fallback off; counting a super
    (who passes every key) would do either for every organisation a super happened to sit in.
    """
    if organisation is None:
        return []
    holds(None, key)                       # validates the key, so a typo raises here too
    if staff is None:
        staff = org_staff(organisation)
    return [a for a in staff if key in resolve(a)]


def team_holding(keys, *, with_lead=False):
    """A `Q` for the TEAM MEMBERS who hold ANY of `keys`, to narrow a `PartnerAdmin` queryset
    (Sprint 3: the Reviewers tab and the assignable list).

    ⚠ TEAM MEMBERS ONLY — never the lead tier, never a super, never a partner. The callers add a
    super themselves where today's list had one. The organisation admin is left out ON PURPOSE
    (owner, 2026-10-19: org admins stay off the Reviewers list even though the lead tier holds
    `qc`).

    Two halves, for the reason `holders` gives: a NULL row is its role's preset, which SQL can
    filter by role; a saved custom set is read in Python (one query over the custom rows, which
    are few) and joined back by id, because JSONField `__contains` does not run on SQLite.
    """
    from django.db.models import Q
    from .models_staff import PartnerAdmin
    wanted = set(keys)
    for key in wanted:
        holds(None, key)                   # validates the key, so a typo raises here too
    preset_roles = [r for r in TEAM_ROLES if wanted & set(preset_for(r))]
    # Team tables T2: ``with_lead`` also answers the ORGANISATION ADMINS who joined the Reviewers table
    # (`lead_reviews`) when `review` is asked — read in the SAME query (the Reviewers list's budget).
    roles = (*TEAM_ROLES, LEAD_ROLE) if with_lead and LEAD_MAY_ADD in wanted else TEAM_ROLES
    custom = (PartnerAdmin.objects.filter(role__in=roles, permissions__isnull=False)
              .only('id', 'role', 'permissions'))
    custom_ids = [a.pk for a in custom
                  if (lead_reviews(a) if a.role == LEAD_ROLE else wanted & set(resolve(a)))]
    return (Q(permissions__isnull=True, role__in=preset_roles)
            | Q(pk__in=custom_ids))

