"""POST .../applications/<pk>/withdraw-award/ {reason} — A1.13 (TD-198 / CO-09, owner ruling D3).

SUPER-ONLY (403 for everyone else). The service (`award_withdrawal.withdraw_award`) does the work
under the application row lock; this view only gates, scopes and answers.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import award_withdrawal as service
from .applications import _detail_payload
from .base import _AdminBase

#: What each refusal answers (the web shows its own translated copy of each).
_REFUSALS = {
    'reason_required': (status.HTTP_400_BAD_REQUEST, 'Write the reason for withdrawing this award.'),
    'reason_too_long': (status.HTTP_400_BAD_REQUEST, 'The reason is too long.'),
    'not_awarded': (status.HTTP_409_CONFLICT, 'Only an awarded case can have its award withdrawn.'),
    'has_payments': (status.HTTP_409_CONFLICT,
                     'Money has already been paid on this case, so its award cannot be withdrawn '
                     'here. Ask the platform owner.'),
}


class AdminWithdrawAwardView(_AdminBase):
    """A super withdraws an awarded case's award, with a required reason (internal, never shown to
    the student). Answers the refreshed case detail."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        try:
            service.withdraw_award(app, by_admin=admin, reason=request.data.get('reason'))
        except service.AwardWithdrawalError as e:
            code, message = _REFUSALS[e.code]
            return Response({'error': message, 'code': e.code}, status=code)
        return Response(_detail_payload(app, admin))
