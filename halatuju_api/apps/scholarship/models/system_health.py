"""The admin System health light's own small store (2026-10-28).

One row per thing the light watches that leaves no trace anywhere else: the email send path
(`email`), each Cloud Scheduler job run through `CronRunView` (`cron:<job>`), and the moment the
recorders first wrote anything (`cron:_since`), so a job that has simply not come round yet since
the deploy reads "waiting for its first run", not "missed".

⚠ WHY A NEW TABLE AND NOT `course_data_status`: that table's admin payload returns EVERY row it
holds, so health rows written there would leak into the Course Data dashboard, and its `key`
choices are the course-data sources. A status row is not a course-data source.

⚠ NO PERSONAL DATA, EVER. A row holds timestamps, counts and an exception CLASS name — never an
address, a subject, a body, or an exception's message (an SMTP refusal names its recipients).
"""
from django.db import models


class SystemHealthStatus(models.Model):
    """The last outcome of one watched path. Written best-effort by `system_health_store`, read by
    `services/system_health.py`. A missing row means "nothing recorded yet"."""
    key = models.CharField(max_length=80, primary_key=True,
                           help_text="'email', 'cron:<job>' or 'cron:_since'")
    data = models.JSONField(default=dict, blank=True,
                            help_text='Timestamps (ISO), counts and an error class name. No PII.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_health_status'
        verbose_name_plural = 'System health statuses'

    def __str__(self):
        return self.key
