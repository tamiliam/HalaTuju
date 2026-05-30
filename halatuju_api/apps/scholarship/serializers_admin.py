"""Admin-facing serializers for the B40 Assistance Programme (Sprint 6a)."""
from rest_framework import serializers

from .models import (
    FundingNeed, InterviewSession, ScholarshipApplication, SponsorProfile,
)
from .serializers import (
    ApplicantDocumentSerializer,
    ConsentSerializer,
    FundingNeedSerializer,
    RefereeSerializer,
)


class InterviewSessionSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.CharField(source='interviewer.name', read_only=True, default=None)

    class Meta:
        model = InterviewSession
        fields = [
            'id', 'status', 'findings', 'rubric', 'overall_note',
            'interviewer_name', 'started_at', 'submitted_at', 'updated_at',
        ]


class SponsorProfileSerializer(serializers.ModelSerializer):
    current_markdown = serializers.CharField(read_only=True)

    class Meta:
        model = SponsorProfile
        fields = [
            'draft_markdown', 'edited_markdown', 'current_markdown', 'status',
            'model_used', 'generated_at', 'published_at', 'updated_at',
        ]


class AdminApplicationListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    # Academic data is read live from the canonical profile, not the application.
    qualification = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'profile_id', 'cohort_code', 'qualification',
            'spm_a_count', 'stpm_pngk', 'status', 'bucket', 'shortlist_reason',
            'submitted_at', 'profile_completed_at',
            'assigned_to_id', 'assigned_to_name',
        ]

    def get_name(self, obj):
        return getattr(obj.profile, 'name', '') if obj.profile else ''

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0


class AdminApplicationDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()
    # NRIC shown in full so the admin can compare it to the uploaded MyKad at verify time.
    nric = serializers.CharField(source='profile.nric', read_only=True)
    nric_verified = serializers.BooleanField(source='profile.nric_verified', read_only=True)
    # Academic + financial data is read live from the canonical profile.
    qualification = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
    household_income = serializers.IntegerField(source='profile.household_income', read_only=True)
    household_size = serializers.IntegerField(source='profile.household_size', read_only=True)
    receives_str = serializers.BooleanField(source='profile.receives_str', read_only=True)
    receives_jkm = serializers.BooleanField(source='profile.receives_jkm', read_only=True)
    # Profile-stored address (S14) — surfaced so the admin Vision card can show
    # it alongside `vision_address` (the MyKad-read address) for eyeball compare.
    address = serializers.CharField(source='profile.address', read_only=True, allow_blank=True)
    spm_a_count = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    sponsor_profile = serializers.SerializerMethodField()
    # Pre-interview deterministic flag list (S16 Phase A). Each entry is
    # {code, params}; the frontend resolves human copy from its i18n bundle.
    anomalies = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()
    interview_session = serializers.SerializerMethodField()
    assigned_to_id = serializers.IntegerField(source='assigned_to.id', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, default=None)
    documents = ApplicantDocumentSerializer(many=True, read_only=True)
    referees = RefereeSerializer(many=True, read_only=True)
    consents = ConsentSerializer(many=True, read_only=True)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'school', 'nric', 'nric_verified', 'profile_id', 'qualification',
            'spm_a_count', 'stpm_pngk', 'household_income', 'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'address',
            'status', 'bucket', 'shortlist_reason', 'submitted_at',
            # Phase C handoff + interview funnel
            'profile_completed_at', 'completeness', 'interview_session',
            'assigned_to_id', 'assigned_to_name', 'info_request_note', 'info_requested_at',
            # S11a verify-&-accept + mentoring
            'mentoring_candidate', 'verified_at', 'verified_by', 'verify_checklist',
            # S10 plans/support intake (surface for the admin review)
            'pathways_considered', 'top_choices', 'upu_status', 'field_of_study',
            'other_scholarships', 'other_scholarships_text', 'help_university',
            'help_scholarship', 'anything_else',
            # Plans redesign — surface the structured pathway plan for admin/coordinator
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            'funding_need', 'documents', 'referees', 'consents', 'sponsor_profile',
            'anomalies',
            'intake_snapshot',
        ]

    def get_name(self, obj):
        return getattr(obj.profile, 'name', '') if obj.profile else ''

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_sponsor_profile(self, obj):
        try:
            return SponsorProfileSerializer(obj.sponsor_profile).data
        except SponsorProfile.DoesNotExist:
            return None

    def get_anomalies(self, obj):
        """S16 Phase A: deterministic pre-interview flag list. Pure rules,
        no LLM calls. Returns ``[]`` when nothing flags."""
        from .anomaly_engine import detect_anomalies
        return detect_anomalies(obj)

    def get_completeness(self, obj):
        """Phase C: the 7-part completeness breakdown, so the admin can see
        exactly which steps a student still owes (drives the accept-gate UI)."""
        from .services import application_completeness
        return application_completeness(obj)

    def get_interview_session(self, obj):
        """Phase C: the latest interview session (draft or submitted), or None."""
        session = obj.interview_sessions.first()  # ordering = -created_at
        return InterviewSessionSerializer(session).data if session else None
