"""B40 Assistance Programme API — application intake (Phase 1, Sprint 1)."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from .models import ScholarshipApplication
from .serializers import ApplicationCreateSerializer, ApplicationReadSerializer
from .services import create_application, resolve_open_cohort


def _get_profile(user_id):
    return StudentProfile.objects.filter(supabase_user_id=user_id).first()


class ApplicationListCreateView(APIView):
    """
    GET  /api/v1/scholarship/applications/  -> list the caller's applications
    POST /api/v1/scholarship/applications/  -> submit a new application
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        qs = ScholarshipApplication.objects.filter(
            profile_id=request.user_id
        ).select_related('cohort')
        data = ApplicationReadSerializer(qs, many=True).data
        return Response({'total_count': len(data), 'applications': data})

    def post(self, request):
        # Applications need a real, identified student. Anonymous browsers and
        # users without a profile cannot apply. (The NRIC gate already blocks
        # non-anonymous users who lack an NRIC before we get here.)
        supabase_user = getattr(request, 'supabase_user', None) or {}
        if supabase_user.get('is_anonymous', False):
            return Response(
                {'error': 'A verified account is required to apply.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        profile = _get_profile(request.user_id)
        if profile is None:
            return Response(
                {'error': 'A HalaTuju profile is required to apply.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        cohort = resolve_open_cohort(validated.get('cohort_code', ''))
        if cohort is None:
            return Response(
                {'error': 'No open application round is currently available.'},
                status=status.HTTP_409_CONFLICT,
            )

        # One application per student per cohort.
        if ScholarshipApplication.objects.filter(
            cohort=cohort, profile=profile
        ).exists():
            return Response(
                {'error': 'You have already applied to this round.'},
                status=status.HTTP_409_CONFLICT,
            )

        lang = request.data.get('lang') or 'en'
        to_email = profile.contact_email or supabase_user.get('email') or ''
        application = create_application(
            profile=profile, cohort=cohort,
            validated_data=validated, to_email=to_email, lang=lang,
        )
        return Response(
            ApplicationReadSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(APIView):
    """GET /api/v1/scholarship/applications/<id>/ -> the caller's application."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk):
        application = ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id
        ).select_related('cohort').first()
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ApplicationReadSerializer(application).data)
