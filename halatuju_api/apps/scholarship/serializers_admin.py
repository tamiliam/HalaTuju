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


def _full_name(application):
    """The applicant's full legal name. Prefer the declaration signature (typed
    at submit, e.g. 'SHARMILA A/P SANGGAR') over profile.name — the latter is
    often the Google display name / handle ('Sharmila 1204')."""
    declared = (getattr(application, 'declaration_name', '') or '').strip()
    if declared:
        return declared
    return getattr(application.profile, 'name', '') if application.profile else ''


def _verified_email(application):
    """The applicant's VERIFIED email, for admin display. A typed contact email
    is only trusted once the student clicks "Verify" (contact_email_verified);
    until then we show the Google/Supabase login email, which is always verified.
    Returns '' if neither is available (admin then sees a dash) — we never show an
    unverified address here. NOTE: `notify_email` is deliberately NOT a fallback —
    it captures the comms email at submit and CAN be a custom unverified one."""
    p = getattr(application, 'profile', None)
    if p is None:
        return ''
    if p.contact_email and p.contact_email_verified:
        return p.contact_email
    # Fall back to the verified login email from Supabase auth.users. The admin is
    # the caller here (not the student), so the login email isn't on the JWT — we
    # look it up by the profile's supabase_user_id. One query, detail view only.
    if getattr(p, 'supabase_user_id', None):
        try:
            from apps.courses.views_admin import _fetch_auth_data
            auth = _fetch_auth_data([p.supabase_user_id]).get(p.supabase_user_id, {})
            login_email = (auth.get('email') or '').strip()
            if login_email:
                return login_email
        except Exception:  # pragma: no cover - auth.users absent in unit-test DB
            pass
    return ''


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
        return _full_name(obj)

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
    # Complete-profile view — the remaining profile-sourced fields the student
    # entered at /apply (contact, family, academic detail). All read-only mirrors.
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True, allow_blank=True)
    city = serializers.CharField(source='profile.city', read_only=True, allow_blank=True)
    preferred_state = serializers.CharField(source='profile.preferred_state', read_only=True, allow_blank=True)
    contact_phone = serializers.CharField(source='profile.contact_phone', read_only=True, allow_blank=True)
    contact_email = serializers.CharField(source='profile.contact_email', read_only=True, allow_blank=True)
    preferred_call_language = serializers.CharField(source='profile.preferred_call_language', read_only=True, allow_blank=True)
    referral_source = serializers.CharField(source='profile.referral_source', read_only=True, allow_null=True)
    guardians = serializers.JSONField(source='profile.guardians', read_only=True)
    # Academic detail (rendered SPM/STPM-aware on the admin page).
    muet_band = serializers.IntegerField(source='profile.muet_band', read_only=True)
    coq_score = serializers.FloatField(source='profile.coq_score', read_only=True)
    grades = serializers.JSONField(source='profile.grades', read_only=True)
    stpm_grades = serializers.JSONField(source='profile.stpm_grades', read_only=True)
    spm_prereq_grades = serializers.JSONField(source='profile.spm_prereq_grades', read_only=True)
    spm_a_count = serializers.SerializerMethodField()
    merit_score = serializers.SerializerMethodField()
    verified_email = serializers.SerializerMethodField()
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
            'spm_a_count', 'merit_score', 'stpm_pngk', 'household_income', 'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'address', 'postal_code', 'city', 'preferred_state',
            'contact_phone', 'contact_email', 'notify_email', 'verified_email', 'preferred_call_language', 'referral_source', 'guardians',
            # Academic detail (FE renders SPM vs STPM by qualification)
            'muet_band', 'coq_score', 'grades', 'stpm_grades', 'spm_prereq_grades',
            # "Your story" narrative (S2) + support + declaration
            'first_in_family', 'parents_occupation', 'siblings_studying_count',
            'family_context', 'daily_life', 'consent_to_contact',
            'declaration_name', 'declared_at',
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
        return _full_name(obj)

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_merit_score(self, obj):
        """The course-guide merit (0-100) used for ranking — a single number that
        rolls up grades + co-curriculum. SPM: computed academic+CoQ merit. STPM:
        the PNGK (CGPA) is the merit indicator. None if there's nothing to score."""
        p = obj.profile
        if not p:
            return None
        if p.exam_type == 'stpm':
            return p.stpm_cgpa
        grades = dict(p.grades or {})
        if not grades:
            return None
        # The engine's core uses 'history'; profiles store it as 'hist'. The
        # eligibility flow renames it before scoring, so mirror that here —
        # otherwise History is read as a fail (G) and the merit is understated.
        if 'hist' in grades:
            grades['history'] = grades.pop('hist')
        from apps.courses.engine import prepare_merit_inputs, calculate_merit_score
        s1, s2, s3 = prepare_merit_inputs(grades, getattr(p, 'stream_subjects', None) or None)
        coq = p.coq_score if p.coq_score is not None else 0
        result = calculate_merit_score(s1, s2, s3, coq)
        return round(result['final_merit'], 1)

    def get_verified_email(self, obj):
        """The verified email to display on the admin card (see _verified_email)."""
        return _verified_email(obj)

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
