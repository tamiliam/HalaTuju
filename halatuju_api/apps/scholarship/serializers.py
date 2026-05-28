"""Serializers for B40 Assistance Programme intake."""
from rest_framework import serializers

from .models import ApplicantDocument, Consent, FundingNeed, Referee, ScholarshipApplication


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """
    Validates an incoming application. ``cohort`` and ``profile`` are resolved
    and attached by the view, not the client.

    Academic data (grades, exam type, STPM CGPA) is never accepted here — it is
    read live from the canonical HalaTuju profile. The financial fields below are
    write-only: the form may collect/refresh them, and the service syncs them
    back to the profile (their canonical home) rather than storing them on the
    application.
    """
    cohort_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text="Optional; defaults to the active open cohort",
    )
    household_income = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, write_only=True,
    )
    household_size = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, write_only=True,
    )
    receives_str = serializers.BooleanField(required=False, write_only=True)
    receives_jkm = serializers.BooleanField(required=False, write_only=True)

    # About Me + My Family (apply-form rebuild S9): the form edits these profile
    # fields inline and commits them on submit. Like the financial fields above
    # they are write-only — the service syncs them back to the canonical profile
    # (StudentProfile), never storing them on the application. NRIC is NOT here:
    # it changes only through the validated claim path (/profile/claim-nric/).
    name = serializers.CharField(required=False, allow_blank=True, write_only=True)
    school = serializers.CharField(required=False, allow_blank=True, write_only=True)
    preferred_state = serializers.CharField(required=False, allow_blank=True, write_only=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True, write_only=True)
    preferred_call_language = serializers.CharField(required=False, allow_blank=True, write_only=True)
    referral_source = serializers.CharField(required=False, allow_blank=True, write_only=True)
    guardians = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'cohort_code',
            'household_income', 'household_size', 'receives_str', 'receives_jkm',
            # About Me + My Family profile fields (write-only; synced to profile)
            'name', 'school', 'preferred_state', 'contact_phone',
            'preferred_call_language', 'referral_source', 'guardians',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact', 'form_data',
            # Plans + Support intake (Sprint 7) — all optional (blank/default on the model)
            'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
            'other_scholarships', 'other_scholarships_text',
            'help_university', 'help_scholarship', 'anything_else',
            # Plans redesign (context-aware step) — all optional/additive
            'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
            'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
            # Truthfulness declaration signature (declared_at is stamped server-side)
            'declaration_name',
        ]

    def validate_consent_to_contact(self, value):
        if not value:
            raise serializers.ValidationError(
                'Consent to be contacted is required to apply.'
            )
        return value


class FundingNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = FundingNeed
        fields = ['categories', 'funding_note', 'programme_months']


class ApplicationDetailsUpdateSerializer(serializers.Serializer):
    """PATCH payload for STEP 2 deeper-info + funding need."""
    aspirations = serializers.CharField(required=False, allow_blank=True)
    plans = serializers.CharField(required=False, allow_blank=True)
    fears = serializers.CharField(required=False, allow_blank=True)
    justification = serializers.CharField(required=False, allow_blank=True)
    funding_need = FundingNeedSerializer(required=False)
    # "Your story" guided narrative fields (S2 redesign)
    first_in_family = serializers.BooleanField(required=False)
    parents_occupation = serializers.CharField(required=False, allow_blank=True)
    siblings_studying = serializers.BooleanField(required=False)
    family_context = serializers.CharField(required=False, allow_blank=True)
    daily_life = serializers.CharField(required=False, allow_blank=True)
    # Address — stored on the profile, captured in the Story tab (S14).
    # State already came from /apply (profile.preferred_state).
    address = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)


