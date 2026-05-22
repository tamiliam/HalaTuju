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

from .models import ScholarshipApplication, SponsorProfile
from .profile_engine import generate_sponsor_profile
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


class AdminGenerateProfileView(_AdminBase):
    def post(self, request, pk):
        if not self.get_admin(request):
            return self._deny()
        app = self._get_application(pk)
        if app is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        result = generate_sponsor_profile(app)
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
