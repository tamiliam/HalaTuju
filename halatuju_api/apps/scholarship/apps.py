"""B40 Assistance Programme app configuration."""
from django.apps import AppConfig


class ScholarshipConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scholarship'
    verbose_name = 'B40 Assistance Programme'
