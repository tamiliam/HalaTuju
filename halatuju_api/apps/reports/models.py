"""
Models for AI-generated reports.
"""
from django.db import models


class GeneratedReport(models.Model):
    """
    AI-generated career counselor report.
    """
    student = models.ForeignKey(
        'courses.StudentProfile',
        on_delete=models.CASCADE,
        related_name='reports'
    )

    # Report content
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="AI-generated report text")
    summary = models.TextField(blank=True, help_text="Short summary")

    # Input data snapshot
    student_profile_snapshot = models.JSONField(
        help_text="Copy of student profile at generation time"
    )
    eligible_courses_snapshot = models.JSONField(
        help_text="List of eligible courses at generation time"
    )

    # Metadata
    model_used = models.CharField(max_length=50, help_text="gemini-pro, gpt-4, etc.")
    generation_time_ms = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'generated_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report {self.id} for {self.student_id}"
