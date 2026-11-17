"""A scholar's graduation thank-yous, read and decided from the SCHOLAR FILE (sprint THANKS-SCHOLARS).

Part of the `views_admin` package; every name below is re-exported from `views_admin/__init__.py`.

⚠ THE RULING (owner 2026-11-16): "Thank yous are part of the scholar maintenance process." So a
thank-you follows the scholar file's own rules (`_ScholarsBase`), not the `review` key:
  * READ (`_file_for`): `scholars` holders in their own organisation, a super anywhere, and a mentor
    ONLY for a current student, read-only. Everyone else — a reviewer too, even the assigned one —
    gets the file's answer (403 without the `scholars` key, 404 outside the fence).
  * DECIDE (`may_decide_thanks`, the ONE home of the rule): today the scholar-file write,
    `_may_write_file` — a `scholars` holder of the file's organisation (a super passes every key). A
    mentor never decides (`_file_for` refuses their POST; `_may_write_file` is false for them). The
    owner chose today's Scholars key now: Scholars will be split into View and View-and-change for every
    scholar-file write in a later sprint, and today's holders keep the change power. That swap is this
    one method; the web follows the served `may_decide` without a change. No new key here.
    This applies R5 (2026-11-12, "An open case ends at awarded"): a reviewer's work ends at the award.
Unlike the other file writes there is NO `file_closed` check: a student may still thank their sponsor
once the file is closed (`in_programme._require_can_thank`), and that thank-you must be decidable.
The text may name the student, so no log line carries it.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import in_programme as in_programme_service
from ..models import GraduationMessage
from ..serializers_admin import AdminGraduationMessageSerializer
from .scholars import _ScholarsBase, _staff_names

logger = logging.getLogger('apps.scholarship.views_admin')


class _ThanksBase(_ScholarsBase):
    """The scholar-file fence, plus the ONE thank-you decide rule."""

    def may_decide_thanks(self, admin, app):
        """True when ``admin`` may approve or reject a thank-you on ``app``'s file. Today: the scholar-file
        write (`_may_write_file`). The GET serves it as `may_decide` and the POST asks it — one home."""
        return self._may_write_file(admin, app)


class AdminScholarThanksView(_ThanksBase):
    """GET admin/scholarship/scholars/<pk>/graduation-messages/ — the scholar's thank-yous, newest
    first, and `may_decide` (served, never derived on the web: the scholar-file write rule). A mentor
    reads them with `may_decide` false and the decider's NAME in `approved_by`, never an email (S1
    ruling A)."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        logger.info('AUDIT graduation_messages_read admin_id=%s app_id=%s', admin.id, app.id)
        # org-fence: `app` came through _file_for (the scholar file's own fence) just above.
        rows = list(GraduationMessage.objects.filter(application=app).order_by('-created_at', '-id'))
        messages = AdminGraduationMessageSerializer(rows, many=True).data
        as_mentor = self._as_mentor(admin)
        if as_mentor:
            names = _staff_names(m['approved_by'] for m in messages)
            for m in messages:
                m['approved_by'] = names.get((m['approved_by'] or '').lower(), '')
                m['review_note'] = ''   # staff-only, as the activity log's internal rows (review round)
        # A mentor is read-only (`_file_for`); not asking the rule for them saves its scope read.
        return Response({'messages': messages,
                         'may_decide': not as_mentor and self.may_decide_thanks(admin, app)})


class AdminScholarThanksReviewView(_ThanksBase):
    """POST admin/scholarship/scholars/<pk>/graduation-messages/<message_id>/review/ — approve or
    reject one thank-you (F9a). Body: ``{action: 'approve'|'reject', scrubbed_text?, review_note?}``.
    On approve the ``scrubbed_text`` (defaults to the raw text) is RE-SCANNED so a staff edit can never
    reintroduce an identifier (400 `scrubbed_leak`). Only a `pending` message can be approved;
    `pending`/`blocked` can be rejected; the decision locks the row (`in_programme._lock_status`).

    The order is fence → validate → lock: the file fence first, then the message must belong to THIS
    file (another file's message, or none, is the same 404 as a missing file, so walking ids tells
    nobody which exist), then the decide rule (`may_decide_thanks`), then the body."""

    def post(self, request, pk, message_id):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        # org-fence: the message is looked up only inside `app`, which came through _file_for.
        message = GraduationMessage.objects.filter(pk=message_id, application=app).first()
        if message is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self.may_decide_thanks(admin, app):
            return self._deny_role()
        message.application = app
        action = request.data.get('action') if isinstance(request.data, dict) else None
        action = action.strip() if isinstance(action, str) else ''
        by_email = getattr(admin, 'email', '') or ''
        try:
            if action == 'approve':
                in_programme_service.approve_graduation_message(
                    message, by_email=by_email,
                    scrubbed_text=request.data.get('scrubbed_text'),
                )
            elif action == 'reject':
                in_programme_service.reject_graduation_message(
                    message, by_email=by_email,
                    review_note=request.data.get('review_note', ''),
                )
            else:
                return Response({'error': 'action must be approve or reject',
                                 'code': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminGraduationMessageSerializer(message).data)
