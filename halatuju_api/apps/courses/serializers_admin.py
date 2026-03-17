from rest_framework import serializers
from .models import StudentProfile


class PartnerStudentListSerializer(serializers.ModelSerializer):
    org_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'gender',
            'exam_type', 'school', 'phone', 'referral_source',
            'org_name', 'created_at',
        ]

    def get_org_name(self, obj):
        if obj.referred_by_org:
            return obj.referred_by_org.name
        return None


class PartnerStudentDetailSerializer(serializers.ModelSerializer):
    saved_courses = serializers.SerializerMethodField()
    org_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'angka_giliran',
            'gender', 'nationality',
            'phone', 'address', 'school',
            'family_income', 'siblings',
            'colorblind', 'disability',
            'exam_type', 'grades', 'stpm_grades', 'stpm_cgpa', 'muet_band',
            'student_signals', 'preferred_state',
            'financial_pressure', 'travel_willingness',
            'referral_source', 'org_name',
            'created_at', 'saved_courses',
        ]

    def get_org_name(self, obj):
        if obj.referred_by_org:
            return obj.referred_by_org.name
        return None

    def get_saved_courses(self, obj):
        from .models import SavedCourse
        saved = SavedCourse.objects.filter(student=obj).select_related('course', 'stpm_course')[:10]
        results = []
        for sc in saved:
            course = sc.course or sc.stpm_course
            if course:
                results.append({
                    'course_id': course.course_id,
                    'name': getattr(course, 'name', None) or getattr(course, 'course_name', None) or getattr(course, 'course', ''),
                })
        return results
