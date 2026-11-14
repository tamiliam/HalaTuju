"""GET/POST .../applications/<pk>/reviewer-notes/ — "Notes for the reviewer" (request #55, 2026-11-07).

READ: whoever may already open the file — `_scoped_application`, the detail GET's own fence: super,
org_admin, admin, qc (scope 'all', own organisation), the reviewer ASSIGNED to it (scope 'assigned');
an unassigned reviewer 403, finance / partner 403 (scope 'none'), another organisation 404.

WRITE: org_admin and a platform super ONLY (owner); the same fence; then the window and the body
rules in `reviewer_notes.add_note`. Append-only: there is no PATCH and no DELETE.

A SEPARATE fetch, not a key on the detail payload, so the applicant-detail GET stays at its pinned
38 queries (`test_query_budgets.py`). Every refusal carries a `code`; the card words it in en/ms/ta.

Part of the `views_admin` package: re-exported from `views_admin/__init__.py`.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import reviewer_notes, surface_gates
from ..models.reviewer_notes import NOTE_MAX
from .base import _AdminBase

logger = logging.getLogger('apps.scholarship.views_admin')

_MESSAGES = {
    'writer_only': 'Only an organisation admin can add a note for the reviewer.',
    'notes_closed': 'Notes can be added from Awaiting review until the reviewer records a decision.',
    'bad_body': 'This note contains characters that cannot be saved. Remove them and try again.',
    'empty_body': 'Write the note first.',
    'too_long': f'A note can be at most {NOTE_MAX:,} characters.',
}


def _may_write(view, admin):
    return surface_gates.may_work_students(admin)   # students.edit (M3b G5; a super holds every key)


class AdminReviewerNotesView(_AdminBase):
    """`GET` → `{notes, can_add, window_open, max_length}`; `POST {body}` → the same, 201."""

    def _payload(self, app, admin):
        is_open = reviewer_notes.window_open(app)
        return {
            'notes': reviewer_notes.notes_for(app),
            'window_open': is_open,
            'can_add': is_open and _may_write(self, admin),
            'max_length': NOTE_MAX,
        }

    def get(self, request, pk):
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        admin = self.get_admin(request)
        # Review R5: the notes are part of the file, so their read is audited like the detail GET's
        # (`AUDIT applicant_detail_read`): ids only, never the text.
        logger.info('AUDIT reviewer_notes_read admin_id=%s app_id=%s', getattr(admin, 'id', '?'), pk)
        return Response(self._payload(app, admin))

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not _may_write(self, admin):
            return Response({'error': _MESSAGES['writer_only'], 'code': 'writer_only'},
                            status=status.HTTP_403_FORBIDDEN)
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        try:
            # Review R2: a JSON body that is not an object (`[...]`, `"text"`) has no `.get`.
            body = request.data.get('body') if isinstance(request.data, dict) else None
            note = reviewer_notes.add_note(app, body, author=admin)
        except reviewer_notes.ReviewerNoteError as e:
            return Response({'error': _MESSAGES[e.code], 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        # No text in the log line: a note may name the family's circumstances.
        logger.info('AUDIT reviewer_note_added admin_id=%s app_id=%s note_id=%s',
                    admin.id, app.id, note.id)
        return Response(self._payload(app, admin), status=status.HTTP_201_CREATED)
