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

#: The eight keys, in the order the screen will group them (Students, then Money, then the team).
CATALOGUE = (
    'review',            # can be ASSIGNED cases; works on the cases assigned to them (files included)
    'see_all',           # reads every application in the organisation (no writes unless assigned)
    'qc',                # the QC gate + working on any case in the organisation; needs `see_all`
    'spending',          # the Spending page: named students' spending, flags, categories
    'payments_prepare',  # create / edit / cancel runs; signs as MAKER
    'payments_check',    # the optional middle signature (armed while an active member holds it)
    'payments_approve',  # the final signature, which completes the run and releases the money
    'manage_team',       # invite / resend / revoke / restore / delete / change role (lead tier only)
)

#: A key that needs another key. The editor (Sprint 4) adds the dependency; a stored list that
#: breaks it is read FAIL-CLOSED here (the dependent key is dropped, never the other one added).
DEPENDS_ON = {'qc': ('see_all',)}

#: Keys that are never granted to a team member in #39 (owner question 3: "Manage team" stays an
#: org-admin power). A stored list naming one is read without it.
LEAD_TIER_ONLY = frozenset({'manage_team'})

#: The roles that are team members — whose `permissions` may one day be edited.
TEAM_ROLES = ('admin', 'finance', 'qc', 'reviewer')

#: Each team role's preset: exactly what that role can do TODAY (proven by the golden table).
PRESETS = {
    'reviewer': ('review',),
    'qc': ('see_all', 'qc'),
    'admin': ('see_all', 'spending', 'payments_prepare'),
    'finance': ('payments_approve',),    # Sprint 2 (owner, 2026-10-19): was payments_check
}

#: The organisation lead's fixed bundle. Never stored, never edited. Its other lead powers
#: (configuration, gifts, contracts, sponsors' acceptance, assigning cases, billing, requests, the
#: parent's contact, creating / editing / cancelling runs without signing as maker, and approving a
#: run under the FALLBACK when nobody else can) are not catalogue keys: they stay on
#: `role == 'org_admin'` (`is_lead_tier`).
LEAD_ROLE = 'org_admin'
LEAD_TIER = ('see_all', 'qc', 'spending', 'manage_team')   # Sprint 2: payments_approve removed


def _ordered(keys):
    """`keys` in catalogue order, as a tuple. One spelling of a set for every reader."""
    held = set(keys)
    return tuple(k for k in CATALOGUE if k in held)


def clean(keys):
    """A stored list read FAIL-CLOSED: unknown keys, lead-tier-only keys, duplicates and a
    dependent key without its dependency are all dropped. Returns a tuple in catalogue order.

    ⚠ It never ADDS a key. A list that says `qc` without `see_all` is a list somebody wrote by hand
    (the Sprint 4 editor refuses it, `apps/scholarship/staff_permissions_admin.asked_set`); answering
    it with LESS access is the safe reading."""
    if not isinstance(keys, (list, tuple)):
        return ()
    held = {k for k in keys if isinstance(k, str) and k in CATALOGUE and k not in LEAD_TIER_ONLY}
    for key, needs in DEPENDS_ON.items():
        if key in held and not all(n in held for n in needs):
            held.discard(key)
    return _ordered(held)


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
      org_admin    → the lead tier, whatever `permissions` says (never editable)
      team member  → `permissions` cleaned, or the preset of `role` when it is NULL
      anyone else  → nothing (a referral partner, an unknown role, None)
    """
    if admin is None:
        return ()
    if admin.is_super:
        return CATALOGUE
    if admin.role == LEAD_ROLE:
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
    the preset is stored as NULL by the editor (Sprint 4), so this is derivable, never stored."""
    return (admin is not None and not admin.is_super and admin.role in PRESETS
            and getattr(admin, 'permissions', None) is not None)


def preset_diff(admin):
    """``(added, removed)``: the keys a team member holds BEYOND their preset, and the preset keys
    they do NOT hold — what People's permission chips show (Sprint 4). Both empty on the preset, and
    for anybody whose set is not editable (the lead tier, a super, a partner)."""
    if not is_custom(admin):
        return [], []
    held, preset = resolve(admin), preset_for(admin.role)
    return [k for k in held if k not in preset], [k for k in preset if k not in held]


def holders(organisation, key):
    """The organisation's ACTIVE staff who hold `key`, as a list.

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
    from .models_staff import PartnerAdmin
    staff = (PartnerAdmin.objects.filter(owning_organisation=organisation, is_active=True,
                                         is_super_admin=False)
             .exclude(role='super').order_by('id'))
    return [a for a in staff if key in resolve(a)]


def team_holding(keys):
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
    custom = (PartnerAdmin.objects.filter(role__in=TEAM_ROLES, is_super_admin=False,
                                          permissions__isnull=False)
              .only('id', 'role', 'is_super_admin', 'permissions'))
    custom_ids = [a.pk for a in custom if wanted & set(resolve(a))]
    return (Q(permissions__isnull=True, role__in=preset_roles, is_super_admin=False)
            | Q(pk__in=custom_ids))
