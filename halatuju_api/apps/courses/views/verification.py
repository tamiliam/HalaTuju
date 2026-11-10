"""Contact verification: the email link and the phone code."""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from ..models import EmailVerification, StudentProfile

logger = logging.getLogger('apps.courses.views')


VERIFICATION_EMAIL_SUBJECTS = {
    'en': 'HalaTuju — Verify your email',
    'ms': 'HalaTuju — Sahkan e-mel anda',
    'ta': 'HalaTuju — உங்கள் மின்னஞ்சலை சரிபார்க்கவும்',
}


VERIFICATION_EMAIL_BODIES = {
    'en': 'Click this link to verify your email: {url}\n\nThis link expires in 24 hours.',
    'ms': 'Klik pautan ini untuk mengesahkan e-mel anda: {url}\n\nPautan ini tamat tempoh dalam 24 jam.',
    'ta': 'உங்கள் மின்னஞ்சலை சரிபார்க்க இந்த இணைப்பைக் கிளிக் செய்யவும்: {url}\n\nஇந்த இணைப்பு 24 மணி நேரத்தில் காலாவதியாகும்.',
}


class SendVerificationView(APIView):
    """
    POST /api/v1/profile/verify-email/send/
    Generates a verification token and sends an email with a verification link.
    Rate limited to 3 requests per hour per user.
    Accepts optional ``lang`` parameter (en/ms/ta) for trilingual email.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from django.conf import settings
        from .. import profile_claim

        email = request.data.get('email', '').strip()
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        lang = request.data.get('lang', 'en')
        if lang not in ('en', 'ms', 'ta'):
            lang = 'en'

        try:
            profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        # Rate limit: max 3 verification emails per hour per profile
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = EmailVerification.objects.filter(
            profile=profile, created_at__gte=one_hour_ago
        ).count()
        if recent_count >= 3:
            return Response(
                {'error': 'Too many verification requests. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Invalidate previous tokens for this profile+email
        EmailVerification.objects.filter(profile=profile, email=email, used=False).update(used=True)

        token = uuid.uuid4()
        EmailVerification.objects.create(
            profile=profile,
            email=email,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send verification email in the user's language
        frontend_url = getattr(settings, 'FRONTEND_URL', '')
        verify_url = f"{frontend_url}/verify-email?token={token}"
        try:   # TD-428: through the metered seam, not a bare send_mail
            profile_claim.send_verification_email(
                email, VERIFICATION_EMAIL_SUBJECTS[lang],
                VERIFICATION_EMAIL_BODIES[lang].format(url=verify_url))
        except Exception:
            logger.warning('Verification email failed for profile %s', profile.pk, exc_info=True)

        return Response({'status': 'sent'})


class VerifyEmailView(APIView):
    """
    GET /api/v1/profile/verify-email/<token>/
    Public endpoint — student clicks link from email.
    """
    permission_classes = []  # Public

    def get(self, request, token):
        from django.db import transaction

        with transaction.atomic():
            try:
                verification = EmailVerification.objects.select_for_update().get(token=token)
            except EmailVerification.DoesNotExist:
                return Response({'error': 'Invalid token'}, status=status.HTTP_404_NOT_FOUND)

            if verification.used:
                return Response({'error': 'Token already used'}, status=status.HTTP_400_BAD_REQUEST)

            if verification.is_expired:
                return Response({'error': 'Token expired'}, status=status.HTTP_400_BAD_REQUEST)

            verification.used = True
            verification.save(update_fields=['used'])

            profile = verification.profile
            profile.contact_email = verification.email
            profile.contact_email_verified = True
            profile.save(update_fields=['contact_email', 'contact_email_verified'])

        return Response({'status': 'verified', 'email': verification.email})


class PhoneVerifyStartView(APIView):
    """
    POST /api/v1/profile/verify-phone/send/
    Send a one-time code to the student's ``contact_phone`` via Twilio Verify (roadmap S4 /
    TD-136), over ``settings.PHONE_VERIFY_CHANNEL`` (SMS by default; WhatsApp once onboarded).
    Opt-in / voluntary — the student initiates this from /profile.
    Body: optional ``phone`` (defaults to the saved contact_phone). Soft-rate-limited to 5
    sends/hour per profile (Twilio Verify enforces the hard per-number limits).
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from django.conf import settings
        from django.core.cache import cache
        from apps.scholarship import whatsapp  # local import: avoids app-load order issues

        # Student phone verification is paused (see settings.PHONE_VERIFY_ENABLED). Refuse
        # gracefully — the /profile UI shows a "planned for the future" note, but guard the
        # endpoint too so a direct hit can't spend an SMS.
        if not getattr(settings, 'PHONE_VERIFY_ENABLED', False):
            return Response({'error': 'phone_verify_paused'}, status=status.HTTP_403_FORBIDDEN)

        try:
            profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        phone = (request.data.get('phone') or profile.contact_phone or '').strip()
        if not phone:
            return Response({'error': 'phone_required'}, status=status.HTTP_400_BAD_REQUEST)

        # Soft rate limit: 5 sends/hour per profile (best-effort; Twilio Verify is the backstop).
        rl_key = f'phoneverify:send:{profile.pk}'
        sent = cache.get(rl_key, 0)
        if sent >= 5:
            return Response({'error': 'rate_limited'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        channel = getattr(settings, 'PHONE_VERIFY_CHANNEL', 'sms')
        ok, vstatus, _err = whatsapp.start_phone_verification(phone, channel=channel)
        if not ok:
            http = {'unconfigured': status.HTTP_503_SERVICE_UNAVAILABLE,
                    'invalid_number': status.HTTP_400_BAD_REQUEST}.get(vstatus, status.HTTP_502_BAD_GATEWAY)
            return Response({'error': vstatus or 'failed'}, status=http)

        cache.set(rl_key, sent + 1, 3600)
        return Response({'status': 'sent'})


class PhoneVerifyCheckView(APIView):
    """
    POST /api/v1/profile/verify-phone/check/  {code, [phone]}
    Confirm the one-time code with Twilio Verify; on success mark ``contact_phone_verified``
    (and persist the number if a new one was being verified). A wrong/expired code → 400.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from django.conf import settings
        from apps.scholarship import whatsapp  # local import: avoids app-load order issues

        if not getattr(settings, 'PHONE_VERIFY_ENABLED', False):
            return Response({'verified': False, 'error': 'phone_verify_paused'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        code = (request.data.get('code') or '').strip()
        phone = (request.data.get('phone') or profile.contact_phone or '').strip()
        if not code:
            return Response({'error': 'code_required'}, status=status.HTTP_400_BAD_REQUEST)

        approved, err = whatsapp.check_phone_verification(phone, code)
        if not approved:
            if err == 'unconfigured':
                return Response({'verified': False, 'error': 'unconfigured'},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'verified': False, 'error': err or 'incorrect'},
                            status=status.HTTP_400_BAD_REQUEST)

        fields = ['contact_phone_verified']
        if phone and profile.contact_phone != phone:
            profile.contact_phone = phone
            fields.append('contact_phone')
        profile.contact_phone_verified = True
        profile.save(update_fields=fields)
        return Response({'verified': True})
