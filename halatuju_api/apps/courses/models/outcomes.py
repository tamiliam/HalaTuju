"""Saved courses, admission outcomes and the course-data status row."""

from django.db import models
from django.db.models import Q
from .catalogue import Course, Institution
from .student import StudentProfile


class SavedCourse(models.Model):
    """
    Courses saved/bookmarked by students.

    Supports both SPM (Course) and STPM (StpmCourse) via two nullable FKs.
    Exactly one FK must be set per row (enforced by DB check constraint).
    """
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='saved_courses'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    stpm_course = models.ForeignKey(
        'StpmCourse',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    interest_status = models.CharField(
        max_length=20,
        choices=[
            ('interested', 'Interested'),
            ('planning', 'Planning to apply'),
            ('applied', 'Applied'),
            ('got_offer', 'Got offer'),
        ],
        default='interested',
        help_text="Student's self-reported interest level"
    )

    class Meta:
        db_table = 'saved_courses'
        ordering = ['-saved_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(course__isnull=False, stpm_course__isnull=True) |
                    Q(course__isnull=True, stpm_course__isnull=False)
                ),
                name='exactly_one_course_type',
            ),
        ]

    @property
    def course_id_value(self):
        """Return whichever course ID is set."""
        return self.course_id if self.course_id else self.stpm_course_id

    @property
    def course_type(self):
        """Return 'stpm' or 'spm' based on which FK is set."""
        return 'stpm' if self.stpm_course_id else 'spm'

    def __str__(self):
        return f"{self.student_id} saved {self.course_id_value}"


class AdmissionOutcome(models.Model):
    """
    Tracks a student's application outcome for a specific course/institution.
    Enables HalaTuju to measure real-world impact: did we help them get in?
    """
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('offered', 'Offered'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='outcomes'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='outcomes'
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outcomes'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    intake_year = models.IntegerField(null=True, blank=True)
    intake_session = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateField(null=True, blank=True)
    outcome_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admission_outcomes'
        unique_together = ['student', 'course', 'institution']
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.student_id} → {self.course_id} ({self.status})"


class CourseDataStatus(models.Model):
    """Last-run status per course-data source/check, for the admin Course Data dashboard.

    The refresh/validate/audit tools upsert a row here when they run, so the dashboard can
    show freshness ("STPM refreshed 13 Jun", "SPM never refreshed") and last link-health /
    audit findings WITHOUT re-running anything. A missing row = 'never run' (rendered as a
    first-class state). Read-only on the dashboard; written only by the management commands.
    """
    KEY_CHOICES = [
        ('epanduan_stpm', 'e-Panduan — STPM refresh'),
        ('epanduan_spm', 'e-Panduan — SPM refresh'),
        ('uptvet', 'UP_TVET inventory'),
        ('emasco', 'eMASCO occupations'),
        ('link_health', 'Catalogue link health'),
        ('audit', 'Data audit'),
    ]
    key = models.CharField(max_length=40, primary_key=True, choices=KEY_CHOICES)
    last_run_at = models.DateTimeField(help_text='When the tool that writes this key last completed')
    summary = models.JSONField(default=dict, blank=True, help_text='Run summary (counts/findings) for display')
    detail = models.TextField(blank=True, default='', help_text='Optional human note / command used')

    class Meta:
        db_table = 'course_data_status'
        verbose_name_plural = 'Course data statuses'

    def __str__(self):
        return f"{self.key} @ {self.last_run_at:%Y-%m-%d %H:%M}"
