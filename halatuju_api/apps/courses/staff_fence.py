"""The staff fence: which staff rows a caller may manage, and which may be deleted (M1a, 2026-11-10).

Moved verbatim from `views_admin.py` (moves only, before M1 grows them), and re-exported there, so
every `from apps.courses.views_admin import _staff_target_manageable` keeps working. Edit HERE.
"""


# Programme-staff roles an org_admin may manage (invite / list / resend / revoke). Never
# partner (referral), never super, never org_admin — no privilege escalation.
# `finance` joined 2026-07-23 (owner decision D5): the org lead appoints their own finance
# checker. Safe against escalation because finance grants LESS than the roles already here —
# it has no B40 scope at all — and it cannot manage staff, so it can never appoint anyone.
_ORG_ADMIN_MANAGEABLE_ROLES = {'reviewer', 'admin', 'qc', 'finance'}

# Everyone who belongs to a TENANT's own staff list — what an org_admin may SEE. Wider than
# `_ORG_ADMIN_MANAGEABLE_ROLES` by exactly one role, `org_admin`, and the gap is the point: you can
# see your fellow organisation admins, you cannot revoke them. Mirrors the frontend's
# `adminStaff.PROGRAMME_STAFF_ROLES`; `super` and `partner` are platform-world and never here.
PROGRAMME_STAFF_ROLES = {'reviewer', 'admin', 'qc', 'finance', 'org_admin'}

# The roles a staff account may be DELETED in. D6 (Sprint T2, 2026-11-08) REVERSES 2026-09-09's "admins,
# not reviewers": reviewers and QC too, under the SAME no-work test (`staff_footprint` counts every case
# they held, reviewed, interviewed, QC'd or mentored). A pure mentor: `mentor_invite.delete_mentor`.
_DELETABLE_ROLES = {'admin', 'finance', 'org_admin', 'reviewer', 'qc'}


def _deletable_now(caller, target, work=None):
    """Whether ``caller`` may DELETE ``target`` outright, rather than only revoke them.

    Three conditions, all required, and each is refused again by `AdminDeleteView`:
      * the caller may manage them at all (`_staff_target_manageable`);
      * the role is a programme-staff one (`_DELETABLE_ROLES`; reviewers and QC since D6, 2026-11-08);
      * they have done NO recorded work (`staff_footprint`).
    """
    from .views_admin import scholarship_staff   # lazy: views_admin re-exports this module
    staff_footprint, _ = scholarship_staff()
    if not _staff_target_manageable(caller, target):
        return False
    if target.is_super or target.role not in _DELETABLE_ROLES:
        return False
    return not (work if work is not None else staff_footprint.footprint(target))


def _staff_target_manageable(caller, target):
    """Whether ``caller`` may manage (resend/revoke) the staff row ``target``. A platform
    super manages anyone; an ``org_admin`` manages ONLY non-super programme staff
    (reviewer/admin/qc) bound to the caller's OWN owning organisation. Anyone else: no.
    Caller/target visibility failures collapse to a 404 at the call site (no existence leak)."""
    if caller is None or target is None or target.is_source_user or target.is_mentor:
        return False        # not staff: a source user (S1; S2 has its doors), a mentor (S7a, ditto)
    if caller.is_super:
        return True
    if caller.role == 'org_admin':
        if target.is_super or target.role not in _ORG_ADMIN_MANAGEABLE_ROLES:
            return False
        return (caller.owning_organisation_id is not None
                and target.owning_organisation_id == caller.owning_organisation_id)
    return False
