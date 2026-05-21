"""Serializers for B40 Assistance Programme intake."""
from rest_framework import serializers

from .models import ScholarshipApplication


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


class ApplicationReadSerializer(serializers.ModelSerializer):
    """Output representation of an application (read-only)."""
    cohort_code = serializers.CharField(source='cohort.code', read_only=True)
    cohort_name = serializers.CharField(source='cohort.name', read_only=True)
    profile_id = serializers.CharField(
        source='profile.pk', read_only=True, allow_null=True,
    )

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
            'form_data',
        ]
