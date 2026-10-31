"""B40 Assistance Programme app configuration."""
from django.apps import AppConfig


class ScholarshipConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scholarship'
    verbose_name = 'B40 Assistance Programme'

    def ready(self):
        # D1 (third results route S4): `results_held` asks this app whether a live document is
        # recognised as STPM results. Registered, not imported there - the courses app imports
        # nothing from scholarship at module level (the app boundary, `test_code_standards`).
        from apps.courses import exam_questions
        from .wrong_slip import stpm_results_on_file
        exam_questions.STPM_DOCUMENT_WITNESS = stpm_results_on_file
        # Common profile S2: deleting a staff profile row (a deleted account cascades to it) deletes
        # its photo from the bucket after the commit (`staff_photo.on_profile_deleted`).
        from django.db.models.signals import post_delete
        from .models import StaffProfile
        from .staff_photo import on_profile_deleted
        post_delete.connect(on_profile_deleted, sender=StaffProfile,
                            dispatch_uid='staff_photo_on_profile_deleted')
