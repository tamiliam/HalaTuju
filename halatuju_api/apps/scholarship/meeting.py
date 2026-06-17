"""Google Meet / Calendar seam for interview scheduling.

Creates (and updates/cancels) a Google Calendar event with an attached Google Meet
link for a booked interview, using a Google Workspace **service account with
domain-wide delegation** that impersonates ``settings.MEET_ORGANISER_EMAIL``
(e.g. ``info@halatuju.xyz``). Every applicant has a Gmail, so the event lands in
their Google Calendar with native reminders and a one-tap join.

Design rules (so a Google outage or a not-yet-configured Workspace never breaks a
booking):
  * Every public function is **best-effort** — it returns ``None`` (create) / ``False``
    (update, cancel) and logs, rather than raising, on any failure.
  * It is fully **inert** until ``settings.INTERVIEW_MEET_ENABLED`` is true AND
    ``settings.GOOGLE_MEET_SA_JSON`` holds the service-account credentials. So the
    scheduling surface can ship and go live before the Workspace account exists.
  * The Google client libraries are imported **lazily** inside the functions, so the
    module imports cleanly even if ``google-api-python-client`` isn't installed, and
    tests mock ``_calendar_service`` (the single seam) without touching the network.

NEVER call this with a live network in CI — tests patch ``_calendar_service``.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings

logger = logging.getLogger(__name__)

# Calendar scope: create/update events (incl. conferenceData for the Meet link).
_SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def meet_enabled() -> bool:
    """True only when auto-Meet is switched on AND credentials are present."""
    return bool(
        getattr(settings, 'INTERVIEW_MEET_ENABLED', False)
        and getattr(settings, 'GOOGLE_MEET_SA_JSON', '')
    )


def _calendar_service():
    """Build an authorised Google Calendar API client impersonating the organiser.

    Returns the service object, or ``None`` if disabled / misconfigured / the client
    libraries are unavailable. This is the single seam tests patch.
    """
    if not meet_enabled():
        return None
    try:
        import json

        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        info = json.loads(settings.GOOGLE_MEET_SA_JSON)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=_SCOPES,
        ).with_subject(settings.MEET_ORGANISER_EMAIL)
        # cache_discovery=False — no file cache on Cloud Run's read-only FS.
        return build('calendar', 'v3', credentials=creds, cache_discovery=False)
    except Exception:
        logger.warning('Meet: could not build calendar service', exc_info=True)
        return None


def _event_body(*, summary, description, start, duration_min, attendee_emails, with_meet):
    end = start + timedelta(minutes=duration_min or 45)
    body = {
        'summary': summary,
        'description': description or '',
        # RFC3339; the stored datetimes are tz-aware (UTC) so isoformat carries the offset.
        'start': {'dateTime': start.isoformat()},
        'end': {'dateTime': end.isoformat()},
        'attendees': [{'email': e} for e in attendee_emails if e],
        'guestsCanInviteOthers': False,
        'reminders': {'useDefault': True},
    }
    if with_meet:
        # Request a fresh Meet conference for THIS event (unique requestId per event).
        body['conferenceData'] = {
            'createRequest': {
                'requestId': f'b40-{summary}-{int(start.timestamp())}'[:64],
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
            }
        }
    return body


def _meet_link(event) -> str:
    """Pull the Meet URL out of a created/updated event payload."""
    if not event:
        return ''
    entry = (event.get('conferenceData') or {}).get('entryPoints') or []
    for ep in entry:
        if ep.get('entryPointType') == 'video' and ep.get('uri'):
            return ep['uri']
    return event.get('hangoutLink', '') or ''


def create_event(*, summary, description, start, duration_min, attendee_emails):
    """Create a calendar event with a Meet link. Best-effort.

    Returns ``{'url': <meet_url>, 'event_id': <id>}`` on success, else ``None``.
    """
    service = _calendar_service()
    if service is None:
        return None
    try:
        body = _event_body(
            summary=summary, description=description, start=start,
            duration_min=duration_min, attendee_emails=attendee_emails, with_meet=True,
        )
        event = service.events().insert(
            calendarId='primary', body=body, conferenceDataVersion=1,
            sendUpdates='none',  # we send our own bilingual confirmation email
        ).execute()
        return {'url': _meet_link(event), 'event_id': event.get('id', '')}
    except Exception:
        logger.warning('Meet: create_event failed', exc_info=True)
        return None


def update_event(event_id, *, start, duration_min):
    """Move an existing event to a new time (reschedule). Best-effort → bool."""
    if not event_id:
        return False
    service = _calendar_service()
    if service is None:
        return False
    try:
        end = start + timedelta(minutes=duration_min or 45)
        service.events().patch(
            calendarId='primary', eventId=event_id,
            body={'start': {'dateTime': start.isoformat()},
                  'end': {'dateTime': end.isoformat()}},
            conferenceDataVersion=1, sendUpdates='none',
        ).execute()
        return True
    except Exception:
        logger.warning('Meet: update_event failed for %s', event_id, exc_info=True)
        return False


def cancel_event(event_id):
    """Delete the calendar event (cancel). Best-effort → bool."""
    if not event_id:
        return False
    service = _calendar_service()
    if service is None:
        return False
    try:
        service.events().delete(
            calendarId='primary', eventId=event_id, sendUpdates='none',
        ).execute()
        return True
    except Exception:
        logger.warning('Meet: cancel_event failed for %s', event_id, exc_info=True)
        return False
