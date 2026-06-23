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


def _wa_reminder_body(student_name, start, meeting_url, when, english_only, reviewer_name='your interviewer'):
    """Plain-text interview reminder for WhatsApp (sandbox free-text path; mirrors the v2 templates).

    EN-only when ``english_only``, else EN + BM. Names the interviewer and differentiates the 24h
    ("tomorrow at …") vs the 1h ("in about an hour, at …") reminder. The Meet link is inline so it
    works from a phone OR a computer."""
    t = emails._fmt_myt_time(start)
    when_en = f'tomorrow at {t}' if when == '1day' else f'in about an hour, at {t}'
    when_bm = f'esok pada {t}' if when == '1day' else f'kira-kira sejam lagi, pada {t}'
    link = meeting_url or 'https://halatuju.xyz/scholarship/application'
    en = (f'Hi {student_name} — a reminder: your B40 Assistance interview with {reviewer_name} is '
          f'{when_en}. Join from your phone or computer here: {link} — see you then.')
    if english_only:
        return en
    bm = (f'Salam {student_name} — peringatan: temu duga Bantuan B40 anda bersama {reviewer_name} adalah '
          f'{when_bm}. Sertai melalui telefon atau komputer di sini: {link} — jumpa nanti.')
    return f'{en}\n\n{bm}'


def _booked_with_notice(app, hours):
    """True if the booking gave at least ``hours`` of notice — i.e. the reminder is meaningful.

    Gates each reminder on (interview_start − interview_booked_at): a same-day booking shouldn't
    trigger an instant "24h reminder", and a last-minute booking shouldn't trigger an instant
    "1h reminder". Firing itself stays late-tolerant (fire at/after the mark), so cron jitter never
    *skips* a legitimate reminder — only the booking-notice decides eligibility. Unknown booked_at
    (legacy rows) → True, so we never silently suppress an expected reminder."""
    booked_at = app.interview_booked_at
    if not booked_at or not app.interview_start:
        return True
    return (app.interview_start - booked_at) >= timedelta(hours=hours)


def _send_wa_reminder(app, student_name, start, when):
    """Best-effort WhatsApp interview reminder, gated on the student's opt-in.

    Picks a v2 template by ``english_only`` — EN-only (``..._CONTENT_SID_EN``) or EN+BM
    (``..._CONTENT_SID_BM``) — each serving BOTH the 24h and 1h reminder via a 'when' variable and
    naming the interviewer. Falls back to the legacy generic template (``..._CONTENT_SID``, current
    prod) while the v2 templates aren't set, then to sandbox free text."""
    if not getattr(app.profile, 'whatsapp_opt_in', True):
        return
    phone = getattr(app.profile, 'contact_phone', '')
    student_name = (student_name or '').strip().split(' ')[0] or 'there'   # first name
    reviewer_name = (getattr(app.assigned_to, 'name', '') or '').strip() or 'your interviewer'
    kind = f'interview_reminder_{when}'
    link = app.interview_meeting_url or 'https://halatuju.xyz/scholarship/application'
    t = emails._fmt_myt_time(start)
    when_en = f'tomorrow at {t}' if when == '1day' else f'in about an hour, at {t}'
    when_bm = f'esok pada {t}' if when == '1day' else f'kira-kira sejam lagi, pada {t}'
    en_only = emails.english_only_email(app)
    en_sid = getattr(settings, 'TWILIO_WHATSAPP_REMINDER_CONTENT_SID_EN', '')
    bm_sid = getattr(settings, 'TWILIO_WHATSAPP_REMINDER_CONTENT_SID_BM', '')
    new_sid = en_sid if en_only else (bm_sid or en_sid)   # variant by language preference
    if new_sid:
        cv = {'1': student_name, '2': reviewer_name, '3': when_en, '4': link}
        if new_sid == bm_sid:          # the bilingual template carries the BM 'when' too
            cv['5'] = when_bm
        whatsapp.send_whatsapp(phone, application=app, kind=kind, content_sid=new_sid, content_variables=cv)
        return
    legacy_sid = getattr(settings, 'TWILIO_WHATSAPP_REMINDER_CONTENT_SID', '')
    if legacy_sid:                     # current prod generic template (1=name, 2=time, 3=link)
        whatsapp.send_whatsapp(
            phone, application=app, kind=kind, content_sid=legacy_sid,
            content_variables={'1': student_name, '2': emails._fmt_myt(start), '3': link})
        return
    body = _wa_reminder_body(student_name, start, app.interview_meeting_url, when, en_only, reviewer_name)
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

            # 1-day reminder: inside 24h of the start, once — but only if the booking gave ≥24h
            # notice (a same-day booking skips this; the 1-hour reminder still covers it).
            if (app.interview_reminded_1d_at is None and start <= now + timedelta(hours=24)
                    and _booked_with_notice(app, 24)):
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

            # 1-hour reminder: inside 1h of the start, once — but only if the booking gave ≥1h
            # notice (a sub-1h booking skips it; the confirmation already went out at booking).
            if (app.interview_reminded_1h_at is None and start <= now + timedelta(hours=1)
                    and _booked_with_notice(app, 1)):
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
