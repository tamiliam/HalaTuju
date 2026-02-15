"""
Django Admin configuration for reports app.
"""
from django.contrib import admin
from .models import GeneratedReport


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'title', 'model_used', 'created_at']
    list_filter = ['model_used', 'created_at']
    search_fields = ['title', 'student__supabase_user_id']
    readonly_fields = ['created_at', 'generation_time_ms']
