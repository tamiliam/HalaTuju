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
    SponsorInterestSerializer,
)
from .emails import send_sponsor_interest_admin_email
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
        # Supporting docs: soft check that the student's OR a parent/guardian's
        # name appears (and, for utility bills, the home address). Never blocks;
        # surfaced to the student + the interviewer.
        elif doc.doc_type in SUPPORTING_NAME_CHECK_TYPES:
            from .vision import run_vision_match_for_document
            profile = app.profile
            names = [getattr(profile, 'name', '') or '']
            names += [g.get('name', '') for g in (getattr(profile, 'guardians', None) or [])
                      if isinstance(g, dict)]
            run_vision_match_for_document(
                doc,
                names=[n for n in names if n],
                postcode=getattr(profile, 'postal_code', '') or '',
                city=getattr(profile, 'city', '') or '',
                check_address=doc.doc_type in BILL_DOC_TYPES,
            )
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
        # Best-effort sweep the Storage blob before deleting the DB row, so
        # an explicit "Remove" click doesn't leave an orphan object behind.
        if doc.storage_path:
            from .storage import delete_objects
            delete_objects([doc.storage_path])
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
            # S17: for non-parent relationships, the guardianship letter (court
            # order OR parent's written authorisation) must be uploaded too.
            from .services import needs_guardianship_letter
            if (needs_guardianship_letter(d['guardian_relationship'])
                    and 'guardianship_letter' not in present):
                return Response(
                    {'error': 'guardianship_letter_required',
                     'message': "Because you are not the applicant's father "
                                "or mother, please also upload the guardianship "
                                "letter or parent's written authorisation "
                                "before signing."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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


class SponsorInterestView(APIView):
    """POST /api/v1/sponsor-interest/ — public 'register interest in sponsoring'
    lead capture (no auth; sponsors have no self-serve account yet). Stores the
    lead + notifies the admin. Browse-first: this is an open endpoint."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SponsorInterestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        interest = serializer.save()
        send_sponsor_interest_admin_email(
            name=interest.name, email=interest.email,
            organisation=interest.organisation, message=interest.message,
        )
        return Response(SponsorInterestSerializer(interest).data, status=status.HTTP_201_CREATED)
