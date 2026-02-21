"""
Serializers for the courses API.
"""
from rest_framework import serializers
from .models import Course, Institution, CourseRequirement, CourseTag, MascoOccupation


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""

    class Meta:
        model = Course
        fields = [
            'course_id', 'course', 'wbl', 'level', 'department',
            'field', 'frontend_label', 'semesters',
            'headline', 'headline_en', 'description', 'description_en',
        ]


class MascoOccupationSerializer(serializers.ModelSerializer):
    """Serializer for MASCO occupation."""

    class Meta:
        model = MascoOccupation
        fields = ['masco_code', 'job_title', 'emasco_url']


class InstitutionSerializer(serializers.ModelSerializer):
    """Serializer for Institution model."""

    class Meta:
        model = Institution
        fields = [
            'institution_id', 'institution_name', 'acronym', 'type',
            'category', 'subcategory', 'state', 'address', 'phone',
            'url', 'latitude', 'longitude'
        ]


class EligibilityRequestSerializer(serializers.Serializer):
    """
    Serializer for eligibility check request.

    Validates the student profile data sent to the eligibility endpoint.
    Accepts multiple input formats and normalizes to engine-expected values.
    """
    # Frontend subject IDs → engine internal keys
    GRADE_KEY_MAP = {
        'BM': 'bm',
        'BI': 'eng',
        'SEJ': 'hist',
        'MAT': 'math',
        'PHY': 'phy',
        'CHE': 'chem',
        'BIO': 'bio',
        'AMT': 'addmath',
        'PI': 'islam',
        'PM': 'moral',
        'SN': 'sci',
        'ECO': 'ekonomi',
        'ACC': 'poa',
        'BUS': 'business',
        'GEO': 'geo',
    }

    grades = serializers.DictField(
        child=serializers.CharField(),
        required=True,
        help_text="SPM grades: {'BM': 'A+', 'MAT': 'B', ...}"
    )
    gender = serializers.CharField(default='Lelaki')
    nationality = serializers.CharField(default='Warganegara')
    colorblind = serializers.BooleanField(default=False, required=False)
    disability = serializers.BooleanField(default=False, required=False)
    other_tech = serializers.BooleanField(default=False)
    other_voc = serializers.BooleanField(default=False)

    def validate_grades(self, value):
        """Map frontend subject IDs to engine internal keys."""
        mapped = {}
        for key, grade in value.items():
            engine_key = self.GRADE_KEY_MAP.get(key, key.lower())
            mapped[engine_key] = grade
        return mapped

    def validate_gender(self, value):
        """Normalize gender to engine format."""
        mapping = {
            'male': 'Lelaki',
            'female': 'Perempuan',
            'lelaki': 'Lelaki',
            'perempuan': 'Perempuan',
            'ஆண்': 'Lelaki',
            'பெண்': 'Perempuan',
        }
        return mapping.get(value.lower(), value)

    def validate_nationality(self, value):
        """Normalize nationality to engine format."""
        mapping = {
            'malaysian': 'Warganegara',
            'non_malaysian': 'Bukan Warganegara',
            'non-malaysian': 'Bukan Warganegara',
            'warganegara': 'Warganegara',
            'bukan warganegara': 'Bukan Warganegara',
        }
        return mapping.get(value.lower(), value)

    def to_internal_value(self, data):
        """Convert boolean colorblind/disability to engine format after validation."""
        result = super().to_internal_value(data)
        # Convert booleans to Ya/Tidak for engine
        result['colorblind'] = 'Ya' if result.get('colorblind') else 'Tidak'
        result['disability'] = 'Ya' if result.get('disability') else 'Tidak'
        return result


class EligibilityResponseSerializer(serializers.Serializer):
    """Serializer for eligibility check response."""
    eligible_courses = serializers.ListField()
    total_count = serializers.IntegerField()
    stats = serializers.DictField()


class RankingRequestSerializer(serializers.Serializer):
    """
    Serializer for ranking request.

    Validates the eligible courses list and student signals
    sent to the ranking endpoint.
    """
    eligible_courses = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of eligible course dicts from eligibility check",
    )
    student_signals = serializers.DictField(
        required=True,
        help_text="Categorised student signals from quiz",
    )

    def validate_eligible_courses(self, value):
        """Ensure each course dict has a course_id."""
        if not value:
            raise serializers.ValidationError("eligible_courses must not be empty.")
        for i, course in enumerate(value):
            if 'course_id' not in course:
                raise serializers.ValidationError(
                    f"eligible_courses[{i}] missing course_id."
                )
        return value
