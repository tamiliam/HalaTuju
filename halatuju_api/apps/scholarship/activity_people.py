"""Who wrote each line of a scholar's activity log, and the log's filter (sprint P1, 2026-11-09).

The officer's Activity box shows a NAME and a PHOTO (or initials) per entry, the way Podio does, and
never an email for a known person (owner, P1-d). This module turns the stored ``actor_email`` of a page
of rows into ``actor = {name, photo_url, kind}`` — kind ``staff``, ``mentor``, ``scholar`` or
``unknown`` — or ``None`` for a FULLY AUTOMATIC row (the web shows the System icon).

⚠ COST: ONE query for every distinct email on the page (the logins and their profile rows, joined),
and ONE batch signing call for every photo on the page (`storage.create_signed_download_urls`) — so a
person is looked up and signed once however many rows they wrote. `test_activity_people.py` counts both.

⚠ THE SCHOLAR'S OWN ROWS HAVE NO EMAIL. `letters.acknowledge` and `in_programme.record_semester_result`
write their row with a blank ``actor_email`` (the student is the actor; ``meta.by = 'student'`` on a
result). Those two events are read as the scholar here, so they are not shown as "System". Any other
blank row is the system's.

⚠ A MENTOR IS NEVER NAMED TO A VIEWER OUTSIDE THE MENTORING TAB (P1 risk 1; the S7b rule that already
drops the mentoring rows for them). A pure mentor login (``role='mentor'``) on any row such a viewer
still receives comes back with no name, no photo and no email (``kind`` stays ``mentor``). A staff
member who also mentors is staff: their name is a staff name every reader of the file already sees.
"""
from django.db.models import Count
from django.db.models.functions import Lower

from . import staff_photo, storage
from .models.activity import (
    EVENT_LETTER_ACKNOWLEDGED, EVENT_RESULT_SUBMITTED, KIND_SYSTEM, MANUAL_KINDS,
)

KIND_STAFF, KIND_MENTOR, KIND_SCHOLAR, KIND_UNKNOWN = 'staff', 'mentor', 'scholar', 'unknown'

#: `?show=` on the log: every row, an officer's own entries (every manual kind), or the system's.
SHOW_ALL, SHOW_NOTES, SHOW_SYSTEM = 'all', 'notes', 'system'


def filtered(qs, show):
    """``qs`` narrowed to one filter; an unknown value is ``all`` (a filter never refuses a read)."""
    if show == SHOW_NOTES:
        return qs.filter(kind__in=MANUAL_KINDS)
    if show == SHOW_SYSTEM:
        return qs.filter(kind=KIND_SYSTEM)
    return qs


def counts(qs):
    """``{all, notes, system}`` for the filter's labels — ONE grouped query over the rows the viewer
    may read (the caller has already dropped what they may not)."""
    by_kind = dict(qs.order_by().values_list('kind').annotate(n=Count('id')))
    system = by_kind.get(KIND_SYSTEM, 0)
    total = sum(by_kind.values())
    return {SHOW_ALL: total, SHOW_NOTES: total - system, SHOW_SYSTEM: system}


def _scholar_emails(application):
    prof = getattr(application, 'profile', None)
    return {e.strip().lower() for e in (getattr(application, 'notify_email', ''),
                                        getattr(prof, 'contact_email', '')) if e and e.strip()}


def _by_the_scholar(row):
    if row.event == EVENT_LETTER_ACKNOWLEDGED:
        return True
    meta = row.meta if isinstance(row.meta, dict) else {}
    return row.event == EVENT_RESULT_SUBMITTED and meta.get('by') == 'student'


class Actors:
    """The people behind ONE page of rows. Build it once per request, then ``of(row)`` per row."""

    def __init__(self, rows, application, *, may_see_mentors):
        from apps.courses.models import PartnerAdmin
        self._may_see_mentors = bool(may_see_mentors)
        self._scholar_emails = _scholar_emails(application)
        prof = getattr(application, 'profile', None)
        self._scholar = {'name': getattr(prof, 'name', '') or '', 'photo_url': None, 'kind': KIND_SCHOLAR}
        emails = {(r.actor_email or '').strip().lower() for r in rows} - {''}
        logins = []
        if emails:
            logins = list(PartnerAdmin.objects.annotate(email_key=Lower('email'))
                          .filter(email_key__in=emails).select_related('reviewer_profile')
                          .only('id', 'email', 'name', 'role', 'reviewer_profile__photo_path'))
        self._people = {}
        for login in logins:
            kind = KIND_MENTOR if login.role == PartnerAdmin.MENTOR_ROLE else KIND_STAFF
            hidden = kind == KIND_MENTOR and not self._may_see_mentors
            profile = getattr(login, 'reviewer_profile', None)
            path = (profile.photo_path or '') if profile is not None and not hidden else ''
            self._people[login.email.lower()] = {
                'name': '' if hidden else (login.name or ''), 'kind': kind, 'hidden': hidden,
                'path': path if staff_photo.is_photo_key(path) else ''}
        paths = [p['path'] for p in self._people.values() if p['path']]
        self._urls = (storage.create_signed_download_urls(paths, expires_in=staff_photo.SIGNED_FOR)
                      if paths else {})

    def of(self, row):
        """``(actor or None, the email to serve)`` for one row. The email is blanked only for a
        mentor this viewer may not know about; the web never prints it for a known person."""
        email = (row.actor_email or '').strip()
        if not email:
            return (dict(self._scholar) if _by_the_scholar(row) else None), row.actor_email
        person = self._people.get(email.lower())
        if person is not None:
            actor = {'name': person['name'], 'photo_url': self._urls.get(person['path']) if person['path'] else None,
                     'kind': person['kind']}
            return actor, ('' if person['hidden'] else row.actor_email)
        if email.lower() in self._scholar_emails:
            return dict(self._scholar), row.actor_email
        return {'name': email, 'photo_url': None, 'kind': KIND_UNKNOWN}, row.actor_email
