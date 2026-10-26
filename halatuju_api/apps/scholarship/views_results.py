"""The two student actions behind the higher-results card's SPM-slip note (third results route
S3b, owner ruling D13, 2026-10-26). The rules live in `results_route`; these views only find the
caller's application and document and refuse what the note never offers.

⚠ BOTH ARE REFUSED ONCE THE APPLICATION IS SUBMITTED (409 `application_submitted`; adversarial
review fixes 1+2): after the Step-4 Submit they would wipe results a decision or an award rests on,
raise a ticket the frozen requirement can never close, or demote a slip the reviewer has read. The
reviewer's own request route is the way then.

* POST /api/v1/scholarship/results/refile-to-spm/  {document_id}
    "Move it to SPM results slip" — the higher-results upload reads as an SPM slip, so it is
    re-filed into the SPM slot (the file kept; its read cleared so the live service reads it as an SPM slip). Refused unless it DOES read as one.
* POST /api/v1/scholarship/results/refile-to-higher/  {document_id}   (S4, owner ruling D15)
    "Move it to STPM results" — the mirror: a document in the SPM card that reads as a higher
    result (`wrong_slip.higher_kind`) is re-filed into the higher-results card with that kind (the
    file kept; its read cleared). Refused unless it DOES read as one, and unless the higher card is
    shown for this applicant (D12: `wrong_slip.move_offered`).
* POST /api/v1/scholarship/results/spm-only/       {document_id?}
    "Continue with SPM results only" — the higher results entered are removed (the explicit clear
    the profile sync's no-demote guard never allows), SPM untouched. When a `document_id` is given
    and that upload reads as an SPM slip, it is re-filed too, so the slip the student has is kept
    where it belongs. Refused when no higher results are held.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from . import results_route
from .models import ApplicantDocument


def _refuse_after_submit(app):
    if results_route.submitted(app):
        return Response({'error': 'application_submitted', 'code': 'application_submitted'},
                        status=status.HTTP_409_CONFLICT)
    return None


def _higher_doc(app, doc_id):
    if not doc_id:
        return None
    return ApplicantDocument.objects.filter(
        pk=doc_id, application=app, doc_type='higher_results', superseded_at__isnull=True).first()


def _reads_as_spm(doc):
    from .higher_results import student_higher_check
    return student_higher_check(doc)['kind_status'] == 'spm'


class RefileToSpmView(APIView):
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from .views import _current_application
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        refused = _refuse_after_submit(app)
        if refused:
            return refused
        doc = _higher_doc(app, request.data.get('document_id'))
        if doc is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if not _reads_as_spm(doc):
            return Response({'error': 'not_an_spm_slip', 'code': 'not_an_spm_slip'},
                            status=status.HTTP_400_BAD_REQUEST)
        doc = results_route.refile_to_spm(app, doc)
        return Response({'status': 'refiled', 'document_id': doc.id, 'doc_type': doc.doc_type})


class SpmOnlyView(APIView):
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from apps.courses.exam_questions import is_tertiary
        from .views import _current_application
        app = _current_application(request.user_id)
        if app is None or app.profile is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        refused = _refuse_after_submit(app)
        if refused:
            return refused
        if not is_tertiary(results_route.held(app)):
            return Response({'error': 'nothing_to_clear', 'code': 'nothing_to_clear'},
                            status=status.HTTP_400_BAD_REQUEST)
        doc = _higher_doc(app, request.data.get('document_id'))
        refiled = doc is not None and _reads_as_spm(doc)
        if refiled:
            results_route.refile_to_spm(app, doc)
        note = results_route.clear_to_spm(app, by='student')
        return Response({'status': 'cleared', 'cleared': note['cleared'], 'refiled': refiled})


class RefileToHigherView(APIView):
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from .views import _current_application
        from .wrong_slip import higher_kind, move_offered
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        refused = _refuse_after_submit(app)
        if refused:
            return refused
        doc_id = request.data.get('document_id')
        doc = ApplicantDocument.objects.filter(
            pk=doc_id, application=app, doc_type='results_slip', superseded_at__isnull=True,
        ).first() if doc_id else None
        if doc is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        kind = higher_kind(doc)
        if not kind:
            return Response({'error': 'not_a_higher_result', 'code': 'not_a_higher_result'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not move_offered(app):
            return Response({'error': 'higher_card_not_shown', 'code': 'higher_card_not_shown'},
                            status=status.HTTP_400_BAD_REQUEST)
        doc = results_route.refile_to_higher(app, doc, kind)
        return Response({'status': 'refiled', 'document_id': doc.id, 'doc_type': doc.doc_type,
                         'results_kind': doc.results_kind})
