"""The send primitives and the HTML furniture every rich mail is built from: `_send_html`,
`_send_bilingual`, `english_only_email`, the Malaysian time formats, the calendar invite
and the shell / button / join-line helpers.

`_send_plain` sits here too, away from the reviewer mail it serves: it reads
`_interview_unsub_headers` from this module, and leaving it beside its callers was the
one import cycle the cut found.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import EmailMessage, EmailMultiAlternatives
from .shared import _P, _meter_email, logger


# ── Interview scheduling (booking confirmation + reminders + cancellation) ────
# Student-facing emails are bilingual (English then Bahasa Melayu) and use the
# student-facing term "interviewer" / "Penemu duga". Reviewer-facing emails are
# plain English (internal staff). All best-effort; the booking never depends on them.

def _fmt_myt_time(dt):
    """Time-only in Malaysia time, e.g. '8:00 PM' (used in the reminder 'when' phrase)."""
    if dt is None:
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    except Exception:
        local = dt
    hour12 = local.hour % 12 or 12
    ampm = 'AM' if local.hour < 12 else 'PM'
    return f'{hour12}:{local:%M} {ampm}'


def _fmt_myt(dt):
    """Format a tz-aware datetime in Malaysia time, e.g. 'Mon, 23 Jun 2026, 8:00 PM (MYT)'.

    ⚠ An already-formatted STRING passes through untouched. That exists for one caller — the
    read-only email catalogue, which renders each letter twice through this same builder: once with
    real particulars and once with `{interview_time}` in their place, so a reader sees the SHAPE of
    the email rather than a made-up date they might mistake for a real booking. Without the
    passthrough the token render would raise on the format spec, and the catalogue would have to
    keep its own copy of the prose — which is the one thing it exists to avoid.
    """
    if isinstance(dt, str):
        return dt
    if dt is None:
        return ''
    try:
        from zoneinfo import ZoneInfo
        local = dt.astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
    except Exception:
        local = dt
    # %-I isn't portable (Windows); derive a no-leading-zero 12-hour clock manually.
    hour12 = local.hour % 12 or 12
    ampm = 'AM' if local.hour < 12 else 'PM'
    return f'{local:%a, %d %b %Y}, {hour12}:{local:%M} {ampm} (MYT)'


def _interview_unsub_headers():
    """A harmless List-Unsubscribe on interview/service emails: a mailto to support, so a
    mistaken 'unsubscribe' click just lands a note in the support inbox for a human — instead
    of triggering the ESP's auto-suppression that would silently stop us reaching the student
    about reminders or their decision. No one-click POST header, so nothing auto-fires. (The
    definitive fix is a Brevo-side List-Help on transactional mail.)"""
    return {'List-Unsubscribe': f'<mailto:{_P.email_support}?subject=Unsubscribe%20from%20B40%20emails>'}


def _send_bilingual(to_email, subject, en, bm):
    """Send one EN+BM email (the booking-flow pattern), with Reply-To = the interview
    alias so replies route there. Best-effort → bool."""
    if not to_email:
        return False
    _meter_email()
    try:
        EmailMessage(
            subject=subject,
            body=en + '\n\n———\n\n' + bm,
            from_email=_P.interview_from,
            to=[to_email],
            reply_to=[_P.interview_reply_to],
            headers=_interview_unsub_headers(),
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send interview email to %s', to_email, exc_info=True)
        return False


def english_only_email(application) -> bool:
    """True when we can confidently send a student email in English only: they used the app
    in English, did NOT ask to be contacted in Malay/Tamil, AND scored A/A+ in SPM English.
    Otherwise bilingual (EN+BM) — conservative: any Malay/Tamil signal keeps the Malay mirror."""
    profile = getattr(application, 'profile', None)
    locale = (getattr(application, 'locale', '') or '').lower()
    call_lang = (getattr(profile, 'preferred_call_language', '') or '').lower() if profile else ''
    if locale != 'en' or call_lang in ('ms', 'ta'):
        return False
    grades = getattr(profile, 'grades', None) if profile else None
    eng = ''
    if isinstance(grades, dict):
        eng = str(grades.get('eng', '') or '').strip().upper().replace('−', '-')
    return eng in ('A+', 'A')


def _send_html(to_email, subject, text_body, html_body, reply_to=None, ics=None, from_email=None,
               attachments=None):
    """Send a multipart email — HTML primary + plain-text fallback. From/Reply-To default to
    the interview alias (interview emails are the main caller); pass ``from_email`` +
    ``reply_to`` for a general (non-interview) email, e.g. the info@ sender. ``ics`` (a
    calendar string) is attached as interview.ics so the client offers "add to calendar".
    ``attachments`` is a list of ``(filename, content, mimetype)`` triples — e.g. the Vircle
    installation-guide PDF. Best-effort → bool."""
    if not to_email:
        return False
    _meter_email()
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email or _P.interview_from,
            to=[to_email],
            reply_to=reply_to or [_P.interview_reply_to],
            headers=_interview_unsub_headers(),
        )
        msg.attach_alternative(html_body, 'text/html')
        if ics:
            msg.attach('interview.ics', ics, 'text/calendar')
        for attachment in (attachments or []):
            msg.attach(*attachment)
        msg.send()
        return True
    except Exception:
        logger.warning('Failed to send HTML email to %s', to_email, exc_info=True)
        return False


def _interview_ics(*, start, duration_min, summary, description='', location=''):
    """A minimal VCALENDAR/VEVENT for the booked interview (attached so mail clients show
    an 'add to calendar' affordance)."""
    from datetime import datetime, timedelta, timezone as dtz
    def z(dt):
        return dt.astimezone(dtz.utc).strftime('%Y%m%dT%H%M%SZ')
    def esc(s):
        return (str(s or '').replace('\\', '\\\\').replace(';', '\\;')
                .replace(',', '\\,').replace('\n', '\\n'))
    end = start + timedelta(minutes=duration_min)
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//HalaTuju//B40//EN', 'METHOD:PUBLISH',
        'BEGIN:VEVENT', f'UID:b40-interview-{int(start.timestamp())}@{_P.ics_uid_domain}',
        f'DTSTAMP:{datetime.now(dtz.utc).strftime("%Y%m%dT%H%M%SZ")}', f'DTSTART:{z(start)}', f'DTEND:{z(end)}',
        f'SUMMARY:{esc(summary)}', f'DESCRIPTION:{esc(description)}', f'LOCATION:{esc(location)}',
        'END:VEVENT', 'END:VCALENDAR',
    ]
    return '\r\n'.join(lines) + '\r\n'


def _gcal_url(*, start, duration_min, text, details='', location=''):
    """A Google Calendar 'create event' template URL for the 'Add to calendar' button."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from urllib.parse import urlencode
    def z(dt):
        return dt.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')
    end = start + timedelta(minutes=duration_min)
    q = urlencode({'action': 'TEMPLATE', 'text': text, 'dates': f'{z(start)}/{z(end)}',
                   'details': details, 'location': location})
    return f'https://calendar.google.com/calendar/render?{q}'


