"""Send interview reminders (1 day + 1 hour before a booked interview).

Run frequently (every ~15 min) via the internal cron endpoint job
'interview-reminders'. Idempotent: each reminder fires at most once, gated on the
per-application stamp (interview_reminded_1d_at / interview_reminded_1h_at), which
is reset whenever the student reschedules. Best-effort emails to the student AND the
assigned reviewer. Inert unless INTERVIEW_SCHEDULING_ENABLED.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scholarship import emails
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.pool import pool_ref
from apps.scholarship.scheduling import _student_identity


class Command(BaseCommand):
    help = 'Send 1-day and 1-hour reminders for booked B40 interviews (idempotent).'

    def handle(self, *args, **options):
        if not getattr(settings, 'INTERVIEW_SCHEDULING_ENABLED', False):
            self.stdout.write('INTERVIEW_SCHEDULING_ENABLED is off — no reminders sent.')
            return
        now = timezone.now()
        qs = (ScholarshipApplication.objects
              .filter(interview_status='booked', interview_start__gt=now)
              .select_related('profile', 'assigned_to'))
        sent_1d, sent_1h = [], []
        for app in qs:
            start = app.interview_start
            student_email, student_name = _student_identity(app)
            reviewer = app.assigned_to
            reviewer_email = getattr(reviewer, 'email', '') if reviewer else ''
            reviewer_name = getattr(reviewer, 'name', '') if reviewer else ''

            # 1-day reminder: inside 24h of the start, once.
            if app.interview_reminded_1d_at is None and start <= now + timedelta(hours=24):
                emails.send_interview_reminder_email(
                    student_email, student_name=student_name, start=start,
                    meeting_url=app.interview_meeting_url, when='1day',
                    english_only=emails.english_only_email(app))
                if reviewer_email:
                    emails.send_reviewer_interview_reminder_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
                        start=start, meeting_url=app.interview_meeting_url, when='1day',
                        ref=pool_ref(app.id))
                app.interview_reminded_1d_at = now
                app.save(update_fields=['interview_reminded_1d_at'])
                sent_1d.append(app.id)

            # 1-hour reminder: inside 1h of the start, once.
            if app.interview_reminded_1h_at is None and start <= now + timedelta(hours=1):
                emails.send_interview_reminder_email(
                    student_email, student_name=student_name, start=start,
                    meeting_url=app.interview_meeting_url, when='1hour',
                    english_only=emails.english_only_email(app))
                if reviewer_email:
                    emails.send_reviewer_interview_reminder_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
                        start=start, meeting_url=app.interview_meeting_url, when='1hour',
                        ref=pool_ref(app.id))
                app.interview_reminded_1h_at = now
                app.save(update_fields=['interview_reminded_1h_at'])
                sent_1h.append(app.id)

        self.stdout.write(f'Interview reminders sent. 1day={sent_1d} 1hour={sent_1h}')
