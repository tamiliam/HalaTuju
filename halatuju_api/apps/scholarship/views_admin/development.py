"""Programme → Development (student maintenance Sprint 10, 2026-11-02): an organisation's development modules
for its scholars, each module's Progress, and each scholar file's Growth tab. Part of the `views_admin` package;
re-exported from `views_admin/__init__.py`. The rules live in `apps/scholarship/development.py` (the staff
payloads in `development_progress.py`, the files in `development_files.py`, the emails in
`development_emails.py`); THIS module is the fence.

WHO (owner ruling, 2026-11-02): `development.may_make` — a super, an organisation admin, an admin. Every other
role (reviewer, QC, finance, partner, source, mentor) is refused 403. WHICH ORGANISATION: the gift named by
`?programme=` (resolved INSIDE the caller's organisation — another tenant's code is 404), else the caller's
own; a super with no organisation must name a gift (400 `programme_required`). A module outside the caller's
organisation is 404 on EVERY door — the CSV, a lesson file, a scholar's upload and the scholar file's tab
included. Scholars' work carries their names: staff only, never a sponsor or partner door. Each write leaves an
AUDIT line; nothing is written on a scholar's file. One class per url shape.
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from .. import development as svc
from .. import development_emails, development_files, development_progress
from ..models import DevelopmentModule, ModuleLesson
from ..survey_results import audiences
from .base import _AdminBase
from .letters import _data
from .scholars import _ScholarsBase

logger = logging.getLogger('apps.scholarship.views_admin')

_CONFLICT = {'task_locked', 'started_locked', 'archive_instead', 'not_published', 'not_live', 'switched_off',
             'no_due_date', 'nothing_to_review', 'video_or_file'}
_UNAVAILABLE = {'storage_unavailable'}


def _module_refusal(e):
    if e.code == 'not_found':   # deleted while the request was in flight
        return _module_not_found()
    body = {'error': e.code, 'code': e.code}
    if e.detail is not None:
        body['detail'] = e.detail
    code = (status.HTTP_409_CONFLICT if e.code in _CONFLICT else status.HTTP_503_SERVICE_UNAVAILABLE
            if e.code in _UNAVAILABLE else status.HTTP_400_BAD_REQUEST)
    return Response(body, status=code)


def _module_not_found():
    return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class _DevelopmentBase(_AdminBase):
    def _maker(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not svc.may_make(admin):
            return None, self._deny_role()
        return admin, None

    def _organisation(self, request, admin):
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return None, err
        if programme is not None:
            return programme.organisation, None
        if admin.owning_organisation_id:
            return admin.owning_organisation, None
        return None, Response({'error': 'programme_required', 'code': 'programme_required'},
                              status=status.HTTP_400_BAD_REQUEST)

    def _module(self, request, pk):
        """`(admin, module, error)` — the row IFF it is the caller's organisation's (a super: any)."""
        admin, err = self._maker(request)
        if err:
            return None, None, err
        qs = DevelopmentModule.objects.select_related('organisation', 'programme').filter(pk=pk)
        if not admin.is_super:
            qs = qs.filter(organisation_id=admin.owning_organisation_id) if admin.owning_organisation_id else qs.none()
        m = qs.first()
        return (admin, m, None) if m is not None else (None, None, _module_not_found())

    def _row(self, m):
        return development_progress.module_rows(m.organisation, only_id=m.id)[0]

    def _lesson(self, request, pk, lid):
        """`(admin, module, lesson, error)` — the lesson IFF it is a lesson of the caller's module."""
        admin, m, err = self._module(request, pk)
        if err:
            return None, None, None, err
        lesson = ModuleLesson.objects.filter(pk=lid, module=m).first()
        if lesson is None:
            return None, None, None, _module_not_found()
        return admin, m, lesson, None


