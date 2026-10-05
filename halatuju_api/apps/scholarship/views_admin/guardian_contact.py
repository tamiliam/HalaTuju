"""POST .../applications/<pk>/guardian-contact/ — an administrator corrects the parent/guardian contact.

Request #26 (2026-10-05), owner ruling R3: a **super or org_admin** may correct the contact of the
student behind an application AT ANY TIME — including while it is frozen for the student because
bursary signing is possible — and every real change is recorded (`GuardianContactChange`, with
the admin's email and role 'admin'). While frozen, an org_admin may correct it only if THEIR
organisation holds the open offer (review F1); a super always may. Every other role is refused:
admin, reviewer, qc, finance and partner. The rules are `guardian_contact.py`'s; this view is the
gate. (Every change made through the PRODUCT is recorded; Django's staff-only `/admin/` site is the
one writer that records nothing.) `AdminGuardianCallView` ("Record call") shares the same gate.

Part of the `views_admin` package: re-exported from `views_admin/__init__.py`.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import guardian_contact, parent_call
from .base import _AdminBase


def _guardian_gate(view, request, pk):
    """The ONE gate for both guardian actions — correct and record a call. Returns
    ``(app, admin, error_response|None)``.

    The established per-application gate (org fence: cross-org 404, never 403), then narrowed to the
    R3 roles — the AdminOrgRejectView / AdminNudgeStudentView shape, because `_require_app_write`
    alone would also admit qc and an assigned admin/reviewer. Then review F1 (+ second review D):
    while frozen, only an organisation holding every open offer may act — not another organisation
    the same student also applied to."""
    app, admin, err = view._require_app_write(request, pk)
    if err:
        return None, None, err
    if not (admin.is_super or admin.role == 'org_admin'):
        return None, None, view._deny_role()
    if app.profile is None:
        return None, None, Response({'error': 'no_profile', 'code': 'no_profile'},
                                    status=status.HTTP_400_BAD_REQUEST)
    if not admin.is_super and guardian_contact.frozen_for_organisation(
            app.profile, admin.owning_organisation_id):
        return None, None, Response(
            {'error': guardian_contact.LOCKED, 'code': guardian_contact.LOCKED},
            status=status.HTTP_409_CONFLICT)
    return app, admin, None


def _refusal(e):
    return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)


class AdminGuardianContactView(_AdminBase):
    """`{name, phone}` → `{name, phone, changed}`. Roles: super + org_admin ONLY (403 otherwise).
    Organisation-fenced: another tenant's application is 404, never 403."""

    def post(self, request, pk):
        app, admin, err = _guardian_gate(self, request, pk)
        if err:
            return err
        try:
            change = guardian_contact.update_guardian_contact(
                app.profile, name=request.data.get('name'), phone=request.data.get('phone'),
                by_email=getattr(admin, 'email', '') or '', by_role='admin',
                application=app, allow_frozen=True)
        except guardian_contact.GuardianContactError as e:
            return _refusal(e)
        name, phone = guardian_contact.current_contact(app.profile)
        return Response({'name': name, 'phone': phone, 'changed': change is not None})


class AdminGuardianCallView(_AdminBase):
    """POST .../applications/<pk>/guardian-call/ — "Record call" (the owner's consent framing,
    2026-10-05). `{outcome, consent, number, parent_name, note}` → `{id, outcome, needs_call,
    name, phone}`. Same gate as the correction. `parent_number_corrected` also stores the number."""

    def post(self, request, pk):
        app, admin, err = _guardian_gate(self, request, pk)
        if err:
            return err
        d = request.data
        try:
            row = parent_call.record_call(
                app.profile, application=app, outcome=d.get('outcome'), consent=d.get('consent'),
                number=d.get('number') or '', parent_name=d.get('parent_name') or '',
                note=d.get('note') or '', by_email=getattr(admin, 'email', '') or '')
        except guardian_contact.GuardianContactError as e:
            return _refusal(e)
        name, phone = guardian_contact.current_contact(app.profile)
        return Response({'id': row.pk, 'outcome': row.call_outcome, 'name': name, 'phone': phone,
                         'needs_call': parent_call.needs_parent_call(app.profile)})
