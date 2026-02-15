"""
Serializers for the courses API.
"""
from rest_framework import serializers
from .models import Course, Institution, CourseRequirement, CourseTag


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""

    class Meta:
        model = Course
        fields = [
            'course_id', 'course', 'wbl', 'level', 'department',
            'field', 'frontend_label', 'semesters', 'description'
        ]


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