class ApplicationReadSerializer(serializers.ModelSerializer):
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
    # Profile-derived (read live from the canonical StudentProfile).
    exam_type = serializers.CharField(source='profile.exam_type', read_only=True)
    stpm_pngk = serializers.FloatField(source='profile.stpm_cgpa', read_only=True)
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
    # The address decision/comms emails are actually sent to (resolved at submit).
    notify_email = serializers.EmailField(read_only=True)

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
            'status', 'bucket', 'shortlist_reason',
            'acknowledged_at', 'submitted_at', 'updated_at',
            'aspirations', 'plans', 'fears', 'justification',
            # "Your story" guided narrative fields (S2 redesign)
            'first_in_family', 'parents_occupation', 'siblings_studying',
            'family_context', 'daily_life',
            # Address pre-fill (profile-derived, read-only here; written via
            # ApplicationDetailsUpdateSerializer + save_application_details).
            'address', 'postal_code', 'city', 'preferred_state',
            'funding_need', 'completeness', 'notify_email',
            'form_data', 'intake_snapshot',
        ]

    def get_spm_a_count(self, obj):
        from .shortlisting import count_spm_a_grades
        return count_spm_a_grades(getattr(obj.profile, 'grades', None)) if obj.profile else 0

    def get_funding_need(self, obj):
        try:
            return FundingNeedSerializer(obj.funding_need).data
        except FundingNeed.DoesNotExist:
            return None

    def get_completeness(self, obj):
        from .services import application_completeness
        return application_completeness(obj)


# ── Documents / referee / consent (Sprint 5a) ────────────────────────────

class ApplicantDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    # S13: server-computed match verdicts (so client doesn't reimplement matchers).
    vision_nric_verdict = serializers.SerializerMethodField()
    vision_name_verdict = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantDocument
        fields = [
            'id', 'doc_type', 'original_filename', 'content_type', 'size',
            'verification_status', 'uploaded_at', 'download_url',
            # S13: Vision OCR soft-signal fields (populated only for IC).
            'vision_nric', 'vision_name', 'vision_run_at', 'vision_error',
            'vision_nric_verdict', 'vision_name_verdict',
        ]
        read_only_fields = ['vision_nric', 'vision_name', 'vision_run_at', 'vision_error']

    def get_download_url(self, obj):
        from .storage import create_signed_download_url
        return create_signed_download_url(obj.storage_path)

    def get_vision_nric_verdict(self, obj):
        """'match' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        if obj.vision_error or not obj.vision_nric:
            return 'unreadable'
        from .vision import nric_match
        return 'match' if nric_match(obj.vision_nric, getattr(obj.application.profile, 'nric', '') or '') else 'mismatch'

    def get_vision_name_verdict(self, obj):
        """'match' / 'partial' / 'mismatch' / 'unreadable' — soft signal. Empty when Vision hasn't run."""
        if obj.doc_type != 'ic' or obj.vision_run_at is None:
            return ''
        if obj.vision_error or not obj.vision_name:
            return 'unreadable'
        from .vision import name_match
        return name_match(obj.vision_name, getattr(obj.application.profile, 'name', '') or '')



class SignUploadSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True)


class DocumentCreateSerializer(serializers.Serializer):
    doc_type = serializers.ChoiceField(choices=[c[0] for c in ApplicantDocument.DOC_TYPES])
    storage_path = serializers.CharField(max_length=500)
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    content_type = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    size = serializers.IntegerField(required=False, default=0)


class RefereeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referee
        fields = ['id', 'name', 'role', 'relationship', 'phone', 'email']


class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        fields = [
            'id', 'consent_type', 'version', 'locale', 'granted_by',
            'guardian_name', 'guardian_relationship', 'is_active', 'granted_at',
        ]


class ConsentCreateSerializer(serializers.Serializer):
    consent_type = serializers.CharField(required=False, default='share_with_sponsors')
    locale = serializers.CharField(required=False, default='en')
    granted_by = serializers.ChoiceField(choices=['self', 'guardian'], required=False, default='self')
    guardian_name = serializers.CharField(required=False, allow_blank=True, default='')
    guardian_relationship = serializers.CharField(required=False, allow_blank=True, default='')
