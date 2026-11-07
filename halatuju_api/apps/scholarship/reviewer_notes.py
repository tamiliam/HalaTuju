"""Notes for the reviewer — the ONE writer and the window (request #55, 2026-11-07).

The table is `models/reviewer_notes.py` (`reviewer_notes`). The view is
`views_admin/reviewer_notes.py`; the gate (who may read, who may write) lives there, on `_AdminBase`.

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

from .interview_completeness import decision_gate_applies
from .models import ReviewerNote
from .models.reviewer_notes import NOTE_MAX

#: The statuses a note may be added at: Awaiting review, Interviewing.
NOTE_STATUSES = ('profile_complete', 'interviewing')

#: What does not count as writing: whitespace and the zero-width / BOM characters.
_BLANK = re.compile(r'[\s​-‍⁠﻿]')


class ReviewerNoteError(Exception):
    """Raised by ``add_note`` with a machine code: 'notes_closed', 'empty_body', 'too_long'."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def window_open(application):
    """May a note be added to ``application`` now? (Who may add one is the view's question.)"""
    return application.status in NOTE_STATUSES and decision_gate_applies(application)


def add_note(application, body, *, author):
    """Append one note by ``author`` (a `PartnerAdmin`). Raises ``ReviewerNoteError``."""
    if not window_open(application):
        raise ReviewerNoteError('notes_closed')
    text = body.strip() if isinstance(body, str) else ''
    if not _BLANK.sub('', text):
        raise ReviewerNoteError('empty_body')
    if len(text) > NOTE_MAX:
        raise ReviewerNoteError('too_long')
    return ReviewerNote.objects.create(
        application=application, body=text, author=author,
        author_email=(getattr(author, 'email', '') or '')[:254])


def notes_for(application):
    """Every note on ``application``, oldest first, as the card draws them."""
    rows = ReviewerNote.objects.filter(application=application).select_related('author')
    return [{
        'id': n.id,
        'body': n.body,
        'author_name': (getattr(n.author, 'name', '') or '') or n.author_email,
        'created_at': n.created_at.isoformat(),
    } for n in rows]