class AdminModulesView(_DevelopmentBase):
    """GET admin/scholarship/development/ `?programme=` — the organisation's modules (each with its lessons), the
    four tabs' counts, the "For" picker with live counts, whether its `module_published` email is switched on,
    and the limits. POST — a new one `{title, summary, programme (gift code or null), publish_at (ISO or null =
    now), due_on (YYYY-MM-DD or null), task_kind, task_prompt, email_on_publish, remind, lessons: [{title, body,
    video_url}], action: publish|draft}`."""

    def get(self, request):
        admin, err = self._maker(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        from ..student_email_catalogue import may_send
        rows = development_progress.module_rows(org)
        counts = {k: sum(1 for r in rows if r['status'] == k) for k in ('published', 'scheduled', 'draft', 'archived')}
        return Response({'organisation': {'code': org.code, 'name': org.name}, 'modules': rows, 'counts': counts,
                         'audiences': audiences(org), 'email_switch_on': may_send(org, svc.EMAIL_KEY),
                         'limits': {'title': svc.TITLE_MAX, 'summary': svc.SUMMARY_MAX,
                                    'lesson_title': svc.LESSON_TITLE_MAX, 'lesson_body': svc.LESSON_BODY_MAX,
                                    'lessons': svc.MAX_LESSONS, 'prompt': svc.PROMPT_MAX,
                                    'file_bytes': development_files.MAX_BYTES}})

    def post(self, request):
        admin, err = self._maker(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        try:
            m = svc.create_module(org, _data(request), by_email=admin.email or '')
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        logger.warning('AUDIT module_created id=%s org=%s status=%s by=%s', m.id, org.code, m.status, admin.email)
        return Response(self._row(m), status=status.HTTP_201_CREATED)


class AdminModuleView(_DevelopmentBase):
    """PATCH admin/scholarship/development/<pk>/ — edit (from the first start the task type, the audience, the
    publishing time and "back to draft" are locked: 409 `task_locked` / `started_locked`). DELETE — a draft or
    a module nobody started (409 `archive_instead`)."""

    def patch(self, request, pk):
        admin, m, err = self._module(request, pk)
        if err:
            return err
        try:
            m = svc.update_module(m, _data(request), by_email=admin.email or '')
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        logger.warning('AUDIT module_edited id=%s org=%s status=%s by=%s', m.id, m.organisation.code, m.status,
                       admin.email)
        return Response(self._row(m))

    def delete(self, request, pk):
        admin, m, err = self._module(request, pk)
        if err:
            return err
        try:
            svc.delete_module(m)
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        logger.warning('AUDIT module_deleted id=%s org=%s by=%s', pk, m.organisation.code, admin.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminModuleActionView(_DevelopmentBase):
    """POST admin/scholarship/development/<pk>/archive/ — a published module leaves those who have not started
    (409 `not_published`). POST .../remind/ — "Remind those not done": the same reminder as the job, now, once
    per scholar (`{sent}`; 409 `not_live` / `no_due_date` / `switched_off` — the last writes nothing)."""
    ACTIONS = ('archive', 'remind')

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            return _module_not_found()
        admin, m, err = self._module(request, pk)
        if err:
            return err
        try:
            if action == 'archive':
                m = svc.archive(m, by_email=admin.email or '')
                logger.warning('AUDIT module_archived id=%s org=%s by=%s', m.id, m.organisation.code, admin.email)
                return Response(self._row(m))
            sent = development_emails.remind_not_done(m, by_email=admin.email or '')
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        return Response({'sent': sent, **development_progress.progress(m)})


class AdminModuleProgressView(_DevelopmentBase):
    """GET admin/scholarship/development/<pk>/progress/ — the module's row and one row per scholar (lessons read,
    task date, mentor, review, Late), the four tabs' counts (staff only)."""

    def get(self, request, pk):
        admin, m, err = self._module(request, pk)
        if err:
            return err
        from ..student_email_catalogue import may_send
        return Response({'module': self._row(m), 'email_switch_on': may_send(m.organisation, svc.EMAIL_KEY),
                         **development_progress.progress(m)})


class AdminModuleCsvView(_DevelopmentBase):
    """GET admin/scholarship/development/<pk>/csv/ — one row per scholar. The same roles and fence as every other
    module door; cells a spreadsheet could run are escaped."""

    def get(self, request, pk):
        admin, m, err = self._module(request, pk)
        if err:
            return err
        logger.warning('AUDIT module_csv id=%s org=%s by=%s', m.id, m.organisation.code, admin.email)
        response = HttpResponse(development_progress.progress_csv(m), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="module-{m.id}.csv"'
        return response


class AdminModuleScholarView(_DevelopmentBase):
    """GET admin/scholarship/development/<pk>/progress/<app>/file/ — a short signed link to ONE scholar's
    uploaded task for THIS module (404 when there is none, or the module is not the caller's organisation's).
    POST .../<app>/review/ `{comment}` — "Mark reviewed" (409 `nothing_to_review`; 400 `comment_too_long`)."""
    ACTIONS = ('file', 'review')

    def get(self, request, pk, app_id, action):
        admin, m, err = self._module(request, pk)
        if err or action != 'file':
            return err or _module_not_found()
        url = development_files.signed_url(development_progress.task_file_path(m, app_id))
        if not url:
            return _module_not_found()
        logger.warning('AUDIT module_task_file id=%s app=%s by=%s', m.id, app_id, admin.email)
        return Response({'url': url, 'expires_in': development_files.SIGNED_FOR})

    def post(self, request, pk, app_id, action):
        admin, m, err = self._module(request, pk)
        if err or action != 'review':
            return err or _module_not_found()
        try:
            development_progress.review(m, app_id, _data(request).get('comment'), by_email=admin.email or '')
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        logger.warning('AUDIT module_reviewed id=%s app=%s by=%s', m.id, app_id, admin.email)
        return Response(development_progress.progress(m))


class AdminModuleLessonFileView(_DevelopmentBase):
    """A lesson's file (staff). POST .../<pk>/lessons/<lid>/file/ `{storage_path, original_filename}` records it
    after the PUT to the signed URL (`AdminModuleLessonFileSignView`) — type and size are checked from the BYTES;
    GET → a short signed link; DELETE takes it off (the object goes after the commit). The lesson must be THIS
    module's (404 otherwise); a lesson with a video link takes no file (409 `video_or_file`)."""

    def get(self, request, pk, lid):
        admin, m, lesson, err = self._lesson(request, pk, lid)
        if err:
            return err
        url = development_files.signed_url(lesson.file_path)
        if not url:
            return _module_not_found()
        return Response({'url': url, 'expires_in': development_files.SIGNED_FOR})

    def post(self, request, pk, lid):
        admin, m, lesson, err = self._lesson(request, pk, lid)
        if err:
            return err
        data = _data(request)
        try:
            development_files.attach_lesson_file(m, lesson, data.get('storage_path'), data.get('original_filename'))
        except svc.DevelopmentError as e:
            return _module_refusal(e)
        logger.warning('AUDIT module_lesson_file id=%s lesson=%s by=%s', m.id, lesson.id, admin.email)
        return Response(self._row(m))

    def delete(self, request, pk, lid):
        admin, m, lesson, err = self._lesson(request, pk, lid)
        if err:
            return err
        development_files.remove_lesson_file(m, lesson)
        logger.warning('AUDIT module_lesson_file_removed id=%s lesson=%s by=%s', m.id, lesson.id, admin.email)
        return Response(self._row(m))


class AdminModuleLessonFileSignView(_DevelopmentBase):
    """POST admin/scholarship/development/<pk>/lessons/<lid>/file/sign/ `{size}` → `{upload_url, storage_path}`
    under THIS module's own prefix (409 `video_or_file`; 400 `file_too_large`; 503 `storage_unavailable`)."""

    def post(self, request, pk, lid):
        admin, m, lesson, err = self._lesson(request, pk, lid)
        if err:
            return err
        if lesson.video_url:
            return _module_refusal(svc.DevelopmentError('video_or_file'))
        try:
            return Response(development_files.lesson_upload_url(m, _data(request).get('size')))
        except svc.DevelopmentError as e:
            return _module_refusal(e)


class AdminScholarGrowthView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/development/ — the scholar file's Growth tab: each module this scholar
    can see or started, with their work. The file's own fence (`_file_for`: another organisation's, unknown or
    no file is 404) AND the module makers' roles."""

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        if not svc.may_make(admin):
            return self._deny_role()
        return Response(development_progress.scholar_file_payload(app))
