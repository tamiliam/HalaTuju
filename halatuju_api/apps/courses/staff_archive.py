"""Delete as archive, and the re-invite that restores the same row (Sprint M1a, 2026-11-10; owner O7).

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §5.

**Delete (owner).** A person with NO records is erased by today's path (`views_staff.AdminDeleteView`,
`mentor_invite.delete_mentor`). A person WITH records (`staff_footprint.footprint` non-empty) is
ARCHIVED, when the caller asks for it with `{"archive": true}` — without the flag the answer is
today's 409 `has_work`, so a screen that never sends it (today's web) sees nothing change. Delete is
refused while anything is still waiting on them in ANY group (`staff_work.unfinished`, owner O7):
409 `has_unfinished_work` with the counts.

**Archive (lead)**, in ONE transaction, under the row lock and `lock_org_admins_of`
(`archive_locked`): the sole-org-admin refusal stays; the mentoring is left (`staff_mentor_leaves`, and a
mentor login's own mentor stamped deactivated); `is_active=False`, `archived_at`, `archived_by_email`;
waiting staff and mentor invitations cancelled; the login retired exactly as a delete retires it
(`plan_login_retirement` inside, `retire_login` after the commit) and `supabase_user_id` cleared. The
row, its role, permissions, mentor link, profile and gift rows are KEPT: the name stays on every record.

⚠ An archived row is out of reach by id (`staff_fence._staff_target_manageable` refuses it: 404 at every
door) and off every list. The ONE way back is a re-invite of the address:

**Restore (owner; closes TD-484).** `staff_reinvite.provision` hands an archived `reuse` to `restore`,
never to `bring_back` (which refuses archived rows): the same id, a NEW login, `first_seen_at` NULL (they
wait on Invitations again), the invite's role with `invite_permissions(role)` (owner answer 2), the
invite's gifts. The mentor link is kept with its mentor still deactivated (mentoring comes back only
through Add to Mentors), unless the new role or organisation may not carry it. The caller writes the new
Invitation, as for any invite. Another organisation's archived address keeps `not_invitable`.

⚠ The activity verb: `staff_activity` verbs are a closed list with a database `choices`, so a
`staff_archived` verb needs a scholarship migration M1a does not carry (TD-603). The AUDIT log line is
the record meanwhile.
"""
import logging
from collections import namedtuple

from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response

from .models import PartnerAdmin

logger = logging.getLogger('apps.courses.views_admin')

#: What `archive_locked` did: ``error`` (`has_unfinished_work` with ``work``, `login_cleanup_failed`) or
#: None, and the login plan to carry out after the commit (`staff_lifecycle.retire_login`).
Archived = namedtuple('Archived', 'error work plan account uid')


def _modules():
    """`(staff_lifecycle, invitations, staff_work)` through the ONE courses → scholarship door."""
    from .views_admin import _scholarship_staff_modules
    modules = _scholarship_staff_modules()
    return modules[1], modules[4], modules[5]


def archive_asked(data):
    """Only the JSON value ``true`` asks for an archive; anything else is today's Delete."""
    return isinstance(data, dict) and data.get('archive') is True


def archive_locked(caller, row):
    """Archive ``row`` — the caller holds it LOCKED inside its transaction and has made every refusal
    of its own door. Writes nothing when it refuses. Shared by the staff and the mentor Delete."""
    staff_lifecycle, invitations, staff_work = _modules()
    work = staff_work.unfinished(row)
    if staff_work.any_work(work):
        return Archived('has_unfinished_work', work, None, None, None)
    plan, account = staff_lifecycle.plan_login_retirement(row)
    if plan == 'failed':
        return Archived('login_cleanup_failed', None, None, None, None)
    from .views_admin import staff_mentor_leaves
    now, by, uid = timezone.now(), (caller.email or '')[:254], row.supabase_user_id
    staff_mentor_leaves(row, by=by)   # a staff mentor: stamped deactivated (no scholar is left: refused above)
    if row.mentor_id is not None:     # a mentor login: its mentor too. The LINK is kept (the name stays)
        PartnerAdmin._meta.get_field('mentor').related_model.objects.filter(
            pk=row.mentor_id, deactivated_at__isnull=True).update(deactivated_at=now, deactivated_by_email=by)
    invitations.open_only(invitations.Invitation.objects.filter(partner_admin=row)).update(
        revoked_at=now, updated_at=now)
    PartnerAdmin.objects.filter(pk=row.pk).update(
        is_active=False, archived_at=now, archived_by_email=by, supabase_user_id=None)
    logger.info('AUDIT staff_archived by=%s target=%s role=%s', caller.email, row.pk, row.role)
    return Archived(None, None, plan, account, uid)


