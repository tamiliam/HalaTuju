"""B40 Assistance Programme API — application intake (Phase 1, Sprint 1)."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from .models import ApplicantDocument, Consent, Referee, ScholarshipApplication
from .serializers import (
    ApplicantDocumentSerializer,
    ApplicationCreateSerializer,
    ApplicationDetailsUpdateSerializer,
    ApplicationReadSerializer,
    ConsentCreateSerializer,
    ConsentSerializer,
    DocumentCreateSerializer,
    RefereeSerializer,
    SignUploadSerializer,
)
from .services import (
    CONSENT_VERSION,
    create_application,
    is_minor,
    record_consent,
    resolve_open_cohort,
    save_application_details,
    score_application,
)


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
        ).select_related('cohort', 'profile')
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
        # Score silently now (S8 delayed reveal): the verdict + decision_due_at are
        # stored, status stays 'submitted', no decision email yet. The scheduler
        # (release_due_decisions) reveals it at +2h (shortlist) / +48h (decline).
        score_application(application)
        return Response(
            ApplicationReadSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(APIView):
    """
    GET   /api/v1/scholarship/applications/<id>/  -> the caller's application
    PATCH /api/v1/scholarship/applications/<id>/  -> save STEP 2 deeper-info + funding need
    """
    permission_classes = [SupabaseIsAuthenticated]

    def _get_own(self, request, pk):
        return ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id
        ).select_related('cohort', 'profile').first()

    def get(self, request, pk):
        application = self._get_own(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ApplicationReadSerializer(application).data)

    def patch(self, request, pk):
        application = self._get_own(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Deeper info + funding need are a post-shortlist (STEP 2) step.
        if application.status != 'shortlisted':
            return Response(
                {'error': 'Details can only be added once your application is shortlisted.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ApplicationDetailsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_application_details(application, serializer.validated_data)
        return Response(ApplicationReadSerializer(application).data)


def _current_application(user_id):
    """The caller's current shortlisted application (one per cohort; latest wins)."""
    return (
        ScholarshipApplication.objects
        .filter(profile_id=user_id, status='shortlisted')
        .select_related('profile')
        .order_by('-submitted_at')
        .first()
    )


class DocumentSignUploadView(APIView):
    """POST /api/v1/scholarship/documents/sign-upload/ -> signed URL to PUT a file."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        import uuid
        from .storage import create_signed_upload_url
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SignUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc_type = serializer.validated_data['doc_type']
        path = f"{app.id}/{doc_type}/{uuid.uuid4().hex}"
        url = create_signed_upload_url(path)
        if not url:
            return Response(
                {'error': 'Document storage is temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'upload_url': url, 'storage_path': path, 'doc_type': doc_type})


class DocumentListCreateView(APIView):
    """GET list / POST record the caller's documents."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _current_application(request.user_id)
        docs = ApplicantDocument.objects.filter(application=app) if app else ApplicantDocument.objects.none()
        return Response({'documents': ApplicantDocumentSerializer(docs, many=True).data})

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = ApplicantDocument.objects.create(application=app, **serializer.validated_data)
        # S13: auto-run Vision OCR on IC uploads (soft signal — never blocks).
        if doc.doc_type == 'ic':
            from .vision import run_vision_for_document
            run_vision_for_document(doc)
        return Response(ApplicantDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    """DELETE the caller's document."""
    permission_classes = [SupabaseIsAuthenticated]

    def delete(self, request, pk):
        doc = ApplicantDocument.objects.filter(
            pk=pk, application__profile_id=request.user_id,
        ).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response({'status': 'deleted'})


class RefereeListCreateView(APIView):
    """GET list / POST add a referee for the caller's application."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _current_application(request.user_id)
        refs = Referee.objects.filter(application=app) if app else Referee.objects.none()
        return Response({'referees': RefereeSerializer(refs, many=True).data})

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = RefereeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = Referee.objects.create(application=app, **serializer.validated_data)
        return Response(RefereeSerializer(ref).data, status=status.HTTP_201_CREATED)


class ConsentView(APIView):
    """GET consent status / POST record consent (guardian gate for minors)."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _current_application(request.user_id)
        consents = Consent.objects.filter(application=app, is_active=True) if app else Consent.objects.none()
        return Response({
            'is_minor': is_minor(app.profile) if app else False,
            'consent_version': CONSENT_VERSION,
            'consents': ConsentSerializer(consents, many=True).data,
        })

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if is_minor(app.profile):
            if (d['granted_by'] != 'guardian'
                    or not d['guardian_name'].strip()
                    or not d['guardian_relationship'].strip()):
                return Response(
                    {'error': 'A guardian must consent for applicants under 18 '
                              '(name + relationship required).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        consent = record_consent(
            app,
            consent_type=d['consent_type'],
            locale=d['locale'],
            granted_by=d['granted_by'],
            guardian_name=d['guardian_name'],
            guardian_relationship=d['guardian_relationship'],
            ip=request.META.get('REMOTE_ADDR'),
        )
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)
