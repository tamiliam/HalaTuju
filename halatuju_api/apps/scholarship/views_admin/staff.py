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
        if target.is_member or new_role == PartnerAdmin.MEMBER_ROLE:
            # M1a (brief §2 item 9): "No group" is reached and left by a group's Add / Remove, never here.
            return Response({'error': 'Add them to a group from the Staff list.', 'code': 'not_eligible'},
                            status=status.HTTP_400_BAD_REQUEST)
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
                         'consequences': plan['consequences'], 'dry_run': dry_run,
                         # S7d: the switch ends their mentoring (Admin → Finance of a staff mentor).
                         'stops_mentoring': plan['stops_mentoring']})


class AdminStaffPermissionsView(_AdminBase):
    """GET / PATCH admin/admins/<id>/permissions/ — what one person may do (request #39 Sprint 4).

    GET serves the editor: the person's preset, their RESOLVED set, whether it is custom, and the
    keys the editor may show — plus, since 2026-10-22, the person page's header (email, joined,
    signed in, paused) and the latest ``history`` rows, so the page and its "Changes" list need no
    second request. PATCH ``{permissions: [...], dry_run?}`` saves a new set; with
    ``dry_run: true`` it answers what the save WOULD do (``added`` / ``removed`` / ``consequences``)
    without writing, and refuses exactly as the save would — the screen's consequence line reads it.

    The SAME fence as Change role, Revoke, Resend and Delete: only a super or an org_admin knocks, and
    an org_admin only on somebody `_staff_target_manageable` lets them manage (own organisation,
    never an org_admin, super or partner) — anything else is 404, never 403, so existence does not
    leak. A super passes that fence for everyone, so the service refuses the targets nobody edits
    (an org_admin's lead tier, a super, a partner, your own row). The edited person's cached
    `/admin/role/` is not trusted: every gate re-reads the row (`get_admin`) on every request.
    """

    def _target(self, request, admin_id, read=False):
        """``read=True`` (the GET): the O10 read fence (`staff_target_readable`, M1a §6): an org admin also
        OPENS a fellow org admin's page and their own, view-only. Every write keeps the manage fence."""
        from apps.courses.models import PartnerAdmin
        from apps.courses.staff_fence import staff_target_readable
        from apps.courses.views_admin import _staff_target_manageable
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return None, None, self._deny_role()
        # T3: the profile and the mentor link ride on this query (the person page's `person` block).
        target = (PartnerAdmin.objects.select_related('reviewer_profile', 'mentor')
                  .filter(pk=admin_id).first())
        fence = staff_target_readable if read else _staff_target_manageable
        if target is None or not fence(admin, target):
            return None, None, Response({'error': 'Admin not found', 'code': 'not_found'},
                                        status=status.HTTP_404_NOT_FOUND)
        return admin, target, None

    def get(self, request, admin_id):
        from apps.courses import staff_permissions as sp
        from apps.courses import staff_tables
        from .. import staff_permissions_admin as spa
        from .. import staff_person, staff_tables_admin
        from apps.courses.views_admin import _staff_target_manageable
        admin, target, err = self._target(request, admin_id, read=True)
        if err:
            return err
        # S4 review fix 8: a revoked person is not editable either (the PATCH refuses `not_active`),
        # so the card draws no dead switches; `is_active` lets it say "restore them first".
        # M1a (O10): a page opened through the read fence only (a fellow org admin) is view-only.
        manageable = _staff_target_manageable(admin, target)
        editable = (manageable and not target.is_super and target.role in sp.TEAM_ROLES
                    and target.pk != admin.pk and target.is_active)
        # Sprint T2: the person page offers Revoke and Delete as the Admins table does — by one rule
        # (`staff_delete_rules.delete_fields`: work, deletable, delete_never, revocable).
        from apps.courses.staff_delete_rules import delete_fields
        return Response({'id': target.pk, 'name': target.name, 'role': target.role,
                         'is_active': target.is_active, 'editable': editable,
                         # The person page's header (Team → a person → Permissions, 2026-10-22).
                         'email': target.email, 'created_at': target.created_at,
                         'signed_in': target.first_seen_at is not None,
                         'paused': target.paused_at is not None,
                         'preset': list(sp.preset_for(target.role)), 'manageable': manageable,
                         # M1a (owner O12, addendum): each table's own preset, for that table's "Custom".
                         'table_presets': staff_tables_admin.table_presets(target),
                         'permissions': list(sp.resolve(target)),
                         'custom': sp.is_custom(target), 'keys': list(spa.editable_keys()),
                         # Team tables T3 (owner): the Permissions tab shows one section per table the
                         # person sits in (Admin permissions, Reviewer permissions). Read-only.
                         'tables': list(staff_tables.tables(target)),
                         'history': _permission_history(target, admin),
                         # Sprint T3: the ONE person page's header and Profile tab (`staff_person`) —
                         # Last seen, the lead flag and the profile, under the reviewer detail's PII rules.
                         'person': staff_person.person(target),
                         **delete_fields(admin, target)})


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


#: How many history rows the person page shows. The table keeps every row; the screen the latest.
HISTORY_LIMIT = 20


