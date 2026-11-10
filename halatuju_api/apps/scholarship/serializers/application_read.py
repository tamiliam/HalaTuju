"""The student-facing read of an application."""

from rest_framework import serializers
from apps.courses.exam_questions import ResultsHeldField, spm_grades_for
from ..serializers_maintenance import StudentMaintenanceFields
from ..models import FundingNeed, ScholarshipApplication
from .application import FundingNeedSerializer


class ApplicationReadSerializer(StudentMaintenanceFields, serializers.ModelSerializer):
    """
    Output representation of an application (read-only).

    Academic + financial fields are derived live from the linked profile (the
    single source of truth), never stored on the application. ``intake_snapshot``
    is the frozen audit copy of what was declared at submit time.
    """
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    cohort_name = serializers.CharField(source='cohort.name', read_only=True)
    profile_id = serializers.CharField(
        source='profile.pk', read_only=True, allow_null=True,
    )
    exam_type = ResultsHeldField()   # live: the results we HOLD, not the declared exam (TD-218)
    stpm_pngk = serializers.FloatField(source='profile.stpm_pngk', read_only=True)   # CGPA sprint C2
    household_income = serializers.IntegerField(source='profile.household_income', read_only=True)
    household_size = serializers.IntegerField(source='profile.household_size', read_only=True)
    receives_str = serializers.BooleanField(source='profile.receives_str', read_only=True)
    receives_jkm = serializers.BooleanField(source='profile.receives_jkm', read_only=True)
    # Address pre-fill for the Story tab (writes round-trip via the details
    # serializer below; state already comes from /apply as preferred_state).
    address = serializers.CharField(source='profile.address', read_only=True, allow_blank=True)
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True, allow_blank=True)
    city = serializers.CharField(source='profile.city', read_only=True, allow_blank=True)
    preferred_state = serializers.CharField(source='profile.preferred_state', read_only=True, allow_blank=True)
    spm_a_count = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    income_shown = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    # The address decision/comms emails are actually sent to (resolved at submit).
    notify_email = serializers.EmailField(read_only=True)
    # Pre-fills the Vircle setup task's mobile field (the student may correct it there if they
    # registered with Vircle under a different number).
    contact_phone = serializers.CharField(
        source='profile.contact_phone', read_only=True, allow_blank=True,
    )

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'cohort_code', 'cohort_name', 'profile_id',
            'exam_type', 'spm_a_count', 'stpm_pngk',
            'household_income', 'household_size',
            'receives_str', 'receives_jkm',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact',
            'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
            'other_scholarships', 'other_scholarships_text',
            'help_university', 'help_scholarship', 'anything_else', 'mentoring_candidate',
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            'declaration_name', 'declared_at',
            # ⚠ NO `shortlist_reason` (request #31 review, 2026-10-08). It is the ENGINE'S note for
            # staff ("born in Selangor (IC code 10); this intake accepts Sabah") and was served here
            # before the decision was revealed; no student screen ever read it. Staff read it on
            # the admin serializer.
            'status', 'bucket',
            # Maintenance S1: served answers, never the raw sub-state (serializers_maintenance.py).
            'support_paused', 'in_maintenance', 'has_file', 'can_record_results',
            # S6: closure bucket — lets the in-programme page show the right "programme
            # complete" (graduated/completed) vs neutral closed copy.
            'closure_reason',
            # TD-352: a 'closed' case is in-programme (the thank-you relay) only if it was ever
            # FUNDED — an officer may now close a stalled case before any award.
            'active_at',
            'acknowledged_at', 'submitted_at', 'updated_at',
            # Phase C: confirm-submit timestamp + the admin's request-more-docs note
            'profile_completed_at', 'info_request_note', 'info_requested_at',
            # B40 Phase E/F (F8a): post-award onboarding completion timestamp
            'onboarded_at',
            'aspirations', 'plans', 'fears', 'justification',
            # "Your story" guided narrative fields (S2 redesign)
            'first_in_family', 'parents_occupation',
            'siblings_studying_count',
            'family_context', 'daily_life',
            # Structured family roster (redesign 2026-06) — the new inputs.
            'father_name', 'father_occupation', 'father_occupation_other',
            'mother_name', 'mother_occupation', 'mother_occupation_other',
            'other_family_members',
            # Income Check-1 wizard answers.
            'income_route', 'income_earner', 'income_working_members', 'income_declared',
            'income_nonearning', 'earner_work_status',
            'household_other_earners', 'siblings_in_school', 'siblings_in_tertiary',
            # Address pre-fill (profile-derived, read-only here; written via
            # ApplicationDetailsUpdateSerializer + save_application_details).
            'address', 'postal_code', 'city', 'preferred_state',
            'funding_need', 'completeness', 'requirements', 'notify_email', 'contact_phone',
            'income_shown',
            'form_data', 'intake_snapshot',
        ]

    def get_status(self, obj):
        # The student-facing status is deliberately MASKED (an embargoed decline reads as the
        # stage it was declined from; 'recommended' reads as 'interviewed'). The rule and its
        # reasons live in `student_status.py`, its one home since 2026-10-05: the apply gate
        # (`services/apply_gate.py`) decides on the SAME answer, so the embargo cannot leak there.
        from ..student_status import student_facing_status
        return student_facing_status(obj)

    def get_income_shown(self, obj):
        """TD-262 F2 — the per-earner answer (``income_shown.py``), served to the student's own
        screen in exactly the shape the officer's payload serves. The reason is at that module.

        ⚠ THE MEMBERS HER SCREEN CAN ASK ABOUT, not all five (audit 2026-09-21) — three queries
        each, on a serializer the LIST also runs. `student_income_members` carries the reasoning
        and the proof that an absent key is safe."""
        from ..income_shown import income_shown_map, student_income_members
        return income_shown_map(obj, student_income_members(obj))

    def get_spm_a_count(self, obj):
        from ..shortlisting import count_spm_a_grades
        return count_spm_a_grades(spm_grades_for(obj.profile))   # tertiary: SPM prereq only (#62)

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_completeness(self, obj):
        from ..services import application_completeness
        return application_completeness(obj)

    def get_requirements(self, obj):
        """What THIS programme asks for — `{'documents': {...}, 'questions': {...}}`, each block
        `{'required': [...], 'optional': [...]}`.

        The Documents tab renders from this, so a document an organisation has not asked for is
        not drawn at all, and one it has promoted to required carries the marker. Before Sprint 3b
        the web app decided that for itself from a hard-coded list, and the two disagreed in
        production: `COMPULSORY_DOC_TYPES` said identity card + results slip while the submission
        gate also required the offer letter and the income route. A student could complete every
        card the front end marked compulsory and still be blocked.

        `income_proof` is an AGGREGATE, not a card: it switches the whole income route engine on
        or off (see `requirements.DOCUMENT_AGGREGATES`). The Documents tab reads it as "render the
        income section", which is a membership test, not a re-implementation of the route rules —
        those stay entirely on the server.

        Sprint 4 added `questions`: the story / funding / address parts of the Step-4 wizard
        render (and mark compulsory) from it, exactly as the Documents tab reads `documents`.
        A code that appears in neither list is not asked — the front end does not draw it, and
        `application_completeness` does not gate on it. The codes are a closed vocabulary (the
        catalogue selects from it; an organisation never authors a question), so the front end
        may key rendering on them the way `DocType` keys the document cards.

        Cheap: `requirements.resolve` is one query per kind, memoised on the instance, and
        `get_completeness` above has already paid for it on every application.
        """
        from .. import requirements
        return {
            'documents': requirements.payload_for(obj, 'document'),
            'questions': requirements.payload_for(obj, 'question'),
        }
