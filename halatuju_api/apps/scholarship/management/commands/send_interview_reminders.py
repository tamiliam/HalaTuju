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

from apps.scholarship import emails, whatsapp
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.pool import pool_ref
from apps.scholarship.scheduling import _student_identity


def _wa_reminder_body(student_name, start, meeting_url, when, english_only):
    """Plain-text bilingual interview reminder for WhatsApp (sandbox: free-form).

    A production WhatsApp sender needs a Meta-approved template — that lands at
    go-live (Sprint 2); the sandbox accepts free text to joined numbers."""
    when_en = 'tomorrow' if when == '1day' else 'in 1 hour'
    when_bm = 'esok' if when == '1day' else 'dalam 1 jam'
    t = emails._fmt_myt(start)
    en = f'Hi {student_name}, a reminder: your B40 Assistance interview is {when_en} — {t}.'
    if meeting_url:
        en += f'\nJoin: {meeting_url}'
    if english_only:
        return en
    bm = f'Salam {student_name}, peringatan: temu duga Bantuan B40 anda {when_bm} — {t}.'
    if meeting_url:
        bm += f'\nSertai: {meeting_url}'
    return f'{en}\n\n{bm}'


def _send_wa_reminder(app, student_name, start, when):
    """Best-effort WhatsApp interview reminder, gated on the student's opt-in.

    Uses the approved Meta template (``TWILIO_WHATSAPP_REMINDER_CONTENT_SID``) when
    configured — required for production business-initiated sends — and falls back to
    free text in the sandbox/dev (no template set)."""
    if not getattr(app.profile, 'whatsapp_opt_in', True):
        return
    phone = getattr(app.profile, 'contact_phone', '')
    kind = f'interview_reminder_{when}'
    content_sid = getattr(settings, 'TWILIO_WHATSAPP_REMINDER_CONTENT_SID', '')
    if content_sid:
        link = app.interview_meeting_url or 'https://halatuju.xyz/scholarship/application'
        whatsapp.send_whatsapp(
            phone, application=app, kind=kind, content_sid=content_sid,
            content_variables={'1': student_name, '2': emails._fmt_myt(start), '3': link})
    else:
        body = _wa_reminder_body(student_name, start, app.interview_meeting_url, when,
                                 emails.english_only_email(app))
        whatsapp.send_whatsapp(phone, body, application=app, kind=kind)


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
            # Heads-up: the verdict is a different clock from the interview (TD-131). Surface the
            # due date in the reviewer reminder iff a verdict isn't recorded yet.
            verdict_due = ''
            if app.assigned_at and app.verdict_decided_at is None:
                _sla = getattr(settings, 'REVIEW_SLA_DAYS', 10)
                verdict_due = (app.assigned_at + timedelta(days=_sla)).date().strftime('%d %b %Y')

            # 1-day reminder: inside 24h of the start, once.
            if app.interview_reminded_1d_at is None and start <= now + timedelta(hours=24):
                _eo = emails.english_only_email(app)
                emails.send_interview_reminder_email(
                    student_email, student_name=student_name, start=start,
                    meeting_url=app.interview_meeting_url, when='1day',
                    english_only=_eo)
                # Best-effort WhatsApp alongside the email (gated on opt-in; approved
                # template in prod, free text in the sandbox; no-op unless WHATSAPP_ENABLED).
                _send_wa_reminder(app, student_name, start, '1day')
                if reviewer_email:
                    emails.send_reviewer_interview_reminder_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
                        start=start, meeting_url=app.interview_meeting_url, when='1day',
                        ref=pool_ref(app.id), verdict_due=verdict_due)
                app.interview_reminded_1d_at = now
                app.save(update_fields=['interview_reminded_1d_at'])
                sent_1d.append(app.id)

            # 1-hour reminder: inside 1h of the start, once.
            if app.interview_reminded_1h_at is None and start <= now + timedelta(hours=1):
                _eo = emails.english_only_email(app)
                emails.send_interview_reminder_email(
                    student_email, student_name=student_name, start=start,
                    meeting_url=app.interview_meeting_url, when='1hour',
                    english_only=_eo)
                _send_wa_reminder(app, student_name, start, '1hour')
                if reviewer_email:
                    emails.send_reviewer_interview_reminder_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
                        start=start, meeting_url=app.interview_meeting_url, when='1hour',
                        ref=pool_ref(app.id), verdict_due=verdict_due)
                app.interview_reminded_1h_at = now
                app.save(update_fields=['interview_reminded_1h_at'])
                sent_1h.append(app.id)

        self.stdout.write(f'Interview reminders sent. 1day={sent_1d} 1hour={sent_1h}')
