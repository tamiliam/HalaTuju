"""``GET /api/v1/scholarship/bursary/summary/`` — the student's own "My Bursary" hub (maintenance S3).

The signed-in student's OWN file: the newest of her applications that has one
(``maintenance_scope.has_file_q``). 404 when she has none — the same answer whether she never
applied, was never funded, or her pre-award case was closed (TD-352).

⚠ WHAT IT NEVER SERVES: no actor email, no activity row, no officer note, no sub-state word. The only
maintenance signal is ``support_paused`` (``maintenance.is_on_hold``) — probation and ready-to-close
are staff flags (S1 review L5). No standing is judged (Sprint 4). Money is HER money: what the
award is, what has reached her wallet, what remains (``payments._remaining`` — the funding summary's
own rule) and the last payment.

A separate module, not ``views.py``: that file is on the oversize ledger and may not grow.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from . import card_display
from .in_programme import can_record_results
from .maintenance import is_on_hold
from .maintenance_scope import has_file_q, is_in_maintenance
from .models import Disbursement, ScholarshipApplication, SemesterResult
from .results_expectations import next_due
from .scholars import _two


def summary_payload(app):
    """The hub's payload for ONE application the caller owns and that has a file."""
    from .payments import _remaining, paid_to_date
    last = (Disbursement.objects.filter(application=app, status__in=Disbursement.PAID)
            .order_by('-released_at', '-id').values('amount', 'released_at').first())
    latest = (SemesterResult.objects.filter(application=app).order_by('-created_at', '-id')
              .values('semester', 'cgpa', 'created_at', 'review_status').first())
    programme = getattr(app, 'programme', None)
    return {
        'application_id': app.id,
        'name': getattr(app.profile, 'name', '') or '',
        'gift': programme.name_en if programme is not None else '',
        # Her gift in each language, falling back to English (S3 review L3); the page picks hers.
        'gift_names': ({lang: (getattr(programme, f'name_{lang}', '') or programme.name_en)
                        for lang in ('en', 'ms', 'ta')} if programme is not None else {}),
        'course': card_display.resolve_course(app),
        'institution': card_display.resolve_institution(app),
        'status': app.status,
        'closure_reason': app.closure_reason,
        'in_maintenance': is_in_maintenance(app),
        'can_record_results': can_record_results(app),
        'support_paused': is_on_hold(app),
        'funds': {
            'award_amount': _two(app.award_amount),
            'received': _two(paid_to_date(app)),
            'remaining': _two(_remaining(app)),
            'last_payment': ({'amount': _two(last['amount']), 'at': last['released_at']}
                             if last else None),
        },
        # Her OWN latest result whatever its review — she sees it is awaiting review or queried.
        'latest_result': ({'semester': latest['semester'], 'cgpa': _two(latest['cgpa']),
                           'at': latest['created_at'], 'review_status': latest['review_status']}
                          if latest else None),
        # S4b: when her next result is due (her earliest open term; a past date means it is late).
        'next_result_due': next_due(app) if is_in_maintenance(app) else None,
    }


class BursarySummaryView(APIView):
    """GET — the signed-in student's own hub. Never another student's data."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = (ScholarshipApplication.objects.select_related('profile', 'programme')
               .filter(has_file_q(), profile_id=request.user_id).order_by('-id').first())
        if app is None:
            return Response({'error': 'Not found', 'code': 'no_file'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(summary_payload(app))
