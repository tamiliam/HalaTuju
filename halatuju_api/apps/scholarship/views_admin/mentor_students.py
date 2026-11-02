"""A MENTOR's own students (student maintenance Sprint 7c, 2026-11-01). The rules and the readers are
`apps/scholarship/mentor_desk.py`; THIS module is the door and the HTTP shapes:

- `AdminMentorStudentsView` — `GET admin/mentor/students/` → `{organisation, students}`;
- `AdminMentorStudentView` — `GET admin/mentor/students/<pk>/` → one student (`pk` = the application);
- `AdminMentorStudentSessionsView` — `POST admin/mentor/students/<pk>/sessions/` `{met_on, mode, minutes,
  notes, next_step, concern}` → 201 with the student's page.
- `AdminMentorStudentModuleFileView` — `GET admin/mentor/students/<pk>/modules/<mid>/file/` → a short signed
  link to the student's uploaded development-module task (S10).

⚠ WHO: a MENTOR, and nobody else. These three views are the ONLY additions to `mentor_methods` in 7c
(`test_mentor_denied_everywhere.py` pins the full list); staff, sources and students are refused (403).
S7d: a STAFF member with an active mentor record (`mentor_desk.mentor_of`) is a mentor here too — staff
pass `get_admin` on every method, so `mentor_methods` is untouched; staff WITHOUT one are still 403.
A student who is not the caller's CURRENT student — another mentor's, an ended assignment, another
organisation's, the mentor's own application, an unknown id — is 404, one answer for all.
"""
from rest_framework import status
from rest_framework.response import Response

from .. import mentor_desk
from ..mentoring import MentoringError
from .base import _AdminBase

_STATUS = {'not_found': status.HTTP_404_NOT_FOUND, 'file_closed': status.HTTP_409_CONFLICT}


class _MentorBase(_AdminBase):
    def _mentor(self, request):
        """`(login, error)`: the caller's own mentor login, or 401/403 for anyone else."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if mentor_desk.mentor_of(admin) is None:
            return None, self._deny_role()
        return admin, None

    @staticmethod
    def _not_found():
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class AdminMentorStudentsView(_MentorBase):
    """GET — My students."""
    mentor_methods = ('get',)

    def get(self, request):
        login, err = self._mentor(request)
        if err:
            return err
        return Response(mentor_desk.list_payload(login))


class AdminMentorStudentView(_MentorBase):
    """GET — one current student (404 for anyone else's)."""
    mentor_methods = ('get',)

    def get(self, request, pk):
        login, err = self._mentor(request)
        if err:
            return err
        assignment = mentor_desk.assignment_for(login, pk)
        if assignment is None:
            return self._not_found()
        return Response(mentor_desk.student_payload(login, assignment))


class AdminMentorStudentSessionsView(_MentorBase):
    """POST — log a meeting. 201 with the student's page. Refusals: 404 (not a current student, now or
    once the lock is held); 409 file_closed; 400 bad_date / future_date / bad_mode / bad_minutes /
    notes_required / too_long / before_assignment."""
    mentor_methods = ('post',)

    def post(self, request, pk):
        login, err = self._mentor(request)
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        try:
            mentor_desk.log_own_session(
                login, pk, met_on=data.get('met_on'), mode=data.get('mode'), minutes=data.get('minutes'),
                notes=data.get('notes', ''), next_step=data.get('next_step', ''),
                concern=data.get('concern') is True)
        except MentoringError as e:
            if e.code == 'not_found':
                return self._not_found()
            return Response({'error': e.code, 'code': e.code},
                            status=_STATUS.get(e.code, status.HTTP_400_BAD_REQUEST))
        assignment = mentor_desk.assignment_for(login, pk)
        if assignment is None:   # ended between the write and this read: the meeting is saved
            return Response({'saved': True}, status=status.HTTP_201_CREATED)
        return Response(mentor_desk.student_payload(login, assignment), status=status.HTTP_201_CREATED)


class AdminMentorStudentModuleFileView(_MentorBase):
    """GET admin/mentor/students/<pk>/modules/<mid>/file/ — a short signed link to the student's uploaded task for
    one development module (S10 review 1: signed on the tap, never carried in a payload). The student must be the
    caller's CURRENT student (an ended assignment, another mentor's student: 404) and the module one the student
    can see; no upload is 404 too."""
    mentor_methods = ('get',)

    def get(self, request, pk, mid):
        login, err = self._mentor(request)
        if err:
            return err
        assignment = mentor_desk.assignment_for(login, pk)
        if assignment is None:
            return self._not_found()
        from .. import development_files
        from ..development_progress import mentor_task_file_path
        url = development_files.signed_url(mentor_task_file_path(assignment.application, mid))
        if not url:
            return self._not_found()
        return Response({'url': url, 'expires_in': development_files.SIGNED_FOR})
