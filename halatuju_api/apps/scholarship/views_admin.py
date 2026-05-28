"""
MyNadi admin API for the B40 Assistance Programme (Sprint 6a).

Reuses the existing PartnerAdmin auth (super admin sees all). Routes live under
/api/v1/admin/scholarship/ — covered by the NRIC-gate /admin/ whitelist;
PartnerAdminMixin does the real authorisation.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.views_admin import PartnerAdminMixin

from .models import ApplicantDocument, Referee, ScholarshipApplication, SponsorProfile
from .profile_engine import generate_sponsor_profile
from .serializers import ApplicantDocumentSerializer, RefereeSerializer
from .serializers_admin import (
    AdminApplicationDetailSerializer,
    AdminApplicationListSerializer,
    SponsorProfileSerializer,
)


class _AdminBase(PartnerAdminMixin, APIView):
    """Shared 403-if-not-admin guard + own-application lookup."""

    def _deny(self):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    def _get_application(self, pk):
        return ScholarshipApplication.objects.select_related('profile', 'cohort').filter(pk=pk).first()


class AdminApplicationListView(_AdminBase):
    def get(self, request):
        if not self.get_admin(request):
            return self._deny()
        qs = ScholarshipApplication.objects.select_related('profile', 'cohort').order_by('-submitted_at')
        status_f = request.GET.get('status')
        bucket_f = request.GET.get('bucket')
        if status_f:
            qs = qs.filter(status=status_f)
        if bucket_f:
            qs = qs.filter(bucket=bucket_f)
        data = AdminApplicationListSerializer(qs, many=True).data
        return Response({'applications': data, 'total_count': len(data)})


class AdminApplicationDetailView(_AdminBase):
    def get(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminApplicationDetailSerializer(app).data)

    def patch(self, request, pk):
        """Admin-editable per-application flags (currently the mentoring-candidate flag)."""
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if 'mentoring_candidate' in request.data:
            app.mentoring_candidate = bool(request.data['mentoring_candidate'])
            app.save(update_fields=['mentoring_candidate'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminVerifyAcceptView(_AdminBase):
    """
    POST .../<pk>/verify-accept/ — the human verification gate.

    The admin confirms a checklist (NRIC, name, results, document) against the
    uploaded MyKad. On accept we set ``profile.nric_verified`` (which LOCKS the
    NRIC — the student can no longer edit it), stamp who/when/what was confirmed,
    and advance the application ``shortlisted`` → ``accepted``.

    This is the single point where NRIC uniqueness is enforced (soft-NRIC): if
    another profile already has this NRIC *verified*, the clash is surfaced (409)
    for the admin to resolve rather than silently double-verifying. (Resolves TD-054.)
    """
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if app.status != 'shortlisted':
            return Response(
                {'error': 'Only a shortlisted application can be verified & accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = app.profile
        if profile is None:
            return Response({'error': 'Application has no linked profile.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Soft-NRIC uniqueness is enforced HERE (and only here). A duplicate that
        # was tolerated while unverified must be resolved before a second verify.
        from apps.courses.models import StudentProfile
        if profile.nric and StudentProfile.objects.filter(
            nric=profile.nric, nric_verified=True,
        ).exclude(pk=profile.pk).exists():
            return Response(
                {'error': 'This NRIC is already verified on another account. Resolve the duplicate first.',
                 'code': 'nric_conflict'},
                status=status.HTTP_409_CONFLICT,
            )

        if not profile.nric_verified:
            profile.nric_verified = True
            profile.save(update_fields=['nric_verified'])
        app.status = 'accepted'
        app.verified_at = timezone.now()
        app.verified_by = admin.email
        app.verify_checklist = request.data.get('checklist', {}) or {}
        app.save(update_fields=['status', 'verified_at', 'verified_by', 'verify_checklist'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminApplicationRefereeView(_AdminBase):
    """
    GET  .../<pk>/referees/  — list referees recorded for an application.
    POST .../<pk>/referees/  — coordinator records a referee at the verify-&-accept
    stage (the referee was moved out of the student flow in the Step-4 redesign).
    """
    def get(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        refs = Referee.objects.filter(application=app)
        return Response({'referees': RefereeSerializer(refs, many=True).data})

    def post(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RefereeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ref = Referee.objects.create(application=app, **serializer.validated_data)
        return Response(RefereeSerializer(ref).data, status=status.HTTP_201_CREATED)


class AdminRefereeDetailView(_AdminBase):
    """DELETE .../<pk>/referees/<ref_id>/ — remove a referee from the application."""
    def delete(self, request, pk, ref_id):
        if not self.get_admin(request):
            return self._deny()
        ref = Referee.objects.filter(pk=ref_id, application_id=pk).first()
        if ref is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        ref.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRunVisionView(_AdminBase):
    """
    POST .../<pk>/documents/<doc_id>/re-run-vision/ — re-run Vision OCR on an
    existing IC document. Soft signal only; the admin verify-&-accept stays
    the real identity gate. Returns the updated document.
    """
    def post(self, request, pk, doc_id):
        if not self.get_admin(request):
            return self._deny()
        doc = ApplicantDocument.objects.filter(pk=doc_id, application_id=pk).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if doc.doc_type != 'ic':
            return Response(
                {'error': 'Vision OCR only runs on IC documents.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .vision import run_vision_for_document
        run_vision_for_document(doc)
        return Response(ApplicantDocumentSerializer(doc).data)


class AdminGenerateProfileView(_AdminBase):
    def post(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Optional output language ('en'/'ms'); defaults to the applicant's locale.
        result = generate_sponsor_profile(app, language=request.data.get('language'))
        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        sp, _ = SponsorProfile.objects.get_or_create(application=app)
        sp.draft_markdown = result['markdown']
        sp.model_used = result.get('model_used', '')
        sp.generated_at = timezone.now()
        if sp.status == 'published':
            sp.status = 'draft'  # regenerating a published profile reverts it to draft
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminProfileEditView(_AdminBase):
    def put(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None:
            return Response({'error': 'No profile drafted yet'}, status=status.HTTP_404_NOT_FOUND)
        sp.edited_markdown = request.data.get('edited_markdown', '')
        new_status = request.data.get('status')
        if new_status in ('draft', 'approved'):
            sp.status = new_status
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)


class AdminPublishProfileView(_AdminBase):
    def post(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        sp = SponsorProfile.objects.filter(application_id=pk).first()
        if sp is None or not sp.current_markdown.strip():
            return Response({'error': 'Nothing to publish.'}, status=status.HTTP_400_BAD_REQUEST)
        sp.status = 'published'
        sp.published_at = timezone.now()
        sp.save()
        return Response(SponsorProfileSerializer(sp).data)
