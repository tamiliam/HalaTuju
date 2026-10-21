"""People → a person → "What <name> can do": the rules behind the staff-permission editor
(request #39 Sprint 4, 2026-10-21). The roadmap is `docs/plans/2026-10-19-staff-permissions-roadmap.md`.

The view (`views_admin/staff_permissions.py`) is the door — who may knock, the 404 fence, the AUDIT
line. This module decides what a change may be, what it would do, and writes it with its history.

⚠ WHOSE SET MAY CHANGE. Only a TEAM member's (`admin`, `finance`, `qc`, `reviewer`): never the
organisation admin's (a fixed lead tier nobody edits), a super's, a referral partner's — and never
your OWN. The view's `_staff_target_manageable` already stops an org_admin reaching anybody else; a
super passes that fence for everyone, so `plan_change` refuses the rest here, for both callers.

⚠ A CHANGE MAY NOT STRAND A CASE (the S3 as-built notes). Somebody holding in-play cases keeps
`review`; and if they reach those cases through `see_all` (an admin or qc given work by a super, R1),
they keep that too unless `review` stays. Read under the target's ROW LOCK, and `assign_reviewer`
re-reads its target under the same lock, so an assignment racing a removal is serialised (TD-382
class): whichever commits second sees the first.

⚠ THE MONEY CONSEQUENCES ARE LIVE RULES, NOT STORED STATE (S2). Giving the first signed-in member
`payments_approve` turns the organisation admin's fallback OFF; taking it from the last one turns it
back ON; the same for `payments_check` and the optional check step. The dry run names them so the
screen says it BEFORE the click, from the same holders the payment chain reads.

⚠ STORED AS THE PRESET WHEN IT IS THE PRESET. A set equal to the role's preset is saved as NULL, so
"custom" stays derivable (`permissions IS NOT NULL`) and a Change role later lands on the new preset.
"""
from django.db import transaction

#: The dry run's consequence codes, worded by the screen (`admin.permEditor.effect.*`).
CHECK_ON, CHECK_OFF = 'check_on', 'check_off'
FALLBACK_ON, FALLBACK_OFF = 'approver_fallback_on', 'approver_fallback_off'
FILES_ALL = 'files_widened_all'            # gains `see_all`: EVERY student's file
FILES_ASSIGNED = 'files_widened_assigned'  # gains `review` from no file access: the assigned ones
PREPARE_AND_APPROVE = 'prepare_and_approve'
NOT_SIGNED_IN = 'not_signed_in'


class PermissionChangeRefused(Exception):
    """A refusal the view turns into a response: ``code``, ``status``, a sentence, extra fields."""

    def __init__(self, code, status, message, **extra):
        super().__init__(code)
        self.code, self.status, self.message, self.extra = code, status, message, extra


def editable_keys():
    """The keys the editor shows, in catalogue order: everything but the lead-tier-only ones."""
    from apps.courses import staff_permissions as sp
    return tuple(k for k in sp.CATALOGUE if k not in sp.LEAD_TIER_ONLY)


def asked_set(asked):
    """The asked list as a tuple in catalogue order, or `PermissionChangeRefused`.

    ⚠ It REFUSES what `staff_permissions.clean` would quietly drop: the editor must never save
    something other than what the person saw."""
    from apps.courses import staff_permissions as sp
    if not isinstance(asked, (list, tuple)) or not all(isinstance(k, str) for k in asked):
        raise PermissionChangeRefused(
            'bad_request', 400, 'permissions must be a list of permission names.')
    unknown = sorted({k for k in asked if k not in sp.CATALOGUE})
    if unknown:
        raise PermissionChangeRefused(
            'unknown_permission', 400, f'Unknown permission: {", ".join(unknown)}.', unknown=unknown)
    if any(k in sp.LEAD_TIER_ONLY for k in asked):
        raise PermissionChangeRefused(
            'lead_tier', 400, 'Managing the team stays with the organisation admin. It cannot be '
            'given to a team member.')
    held = set(asked)
    for key, needs in sp.DEPENDS_ON.items():
        if key in held and not all(n in held for n in needs):
            raise PermissionChangeRefused(
                'qc_needs_see_all', 400,
                'Quality check needs "See all students": a checker reads every decision.')
    return tuple(k for k in sp.CATALOGUE if k in held)


#: The roles People lists on the REVIEWERS tab only (`adminStaff.byCategory`), and the keys that put
#: somebody on that tab (`_ReviewersBase._reviewers`: team members holding `review` or `qc`).
REVIEWERS_TAB_ROLES = ('reviewer', 'qc')
REVIEWERS_TAB_KEYS = ('review', 'qc')


def _refuse_unlisted(target, after):
    """#39 S4 review fix 1: a Reviewer or QC whose set holds neither `review` nor `qc` would be on
    NEITHER People tab — the Admins tab lists by role, the Reviewers tab by those keys — so nobody
    could reach their card, Revoke or Delete again. Refused, so People always lists everyone."""
    if target.role in REVIEWERS_TAB_ROLES and not set(REVIEWERS_TAB_KEYS) & set(after):
        raise PermissionChangeRefused(
            'would_leave_people', 400,
            'A Reviewer or QC must keep "Review assigned students" or "Quality check", or they would '
            'disappear from People. For someone who only needs Spending or to view, invite them as '
            'an Admin instead.')


