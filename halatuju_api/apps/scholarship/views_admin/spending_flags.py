"""Flag a shop for review — the officer's notes log on one shop (request #28 follow-up,
2026-10-06). The rules are `merchant_flags.py`'s; this module is the door.

Part of the `views_admin` package: re-exported from `views_admin/__init__.py`.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .spending import _SpendingBase

# ⚠ THE PACKAGE'S name, spelled out — never `__name__` (`AuditLoggerNameTest`).
logger = logging.getLogger('apps.scholarship.views_admin')

#: Codes that describe the STATE of a flag rather than a bad request.
_CONFLICTS = ('already_flagged', 'not_flagged')


def _refuse(code):
    http = status.HTTP_409_CONFLICT if code in _CONFLICTS else status.HTTP_400_BAD_REQUEST
    return Response({'error': code, 'code': code}, status=http)


class AdminSpendingFlagView(_SpendingBase):
    """GET / POST /api/v1/admin/scholarship/spending/flag/ — one shop's flag and its notes log.

    GET `?merchant=…` → `{merchant, flagged, notes: [{kind, body, author, at}]}`, oldest first.
    POST `{merchant, action: open|note|close, note}` → the same shape after the change. The note is
    required for all three — a flag says why, and so does clearing one.

    ⚠⚠ THE FLAG IS ONE ORGANISATION'S. The scope comes from `_spending_admin` (admin + org_admin;
    `finance` refused, as on the rest of the screen), and `merchant_flags.flag_organisation` turns
    it into exactly one organisation — a super's is the gift's, and a super with no gift named is
    `programme_required`, never a guess. A GET for a shop with no flag of OURS reads exactly like an
    unflagged shop, whoever else flagged it; a POST for a shop our students never used is
    `unknown_merchant`, the same code the category correction gives.

    ⚠ The AUDIT line carries the shop, the action, the organisation and the admin — NEVER the note,
    which is free text a person wrote about a shop and has no business in a log stream.

    tenancy: org-fenced on `organisation_id` inside `merchant_flags`, the merchant check on
    `spend_report._txns(org_id, programme)`. Classified in test_org_fence.py.
    """

    def _org(self, request):
        """`(admin, org_id, programme, error)` — the spending door, then the ONE organisation."""
        from .. import merchant_flags

        admin, scope, programme, err = self._spending_admin(request)
        if err:
            return None, None, None, err
        org_id, code = merchant_flags.flag_organisation(scope, programme)
        if code:
            return None, None, None, _refuse(code)
        return admin, org_id, programme, None

    def get(self, request):
        from .. import merchant_flags

        _admin, org_id, _programme, err = self._org(request)
        if err:
            return err
        merchant = request.query_params.get('merchant') or ''
        if not merchant.strip():
            return _refuse('merchant_required')
        return Response(merchant_flags.flag_log(org_id, merchant))

    def post(self, request):
        from .. import merchant_flags, spend_report

        admin, org_id, programme, err = self._org(request)
        if err:
            return err
        action = request.data.get('action') or ''
        log, code = merchant_flags.change_flag(
            org_id, request.data.get('merchant') or '', action, request.data.get('note'),
            admin.email, spend_report._txns(org_id, programme))
        if code:
            return _refuse(code)
        logger.info('AUDIT spend_flag_%s merchant=%r org=%s by=%s',
                    action, log['merchant'], org_id, admin.email or '')
        return Response(log)
