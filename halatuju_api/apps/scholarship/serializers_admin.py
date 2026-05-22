"""Admin-facing serializers for the B40 Assistance Programme (Sprint 6a)."""
from rest_framework import serializers

from .models import FundingNeed, ScholarshipApplication, SponsorProfile
from .serializers import (
    ApplicantDocumentSerializer,
    ConsentSerializer,
    FundingNeedSerializer,
    RefereeSerializer,
)


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

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'profile_id', 'cohort_code', 'qualification',
            'spm_a_count', 'stpm_pngk', 'status', 'bucket', 'shortlist_reason',
            'submitted_at',
        ]

    def get_name(self, obj):
        return getattr(obj.profile, 'name', '') if obj.profile else ''


class AdminApplicationDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    school = serializers.SerializerMethodField()
    funding_need = serializers.SerializerMethodField()
    sponsor_profile = serializers.SerializerMethodField()
    documents = ApplicantDocumentSerializer(many=True, read_only=True)
    referees = RefereeSerializer(many=True, read_only=True)
    consents = ConsentSerializer(many=True, read_only=True)

    class Meta:
        model = ScholarshipApplication
        fields = [
            'id', 'name', 'school', 'profile_id', 'qualification',
            'spm_a_count', 'stpm_pngk', 'household_income', 'household_size',
            'receives_str', 'receives_jkm', 'intended_pathway', 'intends_tertiary_2026',
            'aspirations', 'plans', 'fears', 'justification',
            'status', 'bucket', 'shortlist_reason', 'submitted_at',
            'funding_need', 'documents', 'referees', 'consents', 'sponsor_profile',
        ]

    def get_name(self, obj):
        return getattr(obj.profile, 'name', '') if obj.profile else ''

    def get_school(self, obj):
        return getattr(obj.profile, 'school', '') if obj.profile else ''

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
