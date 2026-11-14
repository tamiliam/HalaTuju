"""
Django Admin configuration for courses app.
"""
from django.contrib import admin
from .models import (
    FieldTaxonomy,
    Course, CourseRequirement, CourseTag,
    Institution, CourseInstitution,
    StudentProfile, SavedCourse,
    PartnerOrganisation, PartnerAdmin
)


@admin.register(FieldTaxonomy)
class FieldTaxonomyAdmin(admin.ModelAdmin):
    list_display = ['key', 'name_ms', 'name_en', 'parent_key', 'image_slug', 'sort_order']
    list_filter = ['parent_key']
    search_fields = ['key', 'name_en', 'name_ms', 'name_ta']
    ordering = ['sort_order']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_id', 'course', 'level', 'field', 'field_key']
    list_filter = ['level', 'field_key', 'wbl']
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
    # Bumi coverage Sprint B: the Bumiputera answer is course-guide only — staff never see it.
    exclude = ['bumiputera']


@admin.register(SavedCourse)
class SavedCourseAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'saved_at']
    list_filter = ['saved_at']


@admin.register(PartnerOrganisation)
class PartnerOrganisationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']


@admin.register(PartnerAdmin)
class PartnerAdminAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'org', 'role', 'created_at']
    list_filter = ['role', 'org']
    search_fields = ['name', 'email']
    # Request #39: read-only here until Sprint 4's editor, which enforces the rules (lead tier,
    # qc => see_all, open cases, history). A hand edit here would bypass every one of them.
    readonly_fields = ['permissions']

    def save_model(self, request, obj, form, change):
        """M3a review (2026-11-14): `role` stays editable here, so a save that CHANGES it also sets
        `permissions` to NULL and writes one `staff_permission_changes` row (kind 'role_change', as
        `staff_lifecycle.change_role`). Since M3a an organisation admin STORES its keys; without the reset
        they would carry over to the new role. NULL is exactly the pre-M3a reading: a demoted organisation
        admin gets the new role's preset, and a promoted row reads as the full organisation-admin set."""
        if not (change and 'role' in form.changed_data):
            return super().save_model(request, obj, form, change)
        from types import SimpleNamespace
        from django.db import transaction
        from . import staff_activity_hook
        with transaction.atomic():
            old = PartnerAdmin.objects.select_for_update().get(pk=obj.pk)
            obj.permissions = None
            super().save_model(request, obj, form, change)
            user = request.user
            by = SimpleNamespace(email=getattr(user, 'email', '') or getattr(user, 'username', ''),
                                 is_super=False, role='django_admin')
            staff_activity_hook.record_role_reset(old, obj, by=by)