def _html_email_shell(*sections):
    """Wrap one or more HTML strings in a simple, email-client-safe card layout."""
    divider = '<hr style="border:none;border-top:1px solid #e5e7eb;margin:22px 0;">'
    inner = divider.join(sections)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;background:#f3f4f6;">'
        '<div style="max-width:560px;margin:0 auto;padding:24px;'
        'font-family:Arial,Helvetica,sans-serif;color:#111827;font-size:15px;line-height:1.55;">'
        '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:24px;">'
        + inner +
        '</div></div></body></html>'
    )


def _email_button(href, label):
    return (
        f'<a href="{href}" style="display:inline-block;background:#2563eb;color:#ffffff;'
        f'text-decoration:none;font-weight:600;padding:12px 22px;border-radius:8px;'
        f'font-size:15px;">{label}</a>'
    )


def _join_line(meeting_url, lang='en'):
    if meeting_url:
        return (f'• Join here: {meeting_url}\n' if lang == 'en'
                else f'• Sertai di sini: {meeting_url}\n')
    return ('• Your interviewer will share the video-call link before the interview.\n'
            if lang == 'en'
            else '• Penemu duga anda akan berkongsi pautan panggilan video sebelum temu duga.\n')



def _send_plain(to_email, subject, body):
    if not to_email:
        return False
    _meter_email()
    try:
        EmailMessage(subject=subject, body=body,
                     from_email=_P.interview_from,
                     to=[to_email], reply_to=[_P.interview_reply_to],
                     headers=_interview_unsub_headers()).send()
        return True
    except Exception:
        logger.warning('Failed to send reviewer interview email to %s', to_email, exc_info=True)
        return False
