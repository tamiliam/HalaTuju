"""POST .../applications/<pk>/guardian-contact/ — an administrator corrects the parent/guardian contact.

Request #26 (2026-10-05), owner ruling R3: a **super or org_admin** may correct the contact of the
student behind an application AT ANY TIME — including while it is frozen for the student because
bursary signing is possible — and every real change is recorded (`GuardianContactChange`, with
the admin's email and role 'admin'). While frozen, an org_admin may correct it only if THEIR
organisation holds the open offer (review F1); a super always may. Every other role is refused:
admin, reviewer, qc, finance and partner. The rules are `guardian_contact.py`'s; this view is the
gate. (Every change made through the PRODUCT is recorded; Django's staff-only `/admin/` site is the
one writer that records nothing.)

Part of the `views_admin` package: re-exported from `views_admin/__init__.py`.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import guardian_contact
from .base import _AdminBase


class AdminGuardianContactView(_AdminBase):
    """`{name, phone}` → `{name, phone, changed}`. Roles: super + org_admin ONLY (403 otherwise).
    Organisation-fenced: another tenant's application is 404, never 403."""

    def post(self, request, pk):
        # The established per-application gate (org fence: cross-org 404, never 403), then
        # narrowed to the R3 roles — the same shape as AdminOrgRejectView / AdminNudgeStudentView,
        # because `_require_app_write` alone would also admit qc and an assigned admin/reviewer.
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        if not (admin.is_super or admin.role == 'org_admin'):
            return self._deny_role()
        if app.profile is None:
            return Response({'error': 'no_profile', 'code': 'no_profile'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Review F1: while frozen, only the organisation holding the OPEN OFFER may move the number
        # its signing PIN goes to — not another organisation the same student also applied to.
        if not admin.is_super and guardian_contact.frozen_for_organisation(
                app.profile, admin.owning_organisation_id):
            return Response({'error': guardian_contact.LOCKED, 'code': guardian_contact.LOCKED},
                            status=status.HTTP_409_CONFLICT)
        try:
            change = guardian_contact.update_guardian_contact(
                app.profile, name=request.data.get('name'), phone=request.data.get('phone'),
                by_email=getattr(admin, 'email', '') or '', by_role='admin',
                application=app, allow_frozen=True)
        except guardian_contact.GuardianContactError as e:
            return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)
        name, phone = guardian_contact.current_contact(app.profile)
        return Response({'name': name, 'phone': phone, 'changed': change is not None})
