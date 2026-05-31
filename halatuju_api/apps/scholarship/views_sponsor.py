"""Phase E: sponsor-facing endpoints — self-registration + own account status.

A sponsor is an ordinary Supabase-authenticated user (signs in like a student),
registers here, and is then VETTED by an admin before getting any access to the
anonymised student pool. These endpoints govern the sponsor's OWN account only —
nothing here exposes student data. All paths are under /api/v1/sponsor/ and are
whitelisted from the NRIC gate (sponsors have no NRIC).
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from .emails import send_sponsor_interest_admin_email
from .models import Sponsor
from .serializers import SponsorSerializer


class SponsorMixin:
    """Resolve the Sponsor for the authenticated Supabase user (by UID)."""
    permission_classes = [SupabaseIsAuthenticated]

    def get_sponsor(self, request):
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return None
        return Sponsor.objects.filter(supabase_user_id=user_id).first()

    def require_approved_sponsor(self, request):
        """For pool/browse endpoints (E2+): returns the Sponsor only if approved,
        else None. Keeps the access gate in one place."""
        sponsor = self.get_sponsor(request)
        return sponsor if (sponsor and sponsor.is_approved) else None


class SponsorRegisterView(SponsorMixin, APIView):
    """POST /api/v1/sponsor/register/ — self-register as a sponsor (status=pending).
    Idempotent: if already registered, returns the existing account unchanged."""
    def post(self, request):
        supa = getattr(request, 'supabase_user', None) or {}
        user_id = getattr(request, 'user_id', None)
        # A sponsor must be a real signed-in account — reject anonymous guests.
        if not user_id or supa.get('is_anonymous', False):
            return Response({'error': 'not_signed_in'}, status=status.HTTP_400_BAD_REQUEST)

        existing = self.get_sponsor(request)
        if existing:
            return Response(SponsorSerializer(existing).data)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'name_required'}, status=status.HTTP_400_BAD_REQUEST)

        sponsor = Sponsor.objects.create(
            supabase_user_id=user_id,
            name=name,
            email=supa.get('email') or (request.data.get('email') or '').strip(),
            organisation=(request.data.get('organisation') or '').strip(),
            note=(request.data.get('note') or '').strip(),
            status='pending',
        )
        # Best-effort: alert the admin there's a new sponsor to vet.
        send_sponsor_interest_admin_email(
            name=sponsor.name, email=sponsor.email,
            organisation=sponsor.organisation, message=sponsor.note,
        )
        return Response(SponsorSerializer(sponsor).data, status=status.HTTP_201_CREATED)


class SponsorMeView(SponsorMixin, APIView):
    """GET /api/v1/sponsor/me/ — the caller's own sponsor account, or
    {registered: false} if they haven't registered yet."""
    def get(self, request):
        sponsor = self.get_sponsor(request)
        if not sponsor:
            return Response({'registered': False})
        return Response(SponsorSerializer(sponsor).data)
