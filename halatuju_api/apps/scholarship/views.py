"""B40 Assistance Programme API — application intake (Phase 1, Sprint 1)."""
from rest_framework import status
from rest_framework.permissions import AllowAny
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
    StudentAwardSerializer,
)
from . import sponsorship as sponsorship_service
from .services import (
    CONSENT_VERSION,
    IncompleteProfileError,
    POST_SHORTLIST_EDITABLE,
    confirm_profile,
    consent_blockers,
    create_application,
    is_minor,
    record_consent,
    resolve_open_cohort,
    revert_if_profile_incomplete,
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
        # Deeper info + funding need are a post-shortlist (STEP 2) step. Editing
        # stays open through the whole post-shortlist funnel — confirming a profile
        # is NOT a freeze (the student may add documents the admin asks for).
        if application.status not in POST_SHORTLIST_EDITABLE:
            return Response(
                {'error': 'Details can only be added once your application is shortlisted.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ApplicationDetailsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_application_details(application, serializer.validated_data)
        # If a confirmed profile was edited back to incomplete, un-confirm it so
        # the funnel stays honest.
        revert_if_profile_incomplete(application)
        return Response(ApplicationReadSerializer(application).data)


class ApplicationConfirmView(APIView):
    """POST /api/v1/scholarship/applications/<id>/confirm/ — the student's explicit
    "I'm done" action. Flips shortlisted → profile_complete (Phase C) if the
    profile is complete; 400 with the completeness dict if not."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        application = ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id
        ).select_related('cohort', 'profile').first()
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            confirm_profile(application)
        except IncompleteProfileError as exc:
            return Response(
                {'error': 'Please complete every required step before submitting.',
                 'code': 'incomplete_profile', 'completeness': exc.completeness},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ApplicationReadSerializer(application).data)


def _current_application(user_id):
    """The caller's current post-shortlist application (one per cohort; latest wins).

    Spans the whole editable funnel (POST_SHORTLIST_EDITABLE), not just
    'shortlisted', so the student can keep uploading documents after confirming
    their profile and while an interview is in progress.
    """
    return (
        ScholarshipApplication.objects
        .filter(profile_id=user_id, status__in=POST_SHORTLIST_EDITABLE)
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


# Supporting docs that get a soft name-presence check on upload (the income docs,
# results slip, offer letter, and utility bills). Utility bills additionally get a
# soft home-address check. IC / parent_ic use the dedicated MyKad pipeline instead.
BILL_DOC_TYPES = frozenset({'water_bill', 'electricity_bill'})
SUPPORTING_NAME_CHECK_TYPES = frozenset({
    'results_slip', 'str', 'salary_slip', 'epf', 'offer_letter',
} | BILL_DOC_TYPES)


class DocumentListCreateView(APIView):
    """GET list / POST record the caller's documents."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _current_application(request.user_id)
        docs = ApplicantDocument.objects.filter(application=app) if app else ApplicantDocument.objects.none()
        return Response({'documents': ApplicantDocumentSerializer(docs, many=True).data})

    # Post-S14 fix: single-instance doc types replace any existing copy on
    # re-upload (avoids the "which IC is the real one?" ambiguity). The three
    # income-proof types stay multi-instance — students may upload several
    # monthly salary slips / EPF statements.
    MULTI_INSTANCE_DOC_TYPES = frozenset({'str', 'salary_slip', 'epf'})

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_doc_type = serializer.validated_data['doc_type']
        from django.conf import settings as _settings
        # Guardrail 1: per-file size cap (the bytes go client→Storage via signed
        # URL, so this validates the reported size).
        if (serializer.validated_data.get('size') or 0) > _settings.MAX_DOC_SIZE_BYTES:
            return Response({'error': 'file_too_large', 'max_mb': _settings.MAX_DOC_SIZE_BYTES // (1024 * 1024)},
                            status=status.HTTP_400_BAD_REQUEST)
        # Guardrail 2: per-application document cap. A single-instance re-upload
        # replaces an existing doc, so it doesn't count toward growth.
        replaces = (new_doc_type not in self.MULTI_INSTANCE_DOC_TYPES
                    and ApplicantDocument.objects.filter(application=app, doc_type=new_doc_type).exists())
        if not replaces and ApplicantDocument.objects.filter(application=app).count() >= _settings.MAX_DOCS_PER_APPLICATION:
            return Response({'error': 'doc_limit_reached', 'max': _settings.MAX_DOCS_PER_APPLICATION},
                            status=status.HTTP_400_BAD_REQUEST)
        # For single-instance types, sweep older copies of the SAME type for
        # this application first — DB row + Supabase Storage object together.
        if new_doc_type not in self.MULTI_INSTANCE_DOC_TYPES:
            stale = ApplicantDocument.objects.filter(application=app, doc_type=new_doc_type)
            stale_paths = [d.storage_path for d in stale if d.storage_path]
            if stale_paths:
                from .storage import delete_objects
                delete_objects(stale_paths)   # best-effort; leaves orphan blob if it fails (logged)
            stale.delete()
        doc = ApplicantDocument.objects.create(application=app, **serializer.validated_data)
        # S13 + S17: auto-run Vision OCR on IC uploads (student's IC OR the
        # parent/guardian IC for minor consent). Soft signal — never blocks.
        if doc.doc_type in ('ic', 'parent_ic'):
            from .vision import run_vision_for_document
            run_vision_for_document(doc)
        # Supporting docs: OCR once, then (a) the free name/address presence check
        # and (b) automatic Gemini field-extraction with student feedback. Soft,
        # never blocks. Gemini is guardrailed by the hourly per-application cap.
        elif doc.doc_type in SUPPORTING_NAME_CHECK_TYPES:
            from . import vision as _vision
            profile = app.profile
            names = [getattr(profile, 'name', '') or '']
            names += [g.get('name', '') for g in (getattr(profile, 'guardians', None) or [])
                      if isinstance(g, dict)]
            names = [n for n in names if n]
            postcode = getattr(profile, 'postal_code', '') or ''
            city = getattr(profile, 'city', '') or ''
            check_address = doc.doc_type in BILL_DOC_TYPES
            ocr = _vision.ocr_document(doc)   # OCR once, shared by both checks
            match = _vision.run_vision_match_for_document(
                doc, names=names, postcode=postcode, city=city, check_address=check_address, ocr=ocr)
            if doc.doc_type in _vision.GEMINI_EXTRACT_DOC_TYPES:
                self._maybe_extract_fields(app, doc, _vision, ocr, names, postcode, city,
                                           check_address, match, _settings)
        return Response(ApplicantDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _maybe_extract_fields(app, doc, _vision, ocr, names, postcode, city, check_address, match, _settings):
        """Run Gemini doc-assist if the cost knob + hourly throttle allow; otherwise
        mark 'review_manually'. Never blocks the upload."""
        from datetime import timedelta
        from django.utils import timezone
        uncertain = (match.get('name_match') in ('not_found', 'unreadable')
                     or match.get('address_match') in ('not_found', 'unreadable'))
        if getattr(_settings, 'DOC_ASSIST_ONLY_WHEN_UNCERTAIN', False) and not uncertain:
            return  # clean upload + knob on → skip the billable call
        recent = ApplicantDocument.objects.filter(
            application=app, vision_fields_run_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= getattr(_settings, 'DOC_ASSIST_RATE_LIMIT_PER_HOUR', 15):
            doc.vision_fields = {'fields': {}, 'warnings': [],
                                 'student_verdict': 'review_manually', 'error': 'rate_limited'}
            doc.vision_fields_run_at = timezone.now()
            doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
            return
        _vision.run_field_extraction_for_document(
            doc, names=names, postcode=postcode, city=city, check_address=check_address, ocr=ocr)


class DocumentDetailView(APIView):
    """DELETE the caller's document."""
    permission_classes = [SupabaseIsAuthenticated]

    def delete(self, request, pk):
        doc = ApplicantDocument.objects.filter(
            pk=pk, application__profile_id=request.user_id,
        ).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Best-effort sweep the Storage blob before deleting the DB row, so
        # an explicit "Remove" click doesn't leave an orphan object behind.
        if doc.storage_path:
            from .storage import delete_objects
            delete_objects([doc.storage_path])
        application = doc.application
        doc.delete()
        # Removing a compulsory document can drop a confirmed profile below
        # complete — un-confirm it so the status reflects reality.
        revert_if_profile_incomplete(application)
        return Response({'status': 'deleted'})


class DocumentHelpView(APIView):
    """GET a warm "Cikgu Gopal" helper message for one of the caller's documents.

    Reacts to the document's already-decided soft verdict (mismatch / unreadable) with a
    short, encouraging note that explains the fix — it never writes the student's answers
    and never sees any admin/score data (the engine only receives doc-type + verdict +
    first name). Soft by construction: nothing to help with → source 'none'; AI down or
    throttled → source 'fallback' (the frontend shows pre-written copy keyed by `verdict`).
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk):
        doc = ApplicantDocument.objects.filter(
            pk=pk, application__profile_id=request.user_id,
        ).select_related('application', 'application__profile').first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        from . import help_engine
        verdict = help_engine.verdict_for_document(doc)
        if not verdict:
            return Response({'message': '', 'source': 'none'})

        # Throttle the billable call (never block — decisions.md "throttle the AI").
        # Per-application hourly cap via the default cache; degrade to the FE fallback copy.
        from django.conf import settings as _settings
        from django.core.cache import cache
        from django.utils import timezone
        cap = getattr(_settings, 'DOC_HELP_RATE_LIMIT_PER_HOUR', 20)
        key = f'help_coach:{doc.application_id}:{timezone.now():%Y%m%d%H}'
        if cache.get(key, 0) >= cap:
            return Response({'message': '', 'source': 'fallback', 'verdict': verdict})
        cache.set(key, cache.get(key, 0) + 1, 3600)

        from .profile_engine import _resolve_language
        language = _resolve_language(doc.application, request.query_params.get('lang'))
        result = help_engine.generate_document_help(
            doc.doc_type, verdict,
            first_name=help_engine.first_name_of(doc), target_language=language,
        )
        result['verdict'] = verdict
        return Response(result)


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
        # S19: surface the bits the FE needs to render the parent-voice consent
        # text (student name + masked NRIC + pronoun) and run the live name+NRIC
        # mismatch check (parent_ic Vision OCR). Keeps the FE to one fetch.
        from .services import gender_from_nric
        profile = app.profile if app else None
        student_nric = (getattr(profile, 'nric', '') or '') if profile else ''
        gender = gender_from_nric(student_nric) if profile else None
        parent_ic = None
        if app:
            parent_ic = next(
                (d for d in app.documents.all()
                 if d.doc_type == 'parent_ic' and d.vision_run_at and not d.vision_error),
                None,
            )
        return Response({
            'is_minor': is_minor(profile) if profile else False,
            'consent_version': CONSENT_VERSION,
            'consents': ConsentSerializer(consents, many=True).data,
            # Student context for the parent-voice consent text — pure interpolation
            # values; the consent body itself lives in the FE i18n bundle.
            'student_name': (getattr(profile, 'name', '') or '') if profile else '',
            'student_nric': student_nric,
            'student_gender': gender or '',  # '' if NRIC unparseable; FE falls back to "they/their"
            # Parent IC Vision values for the FE's live mismatch check (only
            # populated when parent_ic is uploaded + OCR has run).
            'parent_ic_vision_nric': (parent_ic.vision_nric or '') if parent_ic else '',
            'parent_ic_vision_name': (parent_ic.vision_name or '') if parent_ic else '',
            # Every unmet precondition for giving consent (empty = ready). The FE
            # renders these as a checklist and keeps the consent button disabled
            # until it's empty; the POST enforces the same list (defence-in-depth).
            'blockers': consent_blockers(app) if app else ['no_application'],
        })

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        # Consent is the FINAL step: the profile must be complete, the required
        # documents uploaded, and the uploaded IC must be readable + match the
        # student's name/NRIC. Return ALL outstanding items at once so the student
        # can fix them in one pass (the FE shows the same list). Hard block.
        blockers = consent_blockers(app)
        if blockers:
            return Response(
                {'error': 'consent_not_ready', 'blockers': blockers},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if is_minor(app.profile):
            # S17: guardian must give the consent (not the minor).
            # S19: typed NRIC also required (alongside name + relationship).
            if (d['granted_by'] != 'guardian'
                    or not d['guardian_name'].strip()
                    or not d['guardian_relationship'].strip()
                    or not d['guardian_nric'].strip()):
                return Response(
                    {'error': 'A guardian must consent for applicants under 18 '
                              '(name + NRIC + relationship required).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # S17: the guardian's IC must already be uploaded — without it the
            # attested identity is unverifiable. Block at consent submit time.
            present_qs = app.documents.all()
            present = {d2.doc_type for d2 in present_qs}
            if 'parent_ic' not in present:
                return Response(
                    {'error': 'parent_ic_required',
                     'message': "Please upload your IC photo in Documents "
                                "(step 4) before signing this consent."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # S19: hard-gate the typed name + NRIC against the parent_ic Vision
            # OCR. Was a soft anomaly flag in S17; lawyers won't accept anyone
            # being able to type a fake parent name in someone else's session,
            # so this is now a 400 block. The FE pre-checks on the same data
            # so the toggle stays disabled — backend is defence-in-depth.
            from .vision import nric_match, name_match
            parent_ic = next(
                (d2 for d2 in present_qs
                 if d2.doc_type == 'parent_ic' and d2.vision_run_at and not d2.vision_error),
                None,
            )
            if parent_ic and parent_ic.vision_nric and not nric_match(
                    d['guardian_nric'], parent_ic.vision_nric):
                return Response(
                    {'error': 'parent_ic_nric_mismatch',
                     'message': "The NRIC you typed doesn't match the IC you "
                                "uploaded. Please check both."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (parent_ic and parent_ic.vision_name
                    and name_match(parent_ic.vision_name, d['guardian_name']) != 'match'):
                return Response(
                    {'error': 'parent_ic_name_mismatch',
                     'message': "The name you typed doesn't match the IC you "
                                "uploaded. Please check both."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Non-parent guardians (grandparent / legal guardian / sibling /
            # relative) MAY upload a guardianship letter, but it is no longer
            # required — the letter is optional, not a hard block.
        consent = record_consent(
            app,
            consent_type=d['consent_type'],
            locale=d['locale'],
            granted_by=d['granted_by'],
            guardian_name=d['guardian_name'],
            guardian_relationship=d['guardian_relationship'],
            guardian_nric=d.get('guardian_nric', ''),
            ip=request.META.get('REMOTE_ADDR'),
        )
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


class CronRunView(APIView):
    """Internal endpoint for Cloud Scheduler to run a whitelisted management command
    inside the already-running api service (which holds all DB/email config), so we
    avoid a separate Cloud Run Job that would have to replicate plain-env secrets.
    Auth is a shared-secret header compared in constant time. Public route, but inert
    without the secret. Never 500s the scheduler (that just causes retries)."""
    permission_classes = [AllowAny]

    JOBS = {
        'vision-outage': 'alert_vision_outage',
        'decision-emails': 'send_pending_decision_emails',
    }

    def post(self, request, job):
        import hmac
        import io
        import logging
        from django.conf import settings
        from django.core.management import call_command

        secret = getattr(settings, 'CRON_SECRET', '') or ''
        provided = request.headers.get('X-Cron-Secret', '') or ''
        if not secret or not hmac.compare_digest(secret, provided):
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        command = self.JOBS.get(job)
        if not command:
            return Response({'error': 'unknown job'}, status=status.HTTP_404_NOT_FOUND)
        out = io.StringIO()
        try:
            call_command(command, stdout=out)
        except Exception as e:  # noqa: BLE001 — report, never 500 into scheduler retries
            logging.getLogger(__name__).warning('Cron job %s failed: %s', job, e, exc_info=True)
            return Response({'job': job, 'error': str(e)[:300]}, status=status.HTTP_200_OK)
        return Response({'job': job, 'output': out.getvalue()[:2000]})


def _award_application(user_id):
    """The caller's application that currently has an OFFERED award (independent of
    the editable-funnel scoping — an awardable student may be at 'accepted')."""
    return (
        ScholarshipApplication.objects
        .filter(profile_id=user_id, sponsorships__status='offered')
        .select_related('profile').distinct().first()
    )


class StudentAwardView(APIView):
    """Phase E3 — the student's award offer. GET the current offer; POST to accept
    or decline it. The sponsor's identity is never exposed (allowlist). For a minor,
    a guardian must accept (name + NRIC + relationship), mirroring share-consent."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _award_application(request.user_id)
        offer = sponsorship_service.current_offer(app) if app else None
        return Response({
            'offer': StudentAwardSerializer(offer).data if offer else None,
            'is_minor': is_minor(app.profile) if (app and app.profile) else False,
        })

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
                ip=request.META.get('REMOTE_ADDR'),
            )
        except sponsorship_service.SponsorshipError as e:
            return Response({'error': e.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudentAwardSerializer(sponsorship).data)
