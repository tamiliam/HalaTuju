"""The saved courses of a student."""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from ..models import Course, SavedCourse, StpmCourse, StudentProfile
from ..serializers import CourseSerializer


class SavedCoursesView(APIView):
    """
    GET/POST /api/v1/saved-courses/

    Requires authentication. Supports both SPM and STPM courses.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        saved = SavedCourse.objects.filter(
            student_id=request.user_id
        ).select_related('course', 'stpm_course')

        # Optional qualification filter
        qualification = getattr(request, 'query_params', request.GET).get('qualification', '').upper()
        if qualification == 'SPM':
            saved = saved.filter(course__isnull=False)
        elif qualification == 'STPM':
            saved = saved.filter(stpm_course__isnull=False)

        data = []
        for sc in saved:
            if sc.course_id:
                course_data = CourseSerializer(sc.course).data
                # Get primary institution name from offerings
                offering = sc.course.offerings.select_related('institution').first()
                course_data['institution_name'] = (
                    offering.institution.institution_name if offering and offering.institution else ''
                )
            else:
                stpm = sc.stpm_course
                course_data = {
                    'course_id': stpm.course_id,
                    'course': stpm.course_name,
                    'level': 'Ijazah Sarjana Muda',
                    'field': stpm.field or '',
                    'institution_name': stpm.university or '',
                }
            course_data['course_type'] = sc.course_type
            course_data['interest_status'] = sc.interest_status
            data.append(course_data)
        return Response({'saved_courses': data})

    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response({'error': 'course_id required'}, status=status.HTTP_400_BAD_REQUEST)

        profile = StudentProfile.objects.get(
            supabase_user_id=request.user_id
        )

        # Try SPM table first, then STPM — no prefix-guessing needed
        try:
            course = Course.objects.get(course_id=course_id)
            SavedCourse.objects.get_or_create(
                student=profile, course=course,
            )
            return Response({'message': 'Course saved'}, status=status.HTTP_201_CREATED)
        except Course.DoesNotExist:
            pass

        try:
            stpm_course = StpmCourse.objects.get(course_id=course_id)
            SavedCourse.objects.get_or_create(
                student=profile, stpm_course=stpm_course,
            )
            return Response({'message': 'Course saved'}, status=status.HTTP_201_CREATED)
        except StpmCourse.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)


class SavedCourseDetailView(APIView):
    """DELETE/PATCH /api/v1/saved-courses/<course_id>/"""
    permission_classes = [SupabaseIsAuthenticated]

    def _find_saved(self, user_id, course_id):
        """Look up a saved course by either FK."""
        return SavedCourse.objects.filter(
            student_id=user_id,
        ).filter(
            Q(course_id=course_id) | Q(stpm_course_id=course_id)
        )

    def delete(self, request, course_id):
        deleted, _ = self._find_saved(request.user_id, course_id).delete()

        if deleted:
            return Response({'message': 'Course removed'})
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, course_id):
        qs = self._find_saved(request.user_id, course_id)
        sc = qs.first()
        if not sc:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        status_value = request.data.get('interest_status')
        valid = ['interested', 'planning', 'applied', 'got_offer']
        if status_value and status_value in valid:
            sc.interest_status = status_value
            sc.save(update_fields=['interest_status'])
            return Response({'message': 'Status updated'})
        return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
