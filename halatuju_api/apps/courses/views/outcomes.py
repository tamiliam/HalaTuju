"""Admission outcomes a student records."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from ..models import AdmissionOutcome, Course, Institution, StudentProfile


class OutcomeListView(APIView):
    """
    GET /api/v1/outcomes/ — List own admission outcomes.
    POST /api/v1/outcomes/ — Create a new outcome.

    Requires authentication. All queries filtered to requesting user.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        outcomes = AdmissionOutcome.objects.filter(
            student_id=request.user_id
        ).select_related('course', 'institution')

        data = []
        for o in outcomes:
            data.append({
                'id': o.id,
                'course_id': o.course_id,
                'course_name': o.course.course if o.course else o.course_id,
                'institution_id': o.institution_id,
                'institution_name': o.institution.institution_name if o.institution else None,
                'status': o.status,
                'intake_year': o.intake_year,
                'intake_session': o.intake_session,
                'notes': o.notes,
                'applied_at': o.applied_at,
                'outcome_at': o.outcome_at,
                'created_at': o.created_at.isoformat(),
                'updated_at': o.updated_at.isoformat(),
            })

        return Response({'outcomes': data, 'total_count': len(data)})

    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response(
                {'error': 'course_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            course = Course.objects.get(course_id=course_id)
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile = StudentProfile.objects.get(
            supabase_user_id=request.user_id
        )

        institution = None
        institution_id = request.data.get('institution_id')
        if institution_id:
            try:
                institution = Institution.objects.get(institution_id=institution_id)
            except Institution.DoesNotExist:
                pass

        outcome, created = AdmissionOutcome.objects.get_or_create(
            student=profile,
            course=course,
            institution=institution,
            defaults={
                'status': request.data.get('status', 'applied'),
                'intake_year': request.data.get('intake_year'),
                'intake_session': request.data.get('intake_session', ''),
                'notes': request.data.get('notes', ''),
                'applied_at': request.data.get('applied_at'),
            },
        )

        if not created:
            return Response(
                {'error': 'Outcome already exists for this course/institution'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'id': outcome.id,
            'message': 'Outcome created',
        }, status=status.HTTP_201_CREATED)


class OutcomeDetailView(APIView):
    """
    PUT /api/v1/outcomes/<id>/ — Update outcome status.
    DELETE /api/v1/outcomes/<id>/ — Delete outcome.

    Requires authentication. Only own outcomes.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def _get_outcome(self, request, outcome_id):
        try:
            return AdmissionOutcome.objects.get(
                id=outcome_id,
                student_id=request.user_id,
            )
        except AdmissionOutcome.DoesNotExist:
            return None

    def put(self, request, outcome_id):
        outcome = self._get_outcome(request, outcome_id)
        if not outcome:
            return Response(
                {'error': 'Outcome not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        for field in ['status', 'intake_year', 'intake_session', 'notes',
                       'applied_at', 'outcome_at']:
            if field in request.data:
                setattr(outcome, field, request.data[field])

        outcome.save()
        return Response({'message': 'Outcome updated'})

    def delete(self, request, outcome_id):
        outcome = self._get_outcome(request, outcome_id)
        if not outcome:
            return Response(
                {'error': 'Outcome not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        outcome.delete()
        return Response({'message': 'Outcome deleted'})
