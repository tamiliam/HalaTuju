"""``GET /api/v1/scholarship/apply-gate/?programme=<code>`` — may I start an application here?

The apply page asks this BEFORE drawing the form, and the answer is the one the submit will give
(``services/apply_gate.py`` — the owner's one-application-per-organisation rule, TD-337). Until
2026-10-05 the web kept its own, stricter copy of the rule (``mustLeaveApplyPage``), which the
server did not share; the web now keeps none and obeys this.

Answers ``{allowed, reason, application_id}``; ``reason`` is '' / ``application_in_progress`` /
``already_applied`` and ``application_id`` is the caller's OWN blocking application (or null).
What each kind of visit is answered is ``apply_gate.verdict_for_visit``'s docstring; this view is
only the door. In short: a student with an application in play (in ANY organisation, until roadmap
M2) is answered ``application_in_progress`` on EVERY visit — known, unknown or closed code, bare,
nothing open — so an applicant on her closed gift's link is sent to her application; a student with
nothing in play is answered ``allowed`` on an unknown and a closed code alike, and
``already_applied`` only for an open round she already applied to. Either way the answer does not
tell the caller whether a code exists or whose it is.

A separate module, not ``views.py``: that file is on the oversize ledger and may not grow. A new
view rather than a field on the application list: the list read has query budgets of its own
(``code-standards.json``), and the question needs the round, which the list does not know.
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from .services import apply_gate


class ApplyGateView(APIView):
    """GET — the signed-in student's own apply verdict. Never another student's data."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        profile = StudentProfile.objects.filter(supabase_user_id=request.user_id).first()
        verdict = apply_gate.verdict_for_visit(profile, request.query_params.get('programme') or '')
        return Response({
            'allowed': verdict.allowed,
            'reason': verdict.reason,
            'application_id': verdict.application.id if verdict.application is not None else None,
        })
