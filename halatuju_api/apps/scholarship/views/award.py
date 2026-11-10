"""After the offer: the award screen, bursary agreement, bank account, comprehension quiz, guarantor phone."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .. import request_ip, sponsorship as sponsorship_service
from ..document_snapshot import SNAPSHOT_ORDER
from ..models import ApplicantDocument, ScholarshipApplication
from ..serializers import BursaryAgreementSerializer, StudentAwardSerializer
from ..services import apply_gate, is_minor
# `_award_application` lives in signing_window.py (request #26): the guardian-contact freeze reads the SAME rule.
from ..signing_window import award_application as _award_application
from .common import _current_application


class BankAccountView(APIView):
    """The student's bursary payout account (post-award).

    GET  → the confirmed account, or null.
    POST → confirm the three fields the student reviewed/corrected after uploading a
           bank statement. The HOLDER MUST BE THE STUDENT — a hard rule re-checked here
           against the application name (never trusting the AI read). Saving links the
           uploaded bank statement and resolves the Action-Centre task. Awarded/active only.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        from ..models import BankAccount
        from ..serializers import BankAccountSerializer
        app = _current_application(request.user_id)
        acct = BankAccount.objects.filter(application=app).first() if app else None
        return Response({'bank_account': BankAccountSerializer(acct).data if acct else None})

    def post(self, request):
        from ..models import BankAccount
        from ..serializers import BankAccountConfirmSerializer, BankAccountSerializer
        from ..resolution import BANK_CAPTURE_STATES, sync_bank_details_item
        from django.conf import settings as _settings
        # Feature being deprecated (default OFF): refuse new submissions so a stale client
        # can't re-create the task. Already-captured accounts remain readable via GET.
        if not getattr(_settings, 'BANK_DETAILS_CAPTURE_ENABLED', False):
            return Response({'error': 'bank_capture_disabled', 'code': 'bank_capture_disabled'},
                            status=status.HTTP_410_GONE)
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'no_application', 'code': 'no_application'},
                            status=status.HTTP_403_FORBIDDEN)
        if app.status not in BANK_CAPTURE_STATES:
            return Response({'error': 'not_awarded', 'code': 'not_awarded'},
                            status=status.HTTP_400_BAD_REQUEST)
        ser = BankAccountConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        holder = ser.validated_data['account_holder']
        # Hard rule: the payout account must be in the STUDENT's name. Tolerant of
        # spelling/romanisation (name_match != 'mismatch'), like the IC identity gate, but
        # a genuinely different person is refused. Gopal coaches this on the FE.
        from ..vision import name_match
        student_name = getattr(getattr(app, 'profile', None), 'name', '') or ''
        if name_match(holder, student_name) == 'mismatch':
            return Response({'error': 'bank_holder_mismatch', 'code': 'bank_holder_mismatch'},
                            status=status.HTTP_400_BAD_REQUEST)
        source_doc = ApplicantDocument.objects.filter(
            application=app, doc_type='bank_statement',
            superseded_at__isnull=True).order_by(*SNAPSHOT_ORDER).first()
        from django.utils import timezone
        acct, _created = BankAccount.objects.update_or_create(
            application=app,
            defaults=dict(
                bank_name=ser.validated_data['bank_name'],
                account_number=ser.validated_data['account_number'],
                account_holder=holder, source_doc=source_doc,
                holder_verdict='ok', confirmed_at=timezone.now()),
        )
        sync_bank_details_item(app)   # the account exists now → close the task
        return Response(BankAccountSerializer(acct).data, status=status.HTTP_200_OK)


