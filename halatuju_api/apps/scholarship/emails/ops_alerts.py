"""Mail that goes to us: the Vision outage alert and the profile-complete admin note.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.conf import settings
from django.core.mail import send_mail
from .shared import _P, logger


def send_vision_outage_alert_email(stats):
    """Alert the admin that Google Vision OCR appears to be down — every recent
    IC/parent-IC OCR attempt errored and none succeeded. Sent to
    ``settings.ADMIN_NOTIFY_EMAIL`` (contact@halatuju.xyz); skipped silently if unset.
    English-only (internal). Best-effort — swallows send failures."""
    to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
    if not to_email:
        return False
    try:
        send_mail(
            subject='[HalaTuju] Document OCR (Google Vision) may be down',
            message=(
                'Automated check: in the last {window_hours}h, every IC / parent-IC '
                'OCR attempt failed with a service error and none succeeded '
                '({service_failures} service failures across {attempts} attempts).\n\n'
                'While this persists, shortlisted students cannot pass the consent '
                'identity check (their IC can\'t be auto-verified). Please check the '
                'Google Vision API status, quota and billing for the HalaTuju project.\n\n'
                'This is an automated alert and will repeat daily until OCR recovers.'
            ).format(**stats),
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
