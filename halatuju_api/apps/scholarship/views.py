"""B40 Assistance Programme API — application intake (Phase 1, Sprint 1)."""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from halatuju.throttling import UploadRateThrottle

from .models import ApplicantDocument, Consent, Referee, ScholarshipApplication
from .serializers import (
    ApplicantDocumentSerializer,
    ApplicationCreateSerializer,
    ApplicationDetailsUpdateSerializer,
    ApplicationReadSerializer,
    ConsentCreateSerializer,
    IncomeRouteSwitchSerializer,
    ConsentSerializer,
    DocumentCreateSerializer,
    GraduationMessageSerializer,
    RefereeSerializer,
    SemesterResultSerializer,
    SignUploadSerializer,
    StudentAwardSerializer,
)
from . import in_programme as in_programme_service
from . import sponsorship as sponsorship_service
from .services import (
    CONSENT_VERSION,
    IncompleteProfileError,
    OnboardingError,
    POST_SHORTLIST_EDITABLE,
    complete_onboarding,
    confirm_profile,
    consent_blockers,
    create_application,
    is_minor,
    record_consent,
    resolve_open_cohort,
    revert_if_profile_incomplete,
    save_application_details,
    score_application,
    switch_income_route,
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

        # One LIVE application per student per cohort — but an auto-closed ('expired')
        # application never blocks a fresh start (the reminder system promises the
        # student they may restart). The old expired row stays as history.
        if ScholarshipApplication.objects.filter(
            cohort=cohort, profile=profile
        ).exclude(status='expired').exists():
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
        # Prefill the new application's family roster from the profile (the durable
        # home) so the Story editor opens pre-filled; the two then two-way sync while
        # the application is open. Only when the profile has roster data and the new
        # application doesn't.
        from . import family
        if ((profile.father_name or profile.mother_name or profile.other_family_members)
                and not family.has_structured_roster(application)):
            family.copy_family_roster(profile, application)
            application.save(update_fields=list(family.PROFILE_FAMILY_FIELDS))
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


class IncomeRouteSwitchView(APIView):
    """POST /api/v1/scholarship/applications/<id>/income-route/ — student self-serve
    income route switch (STR ↔ salary) from the post-submit Action Centre.

    Own application; allowed across the whole editable + post-submit funnel
    (POST_SHORTLIST_EDITABLE). Recomputes the resolution queue (the new route's doc
    tickets appear, the old route's gap clears) and returns the refreshed income
    requirements. Deliberately separate from the broad details PATCH so it NEVER
    reverts the submission — a submitted student is not re-blocked (consent-gate-v2)."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        application = ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id).select_related('cohort', 'profile').first()
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if application.status not in POST_SHORTLIST_EDITABLE:
            return Response(
                {'error': 'Your income details can only be changed while your application is active.',
                 'code': 'not_editable'}, status=status.HTTP_403_FORBIDDEN)
        serializer = IncomeRouteSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        switch_income_route(application, route=d['income_route'],
                            earner=d.get('income_earner', ''),
                            members=d.get('income_working_members', []), by='student')
        from .income_engine import income_requirements
        return Response({'income_route': application.income_route,
                         'requirements': income_requirements(application)})


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


class ApplicationOnboardingCompleteView(APIView):
    """POST /api/v1/scholarship/applications/<id>/onboarding-complete/ — the student
    finishes post-award onboarding (F8a). Records the student_onboarding_ack consent,
    stores the questionnaire (`answers`), and stamps `onboarded_at`. 400 if the award
    hasn't been accepted yet (status must be 'sponsored')."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        application = ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id
        ).select_related('cohort', 'profile').first()
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        answers = request.data.get('answers') if isinstance(request.data, dict) else None
        if answers is not None and not isinstance(answers, dict):
            return Response({'error': 'answers must be an object', 'code': 'bad_answers'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            complete_onboarding(
                application, answers=answers, locale=application.locale,
                ip=request.META.get('REMOTE_ADDR'),
            )
        except OnboardingError as exc:
            return Response(
                {'error': 'Your award must be accepted before you can complete onboarding.',
                 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ApplicationReadSerializer(application).data)


class _OwnInProgrammeView(APIView):
    """Shared base for the F9a in-programme student endpoints: resolve the caller's
    OWN application (by JWT ``user_id``) and translate ``InProgrammeError`` to a 400
    with a ``code`` the FE can map. The service layer enforces ``status='sponsored'``
    (a student only has an in-programme lifecycle once their award is accepted)."""
    permission_classes = [SupabaseIsAuthenticated]

    def _own_application(self, request, pk):
        return ScholarshipApplication.objects.filter(
            pk=pk, profile_id=request.user_id,
        ).select_related('profile').first()


class SemesterResultView(_OwnInProgrammeView):
    """GET/POST /api/v1/scholarship/applications/<id>/semester-results/ — the student's
    in-programme latest-semester results. GET lists their own (latest first). POST
    records one (`semester`, `cgpa` 0.00–4.00, `graduated`, optional `results_slip`).
    The uploaded slip stays myNADI-only; only the derived progress band crosses to a
    sponsor. 400 `not_in_programme` until the award is accepted; 400 `bad_cgpa`."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        results = application.semester_results.all()
        return Response({'results': SemesterResultSerializer(results, many=True).data})

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        slip = None
        slip_id = data.get('results_slip')
        if slip_id not in (None, '', 0):
            slip = ApplicantDocument.objects.filter(
                pk=slip_id, application=application, doc_type='results_slip',
            ).first()
            if slip is None:
                return Response({'error': 'No such results slip on this application.',
                                 'code': 'bad_slip'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = in_programme_service.record_semester_result(
                application,
                semester=data.get('semester', ''),
                cgpa=data.get('cgpa'),
                graduated=bool(data.get('graduated', False)),
                results_slip=slip,
                note=data.get('note', ''),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(SemesterResultSerializer(result).data, status=status.HTTP_201_CREATED)


class PromotionalConsentView(_OwnInProgrammeView):
    """GET/POST/DELETE /api/v1/scholarship/applications/<id>/promotional-consent/ —
    the SEPARATE, 18+-only promotional_use consent (F9a). GET reports whether it is
    active. POST grants it (hard 400 `minor_not_allowed` if the NRIC says under 18 —
    there is no guardian path by design). DELETE withdraws it (PDPA: revocable)."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'granted': in_programme_service.has_promotional_consent(application),
            'is_minor': is_minor(application.profile),
        })

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            in_programme_service.grant_promotional_consent(
                application, locale=application.locale,
                ip=request.META.get('REMOTE_ADDR'),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'granted': True})

    def delete(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        in_programme_service.withdraw_promotional_consent(application)
        return Response({'granted': False})


class GraduationMessageView(_OwnInProgrammeView):
    """GET/POST /api/v1/scholarship/applications/<id>/graduation-message/ — the
    student's graduation thank-you (F9a). GET lists their submissions + status. POST
    submits ``text``: the structural identifier scan runs immediately — a message
    that leaks the student's own name/school/city/NRIC/phone/email comes back
    ``blocked`` with the offending ``scan_result`` fields (edit + resubmit); a clean
    one is ``pending`` myNADI approval. Never a direct channel to the sponsor."""

    def get(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        msgs = application.graduation_messages.all()
        return Response({'messages': GraduationMessageSerializer(msgs, many=True).data})

    def post(self, request, pk):
        application = self._own_application(request, pk)
        if application is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            message = in_programme_service.submit_graduation_message(
                application, raw_text=data.get('text', ''),
            )
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(GraduationMessageSerializer(message).data,
                        status=status.HTTP_201_CREATED)


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
# Income relationship-proof docs whose VERDICT depends on the Gemini-extracted structured
# fields (e.g. a birth certificate's child/mother names), so they must ALWAYS field-extract —
# never gated by the "only when uncertain" cost knob, and never skipped at upload.
RELATIONSHIP_DOC_TYPES = frozenset({'birth_certificate'})
SUPPORTING_NAME_CHECK_TYPES = frozenset({
    'results_slip', 'str', 'salary_slip', 'epf', 'offer_letter',
} | BILL_DOC_TYPES | RELATIONSHIP_DOC_TYPES)
# Free-text docs (the letter of intent) that get OCR'd into vision_fields['text'] so
# Check-2's submission review can read the student's motivation in her own words. No
# name/address check, no field extraction — just the plain text. Soft, never blocks.
TEXT_READ_DOC_TYPES = frozenset({'statement_of_intent'})

# Accepted upload formats: images (phone photos) + PDF (scan-to-PDF / digital docs
# like EPF & payslips). Everything else (video, etc.) is rejected. Before this
# there was NO format check — that's how a .mp4 IC got through (TD-080).
_ALLOWED_UPLOAD_EXTENSIONS = frozenset({
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.heic', '.heif',
})


def _is_allowed_upload(content_type, filename):
    """True iff the upload is an image or a PDF (by MIME type or file extension)."""
    ct = (content_type or '').lower().split(';')[0].strip()
    if ct.startswith('image/') or ct == 'application/pdf':
        return True
    import os
    return os.path.splitext(filename or '')[1].lower() in _ALLOWED_UPLOAD_EXTENSIONS


class DocumentListCreateView(APIView):
    """GET list / POST record the caller's documents."""
    permission_classes = [SupabaseIsAuthenticated]
    throttle_classes = [UploadRateThrottle]

    def get(self, request):
        app = _current_application(request.user_id)
        docs = ApplicantDocument.objects.filter(application=app) if app else ApplicantDocument.objects.none()
        return Response({'documents': ApplicantDocumentSerializer(docs, many=True).data})

    # EVERY document is single-instance: a re-upload REPLACES the existing copy in the
    # same slot (DB row + Supabase blob), keeping things simple — one IC, one salary slip,
    # one EPF, … per person. The sweep is scoped to the (doc_type, household_member) pair,
    # so re-uploading Mother's salary slip replaces Mother's, never Father's, and a
    # blank-member upload (student IC, STR-route doc) never touches the member-tagged ones.
    # (Retired the former str/salary_slip/epf multi-instance exception — user's call,
    # 2026-06-05; supersedes the S15 "several monthly slips" decision. See TD/decisions.)
    def _is_single_instance(self, doc_type, member):
        return True

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_doc_type = serializer.validated_data['doc_type']
        # Guardrail 0 (TD-080): accept images + PDF only — reject video/other junk.
        if not _is_allowed_upload(serializer.validated_data.get('content_type'),
                                  serializer.validated_data.get('original_filename')):
            return Response({'error': 'unsupported_format', 'code': 'unsupported_format'},
                            status=status.HTTP_400_BAD_REQUEST)
        from django.conf import settings as _settings
        # Guardrail 1: per-file size cap (the bytes go client→Storage via signed
        # URL, so this validates the reported size).
        if (serializer.validated_data.get('size') or 0) > _settings.MAX_DOC_SIZE_BYTES:
            return Response({'error': 'file_too_large', 'max_mb': _settings.MAX_DOC_SIZE_BYTES // (1024 * 1024)},
                            status=status.HTTP_400_BAD_REQUEST)
        new_member = serializer.validated_data.get('household_member', '') or ''
        # Slot model (TD-115): income docs are tagged by the household member they belong to.
        # The STR route has a single earner, so the backend AUTHORITATIVELY tags the earner's
        # income docs (str/parent_ic/salary_slip/epf) regardless of what the client sent — this
        # also slots Action-Centre / Check-2 uploads, which carry no member. The salary route
        # keeps the client's per-block member.
        _INCOME_EARNER_DOCS = {'str', 'parent_ic', 'salary_slip', 'epf'}
        str_income = (new_doc_type in _INCOME_EARNER_DOCS
                      and (getattr(app, 'income_route', '') or '').strip() == 'str')
        if str_income:
            new_member = (getattr(app, 'income_earner', '') or '').strip()
            serializer.validated_data['household_member'] = new_member
        single = self._is_single_instance(new_doc_type, new_member)
        # Slots this upload supersedes — the target (type, member), plus (STR income docs) the
        # legacy UNTAGGED copy, so a re-upload replaces the old blank instead of duplicating it.
        sweep_members = [new_member, ''] if str_income else [new_member]
        # Guardrail 2: per-application document cap. A single-instance re-upload
        # replaces an existing doc, so it doesn't count toward growth.
        replaces = (single and ApplicantDocument.objects.filter(
            application=app, doc_type=new_doc_type, household_member__in=sweep_members).exists())
        if not replaces and ApplicantDocument.objects.filter(application=app).count() >= _settings.MAX_DOCS_PER_APPLICATION:
            return Response({'error': 'doc_limit_reached', 'max': _settings.MAX_DOCS_PER_APPLICATION},
                            status=status.HTTP_400_BAD_REQUEST)
        # Single-instance re-upload REPLACES the existing copy. Order matters for data safety
        # (TD audit 2026-06-14): create the replacement row FIRST (inside a transaction), and only
        # sweep the superseded copies AFTER it is safely committed. The old order (delete blob +
        # row, THEN create) could destroy a student's existing proof — an income slip, IC or STR —
        # if the create then failed, leaving the application with no document and no recovery.
        # Snapshot the stale ids/paths BEFORE the create so the new row (same slot) is never swept.
        stale_ids, stale_paths = [], []
        if single:
            stale = list(ApplicantDocument.objects.filter(
                application=app, doc_type=new_doc_type, household_member__in=sweep_members))
            stale_ids = [d.id for d in stale]
            stale_paths = [d.storage_path for d in stale if d.storage_path]
        with transaction.atomic():
            doc = ApplicantDocument.objects.create(application=app, **serializer.validated_data)
            if stale_ids:
                ApplicantDocument.objects.filter(id__in=stale_ids).delete()
        # New row committed → only now sweep the superseded Storage blobs (an irreversible delete).
        # Best-effort: a failure here merely orphans an old blob (logged), never loses the live doc.
        if stale_paths:
            from .storage import delete_objects
            delete_objects(stale_paths)
        # iPhone HEIC → JPEG, in place, BEFORE any Vision/extraction — so OCR can read it and the
        # cockpit viewer / download URL serve a browser-renderable image (soft; no-op otherwise).
        from .imaging import convert_heic_to_jpeg
        convert_heic_to_jpeg(doc)
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
            street = getattr(profile, 'address', '') or ''   # #3: street line for the bill fallback
            check_address = doc.doc_type in BILL_DOC_TYPES
            ocr = _vision.ocr_document(doc)   # OCR once, shared by both checks
            match = _vision.run_vision_match_for_document(
                doc, names=names, postcode=postcode, city=city, street=street,
                check_address=check_address, ocr=ocr)
            if doc.doc_type in _vision.GEMINI_EXTRACT_DOC_TYPES:
                # force=True: this is the ONE document the student just uploaded in
                # response to a request — always read it now, even if the hourly
                # doc-assist cap is hit. A deferred read here is exactly what let an
                # unscanned re-upload greenlight its task (see resolution.doc_match_verdict).
                self._maybe_extract_fields(app, doc, _vision, ocr, names, postcode, city, street,
                                           check_address, match, _settings, force=True)
        # P1 (Check 2): the letter of intent — OCR its plain text so the submission
        # review can read motivation. No matching/extraction, just the text. Soft.
        elif doc.doc_type in TEXT_READ_DOC_TYPES:
            from . import vision as _vision
            _vision.read_text_document(doc)
        # S3: a new upload may clear a verdict gap → auto-resolve its ticket
        # (and link the doc), or surface a fresh ticket. Idempotent, never blocks.
        from .resolution import sync_resolution_items, resolve_doc_items_for_upload
        sync_resolution_items(app)
        # A verified offer letter silently settles a pathway the student hadn't locked
        # (undecided→decided) — no query; mirrors the apply form's storage shapes. A
        # genuine clash with a specific declared pick is left for the pathway_confirm
        # query. Soft + best-effort: never let it break the upload response.
        if doc.doc_type == 'offer_letter':
            try:
                from .services import autofill_pathway_from_offer
                autofill_pathway_from_offer(app)
            except Exception:
                logging.getLogger(__name__).warning(
                    'autofill_pathway_from_offer failed for app %s', app.id, exc_info=True)
        # Action Centre (post-submit): a clean upload also clears its OFFICER doc task,
        # and the returned verdict tells the frontend whether to surface Cikgu Gopal's
        # advice (mismatch/unreadable) or treat the task as done (ok).
        match_verdict = resolve_doc_items_for_upload(app, doc)
        data = ApplicantDocumentSerializer(doc).data
        data['match_verdict'] = match_verdict
        return Response(data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _maybe_extract_fields(app, doc, _vision, ocr, names, postcode, city, street, check_address, match, _settings, force=False):
        """Run Gemini doc-assist if the cost knob + hourly throttle allow; otherwise
        mark 'review_manually'. Never blocks the upload.

        ``force=True`` (the interactive upload) bypasses BOTH the cost knob and the
        hourly cap and always reads the document — so the file the student just
        submitted is scanned before its accept/keep-open verdict is computed, never
        deferred to a 'review_manually' state that would greenlight an unread doc.
        Abuse is still bounded by the per-request UploadRateThrottle + MAX_DOCS_PER_APPLICATION."""
        from datetime import timedelta
        from django.utils import timezone
        uncertain = (match.get('name_match') in ('not_found', 'unreadable')
                     or match.get('address_match') in ('not_found', 'unreadable'))
        # Relationship docs (birth cert) MUST extract — their verdict reads the structured
        # fields (child/mother names), which a name-presence "found" wouldn't surface. Never
        # let the cost knob skip them.
        always = doc.doc_type in RELATIONSHIP_DOC_TYPES
        if not force and getattr(_settings, 'DOC_ASSIST_ONLY_WHEN_UNCERTAIN', False) and not uncertain and not always:
            return  # clean upload + knob on → skip the billable call
        recent = ApplicantDocument.objects.filter(
            application=app, vision_fields_run_at__gte=timezone.now() - timedelta(hours=1)).count()
        if not force and recent >= getattr(_settings, 'DOC_ASSIST_RATE_LIMIT_PER_HOUR', 15):
            doc.vision_fields = {'fields': {}, 'warnings': [],
                                 'student_verdict': 'review_manually', 'error': 'rate_limited'}
            doc.vision_fields_run_at = timezone.now()
            doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
            return
        _vision.run_field_extraction_for_document(
            doc, names=names, postcode=postcode, city=city, street=street,
            check_address=check_address, ocr=ocr)


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
        # S3: keep the ticket queue consistent after a deletion (idempotent). Note
        # an already-resolved system ticket is NOT re-created if its gap returns
        # (the no-re-nag rule); the gap still shows on the officer's verdict.
        from .resolution import sync_resolution_items
        sync_resolution_items(application)
        return Response({'status': 'deleted'})


class ResolutionItemListView(APIView):
    """GET the caller's resolution queue — the IBKR-style Action Centre (S3).
    Syncs against the live verdict first, then returns the open items + the most
    recently resolved, so the student sees what's left and what just cleared."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        from .resolution import sync_resolution_items
        from .check2_queries import sync_check2_queries
        from .serializers import ResolutionItemSerializer
        app = _current_application(request.user_id)
        # Check-2 gate: NO student queries until the /application is submitted
        # (consent = profile_completed_at). Before that the student works through the
        # Step-4 tabs normally. This also hides any tickets generated prematurely
        # under the old behaviour. (Apply → Shortlist → Consent → Check 2 → Query.)
        if app is None or app.profile_completed_at is None:
            return Response({'open': [], 'resolved': []})
        from django.conf import settings as _settings
        sync_resolution_items(app)
        # Check 2 STEP 2: the AI clarify queries are held behind a flag until the
        # questions have been reviewed — while OFF, students are asked nothing new
        # (officers still review them in the cockpit).
        queries_live = getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False)
        if queries_live:
            sync_check2_queries(app)
        # The student's Action Centre shows: a reviewer's (officer) query/doc-request, the
        # Check-2 student queries (clarify + pathway confirm, source='check2'), AND the
        # "review assistant" (Check 2) asking for any MISSING compulsory document (a `doc`
        # system gap — birth cert / offer letter / earner IC / …). All flag-gated.
        # The uploaded-but-bad system tickets (*_unreadable / *_name_mismatch /
        # str_not_current) stay HIDDEN — those are reviewer-raised re-uploads, coached inline
        # by Gopal (the 2026-06-10 duplicate-noise fix). 'human' = reviewer-only.
        from .resolution import STUDENT_DOC_REQUEST_CODES

        def _student_visible(i):
            if i.kind == 'human':
                return False
            if i.source == 'system':
                return queries_live and i.code in STUDENT_DOC_REQUEST_CODES
            if i.source == 'check2':
                return queries_live
            return True   # officer items always show

        items = [i for i in app.resolution_items.all() if _student_visible(i)]
        openq = [i for i in items if i.status == 'open']
        resolved = [i for i in items if i.status == 'resolved'][:10]
        return Response({
            'open': ResolutionItemSerializer(openq, many=True).data,
            'resolved': ResolutionItemSerializer(resolved, many=True).data,
        })


class ResolutionItemResolveView(APIView):
    """POST {text} to resolve a confirm/explanation ticket the caller owns. Doc
    tickets resolve implicitly when the document is uploaded (the upload re-syncs
    the queue), so this serves the confirm/explanation kinds only."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        from .models import ResolutionItem
        from .resolution import resolve_item
        from .serializers import ResolutionItemSerializer
        item = ResolutionItem.objects.filter(
            pk=pk, application__profile_id=request.user_id, status='open',
        ).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .services import querying_locked
        if querying_locked(item.application):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        if item.kind == 'doc':
            return Response({'error': 'upload_doc_instead', 'doc_type': item.doc_type},
                            status=status.HTTP_400_BAD_REQUEST)
        if item.kind == 'human':   # reviewer-only — not the student's to answer
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        text = (request.data.get('text') or '').strip()
        if item.kind in ('explanation', 'clarify') and not text:
            return Response({'error': 'text_required'}, status=status.HTTP_400_BAD_REQUEST)
        # Phase 2 (D2): on a typed answer, Cikgu Gopal nudges ONLY when it is TOTALLY
        # off-topic — keep the task open and return his one-sentence steer, don't resolve.
        # Flag-gated + AI-off-safe (judge defaults to accept). 'pathway_confirm' is a
        # one-tap Yes (its 'confirmed' text isn't a free answer, so it's never judged).
        if text and item.code != 'pathway_confirm':
            from django.conf import settings as _settings
            if getattr(_settings, 'CHECK2_ANSWER_RELEVANCE_ENABLED', False):
                from .help_engine import judge_answer_relevance
                question = (request.data.get('question') or item.prompt or '').strip()
                verdict = judge_answer_relevance(question, text)
                if not verdict['on_topic']:
                    return Response({'resolved': False, 'nudge': verdict['nudge']})
        resolve_item(item, text=text, by='student')
        # The pathway confirmation is the one 'confirm' that also WRITES state: the
        # student saying Yes settles their final chosen pathway (no human officer).
        if item.code == 'pathway_confirm':
            from .services import confirm_pathway
            confirm_pathway(item.application)
        return Response(ResolutionItemSerializer(item).data)


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


class IncomeClusterHelpView(APIView):
    """GET the SINGLE "Cikgu Gopal" message for one earner's whole income cluster.

    Income is a cluster (the earner's IC + their STR / payslip / EPF + their relationship
    doc), so unlike the single-document facts the coach speaks once per EARNER, anchored at
    the foot of the cluster — even before the IC is uploaded. ``member`` is the household
    member (father / mother / guardian / brother / sister). Same soft contract + hourly
    throttle as the per-document helper; nothing here is admin/score data."""
    permission_classes = [SupabaseIsAuthenticated]

    _MEMBERS = ('father', 'mother', 'guardian', 'brother', 'sister')

    def get(self, request, member):
        if member not in self._MEMBERS:
            return Response({'message': '', 'source': 'none'})
        app = _current_application(request.user_id)
        if app is None:
            return Response({'message': '', 'source': 'none'})

        from . import help_engine
        from .income_engine import income_cluster_advice
        verdict = income_cluster_advice(app, member)
        if not verdict:
            return Response({'message': '', 'source': 'none'})

        from django.conf import settings as _settings
        from django.core.cache import cache
        from django.utils import timezone
        cap = getattr(_settings, 'DOC_HELP_RATE_LIMIT_PER_HOUR', 20)
        key = f'help_coach:{app.id}:{timezone.now():%Y%m%d%H}'
        if cache.get(key, 0) >= cap:
            return Response({'message': '', 'source': 'fallback', 'verdict': verdict})
        cache.set(key, cache.get(key, 0) + 1, 3600)

        from .profile_engine import _resolve_language
        language = _resolve_language(app, request.query_params.get('lang'))
        first_name = (getattr(getattr(app, 'profile', None), 'name', '') or '').strip().split(' ')[0]
        # Non-sensitive specifics so the coach names the RIGHT member + document (e.g. "your
        # mother's MyKad alongside her STR document"), not the generic father/payslip example.
        from .income_engine import (_cluster_proof_identity, relationship_doc_for,
                                     _member_ic_doc, student_income_ic_check)
        _MEMBER_LABEL = {'father': 'father', 'mother': 'mother', 'guardian': 'legal guardian',
                         'brother': 'elder brother', 'sister': 'elder sister'}
        _DOC_LABEL = {'str': 'STR document', 'salary_slip': 'salary slip', 'epf': 'EPF statement',
                      'birth_certificate': 'birth certificate', 'guardianship_letter': 'guardianship letter'}
        proof_kind, _pn, _pi = _cluster_proof_identity(app, member)
        rel_doc = relationship_doc_for(member)
        # Is the earner's MyKad already corroborated by their income document? If so, a
        # relationship clash is the BC's fault, not the IC's — let the coach commit to that
        # (drop the now-pointless "re-check the MyKad" line).
        _ic_doc = _member_ic_doc(app, member)
        _icc = student_income_ic_check(_ic_doc) if _ic_doc else None
        ic_matches_income_doc = bool(_icc and 'match' in
                                     (_icc.get('proof_name_status'), _icc.get('proof_nric_status')))
        # income_proof_needed asks specifically for the salary slip (the proof not yet uploaded,
        # so _cluster_proof_identity has nothing to report). The relationship-mismatch message is
        # member-aware: a mother's clash is between her birth certificate and her MyKad, so name
        # the rel doc there too (not just for the "needed/unreadable" verdicts).
        income_doc = ('salary slip' if verdict == 'income_proof_needed'
                      else _DOC_LABEL.get(proof_kind, ''))
        # #4: on the STR route the salary slip / EPF is OPTIONAL (the STR is the income proof), so a
        # wrong-person proof there is an extra file to REMOVE, not a required one to re-upload.
        _route = (getattr(app, 'income_route', '') or '').strip()
        context = {
            'member': _MEMBER_LABEL.get(member, member),
            'income_doc': income_doc,
            'rel_doc': (_DOC_LABEL.get(rel_doc, '') if verdict in (
                'income_rel_doc_needed', 'income_rel_doc_unreadable',
                'income_relationship_mismatch') else ''),
            'ic_matches_income_doc': (ic_matches_income_doc
                                      and verdict == 'income_relationship_mismatch'),
            'income_proof_optional': (_route == 'str'
                                      and verdict == 'income_proof_person_mismatch'),
        }
        result = help_engine.generate_document_help(
            'income_cluster', verdict, first_name=first_name, target_language=language,
            context=context,
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
        'application-reminders': 'send_application_reminders',
        'query-emails': 'send_due_query_emails',
        'query-reminders': 'send_query_reminders',
        'autogenerate-profiles': 'autogenerate_profiles',
        'sponsor-realtime': 'send_sponsor_realtime',   # F3: hourly
        'sponsor-digests': 'send_sponsor_digests',     # F3: weekly
        'purge-referrals': 'purge_sponsor_referrals',  # F4: daily PDPA purge (60-day)
        'rescore-pending': 'rescore_pending_decisions',  # on-demand after a policy change
        'backup-documents': 'backup_documents',  # weekly: mirror the private doc bucket to GCS
        'refresh-reminder': 'send_refresh_reminder',  # annual: nudge the admin to refresh the course catalogue
        'course-data-check': 'course_data_check',  # weekly: READ-ONLY audit + link reachability for the dashboard
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
