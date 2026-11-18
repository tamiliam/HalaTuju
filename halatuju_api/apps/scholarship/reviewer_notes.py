"""Org admin and reviewer notes — the ONE writer and the window (request #55, 2026-11-07; made two-way by
request #73, 2026-11-16).

The table is `models/reviewer_notes.py` (`reviewer_notes`). The view is
`views_admin/reviewer_notes.py`; who may read is its fence, on `_AdminBase`.

⚠ WHO MAY WRITE (#73), decided HERE, on the locked row: the reviewer ASSIGNED to the case (the note is
recorded as the reviewer's), else anyone who may work students — org admins and a platform super (recorded
as the org admin side's). Anyone else is refused `writer_only`. The new reviewer after a reassignment reads
every note, the earlier reviewer's included, and is the one who may reply.

⚠ WHO HEARS (#73): the OTHER side only — the assigned reviewer when the org admin side writes, the org
admin side when the reviewer writes (`staff_notifications.the_other_side`). `notify` gives them an unseen
row INSIDE the note's transaction; the email goes after the commit, never with the text.

⚠ THE WINDOW: "from Awaiting Review until the reviewer records a decision" (owner, 2026-11-07).
  * FROM Awaiting Review — status `profile_complete` (its label IS "Awaiting review"), then
    `interviewing`. Not `shortlisted`: the student has not finished her profile and the case is not
    with the organisation yet.
  * UNTIL a decision — the codebase's OWN marker, `interview_completeness.decision_gate_applies`:
    the case is the reviewer's to decide while no Approve or Decline is recorded
    (`decision_recorded`: `verdict_decided_at` set AND overall accept/decline). A HOLD or a blank
    verdict also stamps `verdict_decided_at` but is NOT a decision (review F1 of TD-253), so the
    stamp alone would close the window on a reviewer who has not decided. A decision a super
    REOPENS is handed back to the reviewer, and so is the window — but only while the case is back
    at Interviewing; a reopen that lands at awaiting QC stays closed.
  After that the notes stay on the file, read-only, for good (award included).

⚠ NO ACTIVITY ROW. The note itself is the record (author, email, time; append-only). This follows
`merchant_flags`, whose log notes write no `staff_activity` row either (only open / close do).
"""
import re

from django.db import transaction

from . import staff_notifications, surface_gates
from .interview_completeness import decision_gate_applies
from .models import ReviewerNote
from .models.reviewer_notes import NOTE_MAX, ORG_ADMIN, REVIEWER
from .models.staff_notifications import REVIEWER_NOTE
from .staff_lifecycle import OPEN, case_stage
from .status_lock import StatusRefused, lock_application_for

#: The statuses a note may be added at: Awaiting review, Interviewing.
NOTE_STATUSES = ('profile_complete', 'interviewing')
#: Before the window: the case has not reached Awaiting review yet (#73 review). Every other closed status
#: is after it, or off the road (rejected, withdrawn, expired): the review is over.
_BEFORE_THE_WINDOW = ('submitted', 'shortlisted')

#: What does not count as writing, spelled out character by character so the card's counter trims
#: exactly what this trims (Python's `\s` and JS's `\s` / `trim()` disagree, U+FEFF for one): the
#: whitespace, the zero-width and direction marks, the soft hyphen, the Hangul fillers, the Braille
#: blank, the Mongolian vowel separator and the BOM. A note made only of these looks empty, so it is
#: refused (review R4). ⚠ The card's `INVISIBLE` (`view/ReviewerNotesCard.tsx`) must have this exact
#: source; `ReviewerNotesCardDrift.test.tsx` reads this line.
_INVISIBLE = re.compile(r'[\t\n\v\f\r \x1c-\x1f\x85\xa0\xad\u115f\u1160\u1680\u180e\u2000-\u200f\u2028-\u202f\u205f-\u2064\u2800\u3000\u3164\ufeff\uffa0]')
_EDGES = re.compile(f'^{_INVISIBLE.pattern}+|{_INVISIBLE.pattern}+$')


