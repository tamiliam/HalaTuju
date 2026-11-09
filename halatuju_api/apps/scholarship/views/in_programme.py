"""A student already in a programme: semester results, promotional consent, graduation message."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .. import in_programme as in_programme_service, request_ip
from ..models import ScholarshipApplication
from ..serializers import GraduationMessageSerializer, SemesterResultSerializer
from ..services import is_minor


class _OwnInProgrammeView(APIView):
    """Shared base for the F9a in-programme student endpoints: resolve the caller's
    OWN application (by JWT ``user_id``) and translate ``InProgrammeError`` to a 400
    with a ``code`` the FE can map. The service layer enforces ``status='sponsored'``
    (a student only has an in-programme lifecycle once their award is accepted)."""
    permission_classes = [SupabaseIsAuthenticated]

    def _own_application(self, request, pk):
        return ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id,
        ).select_related('profile').first()


class SemesterResultView(_OwnInProgrammeView):
    """GET/POST /api/v1/scholarship/applications/<id>/semester-results/ — the student's
    in-programme latest-semester results. GET lists their own (latest first). POST
    records one (`semester`, `cgpa` 0.00–4.00, `graduated`, optional `results_slip`).
    The uploaded slip stays myNADI-only; only the derived progress band crosses to a
    sponsor. 400 `not_in_programme` until the award is accepted; 400 `bad_cgpa`."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from ..results_review import results_for_file
        return Response({'results': SemesterResultSerializer(results_for_file(application), many=True).data})

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        # S4a: the slip is the file she just PUT (`slip`: storage path + metadata), recorded by the
        # service so the pre-award document pipeline never runs on it (`results_review.record_slip`).
        try:
            result = in_programme_service.record_semester_result(
                application,
                semester=data.get('semester', ''),
                cgpa=data.get('cgpa'),
                graduated=bool(data.get('graduated', False)),
                note=data.get('note', ''), slip_upload=data.get('slip'),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(SemesterResultSerializer(result).data, status=status.HTTP_201_CREATED)


class PromotionalConsentView(_OwnInProgrammeView):
    """GET/POST/DELETE /api/v1/scholarship/applications/<id>/promotional-consent/ —
    the SEPARATE, 18+-only promotional_use consent (F9a). GET reports whether it is
    active. POST grants it (hard 400 `minor_not_allowed` if the NRIC says under 18 —
    there is no guardian path by design). DELETE withdraws it (PDPA: revocable)."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'granted': in_programme_service.has_promotional_consent(application),
            'is_minor': is_minor(application.profile),
        })

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            in_programme_service.grant_promotional_consent(
                application, locale=application.locale,
                ip=request_ip.signer_ip(request),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'granted': True})

    def delete(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        in_programme_service.withdraw_promotional_consent(application)
        return Response({'granted': False})


class GraduationMessageView(_OwnInProgrammeView):
    """GET/POST /api/v1/scholarship/applications/<id>/graduation-message/ — the
    student's graduation thank-you (F9a). GET lists their submissions + status. POST
    submits ``text``: the structural identifier scan runs immediately — a message
    that leaks the student's own name/school/city/NRIC/phone/email comes back
    ``blocked`` with the offending ``scan_result`` fields (edit + resubmit); a clean
    one is ``pending`` myNADI approval. Never a direct channel to the sponsor."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        msgs = application.graduation_messages.all()
        return Response({'messages': GraduationMessageSerializer(msgs, many=True).data})

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            message = in_programme_service.submit_graduation_message(
                application, raw_text=data.get('text', ''),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(GraduationMessageSerializer(message).data,
                        status=status.HTTP_201_CREATED)
