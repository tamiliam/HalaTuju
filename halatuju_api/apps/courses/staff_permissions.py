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

⚠ SPRINT 1 CONVERTS NO GATE. Every gate still reads `role`. What this module must do in Sprint 1 is
reproduce TODAY exactly, and `apps/courses/tests/test_permission_presets.py` (the golden table)
proves it gate by gate. So the presets below are TODAY's powers — including the payment chain as it
stands: `finance` holds the CHECK and `org_admin` the APPROVAL. Sprint 2 applies the owner's ruling of
2026-10-19 (Finance APPROVES runs; the organisation admin stops countersigning and becomes the
fallback approver) by changing those two rows here and the named payment rows of the golden table,
in the same change.

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
    'finance': ('payments_check',),      # Sprint 2 (owner, 2026-10-19): becomes payments_approve
}

#: The organisation lead's fixed bundle, as TODAY. Never stored, never edited. Its other lead powers
#: (configuration, gifts, contracts, sponsors' acceptance, assigning cases, billing, requests, the
#: parent's contact, and creating / editing / cancelling runs without signing as maker) are not
#: catalogue keys: they stay on `role == 'org_admin'` (`is_lead_tier`).
LEAD_ROLE = 'org_admin'
LEAD_TIER = ('see_all', 'qc', 'spending', 'payments_approve', 'manage_team')   # S2: minus approve


def _ordered(keys):
    """`keys` in catalogue order, as a tuple. One spelling of a set for every reader."""
    held = set(keys)
    return tuple(k for k in CATALOGUE if k in held)


def clean(keys):
    """A stored list read FAIL-CLOSED: unknown keys, lead-tier-only keys, duplicates and a
    dependent key without its dependency are all dropped. Returns a tuple in catalogue order.

    ⚠ It never ADDS a key. A list that says `qc` without `see_all` is a list somebody wrote by hand
    (the Sprint 4 editor refuses it); answering it with LESS access is the safe reading."""
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


def holders(organisation, key):
    """The organisation's ACTIVE staff who hold `key`, as a list.

    ⚠ IN PYTHON, NOT A QUERYSET LOOKUP, and on purpose: Django's JSONField `__contains` is not
    supported on SQLite, which the test suite runs on, so a lookup would pass on one database and
    fail on the other. An organisation has tens of staff and this runs on rare operations.

    ⚠ A SUPER IS NEVER A HOLDER, even one bound to the organisation. "An active member holds
    `payments_check`" arms the payment check; counting a super (who passes every key) would arm it
    for every organisation a super happened to sit in — which is not today's rule
    (`payments.finance_check_required` counts active `finance` rows only).
    """
    if organisation is None:
        return []
    holds(None, key)                       # validates the key, so a typo raises here too
    from .models_staff import PartnerAdmin
    staff = (PartnerAdmin.objects.filter(owning_organisation=organisation, is_active=True,
                                         is_super_admin=False)
             .exclude(role='super').order_by('id'))
    return [a for a in staff if key in resolve(a)]
