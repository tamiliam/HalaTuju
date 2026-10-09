"""People → Change role (staff lifecycle sprint, 2026-10-09).

Part of the `views_admin` package; re-exported from `views_admin/__init__.py`. The rules live in
`apps.scholarship.staff_lifecycle` — this file is the door: who may knock, and the AUDIT line.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminStaffRoleView(_AdminBase):
    """PATCH admin/admins/<id>/role/ ``{role, dry_run?}`` — switch a person within their pair.

    Admin ↔ Finance, Reviewer ↔ QC, nothing else (owner, 2026-10-09; see `staff_lifecycle`). Only
    a super or an org_admin acts, and an org_admin only on somebody `_staff_target_manageable`
    lets them manage — the same fence Revoke, Resend and Delete use, so a row the caller may not
    touch is 404, never 403, and existence does not leak.

    ``dry_run: true`` answers what the switch WOULD do (``consequence``: the payment finance check
    switching on or off) without writing — the confirmation reads it so it can name the
    consequence before the click, from the same rule the write applies. A dry run is refused
    exactly as the write would be.

    A role change takes effect at once on the server: `get_admin` reads the row on every request.
    Nobody can switch their OWN role here — an org_admin is never manageable and a super is not
    switchable — so the caller's cached `/admin/role/` never goes stale through this door.
    """

    def patch(self, request, admin_id):
        from apps.courses.models import PartnerAdmin
        from apps.courses.views_admin import _staff_target_manageable
        from .. import staff_lifecycle
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        target = PartnerAdmin.objects.filter(pk=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            return Response({'error': 'Admin not found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # A body that is not an object, or a role that is not text, is a 400 — never a 500 (L1).
        body = request.data if isinstance(request.data, dict) else None
        if body is None or not isinstance(body.get('role'), str):
            return Response({'error': 'role must be a role name.', 'code': 'bad_request'},
                            status=status.HTTP_400_BAD_REQUEST)
        new_role = body['role'].strip()
        dry_run = body.get('dry_run') in (True, 'true', '1', 1)
        try:
            target, plan = staff_lifecycle.change_role(target.pk, new_role, dry_run=dry_run)
        except staff_lifecycle.RoleChangeRefused as refused:
            return Response({'error': refused.message, 'code': refused.code, **refused.extra},
                            status=refused.status)
        if not dry_run:
            logger.info('AUDIT staff_role_changed by=%s target=%s from=%s to=%s',
                        admin.email or '', target.pk, plan['from'], plan['to'])
        return Response({'id': target.pk, 'role': plan['to'] if not dry_run else plan['from'],
                         'from': plan['from'], 'to': plan['to'],
                         'consequence': plan['consequence'], 'dry_run': dry_run})