class StudentComprehensionQuizView(APIView):
    """GET the comprehension checkpoints for the caller's AWARDED application, served
    from the governing contract template (the active version of the application's GIFT,
    TD-229). Returns
    ``{template_version, locale_used, checkpoints}`` — the FE renders these and posts
    ``template_version`` back on pass, so a mid-flight redeploy is caught (409)."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        from .. import contract_scope, contracts
        app = _current_application(request.user_id)
        if app is None or app.status != 'awarded':
            return Response({'error': 'no_application', 'code': 'no_application'},
                            status=status.HTTP_403_FORBIDDEN)
        template = contract_scope.template_for_application(app)
        locale = contracts.resolve_locale(request.query_params.get('locale', 'en'), template)
        return Response({
            'template_version': template.version if template else '',
            'locale_used': locale,
            'checkpoints': contracts.quiz_checkpoints(template, locale) if template else [],
        })


class StudentComprehensionView(APIView):
    """POST: the student passed the bursary-agreement comprehension quiz (the "Understand"
    step on /scholarship/award). Stamps ``comprehension_passed_at`` (idempotent) AND pins
    ``comprehension_template`` to the version they were quizzed on — the runtime guard that
    ``bursary.sign_agreement`` checks (``comprehension_stale``). A posted ``template_version``
    that no longer matches the active template → 409 ``version_changed`` (the FE re-fetches
    and re-takes)."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        from .. import contract_scope
        app = _current_application(request.user_id)
        if app is None or app.status != 'awarded':
            return Response({'error': 'no_application', 'code': 'no_application'},
                            status=status.HTTP_403_FORBIDDEN)
        template = contract_scope.template_for_application(app)
        if template is not None:
            posted = (request.data.get('template_version') or '').strip()
            if posted and posted != template.version:
                return Response({'error': 'version_changed', 'code': 'version_changed',
                                 'template_version': template.version},
                                status=status.HTTP_409_CONFLICT)
        fields = []
        if app.comprehension_passed_at is None:
            app.comprehension_passed_at = timezone.now()
            fields.append('comprehension_passed_at')
        if template is not None and app.comprehension_template_id != template.id:
            app.comprehension_template = template
            fields.append('comprehension_template')
        if fields:
            app.save(update_fields=fields)
        return Response({'ok': True, 'template_version': template.version if template else ''})


def _mask_phone(phone):
    """Last 4 digits only, e.g. '•••• 2222' — never the full number on the wire/FE."""
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    return ('•••• ' + digits[-4:]) if len(digits) >= 4 else '••••'


