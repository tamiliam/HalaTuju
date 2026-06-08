"""Phase E: sponsor-facing endpoints — self-registration + own account status.

A sponsor is an ordinary Supabase-authenticated user (signs in like a student),
registers here, and is then VETTED by an admin before getting any access to the
anonymised student pool. These endpoints govern the sponsor's OWN account only —
nothing here exposes student data. All paths are under /api/v1/sponsor/ and are
whitelisted from the NRIC gate (sponsors have no NRIC).
"""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from . import pool
from . import sponsorship as sponsorship_service
from .emails import send_sponsor_interest_admin_email
from .models import Donation, ScholarshipApplication, Sponsor, Sponsorship
from .serializers import (
    SponsorPoolCardSerializer, SponsorPoolDetailSerializer,
    SponsorSerializer, SponsorSponsorshipSerializer,
)

# PDPA consent text version a sponsor accepts at registration. Bump when the
# sponsor consent wording changes (separate from the student CONSENT_VERSION).
SPONSOR_CONSENT_VERSION = '2026-sponsor-draft-1'


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
    """POST /api/v1/sponsor/register/ — self-register / complete a sponsor account.

    Requires the full registration details: name, phone, source ("how did you find
    us"), and PDPA consent (the password/email are handled by Supabase Auth on the
    client; the JWT proves the account). A Google sponsor lands without phone/source/
    consent and completes them here — so this also UPDATES an existing *incomplete*
    sponsor. An already-complete sponsor is an idempotent no-op (returns unchanged)."""
    def post(self, request):
        supa = getattr(request, 'supabase_user', None) or {}
        user_id = getattr(request, 'user_id', None)
        # A sponsor must be a real signed-in account — reject anonymous guests.
        if not user_id or supa.get('is_anonymous', False):
            return Response({'error': 'not_signed_in'}, status=status.HTTP_400_BAD_REQUEST)

        existing = self.get_sponsor(request)
        # Already fully registered → idempotent no-op (don't re-validate / re-stamp).
        if existing and existing.phone and existing.source and existing.consent_at:
            return Response(SponsorSerializer(existing).data)

        data = request.data
        name = (data.get('name') or (existing.name if existing else '') or '').strip()
        phone = (data.get('phone') or '').strip()
        source = (data.get('source') or '').strip()
        consent = bool(data.get('consent'))

        missing = [f for f, v in (('name', name), ('phone', phone), ('source', source)) if not v]
        if missing:
            return Response({'error': 'missing_fields', 'fields': missing},
                            status=status.HTTP_400_BAD_REQUEST)
        if not consent:
            return Response({'error': 'consent_required'}, status=status.HTTP_400_BAD_REQUEST)

        email = supa.get('email') or (data.get('email') or (existing.email if existing else '') or '').strip()
        organisation = (data.get('organisation') or (existing.organisation if existing else '') or '').strip()
        note = (data.get('note') or (existing.note if existing else '') or '').strip()

        if existing:
            # Complete-details path (e.g. after Google sign-in). Vetting state untouched.
            existing.name = name
            existing.email = existing.email or email
            existing.phone = phone
            existing.source = source
            existing.organisation = organisation
            existing.note = note
            existing.consent_at = timezone.now()
            existing.consent_version = SPONSOR_CONSENT_VERSION
            existing.save()
            return Response(SponsorSerializer(existing).data)

        sponsor = Sponsor.objects.create(
            supabase_user_id=user_id,
            name=name,
            email=email,
            phone=phone,
            source=source,
            organisation=organisation,
            note=note,
            consent_at=timezone.now(),
            consent_version=SPONSOR_CONSENT_VERSION,
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


class SponsorPoolCountView(APIView):
    """GET /api/v1/sponsor/pool/count/ — PUBLIC count of students currently waiting
    in the anonymised pool, for the F1 sponsor-landing live counter.

    Count ONLY — exposes no student data (not even an id). Behind SPONSOR_POOL_ENABLED:
    while the flag is off (lawyer-gated) it returns {count: 0, enabled: False} so the
    landing hides the counter and the whole sponsor programme stays dark until go-live.
    No auth (a public marketing page calls it); the NRIC gate skips anonymous callers."""
    permission_classes = [AllowAny]

    def get(self, request):
        if not getattr(settings, 'SPONSOR_POOL_ENABLED', False):
            return Response({'count': 0, 'enabled': False})
        count = pool.eligible_pool_queryset(ScholarshipApplication).count()
        return Response({'count': count, 'enabled': True})


class _PoolBase(SponsorMixin, APIView):
    """Shared gate for the Phase E2 anonymised pool: the whole pool is behind the
    SPONSOR_POOL_ENABLED flag (off until lawyer sign-off), and only APPROVED
    sponsors may browse. Returns (sponsor, error_response); error is None when OK."""
    def _gate(self, request):
        if not getattr(settings, 'SPONSOR_POOL_ENABLED', False):
            # Don't reveal the feature exists while it's gated off.
            return None, Response({'error': 'pool_not_available'}, status=status.HTTP_404_NOT_FOUND)
        sponsor = self.require_approved_sponsor(request)
        if not sponsor:
            return None, Response({'error': 'not_approved'}, status=status.HTTP_403_FORBIDDEN)
        return sponsor, None


class SponsorPoolListView(_PoolBase):
    """GET /api/v1/sponsor/pool/ — the anonymised student pool for an approved
    sponsor. Each card is an allowlist of non-identifying fields only."""
    def get(self, request):
        _, err = self._gate(request)
        if err:
            return err
        qs = pool.eligible_pool_queryset(ScholarshipApplication)
        return Response({'students': SponsorPoolCardSerializer(qs, many=True).data})


class SponsorPoolDetailView(_PoolBase):
    """GET /api/v1/sponsor/pool/<pk>/ — one anonymised student (card + the
    generated anonymous blurb). 404 unless the student is currently pool-eligible."""
    def get(self, request, pk):
        _, err = self._gate(request)
        if err:
            return err
        app = pool.eligible_pool_queryset(ScholarshipApplication).filter(id=pk).first()
        if not app:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SponsorPoolDetailSerializer(app).data)


