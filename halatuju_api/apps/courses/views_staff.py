"""Deleting a staff account (moved out of `views_admin.py` by the staff lifecycle sprint, 2026-10-09).

`views_admin.py` is in the oversize ledger and a hotspot; this sprint changed what a delete does
(the Supabase login goes too), so the view moved to its own module rather than grow the big one.
The body is the old one plus the login step. `urls.py` imports it from here.

⚠ The logger keeps the OLD module's name, so the `AUDIT staff_deleted` line reads exactly as it did.
"""
import logging

from django.db import DatabaseError, transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PartnerAdmin
from .views_admin import (_DELETABLE_ROLES, PartnerAdminMixin, _staff_target_manageable,
                          scholarship_staff)

logger = logging.getLogger('apps.courses.views_admin')


class AdminDeleteView(PartnerAdminMixin, APIView):
    """DELETE /api/v1/admin/admins/<id>/ — remove a staff account that never started.

    ⚠ **REVOKE IS THE NORMAL ANSWER; THIS IS THE NARROW ONE.** Owner, 2026-09-09: an admin *"should
    only be deleted if they are not doing any work"*. Once somebody has done something, the record
    of who did it has to keep meaning something — so they are revoked, for ever, and this refuses.

    ⚠ **THE GUARD IS A FOOTPRINT, NOT THE DATABASE'S OWN PROTECTIONS**, and the difference is not
    academic. A `PaymentRun` stores its author as `created_by`, an EMAIL STRING with no foreign key:
    on production one admin had made 25 of the 27 runs and signed 8, and a foreign-key rule would
    have declared her safe to delete and left 25 runs naming an address with nobody behind it. See
    `apps.scholarship.staff_footprint`.

    ⚠ **REVIEWERS ARE NEVER DELETABLE** (`_DELETABLE_ROLES`), however empty their record looks —
    the owner scoped this to admins explicitly, and a reviewer is who a student's case passed
    through.

    ⚠ **THE LOGIN GOES TOO, BEFORE THE ROW** (2026-10-09). The row is the only record of which
    Supabase login is ours; deleting it and leaving the login made a re-invite of the same address
    take the "already registered" path and email no password — which happened to a real invitee.
    `staff_lifecycle.plan_login_retirement` decides (only when the login is ours and unused) and
    `retire_login` acts once the row is gone. If Supabase cannot be READ nothing is deleted (502);
    if the removal itself fails after the row is gone, that is logged at ERROR and the leftover
    unused login is adopted by the next invite of the address (`staff_lifecycle.adoptable_login`).
    The account's `Invitation` rows are deleted with it (`Invitation.partner_admin` is CASCADE).

    Refusals are separated on purpose: 404 for a row this caller may not touch (no existence leak),
    400 for a role that is never deletable, and **409 with the counts** when there is work — so the
    screen can say *what* is stopping it rather than greying a button for no visible reason.
    """

    def delete(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)
        staff_footprint, staff_lifecycle = scholarship_staff()

        # ⚠ LOCKED, RE-CHECKED, ROW FIRST, LOGIN LAST (review M2). The row is locked and every
        # refusal re-read on the locked copy, so work landing between the list and the click still
        # refuses; the login is only PLANNED inside the transaction (a read), and removed after the
        # row is gone — so a failed row delete can never leave a row naming a deleted login.
        try:
            return self._delete_locked(admin, admin_id, staff_footprint, staff_lifecycle)
        except DatabaseError:
            logger.exception('staff delete of %s failed in the database; nothing was removed',
                             admin_id)
            return Response({'error': 'Could not delete them just now. Nothing was removed; try '
                             'again.', 'code': 'delete_failed'}, status=503)

    def _delete_locked(self, admin, admin_id, staff_footprint, staff_lifecycle):
        with transaction.atomic():
            target = PartnerAdmin.objects.select_for_update().filter(id=admin_id).first()
            if target is None or not _staff_target_manageable(admin, target):
                return Response({'error': 'Admin not found'}, status=404)
            if target.is_super_admin or target.is_super:
                return Response({'error': 'Cannot delete a super admin', 'code': 'not_deletable'},
                                status=400)
            if target.role not in _DELETABLE_ROLES:
                return Response({'error': 'Only an admin account can be deleted',
                                 'code': 'not_deletable'}, status=400)
            work = staff_footprint.footprint(target)
            if work:
                return Response({'error': f'{target.name} has work on record and can only be '
                                 'revoked.', 'code': 'has_work', 'work': work}, status=409)
            plan, account = staff_lifecycle.plan_login_retirement(target)
            if plan == 'failed':
                return Response({'error': 'Could not check their sign-in. Nothing was deleted; '
                                 'try again.', 'code': 'login_cleanup_failed'}, status=502)
            name, email, uid = target.name, target.email, target.supabase_user_id
            target.delete()
        login = staff_lifecycle.retire_login(uid, plan, account)
        logger.info('AUDIT staff_deleted by=%s target=%s email=%s login=%s',
                    admin.email, admin_id, email, login)
        # ⚠ SAID HONESTLY (review round 2, N3): the row is gone either way, but a login we meant to
        # remove or close may still be there. `retire_login` has logged it at ERROR with the UID.
        if login == 'failed':
            return Response({'message': f'{name} deleted, but their sign-in could not be removed '
                             '— tell support.', 'login': login})
        return Response({'message': f'{name} deleted.', 'login': login})
