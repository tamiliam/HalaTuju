"""
Django Admin configuration for courses app.
"""
from django.contrib import admin
from .models import (
    Course, CourseRequirement, CourseTag,
    Institution, CourseInstitution,
    StudentProfile, SavedCourse
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_id', 'course', 'level', 'field', 'frontend_label']
    list_filter = ['level', 'frontend_label', 'wbl']
    search_fields = ['course_id', 'course', 'department', 'field']
    ordering = ['course_id']


@admin.register(CourseRequirement)
class CourseRequirementAdmin(admin.ModelAdmin):
    list_display = [
        'course', 'source_type', 'min_credits', 'merit_cutoff',
        'req_malaysian', 'pass_bm', 'credit_math'
    ]
    list_filter = ['source_type', 'req_malaysian', 'no_colorblind']
    search_fields = ['course__course_id', 'course__course']


@admin.register(CourseTag)
class CourseTagAdmin(admin.ModelAdmin):
    list_display = [
        'course', 'work_modality', 'people_interaction',
        'cognitive_type', 'environment'
    ]
    list_filter = ['work_modality', 'environment', 'outcome']


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = [
        'institution_id', 'institution_name', 'acronym',
        'type', 'state'
    ]
    list_filter = ['type', 'category', 'state']
    search_fields = ['institution_id', 'institution_name', 'acronym']
    ordering = ['state', 'institution_name']


@admin.register(CourseInstitution)
class CourseInstitutionAdmin(admin.ModelAdmin):
    list_display = ['course', 'institution']
    list_filter = ['institution__state', 'institution__type']
    search_fields = ['course__course_id', 'institution__institution_name']


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['supabase_user_id', 'gender', 'nationality', 'created_at']
    list_filter = ['gender', 'nationality']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SavedCourse)
class SavedCourseAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'saved_at']
    list_filter = ['saved_at']
