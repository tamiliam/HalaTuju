"""The student's side of the interview: read, book, cancel, ask for other times, message."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .. import scheduling
from ..models import ScholarshipApplication
from ..serializers_admin import interview_schedule_payload


class _StudentInterviewBase(APIView):
    """Own-application interview endpoints, dark behind INTERVIEW_SCHEDULING_ENABLED."""
    permission_classes = [SupabaseIsAuthenticated]

    def _own_app(self, request, pk):
        if not scheduling.scheduling_enabled():
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app = (ScholarshipApplication.objects
               .filter(pk=pk, profile_id=request.user_id)
               .select_related('profile', 'assigned_to').first())
        if app is None:
            return None, Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return app, None

    def _error(self, e):
        return Response({'error': str(e), 'code': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StudentInterviewView(_StudentInterviewBase):
    """GET /api/v1/scholarship/applications/<id>/interview/ — the student's proposed
    interview slots + their current booking state (MYT rendered on the client)."""

    def get(self, request, pk):
        app, err = self._own_app(request, pk)
        if err:
            return err
        return Response(interview_schedule_payload(app))


class StudentInterviewBookView(_StudentInterviewBase):
    """POST /api/v1/scholarship/applications/<id>/interview/book/ {slot_id} — book
    (or reschedule to) a proposed slot. Generates the Meet link + sends confirmations."""

    def post(self, request, pk):
        app, err = self._own_app(request, pk)
        if err:
            return err
        try:
            scheduling.book_slot(app, slot_id=request.data.get('slot_id'))
        except scheduling.SchedulingError as e:
            return self._error(e)
        return Response(interview_schedule_payload(app))


class StudentInterviewCancelView(_StudentInterviewBase):
    """POST /api/v1/scholarship/applications/<id>/interview/cancel/ — cancel the
    booked interview (subject to the reschedule cutoff)."""

    def post(self, request, pk):
        app, err = self._own_app(request, pk)
        if err:
            return err
        try:
            scheduling.cancel(app, by='student', reason=request.data.get('reason', ''))
        except scheduling.SchedulingError as e:
            return self._error(e)
        return Response(interview_schedule_payload(app))


class StudentInterviewRequestAlternativesView(_StudentInterviewBase):
    """POST /api/v1/scholarship/applications/<id>/interview/request-alternatives/ {note} —
    the student says none of the proposed times work; notifies the assigned reviewer."""

    def post(self, request, pk):
        app, err = self._own_app(request, pk)
        if err:
            return err
        try:
            scheduling.request_alternatives(app, note=request.data.get('note', ''))
        except scheduling.SchedulingError as e:
            return self._error(e)
        return Response(interview_schedule_payload(app))


class StudentInterviewMessageView(_StudentInterviewBase):
    """POST /api/v1/scholarship/applications/<id>/interview/message/ {text} — the student
    messages their assigned reviewer. Deliberately NO state gate and NO cutoff: this is
    the pressure valve when reschedule/cancel are locked (e.g. running late an hour
    before the call). Rate-limited server-side; the reviewer is emailed best-effort."""

    def post(self, request, pk):
        app, err = self._own_app(request, pk)
        if err:
            return err
        try:
            scheduling.send_student_message(app, text=request.data.get('text', ''))
        except scheduling.SchedulingError as e:
            return self._error(e)
        return Response(interview_schedule_payload(app))
