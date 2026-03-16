from rest_framework import serializers
from .models import StudentProfile


class PartnerStudentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'gender',
            'exam_type', 'created_at',
        ]


class PartnerStudentDetailSerializer(serializers.ModelSerializer):
    saved_courses = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'gender',
            'nationality', 'exam_type', 'grades', 'stpm_grades',
            'student_signals', 'preferred_state', 'created_at',
            'saved_courses',
        ]

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
