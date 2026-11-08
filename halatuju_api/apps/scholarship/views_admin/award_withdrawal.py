"""The award withdrawal routes — A1.13b MAKER and CHECKER (owner rulings 2026-11-08, TD-198).

    POST applications/<pk>/withdrawal-request/ {explanation}   the maker asks
    POST withdrawal-requests/<pk>/approve/ {note?}             a DIFFERENT person approves (the withdrawal runs)
    POST withdrawal-requests/<pk>/refuse/ {reason}             ... or refuses
    POST withdrawal-requests/<pk>/cancel/                      the maker takes it back

Who may act is `award_withdrawal_chain` (the two permission keys; never a super — a super is answered 403
``wrong_role`` at the door). These views only gate, fence and answer: every refusal is
``{'error': code, 'code': code}`` — 400 for a bad text, 403 for the wrong seat, 409 for a case or request
that is not in a state to act on, 404 for a request outside the caller's organisation.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import award_withdrawal_chain as chain
from .applications import _detail_payload
from .base import _AdminBase

_STATUS = {
    'explanation_required': 400, 'explanation_too_long': 400, 'reason_required': 400,
    'reason_too_long': 400, 'note_too_long': 400,
    'wrong_role': 403, 'same_person': 403,
    'not_awarded': 409, 'has_payments': 409, 'already_pending': 409, 'not_pending': 409,
    'stale': 409, 'no_checker': 409,
    'not_found': 404,
}


def _refused(code):
    return Response({'error': code, 'code': code}, status=_STATUS.get(code, status.HTTP_400_BAD_REQUEST))


class _WithdrawalBase(_AdminBase):
    def _door(self, request):
        """(admin, None) or (None, refusal). A super reads requests but never acts on one."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if admin.is_super:
            return None, _refused('wrong_role')
        return admin, None

    def _answer(self, request, application, admin):
        """The refreshed case detail when the caller may read the case, else the request alone."""
        app, err = self._scoped_application(request, application.pk)
        if err is None:
            return Response(_detail_payload(app, admin))
        return Response({'id': application.pk, 'status': application.status,
                         'withdrawal_request': chain.payload_for(application, admin)})

    def _row(self, admin, pk):
        """The request IFF it belongs to the caller's organisation (else None: a 404, never a 403)."""
        from ..models import AwardWithdrawalRequest
        row = AwardWithdrawalRequest.objects.select_related('application').filter(pk=pk).first()
        if row is None or row.organisation_id is None or row.organisation_id != admin.owning_organisation_id:
            return None
        return row

    def _decide(self, request, pk, act):
        admin, err = self._door(request)
        if err:
            return err
        row = self._row(admin, pk)
        if row is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            act(admin, row)
        except chain.AwardWithdrawalError as e:
            return _refused(e.code)
        row.application.refresh_from_db()
        return self._answer(request, row.application, admin)


class AdminWithdrawalRequestView(_WithdrawalBase):
    """The MAKER asks for an awarded case's award to be withdrawn, with a required explanation.
    tenancy: `_scoped_application` (the org fence and the B40 scope), then the chain's same-organisation seat."""
    def post(self, request, pk):
        admin, err = self._door(request)
        if err:
            return err
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        try:
            chain.request_withdrawal(app, by_admin=admin, explanation=request.data.get('explanation'))
        except chain.AwardWithdrawalError as e:
            return _refused(e.code)
        app.refresh_from_db()
        return self._answer(request, app, admin)


class AdminWithdrawalApproveView(_WithdrawalBase):
    """A CHECKER (never the maker) approves a pending request: the withdrawal runs.
    tenancy: the request's own organisation must be the caller's (else 404), then the chain's seat check."""
    def post(self, request, pk):
        return self._decide(request, pk, lambda admin, row: chain.approve_withdrawal(
            row.pk, by_admin=admin, note=request.data.get('note') or ''))


class AdminWithdrawalRefuseView(_WithdrawalBase):
    """A CHECKER (never the maker) refuses a pending request, with a required reason; the award stands.
    tenancy: the request's own organisation must be the caller's (else 404), then the chain's seat check."""
    def post(self, request, pk):
        return self._decide(request, pk, lambda admin, row: chain.refuse_withdrawal(
            row.pk, by_admin=admin, reason=request.data.get('reason')))


class AdminWithdrawalCancelView(_WithdrawalBase):
    """The MAKER takes back their own pending request; the award stands.
    tenancy: the request's own organisation must be the caller's (else 404), then the chain's maker check."""
    def post(self, request, pk):
        return self._decide(request, pk, lambda admin, row: chain.cancel_withdrawal(row.pk, by_admin=admin))