def _permission_history(target, viewer):
    """The target's `StaffPermissionChange` rows, newest first, worded-ready for the screen.

    ⚠ A SUPER'S ADDRESS IS NOT SHOWN TO AN ORGANISATION. A change made by the HalaTuju team comes back
    as ``by_super: true`` with ``by`` blank unless the viewer is a super too; the screen says "the
    HalaTuju team". Anybody else is named from their staff row in the TARGET's organisation, or by
    the address recorded at the time when that row is gone or elsewhere. A change a data migration made
    (``changed_by_role`` 'migration', nobody clicked) comes back as ``by_migration: true`` with ``by``
    blank; the screen says so in words (sprint S1, courses 0095).

    ⚠ ONLY THE TARGET'S CURRENT ORGANISATION'S ROWS. A cancelled invite re-sent into ANOTHER
    organisation reuses the same staff row (`staff_reinvite.bring_back`), so `target=` alone would
    show the new organisation the old one's changes and its admins' addresses (review, 2026-10-22)."""
    from apps.courses.models import PartnerAdmin
    from ..models import StaffPermissionChange
    rows = list(StaffPermissionChange.objects.filter(
        target=target, organisation_id=target.owning_organisation_id)
        .order_by('-created_at', '-id')[:HISTORY_LIMIT])
    emails = {r.changed_by_email for r in rows if r.changed_by_email and r.changed_by_role != 'super'}
    names = {}
    if emails and target.owning_organisation_id is not None:
        names = {a.email.lower(): a.name for a in PartnerAdmin.objects.filter(
            email__in=emails, owning_organisation_id=target.owning_organisation_id) if a.name}
    out = []
    for r in rows:
        before, after = list(r.before or []), list(r.after or [])
        by_super = r.changed_by_role == 'super'
        if by_super:
            by = (r.changed_by_email or '') if viewer.is_super else ''
        else:
            by = names.get((r.changed_by_email or '').lower(), r.changed_by_email or '')
        out.append({'kind': r.kind, 'role': r.role, 'before': before, 'after': after,
                    'added': [k for k in after if k not in before],
                    'removed': [k for k in before if k not in after],
                    'at': r.created_at, 'by': by, 'by_super': by_super,
                    'by_migration': r.changed_by_role == 'migration'})
    return out


class AdminTeamTableView(_AdminBase):
    """POST admin/team/<table>/ ``{admin_id, action: add|remove, dry_run?, to_no_group?}`` — Team -> Admins / Reviewers
    -> Add, or Remove from (Team tables T2). The rules are `staff_tables_admin`; this is the door.

    Only a super or an organisation admin knocks (who may edit permissions on Team today); a person the
    caller may not act on (`staff_tables_admin.may_act`: another organisation's, a fellow organisation
    admin, a super, a referral partner, a source user) is 404, never 403. The org admin may add or remove
    THEMSELVES at Reviewers (lead ruling Q4). Never touches a sign-in; never emails. ``dry_run: true``
    answers what the change WOULD do and refuses exactly as the write would."""

    def post(self, request, table):
        from apps.courses.models import PartnerAdmin
        from .. import staff_tables_admin as sta
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        body = request.data if isinstance(request.data, dict) else None
        action = body.get('action') if body else None
        try:
            target_id = int(body.get('admin_id')) if body else None
        except (TypeError, ValueError):
            target_id = None
        if table not in sta.TABLES or action not in ('add', 'remove') or target_id is None:
            return Response({'error': 'admin_id, and action add or remove, are required.',
                             'code': 'bad_request'}, status=status.HTTP_400_BAD_REQUEST)
        target = PartnerAdmin.objects.filter(pk=target_id).first()
        if target is None or not sta.may_act(admin, target, table):
            return Response({'error': 'Admin not found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        dry_run = body.get('dry_run') is True
        try:
            # M1a (owner O6): only a JSON true opts a last-group Remove into "No group"; absent = today's.
            target, plan = sta.change(target.pk, table, action, by=admin, dry_run=dry_run,
                                      to_no_group=body.get('to_no_group') is True)
        except sta.Refused as refused:
            return Response({'error': refused.message, 'code': refused.code, **refused.extra},
                            status=refused.status)
        if not dry_run:
            logger.info('AUDIT staff_table_%s by=%s target=%s table=%s role=%s->%s before=%s after=%s',
                        action, admin.email or '', target.pk, table, plan['role_from'], plan['role'],
                        ','.join(plan['before']) or '-', ','.join(plan['after']) or '-')
        return Response({'id': target.pk, 'table': table, 'action': action, 'dry_run': dry_run,
                         'role': plan['role'], 'role_changed': plan['role_changed'],
                         'added': plan['added'], 'removed': plan['removed'],
                         'consequences': plan['consequences'],
                         'finance_check_off': plan['finance_check_off'],
                         'opens_admin_pages': plan['opens_admin_pages'],
                         # T3: leaving their last staff table, they stay on as a mentor login.
                         'becomes_mentor': plan['becomes_mentor'],
                         'becomes_member': plan['becomes_member']})


class AdminTeamCandidatesView(_AdminBase):
    """GET admin/team/<table>/candidates/ — the Add sheet: ACTIVE members of the caller's organisation
    (a super: every organisation, or ``?organisation=<id>``) the caller may act on, not in that table,
    whom an Add would accept. Revoked / inactive people and other organisations' are never listed."""

    def get(self, request, table):
        from apps.courses import staff_permissions as sp
        from apps.courses import staff_tables
        from .. import staff_tables_admin as sta
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        if table not in sta.TABLES:
            return Response({'error': 'Not found', 'code': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        org_id = admin.owning_organisation_id
        if admin.is_super:
            raw = request.query_params.get('organisation')
            org_id = int(raw) if raw and raw.isdigit() else None
        rows = []
        for a, plan in sta.candidates(admin, table, org_id):
            rows.append({'id': a.pk, 'name': a.name, 'email': a.email,
                         'lead': sp.is_lead_tier(a), 'mentor_only': a.is_mentor,
                         'tables': list(staff_tables.tables(a)),
                         'consequences': plan.get('consequences', [])})
        return Response({'table': table, 'candidates': rows})
