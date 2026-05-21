"""Serializers for B40 Assistance Programme intake."""
from rest_framework import serializers

from .models import ApplicantDocument, Consent, FundingNeed, Referee, ScholarshipApplication


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """
    Validates an incoming application. ``cohort`` and ``profile`` are resolved
    and attached by the view, not the client.
    """
    cohort_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text="Optional; defaults to the active open cohort",
    )

    class Meta:
        model = ScholarshipApplication
        fields = [
            'cohort_code',
            'qualification', 'spm_a_count', 'stpm_pngk',
            'household_income', 'household_size',
            'receives_str', 'receives_jkm',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact', 'form_data',
        ]

    def validate_consent_to_contact(self, value):
        if not value:
            raise serializers.ValidationError(
                'Consent to be contacted is required to apply.'
            )
        return value


class FundingNeedSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(read_only=True)

    class Meta:
        model = FundingNeed
        fields = [
            'tuition_gap', 'laptop', 'hostel', 'transport', 'books',
            'monthly_allowance', 'allowance_months', 'other', 'other_desc', 'total',
        ]


class ApplicationDetailsUpdateSerializer(serializers.Serializer):
    """PATCH payload for STEP 2 deeper-info + funding need."""
    aspirations = serializers.CharField(required=False, allow_blank=True)
    plans = serializers.CharField(required=False, allow_blank=True)
    fears = serializers.CharField(required=False, allow_blank=True)
    justification = serializers.CharField(required=False, allow_blank=True)
    funding_need = FundingNeedSerializer(required=False)


class ApplicationReadSerializer(serializers.ModelSerializer):
    """Output representation of an application (read-only)."""
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    cohort_name = serializers.CharField(source='cohort.name', read_only=True)
    profile_id = serializers.CharField(
        source='profile.pk', read_only=True, allow_null=True,
    )
    funding_need = serializers.SerializerMethodField()
    completeness = serializers.SerializerMethodField()

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'cohort_code', 'cohort_name', 'profile_id',
            'qualification', 'spm_a_count', 'stpm_pngk',
            'household_income', 'household_size',
            'receives_str', 'receives_jkm',
            'intended_pathway', 'intends_tertiary_2026',
            'consent_to_contact',
            'status', 'bucket', 'shortlist_reason',
            'acknowledged_at', 'submitted_at', 'updated_at',
            'aspirations', 'plans', 'fears', 'justification',
            'funding_need', 'completeness',
            'form_data',
        ]

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

    class Meta:
        model = ApplicantDocument
        fields = [
            'id', 'doc_type', 'original_filename', 'content_type', 'size',
            'verification_status', 'uploaded_at', 'download_url',
        ]

    def get_download_url(self, obj):
        from .storage import create_signed_download_url
        return create_signed_download_url(obj.storage_path)


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
