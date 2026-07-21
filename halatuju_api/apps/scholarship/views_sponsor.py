"""Phase E: sponsor-facing endpoints — self-registration + own account status.

A sponsor is an ordinary Supabase-authenticated user (signs in like a student),
registers here, and is then VETTED by an admin before getting any access to the
anonymised student pool. These endpoints govern the sponsor's OWN account only —
nothing here exposes student data. All paths are under /api/v1/sponsor/ and are
whitelisted from the NRIC gate (sponsors have no NRIC).
"""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Case, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from halatuju.throttling import PublicCountRateThrottle

from . import pool
from . import in_programme as in_programme_service
from . import referrals as referral_service
from . import sponsor_feed
from . import sponsorship as sponsorship_service
from . import trust as trust_service
from .emails import send_sponsor_interest_admin_email
from .models import Donation, ScholarshipApplication, Sponsor, Sponsorship, StandingGift
from .serializers import (
    GraduationRelaySerializer,
    SponsorPoolCardSerializer, SponsorPoolDetailSerializer,
    SponsorReferralSerializer,
    SponsorSerializer, SponsorSponsorshipSerializer,
    StandingGiftSerializer,
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
        # F4: attribute a referral if they arrived via a /sponsor?ref=<code> link.
        ref = (data.get('ref') or '').strip()
        if ref:
            referral_service.attribute_referral(ref, sponsor)
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


class SponsorNotificationsView(SponsorMixin, APIView):
    """PATCH /api/v1/sponsor/notifications/ {notify_frequency: realtime|weekly|off}
    — the sponsor sets how often they hear about newly-published students (F3).
    Self-only; available to any registered sponsor (not gated on approval)."""
    def patch(self, request):
        sponsor = self.get_sponsor(request)
        if not sponsor:
            return Response({'error': 'not_registered'}, status=status.HTTP_400_BAD_REQUEST)
        freq = (request.data.get('notify_frequency') or '').strip()
        valid = {c for c, _ in Sponsor.NOTIFY_FREQUENCIES}
        if freq not in valid:
            return Response({'error': 'bad_frequency', 'allowed': sorted(valid)},
                            status=status.HTTP_400_BAD_REQUEST)
        sponsor.notify_frequency = freq
        sponsor.save(update_fields=['notify_frequency', 'updated_at'])
        return Response(SponsorSerializer(sponsor).data)


class SponsorReferralView(SponsorMixin, APIView):
    """GET/POST /api/v1/sponsor/referrals/ — a sponsor invites a prospective sponsor
    (F4). Approved sponsors only (they vouch for the invite). GET lists their own
    invitations + conversion status. POST {invitee_email, invitee_name?, note?}
    records the invite + sends the email (400 `bad_email`). A duplicate still-pending
    invite to the same email is idempotent (no second email)."""
    def get(self, request):
        sponsor = self.require_approved_sponsor(request)
        if not sponsor:
            return Response({'error': 'not_approved'}, status=status.HTTP_403_FORBIDDEN)
        return Response({'referrals': SponsorReferralSerializer(
            referral_service.sponsor_referrals(sponsor), many=True).data})

    def post(self, request):
        sponsor = self.require_approved_sponsor(request)
        if not sponsor:
            return Response({'error': 'not_approved'}, status=status.HTTP_403_FORBIDDEN)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            referral = referral_service.create_referral(
                sponsor,
                invitee_email=data.get('invitee_email', ''),
                invitee_name=data.get('invitee_name', ''),
                note=data.get('note', ''),
            )
        except referral_service.ReferralError as exc:
            return Response({'error': exc.code, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SponsorReferralSerializer(referral).data, status=status.HTTP_201_CREATED)


class SponsorPoolCountView(APIView):
    """GET /api/v1/sponsor/pool/count/ — PUBLIC count of students currently waiting
    in the anonymised pool, for the F1 sponsor-landing live counter.

    Count ONLY — exposes no student data (not even an id). Behind SPONSOR_POOL_ENABLED:
    while the flag is off (lawyer-gated) it returns {count: 0, enabled: False} so the
    landing hides the counter and the whole sponsor programme stays dark until go-live.
    No auth (a public marketing page calls it); the NRIC gate skips anonymous callers."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicCountRateThrottle]

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
        # The DISPLAY pool includes just-funded students (grace window) shown as read-only
        # "Sponsored" cards — not the strict fundable set (see pool.display_pool_queryset).
        # Annotate the funded-so-far total (sum of HOLDING sponsorships) once per row so
        # the funding-bar field doesn't fire a per-card aggregate across the grid.
        # ORDER (owner 2026-07-21): unfunded ('recommended') cards first, then the just-sponsored
        # grace-window cards — one list, no separator. Within each group, newest-relevant-event
        # first (a funded card by when it was sponsored = awarded_at; an open one by when it entered
        # the pool = recommended_at). Sorting is server-side, so no timestamp leaks to the card.
        qs = pool.display_pool_queryset(ScholarshipApplication).annotate(
            funded_total=Sum('sponsorships__amount',
                             filter=Q(sponsorships__status__in=Sponsorship.HOLDING)),
            _unfunded_first=Case(When(status='recommended', then=Value(0)),
                                 default=Value(1), output_field=IntegerField()),
            _pool_ts=Coalesce('awarded_at', 'recommended_at'),
        ).order_by('_unfunded_first', '-_pool_ts')
        return Response({'students': SponsorPoolCardSerializer(qs, many=True).data})


class SponsorPoolDetailView(_PoolBase):
    """GET /api/v1/sponsor/pool/<pk>/ — one anonymised student (card + the
    generated anonymous blurb). 404 unless the student is currently pool-eligible."""
    def get(self, request, pk):
        _, err = self._gate(request)
        if err:
            return err
        # Display pool (incl. just-funded grace-window cards) — a funded student's detail stays
        # viewable (read-only) for the window; the fund action itself remains gated by is_fundable.
        app = pool.display_pool_queryset(ScholarshipApplication).filter(id=pk).first()
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


class SponsorImpactView(_PoolBase):
    """GET /api/v1/sponsor/impact/ — aggregate giving impact for the My Giving
    dashboard (R2): total given, students supported/active/graduated, semesters
    completed, and the donut breakdown (committed/completed/available). Counts +
    money ONLY — allowlist-safe, no student identity. Behind SPONSOR_POOL_ENABLED +
    approved-sponsor (via _gate)."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        return Response(sponsorship_service.sponsor_impact(sponsor))


class SponsorStatementView(_PoolBase):
    """GET /api/v1/sponsor/statement/ — R4: the giving statement's two ledgers —
    donations INTO the trust + gifts OUT to students (anonymous ref only). Money +
    refs only, allowlist-safe. Behind SPONSOR_POOL_ENABLED + approved-sponsor."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        return Response(sponsorship_service.sponsor_statement(sponsor))


class SponsorActivityView(_PoolBase):
    """GET /api/v1/sponsor/activity/ — R3: a time-ordered feed of THIS sponsor's
    own students' lifecycle events (funded/accepted/semester/graduated/thank-you),
    each carrying the anonymous ``ref`` only. Allowlist-safe, flag + approval gated."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        return Response({'events': sponsor_feed.sponsor_activity(sponsor)})


class SponsorCommunityView(_PoolBase):
    """GET /api/v1/sponsor/community/ — R3: programme-wide belonging counts for the
    My Giving community strip (approved sponsors · students supported · still waiting).
    Counts only, nothing identifying. Flag + approval gated."""
    def get(self, request):
        _, err = self._gate(request)
        if err:
            return err
        return Response(sponsor_feed.community_stats())


class SponsorTrustView(_PoolBase):
    """GET /api/v1/sponsor/trust/ — R5: the Trust & Transparency hub content
    (who-we-are / governance / sources & uses / independent assurance) + live
    community counts. Programme-level content + counts only — no student or sponsor
    identity, allowlist-safe by construction. Behind SPONSOR_POOL_ENABLED +
    approved-sponsor (via _gate)."""
    def get(self, request):
        _, err = self._gate(request)
        if err:
            return err
        return Response(trust_service.get_trust_content())


class SponsorStandingGiftView(_PoolBase):
    """GET/PUT /api/v1/sponsor/standing-gift/ — R6 AutoSponsor. The sponsor's own
    standing-gift config (field/state prefs + optional per-student cap + active).
    GET returns the config (``configured: false`` if none set). PUT upserts it.
    The sponsor's own settings only — no student data. Each allocation still
    produces an OFFERED sponsorship the student must accept (no real money moves).
    Behind SPONSOR_POOL_ENABLED + approved-sponsor (via _gate)."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        sg = StandingGift.objects.filter(sponsor=sponsor).first()
        if sg is None:
            return Response({'configured': False, 'active': False})
        return Response({'configured': True, **StandingGiftSerializer(sg).data})

    def put(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        ser = StandingGiftSerializer(data=data)
        ser.is_valid(raise_exception=True)
        sg, _ = StandingGift.objects.update_or_create(
            sponsor=sponsor, defaults=ser.validated_data)
        return Response({'configured': True, **StandingGiftSerializer(sg).data})


class SponsorGraduationMessagesView(_PoolBase):
    """GET /api/v1/sponsor/graduation-messages/ — the staff-approved graduation
    thank-yous from the students this sponsor actively funds (F9a). Each is *"a
    message from a student you supported"*, linked ONLY to the anonymous ``ref`` —
    never the student's identity, never a reply channel. Behind SPONSOR_POOL_ENABLED
    + approved-sponsor (via _gate); allowlist by construction (GraduationRelaySerializer)."""
    def get(self, request):
        sponsor, err = self._gate(request)
        if err:
            return err
        messages = in_programme_service.approved_messages_for_sponsor(sponsor)
        return Response({'messages': GraduationRelaySerializer(messages, many=True).data})


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
            sponsorship = sponsorship_service.award_and_notify(sponsor, app)
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
    """POST /api/v1/sponsor/sponsorships/<pk>/cancel/ — withdraw an OFFERED award within the
    cool-off, i.e. before the good-news email has gone out; the amount returns to the sponsor's
    balance and the student reverts to 'recommended' (back in the pool). Once the student has been
    emailed the award, cancelling is refused (400 ``already_notified``)."""
    def post(self, request, pk):
        sponsor, err = self._gate(request)
        if err:
            return err
        try:
            s = sponsorship_service.cancel_offer(sponsor, pk)
        except sponsorship_service.SponsorshipError as e:
            if e.code == 'not_found':
                return Response({'error': e.code}, status=status.HTTP_404_NOT_FOUND)
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SponsorSponsorshipSerializer(s).data)
