"""
Serializers for the courses API.
"""
from rest_framework import serializers
from .models import Course, FieldTaxonomy, Institution, CourseRequirement, CourseTag, MascoOccupation, StudentProfile


class FieldTaxonomySerializer(serializers.ModelSerializer):
    """Serializer for FieldTaxonomy entries."""
    children = serializers.SerializerMethodField()

    class Meta:
        model = FieldTaxonomy
        fields = [
            'key', 'name_en', 'name_ms', 'name_ta',
            'image_slug', 'parent_key', 'sort_order', 'children',
        ]

    def get_children(self, obj):
        """Return child entries for parent groups."""
        if obj.parent_key is not None:
            return []
        children = FieldTaxonomy.objects.filter(parent_key=obj.key).order_by('sort_order')
        return FieldTaxonomySerializer(children, many=True).data


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""
    course_name = serializers.CharField(source='course', read_only=True)

    class Meta:
        model = Course
        fields = [
            'course_id', 'course', 'course_name', 'wbl', 'level', 'department',
            'field', 'field_key', 'semesters',
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


class CourseRequirementSerializer(serializers.Serializer):
    """
    Serializes CourseRequirement into structured general/special groups.
    Only includes truthy (non-default) fields.
    """

    # General requirement fields → BM labels
    GENERAL_FIELDS = {
        'req_malaysian': 'Warganegara Malaysia',
        'req_male': 'Lelaki sahaja',
        'req_female': 'Perempuan sahaja',
        'no_colorblind': 'Tidak buta warna',
        'no_disability': 'Tidak cacat fizikal',
        'single': 'Belum berkahwin',
    }

    # Special requirement fields → BM labels
    SPECIAL_FIELDS = {
        # Core pass
        'pass_bm': 'Lulus Bahasa Melayu',
        'pass_history': 'Lulus Sejarah',
        'pass_eng': 'Lulus Bahasa Inggeris',
        'pass_math': 'Lulus Matematik',
        'pass_sci': 'Lulus Sains',
        'pass_islam': 'Lulus Pendidikan Islam',
        'pass_moral': 'Lulus Pendidikan Moral',
        # Credit
        'credit_bm': 'Kredit Bahasa Melayu',
        'credit_english': 'Kredit Bahasa Inggeris',
        'credit_math': 'Kredit Matematik',
        'credit_addmath': 'Kredit Matematik Tambahan',
        'credit_sci': 'Kredit Sains',
        'credit_islam': 'Kredit Pendidikan Islam',
        'credit_moral': 'Kredit Pendidikan Moral',
        # Composite OR-groups (simple flags)
        'credit_stv': 'Kredit Sains/Teknikal/Vokasional',
        'credit_sf': 'Kredit Sains atau Fizik',
        'credit_sfmt': 'Kredit Sains/Fizik/Matematik Tambahan',
        'credit_bmbi': 'Kredit BM atau BI',
        'credit_science_group': 'Kredit kumpulan Sains',
        'credit_math_or_addmath': 'Kredit Matematik atau Matematik Tambahan',
        # TVET composite
        'pass_math_addmath': 'Lulus Matematik atau Matematik Tambahan',
        'pass_science_tech': 'Lulus Sains atau subjek Teknikal',
        'pass_math_science': 'Lulus Matematik atau Sains',
        'credit_math_sci': 'Kredit Matematik atau Sains',
        'credit_math_sci_tech': 'Kredit Matematik/Sains/Teknikal',
        'pass_stv': 'Lulus Sains/Teknikal/Vokasional',
        'three_m_only': 'Boleh membaca, menulis dan mengira (3M)',
        # Grade B
        'credit_bm_b': 'Gred B+ Bahasa Melayu',
        'credit_eng_b': 'Gred B+ Bahasa Inggeris',
        'credit_math_b': 'Gred B+ Matematik',
        'credit_addmath_b': 'Gred B+ Matematik Tambahan',
        # Distinction
        'distinction_bm': 'Cemerlang (A-) Bahasa Melayu',
        'distinction_eng': 'Cemerlang (A-) Bahasa Inggeris',
        'distinction_math': 'Cemerlang (A-) Matematik',
        'distinction_addmath': 'Cemerlang (A-) Matematik Tambahan',
        'distinction_phy': 'Cemerlang (A-) Fizik',
        'distinction_chem': 'Cemerlang (A-) Kimia',
        'distinction_bio': 'Cemerlang (A-) Biologi',
        'distinction_sci': 'Cemerlang (A-) Sains',
    }

    def to_representation(self, instance):
        general = []
        special = []

        # Demographic / general flags
        for field, label in self.GENERAL_FIELDS.items():
            if getattr(instance, field, False):
                general.append({'key': field, 'label': label})

        # Min credits / min pass
        if instance.min_credits and instance.min_credits > 0:
            general.append({
                'key': 'min_credits',
                'label': f'Minimum {instance.min_credits} kredit SPM',
                'value': instance.min_credits,
            })
        if instance.min_pass and instance.min_pass > 0:
            general.append({
                'key': 'min_pass',
                'label': f'Minimum {instance.min_pass} lulus SPM',
                'value': instance.min_pass,
            })

        # Academic / special flags
        for field, label in self.SPECIAL_FIELDS.items():
            if getattr(instance, field, False):
                special.append({'key': field, 'label': label})

        # Advisory
        if instance.req_interview:
            special.append({'key': 'req_interview', 'label': 'Temuduga diperlukan'})

        return {
            'source_type': getattr(instance, 'source_type', ''),
            'general': general,
            'special': special,
            'complex_requirements': instance.complex_requirements,
            'subject_group_req': instance.subject_group_req,
            'merit_cutoff': instance.merit_cutoff,
            'remarks': instance.remarks or '',
        }


class EligibilityRequestSerializer(serializers.Serializer):
    """
    Serializer for eligibility check request.

    Validates the student profile data sent to the eligibility endpoint.
    Accepts multiple input formats and normalizes to engine-expected values.
    """
    grades = serializers.DictField(
        child=serializers.CharField(),
        required=True,
        help_text="SPM grades: {'bm': 'A+', 'math': 'B', ...}"
    )
    gender = serializers.CharField(default='Lelaki')
    nationality = serializers.CharField(default='Warganegara')
    colorblind = serializers.BooleanField(default=False, required=False)
    disability = serializers.BooleanField(default=False, required=False)
    other_tech = serializers.BooleanField(default=False)
    other_voc = serializers.BooleanField(default=False)
    coq_score = serializers.FloatField(default=5.0, required=False,
        help_text="Co-curricular score (0-10). Defaults to 5.0 if not provided."
    )
    student_merit = serializers.FloatField(required=False, default=None,
        help_text="Pre-computed merit score from frontend (0-100). If provided, backend skips recalculation."
    )

    def validate_coq_score(self, value):
        """Clamp CoQ to 0-10 range."""
        return min(max(float(value), 0), 10.0)

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


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for profile update (PUT /profile/ and POST /profile/sync/).

    Validates field types and constrains values to prevent 500 errors
    from malformed input (e.g. string for siblings, invalid JSON for grades).
    """

    class Meta:
        model = StudentProfile
        fields = [
            'grades', 'gender', 'nationality', 'colorblind', 'disability',
            'student_signals', 'preferred_state', 'name', 'school',
            'nric', 'address', 'phone', 'family_income', 'siblings',
            'exam_type', 'stpm_grades', 'stpm_cgpa', 'muet_band',
            'spm_prereq_grades',
        ]
        extra_kwargs = {f: {'required': False} for f in fields}
