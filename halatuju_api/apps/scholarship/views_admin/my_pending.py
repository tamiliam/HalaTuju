"""The Overview's pending cards (Team tables T5c P5b S1, owner rulings 2026-11-05 in `docs/decisions.md`).

`GET admin/scholarship/my-pending/` -> `{'cards': [{'key', 'count', optional 'due_soon',
optional 'oldest_days'}]}`. The cards are `my_pending.pending_for`; a card the caller may not see is
ABSENT, never zero. The programme cards below them are `my-programmes`; the two share one door
(`my_programmes.lands`), so whoever opens the page reads both.

tenancy: org-fenced inside `my_pending` (super: the pooled platform; else the caller's own organisation).
Classified in test_org_fence.py.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import my_pending
from .base import _AdminBase
from .my_programmes import lands


class AdminMyPendingView(_AdminBase):
    """GET /api/v1/admin/scholarship/my-pending/ — see the module docstring.

    tenancy: org-fenced in `my_pending.pending_for`. Classified in test_org_fence.py."""

    #: A MENTOR login reads its own cards here (`test_mentor_denied_everywhere.ALLOWED`); a source user never.
    mentor_methods = ('get',)

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        scope = self._b40_scope(admin)
        if not lands(admin, scope):
            return self._deny_role()
        return Response({'cards': my_pending.pending_for(admin, b40_scope=scope)}, status=status.HTTP_200_OK)
