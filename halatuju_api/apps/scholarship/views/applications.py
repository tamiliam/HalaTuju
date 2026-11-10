"""The student's own application: create / read, income route, confirm, onboarding."""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .. import gift_sources, request_ip
from ..models import ScholarshipApplication
from ..serializers import (
    ApplicationCreateSerializer,
    ApplicationDetailsUpdateSerializer,
    ApplicationReadSerializer,
    IncomeRouteSwitchSerializer,
)
from ..services import (
    AmbiguousOpenCohort,
    apply_gate,
    complete_onboarding,
    confirm_profile,
    IncompleteProfileError,
    OnboardingError,
    POST_SHORTLIST_EDITABLE,
    resolve_open_cohort,
    revert_if_profile_incomplete,
    RoundFinishedError,
    save_application_details,
    score_application,
    submit_application,
    switch_income_route,
)
from .common import _get_profile

logger = logging.getLogger(__name__)


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

        # PF-1: refuse rather than guess. `resolve_open_cohort` raises when more than one round is
        # open and nothing named which — filing the student under an arbitrary organisation is
        # silent and permanent (tenancy is denormalised onto the application at save), whereas an
        # error here is a support message. Logged at ERROR because it is an operator problem, not
        # a student one: either two rounds are open that should not both be, or the apply link
        # they followed lost its programme code.
        try:
            cohort = resolve_open_cohort(
                validated.get('cohort_code', ''), validated.get('programme_code', ''),
            )
        except AmbiguousOpenCohort as exc:
            logger.error('PF-1 ambiguous open cohort at apply: %s', exc)
            return Response(
                {
                    'error': 'We could not tell which programme this application is for.',
                    'code': 'programme_required',
                },
                status=status.HTTP_409_CONFLICT,
            )
        if cohort is None:
            return Response(
                {'error': 'No open application round is currently available.'},
                status=status.HTTP_409_CONFLICT,
            )
        # Intake gate: a closed cohort accepts no NEW applications. resolve_open_cohort
        # already filters is_open on the default path, but an explicit cohort_code skips
        # that — so re-check here so the gate can't be bypassed. Existing applicants
        # never reach this endpoint again (they continue via their own application).
        if not cohort.is_open:
            return Response(
                {'error': 'applications_closed', 'code': 'applications_closed'},
                status=status.HTTP_409_CONFLICT,
            )

        # One application in play (anywhere, until M2), none twice in one round (owner, TD-337).
        # The rule, its embargo masking and its order live in `services/apply_gate.py` — the page
        # asks the same function before the form (`views_apply_gate`), so the two cannot disagree.
        verdict = apply_gate.apply_verdict(profile, cohort)
        if not verdict.allowed:
            return Response({'error': apply_gate.REFUSAL[verdict.reason], 'code': verdict.reason},
                            status=status.HTTP_409_CONFLICT)
        # Who referred you: blank, or a fixed choice / source THIS gift offers — else refused, nothing written.
        if not gift_sources.is_offered(cohort.programme, validated.get('referral_source')):
            return Response({'error': 'referral_source_not_offered', 'code': 'referral_source_not_offered'},
                            status=status.HTTP_400_BAD_REQUEST)

        lang = request.data.get('lang') or 'en'
        to_email = profile.contact_email or supabase_user.get('email') or ''
        application, refused = submit_application(   # TD-348 / TD-351: the gate re-asked under a lock
            profile=profile, cohort=cohort, validated_data=validated, to_email=to_email, lang=lang)
        if refused:   # a submit that ran at the same moment got in first: 409, never a 500
            return Response({'error': apply_gate.REFUSAL[refused], 'code': refused},
                            status=status.HTTP_409_CONFLICT)
        # Prefill the new application's family roster from the profile (the durable
        # home) so the Story editor opens pre-filled; the two then two-way sync while
        # the application is open. Only when the profile has roster data and the new
        # application doesn't.
        from .. import family
        if ((profile.father_name or profile.mother_name or profile.other_family_members)
                and not family.has_structured_roster(application)):
            family.copy_family_roster(profile, application)
            application.save(update_fields=list(family.PROFILE_FAMILY_FIELDS))
        # The apply Plans step writes the chosen pathway onto the APPLICATION; mirror it
        # back onto the profile (its durable home) so /profile shows + can edit it, and
        # the two start two-way-in-sync.
        if family.has_pathway(application):
            family.copy_pathway(application, profile)
            profile.save(update_fields=list(family.PROFILE_PATHWAY_FIELDS))
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
        from ..income_engine import income_requirements
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
        except RoundFinishedError:
            # ⚠ NOT an `incomplete_profile` — nothing the student uploads changes this, so the
            # screen must not send them back to the documents. The round is over.
            return Response(
                {'error': 'This intake round has closed and is no longer accepting submissions.',
                 'code': 'round_finished'},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
                ip=request_ip.signer_ip(request),
            )
        except OnboardingError as exc:
            return Response(
                {'error': 'Your award must be accepted before you can complete onboarding.',
                 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ApplicationReadSerializer(application).data)