class GuarantorPhoneVerifyStartView(APIView):
    """POST /api/v1/scholarship/award/guarantor/verify-phone/send/

    Send a one-time PIN to the parent/guardian SURETY's pre-declared, LOCKED phone (read
    from ``profile.guardians``, captured at apply) over ``settings.PHONE_VERIFY_CHANNEL``
    — the same-session parent gate that precedes the in-session bursary signature. Scoped
    to the caller's awarded application; the student/parent never supplies or edits the
    number. Soft-rate-limited to 5 sends/hour per application. Only when the bursary flag
    is on (no accidental SMS while the contract flow is dark)."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from django.conf import settings as _s
        from django.core.cache import cache
        from .. import bursary, whatsapp
        if not getattr(_s, 'BURSARY_AGREEMENT_ENABLED', False):
            return Response({'error': 'bursary_disabled', 'code': 'bursary_disabled'},
                            status=status.HTTP_403_FORBIDDEN)
        app = _award_application(request.user_id)
        if app is None:
            return Response({'error': 'no_offer', 'code': 'no_offer'},
                            status=status.HTTP_403_FORBIDDEN)
        from ..parent_call import refuse_signing_until_called   # request #26, owner ruling A
        if (waits := refuse_signing_until_called(app)):
            return Response({'error': waits, 'code': waits}, status=status.HTTP_409_CONFLICT)
        phone = bursary.guarantor_phone_for(app)
        if not phone:
            return Response({'error': 'guarantor_phone_missing', 'code': 'guarantor_phone_missing'},
                            status=status.HTTP_400_BAD_REQUEST)
        rl_key = f'guarantor_phoneverify:send:{app.pk}'
        sent = cache.get(rl_key, 0)
        if sent >= 5:
            return Response({'error': 'rate_limited', 'code': 'rate_limited'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        channel = getattr(_s, 'PHONE_VERIFY_CHANNEL', 'sms')
        ok, vstatus, _err = whatsapp.start_phone_verification(phone, channel=channel)
        if not ok:
            http = {'unconfigured': status.HTTP_503_SERVICE_UNAVAILABLE,
                    'invalid_number': status.HTTP_400_BAD_REQUEST}.get(
                        vstatus, status.HTTP_502_BAD_GATEWAY)
            return Response({'error': vstatus or 'failed'}, status=http)
        cache.set(rl_key, sent + 1, 3600)
        return Response({'status': 'sent', 'phone_hint': _mask_phone(phone)})


class GuarantorPhoneVerifyCheckView(APIView):
    """POST /api/v1/scholarship/award/guarantor/verify-phone/check/  {code}

    Confirm the PIN against Twilio Verify for the caller's awarded application; on success
    stamp ``guarantor_phone_verified_at`` + ``guarantor_phone`` (the locked number). That
    stamp is what ``bursary.sign_agreement`` requires to be FRESH. Wrong/expired code → 400."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        from django.conf import settings as _s
        from django.utils import timezone
        from .. import bursary, whatsapp
        if not getattr(_s, 'BURSARY_AGREEMENT_ENABLED', False):
            return Response({'error': 'bursary_disabled', 'code': 'bursary_disabled'},
                            status=status.HTTP_403_FORBIDDEN)
        app = _award_application(request.user_id)
        if app is None:
            return Response({'error': 'no_offer', 'code': 'no_offer'},
                            status=status.HTTP_403_FORBIDDEN)
        phone = bursary.guarantor_phone_for(app)
        if not phone:
            return Response({'error': 'guarantor_phone_missing', 'code': 'guarantor_phone_missing'},
                            status=status.HTTP_400_BAD_REQUEST)
        code = (request.data.get('code') or '').strip()
        if not code:
            return Response({'error': 'code_required', 'code': 'code_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        approved, err = whatsapp.check_phone_verification(phone, code)
        if not approved:
            if err == 'unconfigured':
                return Response({'verified': False, 'error': 'unconfigured'},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({'verified': False, 'error': err or 'incorrect'},
                            status=status.HTTP_400_BAD_REQUEST)
        app.guarantor_phone = phone
        app.guarantor_phone_verified_at = timezone.now()
        app.save(update_fields=['guarantor_phone', 'guarantor_phone_verified_at'])
        return Response({'verified': True})


class StudentAwardView(APIView):
    """Phase E3 — the student's award offer. GET the current offer; POST to accept
    or decline it. The sponsor's identity is never exposed (allowlist). For a minor,
    a guardian must accept (name + NRIC + relationship), mirroring share-consent."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _award_application(request.user_id)
        offer = sponsorship_service.current_offer(app) if app else None
        # Award cool-off (#14): once accepted the sponsorship is 'active' (no longer 'offered')
        # but the app isn't finalised to 'active' yet — surface a 'finalising' state so the page
        # isn't blank during the window (the confirmation email + onboarding open at cool-off end).
        finalising = False
        if not offer:
            pend = (ScholarshipApplication.objects
                    .filter(profile_id=request.user_id, award_due_at__isnull=False)
                    .exclude(status='active')
                    .filter(sponsorships__status='active').select_related('profile').first())
            if pend is not None:
                finalising = True
                app = app or pend
        from django.conf import settings as _award_settings
        payload = {
            'offer': StudentAwardSerializer(offer).data if offer else None,
            'finalising': finalising,
            'is_minor': is_minor(app.profile) if (app and app.profile) else False,
            # Gates the "View my award" panel on /scholarship/application. OFF = the accept +
            # onboarding flow isn't exposed yet (the student is invited by email later).
            'acceptance_enabled': getattr(_award_settings, 'AWARD_ACCEPTANCE_ENABLED', False),
            # TD-291: the page asks for the signed agreement only when this is on; the agreement
            # route 404s while it is off, and every page load used to ask it anyway.
            'agreement_enabled': getattr(_award_settings, 'BURSARY_AGREEMENT_ENABLED', False),
        }
        # Bursary agreement (flag-gated): surface the contract the student is about to
        # sign (particulars + rendered body) when an offer/active award exists, and — if
        # already signed — the agreement status + a signed PDF URL. Never a donor field.
        from django.conf import settings as _settings
        if getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False) and app:
            from .. import agreement_guard, bursary, contract_scope, contracts
            from ..signing_progress import signing_progress
            existing = agreement_guard.live_agreement(app)   # a voided row is no agreement (A1.13)
            template = contract_scope.template_for_application(app) if existing is None else None
            if existing is not None:
                payload['bursary_agreement'] = BursaryAgreementSerializer(existing).data
            elif (offer or finalising) and template is None:
                # TD-229: THIS GIFT has no active agreement — say so; never preview another's.
                payload['bursary_unavailable'] = contract_scope.NO_TEMPLATE
            elif offer or finalising:
                # TD-229: until 2026-10-03 this called both helpers WITHOUT the template they
                # have required since Contract Sprint 5 — a TypeError on every flag-on preview.
                locale = contracts.resolve_locale(app.locale if app.profile else 'en', template)
                p = bursary.particulars_for(app, template, locale)
                preview_html = bursary.render_agreement_html(
                    app, p,
                    student={'name': getattr(app.profile, 'name', '') if app.profile else '',
                             'nric': '', 'signed_at': None},
                    guarantor={'name': '', 'nric': '', 'relationship': '', 'signed_at': None},
                    foundation={'name': p['foundation_signatory_name'],
                                'title': p['foundation_signatory_title'],
                                'nric': p['foundation_signatory_nric'], 'signed_at': None},
                    witness={'by': '', 'org': '', 'signed_at': None}, locale=locale,
                    template=template)
                payload['bursary_preview'] = {
                    'award_amount': str(p['award_amount']) if p['award_amount'] is not None else None,
                    'payment_schedule': p['payment_schedule'],
                    'institution_name': p['institution_name'],
                    'course_name': p['course_name'],
                    'progress_standard': p['progress_standard'],
                    'foundation_signatory_name': p['foundation_signatory_name'],
                    'foundation_signatory_title': p['foundation_signatory_title'],
                    'rendered_html': preview_html,
                    # Mobile M4: what she has already done, so a reload skips it (read-only; each
                    # flag is the exact rule the signature enforces — signing_progress.py).
                    **signing_progress(app, template),
                }
        return Response(payload)

    def post(self, request):
        app = _award_application(request.user_id)
        if app is None:
            return Response({'error': 'no_offer'}, status=status.HTTP_403_FORBIDDEN)
        action = request.data.get('action')
        if action not in ('accept', 'decline'):
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sponsorship = sponsorship_service.respond_to_award(
                app, action=action,
                locale=request.data.get('locale', 'en'),
                granted_by=request.data.get('granted_by', 'self'),
                guardian_name=request.data.get('guardian_name', '') or '',
                guardian_relationship=request.data.get('guardian_relationship', '') or '',
                guardian_nric=request.data.get('guardian_nric', '') or '',
                ip=request_ip.signer_ip(request),
                student_signed_name=request.data.get('student_signed_name', '') or '',
                student_signed_nric=request.data.get('student_signed_nric', '') or '',
                guarantor_name=request.data.get('guarantor_name', '') or '',
                guarantor_nric=request.data.get('guarantor_nric', '') or '',
                guarantor_relationship=request.data.get('guarantor_relationship', '') or '',
            )
        except sponsorship_service.SponsorshipError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudentAwardSerializer(sponsorship).data)


class BursaryAgreementView(APIView):
    """GET the student's OWN bursary agreement (status + particulars + signed PDF URL).
    Allowlist-safe: the serializer never carries a donor field. 404 when the feature is
    off or no agreement exists yet."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        from django.conf import settings as _settings
        if not getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        live = apply_gate.in_play_application(request.user_id)   # her CURRENT one first (TD-337)
        app = (ScholarshipApplication.objects.filter(profile_id=request.user_id, bursary_agreement__isnull=False)
               .filter(**({'pk': live.pk} if live else {})).select_related('bursary_agreement').order_by('-id').first())
        from ..agreement_guard import live_agreement   # a withdrawal's voided row is no agreement
        if app is None or live_agreement(app) is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BursaryAgreementSerializer(app.bursary_agreement).data)
