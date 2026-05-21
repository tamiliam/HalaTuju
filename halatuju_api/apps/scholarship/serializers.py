"""Serializers for B40 Assistance Programme intake."""
from rest_framework import serializers

from .models import FundingNeed, ScholarshipApplication


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