def _refuse_target(target, by):
    from apps.courses import staff_permissions as sp
    if by is not None and target.pk == by.pk:
        raise PermissionChangeRefused(
            'own_permissions', 403, 'You cannot change your own permissions.')
    if target.is_super or target.role not in sp.TEAM_ROLES:
        raise PermissionChangeRefused(
            'not_editable', 400, "An organisation admin's, a super's or a referral partner's "
                                 'permissions are fixed and cannot be edited here.')
    if not target.is_active:
        raise PermissionChangeRefused(
            'not_active', 400,
            f"{target.name}'s access is revoked. Restore them before changing what they can do.")


def _refuse_stranding(target, before, after):
    """Keep somebody holding in-play cases able to open and work them (see the module docstring)."""
    from . import staff_lifecycle
    losing_review = 'review' in before and 'review' not in after
    losing_reach = 'see_all' in before and 'see_all' not in after and 'review' not in after
    if not (losing_review or losing_reach):
        return
    n = staff_lifecycle.open_cases(target)
    if n:
        what = '"Review assigned students"' if losing_review else '"See all students"'
        raise PermissionChangeRefused(
            'has_open_cases', 409,
            f'{target.name} has {n} open case(s) assigned. Taking away {what} would leave them '
            'unable to open those cases, so hand the cases to someone else first.', open_cases=n)


def _others_hold(target, key):
    """Does an ACTIVE member of the target's organisation OTHER than the target, who has signed in,
    hold ``key``? The payment chain's own reading (`payments_chain._signed_in`)."""
    from apps.courses import staff_permissions as sp
    return any(a.pk != target.pk and a.first_seen_at is not None
               for a in sp.holders(target.owning_organisation_id, key))


def consequences(target, before, after):
    """What saving ``after`` over ``before`` would do beyond the keys themselves — codes, in a stable
    order. Pure apart from reads."""
    out = []
    gained, lost = set(after) - set(before), set(before) - set(after)
    signed_in = target.first_seen_at is not None
    if target.owning_organisation_id is not None:
        for key, on, off in (('payments_check', CHECK_ON, CHECK_OFF),
                             ('payments_approve', FALLBACK_OFF, FALLBACK_ON)):
            if signed_in and key in gained and not _others_hold(target, key):
                out.append(on)
            if signed_in and key in lost and not _others_hold(target, key):
                out.append(off)
        if not signed_in and gained & {'payments_check', 'payments_approve'}:
            out.append(NOT_SIGNED_IN)
    # #39 S4 review fix 3: say WHICH files. `see_all` opens every student's (a Reviewer or Finance
    # person given it, or Finance switched to Admin); `review` from no file access opens only the
    # students assigned to them.
    if 'see_all' in gained:
        out.append(FILES_ALL)
    elif 'review' in gained and not ({'review', 'see_all'} & set(before)):
        out.append(FILES_ASSIGNED)
    if {'payments_prepare', 'payments_approve'} <= set(after) and not (
            {'payments_prepare', 'payments_approve'} <= set(before)):
        out.append(PREPARE_AND_APPROVE)
    return out


def plan_change(target, asked, *, by=None):
    """What saving ``asked`` for ``target`` would do, or `PermissionChangeRefused`. Read-only.

    Returns ``{'before', 'after', 'added', 'removed', 'stored', 'custom', 'consequences'}`` — the
    keys as lists in catalogue order; ``stored`` is what the column will hold (None = the preset)."""
    from apps.courses import staff_permissions as sp
    _refuse_target(target, by)
    after = asked_set(asked)
    before = sp.resolve(target)
    _refuse_unlisted(target, after)
    _refuse_stranding(target, before, after)
    stored = None if after == sp.preset_for(target.role) else list(after)
    return {
        'before': list(before), 'after': list(after),
        'added': [k for k in after if k not in before],
        'removed': [k for k in before if k not in after],
        'stored': stored, 'custom': stored is not None,
        'consequences': consequences(target, before, after),
    }


def record(target, before, after, *, by, kind):
    """One history row. Written inside the caller's transaction."""
    from .models import StaffPermissionChange
    return StaffPermissionChange.objects.create(
        target=target, target_email=target.email or '', organisation_id=target.owning_organisation_id,
        kind=kind, role=target.role, before=list(before), after=list(after),
        changed_by_email=(getattr(by, 'email', '') or ''),
        changed_by_role=('super' if getattr(by, 'is_super', False) else getattr(by, 'role', '')) or '')


def change_permissions(target_id, asked, *, by, dry_run=False):
    """Plan, and unless ``dry_run`` apply, the change. Returns ``(target, plan)``; ``plan['changed']``
    says whether anything was written.

    The row is LOCKED for the plan and the write (see the module docstring), and the UPDATE carries
    the role and the active flag it planned against, belt and braces."""
    from apps.courses.models import PartnerAdmin
    with transaction.atomic():
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id).first()
        if target is None:
            raise PermissionChangeRefused('not_found', 404, 'Admin not found')
        plan = plan_change(target, asked, by=by)
        # #39 S4 review fix 10: "changed" means what the person can DO changed. A list that resolves
        # to the same keys (a reordered or hand-written one) writes nothing and records nothing.
        plan['changed'] = plan['before'] != plan['after']
        if dry_run or not plan['changed']:
            return target, plan
        PartnerAdmin.objects.filter(pk=target.pk, role=target.role, is_active=True).update(
            permissions=plan['stored'])
        target.permissions = plan['stored']
        record(target, plan['before'], plan['after'], by=by, kind='edit')
    return target, plan
