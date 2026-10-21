"""People → Change role (staff lifecycle sprint, 2026-10-09), and → What <name> can do (request #39
Sprint 4, 2026-10-21: the staff-permission editor).

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
            target, plan = staff_lifecycle.change_role(target.pk, new_role, dry_run=dry_run,
                                                       by=admin)
        except staff_lifecycle.RoleChangeRefused as refused:
            return Response({'error': refused.message, 'code': refused.code, **refused.extra},
                            status=refused.status)
        if not dry_run:
            logger.info('AUDIT staff_role_changed by=%s target=%s from=%s to=%s permissions_reset=%s',
                        admin.email or '', target.pk, plan['from'], plan['to'],
                        plan['permissions_reset'])
        return Response({'id': target.pk, 'role': plan['to'] if not dry_run else plan['from'],
                         'from': plan['from'], 'to': plan['to'],
                         'consequence': plan['consequence'],
                         # #39 S4: a saved custom set goes back to the NEW role's preset.
                         'permissions_reset': plan['permissions_reset'],
                         'consequences': plan['consequences'], 'dry_run': dry_run})


class AdminStaffPermissionsView(_AdminBase):
    """GET / PATCH admin/admins/<id>/permissions/ — what one person may do (request #39 Sprint 4).

    GET serves the editor: the person's preset, their RESOLVED set, whether it is custom, and the
    keys the editor may show. PATCH ``{permissions: [...], dry_run?}`` saves a new set; with
    ``dry_run: true`` it answers what the save WOULD do (``added`` / ``removed`` / ``consequences``)
    without writing, and refuses exactly as the save would — the screen's consequence line reads it.

    The SAME fence as Change role, Revoke, Resend and Delete: only a super or an org_admin knocks, and
    an org_admin only on somebody `_staff_target_manageable` lets them manage (own organisation,
    never an org_admin, super or partner) — anything else is 404, never 403, so existence does not
    leak. A super passes that fence for everyone, so the service refuses the targets nobody edits
    (an org_admin's lead tier, a super, a partner, your own row). The edited person's cached
    `/admin/role/` is not trusted: every gate re-reads the row (`get_admin`) on every request.
    """

    def _target(self, request, admin_id):
        from apps.courses.models import PartnerAdmin
        from apps.courses.views_admin import _staff_target_manageable
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return None, None, self._deny_role()
        target = PartnerAdmin.objects.filter(pk=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            return None, None, Response({'error': 'Admin not found', 'code': 'not_found'},
                                        status=status.HTTP_404_NOT_FOUND)
        return admin, target, None

    def get(self, request, admin_id):
        from apps.courses import staff_permissions as sp
        from .. import staff_permissions_admin as spa
        admin, target, err = self._target(request, admin_id)
        if err:
            return err
        # S4 review fix 8: a revoked person is not editable either (the PATCH refuses `not_active`),
        # so the card draws no dead switches; `is_active` lets it say "restore them first".
        editable = (not target.is_super and target.role in sp.TEAM_ROLES and target.pk != admin.pk
                    and target.is_active)
        return Response({'id': target.pk, 'name': target.name, 'role': target.role,
                         'is_active': target.is_active, 'editable': editable,
                         'preset': list(sp.preset_for(target.role)),
                         'permissions': list(sp.resolve(target)),
                         'custom': sp.is_custom(target), 'keys': list(spa.editable_keys())})

    def patch(self, request, admin_id):
        from .. import staff_permissions_admin as spa
        admin, target, err = self._target(request, admin_id)
        if err:
            return err
        body = request.data if isinstance(request.data, dict) else None
        if body is None or 'permissions' not in body:
            return Response({'error': 'permissions must be a list of permission names.',
                             'code': 'bad_request'}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = body.get('dry_run') is True          # S4 review fix 10: only a JSON true
        try:
            target, plan = spa.change_permissions(target.pk, body['permissions'], by=admin,
                                                  dry_run=dry_run)
        except spa.PermissionChangeRefused as refused:
            return Response({'error': refused.message, 'code': refused.code, **refused.extra},
                            status=refused.status)
        if not dry_run and plan['changed']:
            logger.info('AUDIT staff_permissions_changed by=%s target=%s role=%s before=%s after=%s',
                        admin.email or '', target.pk, target.role, ','.join(plan['before']) or '-',
                        ','.join(plan['after']) or '-')
        return Response({'id': target.pk, 'role': target.role, 'dry_run': dry_run,
                         'changed': plan['changed'], 'permissions': plan['after'],
                         'custom': plan['custom'], 'added': plan['added'],
                         'removed': plan['removed'], 'consequences': plan['consequences']})
