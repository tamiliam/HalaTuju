"""The student's consent."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .. import request_ip
from ..models import Consent
from ..read_errors import ic_second_opinion_deferred
from ..serializers import ConsentCreateSerializer, ConsentSerializer
from ..services import (
    consent_blockers,
    CONSENT_VERSION,
    is_minor,
    reconcile_income_route,
    record_consent,
)
from .common import _current_application


class ConsentView(APIView):
    """GET consent status / POST record consent (guardian gate for minors)."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        app = _current_application(request.user_id)
        consents = Consent.objects.filter(application=app, is_active=True) if app else Consent.objects.none()
        # S19: surface the bits the FE needs to render the parent-voice consent
        # text (student name + masked NRIC + pronoun) and run the live name+NRIC
        # mismatch check (parent_ic Vision OCR). Keeps the FE to one fetch.
        from ..services import gender_from_nric
        profile = app.profile if app else None
        student_nric = (getattr(profile, 'nric', '') or '') if profile else ''
        gender = gender_from_nric(student_nric) if profile else None
        parent_ic = None
        if app:
            parent_ic = next(
                (d for d in app.documents.filter(superseded_at__isnull=True)
                 if d.doc_type == 'parent_ic' and d.vision_run_at and not d.vision_error),
                None,
            )
        if parent_ic is not None and ic_second_opinion_deferred(parent_ic):
            parent_ic = None    # TD-400: half a read gives no live "doesn't match"; the POST says try later
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
            present_qs = app.documents.filter(superseded_at__isnull=True)
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
            from ..identity import GUARANTOR_IC_PENDING, guarantor_mismatch   # bursary's comparison too
            parent_ic = next(
                (d2 for d2 in present_qs
                 if d2.doc_type == 'parent_ic' and d2.vision_run_at and not d2.vision_error),
                None,
            )
            why = parent_ic and guarantor_mismatch(parent_ic, d['guardian_name'], d['guardian_nric'])
            if why:   # TD-400: a value differing from a card our outage left half-read is "try later"
                return Response(
                    {'error': why,
                     'message': "Our document-check service is temporarily unavailable. Please try again later."
                                if why == GUARANTOR_IC_PENDING else
                                f"The {'NRIC' if 'nric' in why else 'name'} you typed doesn't match the IC you "
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
            ip=request_ip.signer_ip(request),
        )
        # Silently align the income route with whichever evidence actually cleared the gate (a
        # valid dispositive STR vs a complete salary cluster), so the officer's verdict reads the
        # correct route rather than a false route-mismatch red. Audit-logged, never re-blocks.
        reconcile_income_route(app, by='auto_consent')
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)