class SponsorWalletView(_PoolBase):
    """GET /api/v1/sponsor/wallet/ — directed-giving balance + donations + the
    sponsor's holding allocations."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        donations = [
            {'amount': str(d.amount), 'reference': d.reference, 'created_at': d.created_at}
            for d in sponsor.donations.all()
        ]
        holding = sponsor.sponsorships.filter(status__in=Sponsorship.HOLDING).select_related(
            'application', 'application__profile', 'application__sponsor_profile')
        return Response({
            'balance': str(sponsorship_service.sponsor_balance(sponsor)),
            'donations': donations,
            'sponsorships': SponsorSponsorshipSerializer(holding, many=True).data,
        })


class SponsorDonateView(_PoolBase):
    """POST /api/v1/sponsor/wallet/donate/ {amount} — **MOCK** donation (dev/dummy
    only; the real toyyibPay integration is a later, gated step). A donation is
    final and credits the sponsor's balance."""
    def post(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        try:
            amount = Decimal(str(request.data.get('amount')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        Donation.objects.create(sponsor=sponsor, amount=amount, reference='mock')
        return Response({'balance': str(sponsorship_service.sponsor_balance(sponsor))},
                        status=status.HTTP_201_CREATED)


class SponsorFundView(_PoolBase):
    """POST /api/v1/sponsor/pool/<pk>/fund/ — fund a student IN FULL for their
    admin-set award amount → an 'offered' award (1:1, full-or-nothing for now)."""
    def post(self, request, pk):
        sponsor, err = self._gate(request)
        if err:
            return err
        app = ScholarshipApplication.objects.filter(id=pk).first()
        if app is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            sponsorship = sponsorship_service.fund_student(sponsor, app)
        except sponsorship_service.SponsorshipError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SponsorSponsorshipSerializer(sponsorship).data, status=status.HTTP_201_CREATED)


class SponsorSponsorshipsView(_PoolBase):
    """GET /api/v1/sponsor/sponsorships/ — the sponsor's holding allocations
    (offered/active), each as the anonymised student card + money/status."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        qs = sponsor.sponsorships.filter(status__in=Sponsorship.HOLDING).select_related(
            'application', 'application__profile', 'application__sponsor_profile')
        return Response({'sponsorships': SponsorSponsorshipSerializer(qs, many=True).data})


class SponsorCancelOfferView(_PoolBase):
    """POST /api/v1/sponsor/sponsorships/<pk>/cancel/ — withdraw an OFFERED award
    before the student accepts; the amount returns to the sponsor's balance."""
    def post(self, request, pk):
        sponsor, err = self._gate(request)
        if err:
            return err
        s = sponsor.sponsorships.filter(id=pk, status='offered').first()
        if s is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        s.status = 'cancelled'
        s.decided_at = timezone.now()
        s.save(update_fields=['status', 'decided_at', 'updated_at'])
        return Response(SponsorSponsorshipSerializer(s).data)