def _refused(name, done):
    if done.error == 'has_unfinished_work':
        return Response({'error': f'{name} still has work waiting on them. Finish or hand it over first.',
                         'code': 'has_unfinished_work', 'work': done.work}, status=409)
    return Response({'error': 'Could not check their sign-in. Nothing was changed; try again.',
                     'code': 'login_cleanup_failed'}, status=502)


def before_delete(caller, admin_id, data):
    """`AdminDeleteView`'s M1a door, asked FIRST: a Response, or None for today's path.

    - the caller's own account: 403 `self` (lead, O10: no self-delete);
    - no `{"archive": true}`: None (today's Delete, unchanged);
    - a row today's Delete would refuse (not theirs to touch, never deletable, the sole org admin) or would
      ERASE (no records): None, and today's path answers it;
    - else the archive, or its refusal."""
    from .staff_delete_rules import is_sole_org_admin, lock_org_admins_of
    from .staff_fence import _deletable_now
    from .views_admin import scholarship_staff
    if str(admin_id) == str(caller.pk):
        return Response({'error': 'You cannot delete your own account.', 'code': 'self'}, status=403)
    if not archive_asked(data):
        return None
    staff_footprint, staff_lifecycle = scholarship_staff()
    with transaction.atomic():
        lock_org_admins_of(admin_id)
        target = PartnerAdmin.objects.select_for_update().filter(id=admin_id).first()
        if (target is None or not _deletable_now(caller, target, work={}) or is_sole_org_admin(target, lock=True)
                or not staff_footprint.footprint(target)):
            return None
        done = archive_locked(caller, target)
        if done.error:
            return _refused(target.name, done)
    login = staff_lifecycle.retire_login(done.uid, done.plan, done.account)
    if login == 'failed':
        return Response({'message': f'{target.name} archived, but their sign-in could not be removed — tell '
                         'support.', 'archived': True, 'login': login})
    return Response({'message': f'{target.name} archived. Their name stays on past records.',
                     'archived': True, 'login': login})


def may_restore(caller, existing):
    """Whether a staff re-invite of ``existing``'s address brings this ARCHIVED row back (`restore`): the
    caller would manage them once back (`manageable_if_restored`: own organisation, a manageable role,
    never a mentor or source login) and they are not a super. Their records are why they were archived,
    so the footprint does not refuse here (it does for `bring_back`)."""
    from .staff_fence import manageable_if_restored
    return (existing is not None and existing.is_archived and not existing.is_super
            and manageable_if_restored(caller, existing))


def restore(existing, *, name, role, org, owning_org, temp_password=None, email=None, gifts=()):
    """Bring the ARCHIVED ``existing`` back for a re-invite: ``(account, already_registered, error)``, the
    `bring_back` contract. The row is LOCKED and re-checked (still archived), so a second re-invite landing
    in between answers ``'not_reusable'`` (the caller's 409). A Supabase failure writes nothing
    (``'create_failed'``). ``temp_password`` None = a Google address: no login is made; it links on the
    first Google sign-in. The archive cleared the UID, so any other address gets a NEW login (`_new_login`
    adopts our own leftover one, and an address with a login of its own keeps it)."""
    from . import staff_gift, staff_tables
    from .staff_reinvite import _new_login
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=existing.pk, archived_at__isnull=False).first()
        if row is None or (row.role in PartnerAdmin.NOT_STAFF_ROLES and role != row.role):
            return None, False, 'not_reusable'
        email = email or row.email
        if PartnerAdmin.objects.filter(email=email).exclude(pk=row.pk).exists():
            return None, False, 'not_reusable'
        uid, already = None, temp_password is None
        if temp_password is not None:
            uid, already, err = _new_login(email, name, temp_password)
            if err:
                return None, False, err
        fields = []
        if row.mentor_id is not None and (role not in PartnerAdmin.MENTOR_LINK_ROLES
                                          or row.mentor.organisation_id != getattr(owning_org, 'pk', None)):
            row.mentor, fields = None, ['mentor']   # the new role or organisation may not carry the link
        row.archived_at, row.archived_by_email = None, ''
        row.name, row.email, row.role, row.org, row.owning_organisation = name, email, role, org, owning_org
        row.is_active, row.paused_at, row.first_seen_at = True, None, None
        row.permissions = staff_tables.invite_permissions(role)   # owner answer 2: fresh defaults
        row.supabase_user_id = uid
        row.save(update_fields=['archived_at', 'archived_by_email', 'name', 'email', 'role', 'org',
                                'owning_organisation', 'is_active', 'paused_at', 'first_seen_at',
                                'permissions', 'supabase_user_id', *fields])
        staff_gift.set_gifts(row, gifts)
    logger.info('AUDIT staff_restored target=%s role=%s', row.pk, role)
    return row, already, None
