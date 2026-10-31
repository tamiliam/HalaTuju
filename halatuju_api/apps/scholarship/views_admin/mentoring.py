"""The scholar file's Mentoring tab (student maintenance Sprint 7b, 2026-11-01). The rules live in
`apps/scholarship/mentoring.py`; THIS module is the fence and the HTTP shapes:

- `AdminScholarMentoringView` — `GET admin/scholarship/scholars/<pk>/mentoring/`;
- `AdminScholarMentoringActionView` — `POST .../mentoring/assign/` `{mentor_id, reason, email_student}`
  and `POST .../mentoring/end/` `{reason}`;
- `AdminScholarMentoringSessionsView` — `POST .../mentoring/sessions/` `{met_on, mode, minutes, notes,
  next_step}`.

⚠ WHO: the scholar file's own fence (`_ScholarsBase._file_for`: another organisation's file, an unknown
one or one with no file is 404, never 403; finance, partner and source users are refused) AND the
Mentors roster's readers (`mentoring.may_act`: super, org_admin, admin). A reviewer or QC who may open
the file is refused this tab (403) — mentors are the Mentors page's people. A closed file reads, and
refuses every write (409 `file_closed`). One class per url shape (lessons, Billing 2026-10-29).
"""
from rest_framework import status
from rest_framework.response import Response

from .. import mentoring
from ..models import Mentor
from .scholars import _ScholarsBase

_STATUS = {
    'forbidden': status.HTTP_403_FORBIDDEN,
    'not_found': status.HTTP_404_NOT_FOUND,
    'file_closed': status.HTTP_409_CONFLICT,
    'already_assigned': status.HTTP_409_CONFLICT,
    'conflict': status.HTTP_409_CONFLICT,
    'no_mentor': status.HTTP_409_CONFLICT,
}


def _mentoring_refusal(code):
    if code == 'not_found':
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'error': code, 'code': code}, status=_STATUS.get(code, status.HTTP_400_BAD_REQUEST))


def _data(request):
    return request.data if isinstance(request.data, dict) else {}


class _MentoringBase(_ScholarsBase):
    def _mentoring_file(self, request, pk):
        """`(app, admin, error)`: the file's fence, then the Mentoring roles."""
        app, admin, err = self._file_for(request, pk)
        if err:
            return None, None, err
        if not mentoring.may_act(admin):
            return None, None, self._deny_role()
        return app, admin, None


class AdminScholarMentoringView(_MentoringBase):
    """GET — the tab: `{current, history, meetings, asked_for_help, assignable, can_act, file_closed,
    email_switch_on}` (`mentoring.file_payload`)."""

    def get(self, request, pk):
        app, admin, err = self._mentoring_file(request, pk)
        if err:
            return err
        return Response(mentoring.file_payload(admin, app))


class AdminScholarMentoringActionView(_MentoringBase):
    """POST .../mentoring/assign/ and .../mentoring/end/ — 200 with the tab's payload (plus
    `emailed` on an assign). Refusals as `mentoring.MentoringError` codes: 403 forbidden; 404;
    409 file_closed / already_assigned / conflict / no_mentor; 400 mentor_not_found /
    mentor_inactive / own_application / too_long / bad_request."""
    ACTIONS = ('assign', 'end')

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, admin, err = self._mentoring_file(request, pk)
        if err:
            return err
        data = _data(request)
        reason = data.get('reason', '')
        emailed = None
        try:
            if action == 'assign':
                raw = data.get('mentor_id')
                if isinstance(raw, bool) or not isinstance(raw, (int, str)) or not str(raw).isdigit():
                    return _mentoring_refusal('bad_request')
                mentor = Mentor.objects.filter(pk=int(raw)).first()
                email = data.get('email_student', True)
                _row, emailed = mentoring.assign(admin, app, mentor, reason=reason,
                                                 email_student=email is not False)
            else:
                mentoring.end(admin, app, reason=reason)
        except mentoring.MentoringError as e:
            return _mentoring_refusal(e.code)
        payload = mentoring.file_payload(admin, app)
        if action == 'assign':
            payload['emailed'] = emailed
        return Response(payload)


class AdminScholarMentoringSessionsView(_MentoringBase):
    """POST .../mentoring/sessions/ — log a meeting with the CURRENT mentor. 201 with the tab's
    payload. Refusals: 403; 404; 409 file_closed / no_mentor; 400 bad_date / future_date / bad_mode /
    bad_minutes / notes_required / too_long / before_assignment."""

    def post(self, request, pk):
        app, admin, err = self._mentoring_file(request, pk)
        if err:
            return err
        data = _data(request)
        try:
            mentoring.log_session(admin, app, met_on=data.get('met_on'), mode=data.get('mode'),
                                  minutes=data.get('minutes'), notes=data.get('notes', ''),
                                  next_step=data.get('next_step', ''))
        except mentoring.MentoringError as e:
            return _mentoring_refusal(e.code)
        return Response(mentoring.file_payload(admin, app), status=status.HTTP_201_CREATED)
