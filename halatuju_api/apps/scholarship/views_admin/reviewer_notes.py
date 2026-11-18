"""GET/POST .../applications/<pk>/reviewer-notes/ — "Org admin and reviewer notes" (request #55, 2026-11-07;
two-way since request #73, 2026-11-16). Also GET .../staff-notifications/count/, the bell line's numbers.

READ: whoever may already open the file — `_scoped_application`, the detail GET's own fence: super,
org_admin, admin, qc (scope 'all', own organisation), the reviewer ASSIGNED to it (scope 'assigned');
an unassigned reviewer 403, finance / partner 403 (scope 'none'), another organisation 404.

WRITE (#73): org admins and a platform super (students.edit), plus the reviewer ASSIGNED to the case; QC and
everyone else read only. A caller who is neither is refused before the fence (as #55 did), so a stranger
learns nothing about the case; the side is then decided again on the locked row in
`reviewer_notes.add_note`, with the window and the body rules. Append-only: there is no PATCH and no DELETE.
The reviewer writes only while the case is OPEN (`staff_lifecycle.case_stage`, POST-AWARD-CUT): past it they
get main's severed-writer 403, whatever the window says (#73 re-check 4).

SEEN (#73): the GET is what draws the notes on the student page, so it clears the caller's "New note" mark
for this case (`staff_notifications.mark_seen`), and so does a successful POST (the replier has just read
them). The payload says which side the caller is on (`viewer`), so
the card picks its intro, its composer and "(you)" from the server's answer; `reason` says why the window
is shut ('not_yet' before Awaiting review, 'finished' after the review), so the card and the refusal agree.

A SEPARATE fetch, not a key on the detail payload, so the applicant-detail GET stays at its pinned
38 queries (`test_query_budgets.py`). Every refusal carries a `code`; the card words it in en/ms/ta.

Part of the `views_admin` package: re-exported from `views_admin/__init__.py`.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import reviewer_notes, staff_notifications, surface_gates
from ..models import ScholarshipApplication
from ..models.reviewer_notes import NOTE_MAX
from ..staff_lifecycle import OPEN, case_stage
from .base import _AdminBase

logger = logging.getLogger('apps.scholarship.views_admin')

_MESSAGES = {
    'writer_only': 'Only an org admin or the assigned reviewer can add a note.',
    'notes_not_yet': 'Notes can be added once the case reaches Awaiting review.',
    'notes_closed': 'The review is finished, so no more notes can be added.',
    'bad_body': 'This note contains characters that cannot be saved. Remove them and try again.',
    'empty_body': 'Write the note first.',
    'too_long': f'A note can be at most {NOTE_MAX:,} characters.',
}


def _may_write(admin, pk):
    """Before the fence: None when the caller may write, else the refusal ('writer_only' or 'severed').
    students.edit (M3b G5; a super holds every key) writes at any stage, its window permitting. Else only the
    case's ASSIGNED reviewer, and only while the case is OPEN: POST-AWARD-CUT severs the reviewer's link at
    the award, and a case ended before it is not theirs either (`may_write_case`), so this holds even if the
    notes window is ever widened. Still one query (the row, where an EXISTS was); the window is judged
    again on the locked row in `add_note`."""
    if surface_gates.may_work_students(admin):
        return None
    # org-fence: the caller's OWN assignment only; the fence (`_scoped_application`) runs next.
    app = ScholarshipApplication.objects.filter(pk=pk, assigned_to_id=admin.id).first()
    if app is None:
        return 'writer_only'
    return None if case_stage(app) == OPEN else 'severed'


class AdminReviewerNotesView(_AdminBase):
    """`GET` → `{notes, viewer, can_add, window_open, reason, max_length}`; `POST {body}` → the same, 201."""

    def _payload(self, app, admin):
        is_open = reviewer_notes.window_open(app)
        viewer = reviewer_notes.side_of(app, admin)
        return {
            'notes': reviewer_notes.notes_for(app, viewer=admin),
            'viewer': viewer,
            'window_open': is_open,
            'reason': None if is_open else reviewer_notes.closed_reason(app, app.status),
            'can_add': is_open and viewer != 'reader',
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
        if admin is not None:
            staff_notifications.mark_seen(admin, app)
        return Response(self._payload(app, admin))

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        refused = _may_write(admin, pk)
        if refused == 'writer_only':
            return Response({'error': _MESSAGES['writer_only'], 'code': 'writer_only'},
                            status=status.HTTP_403_FORBIDDEN)
        if refused:
            # Main's severed-writer 403 (`_deny_role`), plus the code the card words and reloads on.
            return Response({'error': 'Your admin role cannot perform this action.', 'code': 'notes_closed'},
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
        staff_notifications.mark_seen(admin, app)   # the replier has the notes on screen
        return Response(self._payload(app, admin), status=status.HTTP_201_CREATED)


class AdminStaffNotificationCountView(_AdminBase):
    """`GET admin/scholarship/staff-notifications/count/` → `{from_reviewer, from_org_admin}`: how many
    students have a note from the other side the caller has not seen. One query; the shell fetches it
    after it draws, so it never holds the page up. Anyone signed in to the admin may ask (it counts only
    their own rows)."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        return Response(staff_notifications.unseen_counts(admin))