class ReviewerNoteError(Exception):
    """Raised with a machine code: 'writer_only', 'notes_not_yet', 'notes_closed', 'bad_body', 'empty_body',
    'too_long'."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def window_open(application):
    """May a note be added to ``application`` now? (Who may add one is `side_of`.)"""
    return application.status in NOTE_STATUSES and decision_gate_applies(application)


def closed_reason(application, status=None):
    """Why the window is shut: 'not_yet' (the case has not reached Awaiting review), 'finished' (the review
    is over), or None while it is open. ``status``: a locked row's own (`StatusRefused.status`)."""
    if status is None and window_open(application):
        return None
    return 'not_yet' if (status or application.status) in _BEFORE_THE_WINDOW else 'finished'


def _closed_error(application, status=None):
    return ReviewerNoteError('notes_not_yet' if closed_reason(application, status) == 'not_yet'
                             else 'notes_closed')


def side_of(application, admin):
    """Which side of the notes ``admin`` is on: 'reviewer' (assigned to the case), 'org_admin' (may work
    students: org admins and a super), else 'reader' (QC, an admin without the key: read-only)."""
    if admin is not None and application.assigned_to_id and application.assigned_to_id == admin.id:
        return REVIEWER
    if admin is not None and surface_gates.may_work_students(admin):
        return ORG_ADMIN
    return 'reader'


def clean_body(body):
    """The text a note would store (its invisible ends trimmed), or raise ``ReviewerNoteError``.

    `bad_body`: a NUL or a lone surrogate, which Postgres cannot store (a 500 before review R1)."""
    text = _EDGES.sub('', body) if isinstance(body, str) else ''
    if '\x00' in text or any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        raise ReviewerNoteError('bad_body')
    if not _INVISIBLE.sub('', text):
        raise ReviewerNoteError('empty_body')
    if len(text) > NOTE_MAX:
        raise ReviewerNoteError('too_long')
    return text


def add_note(application, body, *, author):
    """Append one note by ``author`` (a `PartnerAdmin`). Raises ``ReviewerNoteError``.

    ⚠ THE WINDOW IS RE-READ UNDER A ROW LOCK (review R3). A reviewer recording her decision at the
    same moment must not leave a note written after it: the application row is locked
    (`status_lock.lock_application_for`, which also refreshes ``application``), the window is asked
    again on the locked row, and only then is the note inserted, in the same transaction. The reviewer's
    side is also asked the case stage again here (OPEN only, POST-AWARD-CUT; #73 re-check 5)."""
    text = clean_body(body)
    with transaction.atomic():
        try:
            lock_application_for(application, NOTE_STATUSES)
        except StatusRefused as refused:
            raise _closed_error(application, refused.status or 'gone') from None
        side = side_of(application, author)   # asked of the locked row: a reassignment cannot race it
        if side == 'reader':
            raise ReviewerNoteError('writer_only')
        if side == REVIEWER and case_stage(application) != OPEN:
            # POST-AWARD-CUT, asked again of the locked row (#73 re-check 5): an award (or an ending) that
            # committed after the view's check still cuts the reviewer, whatever NOTE_STATUSES says.
            raise ReviewerNoteError('notes_closed')
        if not window_open(application):
            raise _closed_error(application)
        note = ReviewerNote.objects.create(
            application=application, body=text, author=author, author_role=side,
            author_email=(getattr(author, 'email', '') or '')[:254])
        people = staff_notifications.the_other_side(application, side=side, writer=author)
        staff_notifications.sweep(application.id)
        staff_notifications.notify(application, kind=REVIEWER_NOTE, source_id=note.id, recipients=people)
        staff_notifications.alert_by_email(application, author_role=side, recipients=people,
                                           source_id=note.id)
        return note


def notes_for(application, viewer=None):
    """Every note on ``application``, oldest first, as the card draws them. ``is_you``: ``viewer`` wrote it."""
    rows = ReviewerNote.objects.filter(application=application).select_related('author')
    viewer_id = getattr(viewer, 'id', None)
    return [{
        'id': n.id,
        'body': n.body,
        'author_name': (getattr(n.author, 'name', '') or '') or n.author_email,
        'author_role': n.author_role,
        'is_you': viewer_id is not None and n.author_id == viewer_id,
        'created_at': n.created_at.isoformat(),
    } for n in rows]
