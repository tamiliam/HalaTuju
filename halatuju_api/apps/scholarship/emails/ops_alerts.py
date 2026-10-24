"""Mail that goes to us: the Vision outage alert and the profile-complete admin note.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import send_mail
from .shared import _P, logger


#: Per read service: (subject, what failed, what it does to students, where to look). The Gemini row
#: arrived 2026-10-24, after its prepaid credit ran out for ~20 hours and no alert fired.
_OUTAGE_COPY = {
    'vision': (
        'Document OCR (Google Vision) may be down',
        'every Google Vision OCR attempt (ICs and supporting documents)',
        'shortlisted students cannot pass the consent identity check (their IC can\'t be '
        'auto-verified) and supporting documents are held for a reviewer',
        'Please check the Google Vision API status, quota and billing for the HalaTuju project.'),
    'gemini': (
        'Document AI reads (Gemini) may be down',
        'every Gemini document read (results slips, offer letters, income and relationship '
        'documents)',
        'those documents are held as "a reviewer will check this by hand" instead of being '
        'auto-checked; the hourly self-heal sweep re-reads them once Gemini answers again',
        'Please check the Gemini API key, prepaid credit and billing in Google AI Studio.'),
}


def send_vision_outage_alert_email(stats):
    """Alert the admin that a document-READ service appears to be down — every recent attempt
    errored and none succeeded. ``stats['service']`` names it: 'vision' (Google Vision OCR of the
    IC, the original and the default) or 'gemini' (Gemini document reads, 2026-10-24). Sent to
    ``settings.ADMIN_NOTIFY_EMAIL`` (contact@halatuju.xyz); skipped silently if unset.
    English-only (internal). Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    subject, what, impact, where = _OUTAGE_COPY[stats.get('service') or 'vision']
    sample = (stats.get('sample_error') or '').strip()
    repeat = ('This alert is sent when the outage STARTS; the daily check repeats it while it lasts.'
              if stats.get('mode') == 'start' else
              'This is an automated alert and will repeat daily until the service recovers.')
    try:
        send_mail(
            subject=f'[HalaTuju] {subject}',
            message=(
                f'Automated check: in the last {stats["window_hours"]}h, {what} failed with a '
                f'service error and none succeeded ({stats["service_failures"]} service failures '
                f'across {stats["attempts"]} attempts).\n\n'
                + (f'The error we stored:\n{sample}\n\n' if sample else '')
                + f'While this persists, {impact}. {where}\n\n{repeat}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send Vision-outage alert email', exc_info=True)
        return False


def send_profile_complete_admin_email(application_id, applicant_name, programme_name):
    """Phase C: notify the admin that an applicant has confirmed a complete Step-4
    profile and is ready for review. English-only (internal). Sent to
    ``settings.ADMIN_NOTIFY_EMAIL``; skipped silently if that's unset so it never
    blocks the student's confirm. Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    frontend = _P.frontend_url
    name = applicant_name or 'An applicant'
    try:
        send_mail(
            subject=f'[{programme_name}] Application #{application_id} ready for review',
            message=(
                f'{name} has confirmed a complete profile for {programme_name} '
                f'(application #{application_id}) and is ready for review.\n\n'
                f'Review it: {frontend}/admin/scholarship/{application_id}'
            ),
            from_email=_P.email_from,
            recipient_list=[to_email],
        )
        return True
    except Exception:
        logger.warning('Failed to send admin-notify email for application #%s',
                       application_id, exc_info=True)
        return False
