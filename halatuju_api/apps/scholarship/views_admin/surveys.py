"""Programme → Surveys (student maintenance Sprint 9, 2026-11-02): an organisation's questions to its scholars,
and each scholar file's Surveys tab. Part of the `views_admin` package; re-exported from
`views_admin/__init__.py`. The rules live in `apps/scholarship/surveys.py` (the staff payloads in
`survey_results.py`, the emails in `survey_emails.py`); THIS module is the fence.

WHO (owner ruling, 2026-11-02): `surveys.may_make` — a super, an organisation admin, an admin. Every other
role (reviewer, QC, finance, partner, source, mentor) is refused 403. WHICH ORGANISATION: the gift named by
`?programme=` (resolved INSIDE the caller's organisation — another tenant's code is 404), else the caller's
own; a super with no organisation must name a gift (400 `programme_required`). One survey outside the
caller's organisation is 404 on EVERY door, the CSV included. Answers carry the scholar's name: staff
only, never a sponsor or partner door. Each write leaves an AUDIT line; nothing is written on a scholar's
file. One class per url shape.
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from .. import survey_emails, survey_results
from .. import surveys as svc
from ..models import Survey
from .base import _AdminBase
from .letters import _data
from .scholars import _ScholarsBase

logger = logging.getLogger('apps.scholarship.views_admin')

_CONFLICT = {'questions_locked', 'answered_locked', 'close_instead', 'not_open', 'switched_off'}


def _survey_refusal(e):
    if e.code == 'not_found':   # deleted while the request was in flight (review 3)
        return _not_found()
    body = {'error': e.code, 'code': e.code}
    if e.detail is not None:
        body['detail'] = e.detail
    return Response(body, status=status.HTTP_409_CONFLICT if e.code in _CONFLICT else status.HTTP_400_BAD_REQUEST)


def _not_found():
    return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class _SurveysBase(_AdminBase):
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

    def _survey(self, request, pk):
        """`(admin, survey, error)` — the row IFF it is the caller's organisation's (a super: any)."""
        admin, err = self._maker(request)
        if err:
            return None, None, err
        qs = Survey.objects.select_related('organisation', 'programme').filter(pk=pk)
        if not admin.is_super:
            qs = qs.filter(organisation_id=admin.owning_organisation_id) if admin.owning_organisation_id else qs.none()
        s = qs.first()
        return (admin, s, None) if s is not None else (None, None, _not_found())

    def _row(self, s):
        return survey_results.staff_rows(s.organisation, only_id=s.id)[0]


class AdminSurveysView(_SurveysBase):
    """GET admin/scholarship/surveys/ `?programme=` — the organisation's surveys (each with its questions),
    the "For" picker with live counts, whether its `survey_open` email is switched on, and the limits.
    POST — a new one `{title, intro, programme (gift code or null), opens_at, closes_at (ISO), email_on_open,
    remind, questions: [{kind, text, hint, required, mentor_only, options}], action: publish|draft}`."""

    def get(self, request):
        admin, err = self._maker(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        from ..student_email_catalogue import may_send
        rows = survey_results.staff_rows(org)
        counts = {k: sum(1 for r in rows if r['status'] == k) for k in ('open', 'scheduled', 'draft', 'closed')}
        return Response({'organisation': {'code': org.code, 'name': org.name}, 'surveys': rows, 'counts': counts,
                         'audiences': survey_results.audiences(org), 'email_switch_on': may_send(org, svc.EMAIL_KEY),
                         'limits': {'title': svc.TITLE_MAX, 'intro': svc.INTRO_MAX, 'question': svc.QUESTION_MAX,
                                    'hint': svc.HINT_MAX, 'option': svc.OPTION_MAX, 'options': svc.MAX_OPTIONS,
                                    'questions': svc.MAX_QUESTIONS}})

    def post(self, request):
        admin, err = self._maker(request)
        if err:
            return err
        org, err = self._organisation(request, admin)
        if err:
            return err
        try:
            s = svc.create(org, _data(request), by_email=admin.email or '')
        except svc.SurveyError as e:
            return _survey_refusal(e)
        logger.warning('AUDIT survey_created id=%s org=%s status=%s by=%s', s.id, org.code, s.status, admin.email)
        return Response(self._row(s), status=status.HTTP_201_CREATED)


class AdminSurveyView(_SurveysBase):
    """PATCH admin/scholarship/surveys/<pk>/ — edit (from the first answer: title, introduction, closing date
    and the email choices only — 409 `questions_locked` / `answered_locked`). DELETE — only while nobody has
    answered (409 `close_instead`)."""

    def patch(self, request, pk):
        admin, s, err = self._survey(request, pk)
        if err:
            return err
        try:
            s = svc.update(s, _data(request), by_email=admin.email or '')
        except svc.SurveyError as e:
            return _survey_refusal(e)
        logger.warning('AUDIT survey_edited id=%s org=%s status=%s by=%s', s.id, s.organisation.code, s.status,
                       admin.email)
        return Response(self._row(s))

    def delete(self, request, pk):
        admin, s, err = self._survey(request, pk)
        if err:
            return err
        try:
            svc.delete(s)
        except svc.SurveyError as e:
            return _survey_refusal(e)
        logger.warning('AUDIT survey_deleted id=%s org=%s by=%s', pk, s.organisation.code, admin.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminSurveyActionView(_SurveysBase):
    """POST admin/scholarship/surveys/<pk>/close/ — "Close now" (an open one only, 409 `not_open`).
    POST .../remind/ — "Remind those who have not answered": the same reminder as the job, now, once per
    scholar (`{sent}`; 409 `not_open`)."""
    ACTIONS = ('close', 'remind')

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            return _not_found()
        admin, s, err = self._survey(request, pk)
        if err:
            return err
        try:
            if action == 'close':
                s = svc.close_now(s, by_email=admin.email or '')
                logger.warning('AUDIT survey_closed id=%s org=%s by=%s', s.id, s.organisation.code, admin.email)
                return Response(self._row(s))
            sent = survey_emails.remind_now(s, by_email=admin.email or '')
        except svc.SurveyError as e:
            return _survey_refusal(e)
        return Response({'sent': sent, 'email_switch_on': True, **survey_results.results(s)})


class AdminSurveyResultsView(_SurveysBase):
    """GET admin/scholarship/surveys/<pk>/results/ — the survey's row (with its questions), the summary per
    question, each scholar's response and who has not answered (names; staff only)."""

    def get(self, request, pk):
        admin, s, err = self._survey(request, pk)
        if err:
            return err
        from ..student_email_catalogue import may_send
        return Response({'survey': self._row(s), 'email_switch_on': may_send(s.organisation, svc.EMAIL_KEY),
                         **survey_results.results(s)})


class AdminSurveyCsvView(_SurveysBase):
    """GET admin/scholarship/surveys/<pk>/csv/ — one row per response, one column per question. The same
    roles and the same organisation fence as every other survey door; cells a spreadsheet could run are
    escaped."""

    def get(self, request, pk):
        admin, s, err = self._survey(request, pk)
        if err:
            return err
        logger.warning('AUDIT survey_csv id=%s org=%s by=%s', s.id, s.organisation.code, admin.email)
        response = HttpResponse(survey_results.results_csv(s), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="survey-{s.id}.csv"'
        return response


class AdminScholarSurveysView(_ScholarsBase):
    """GET admin/scholarship/scholars/<pk>/surveys/ — the scholar file's Surveys tab: each survey this
    scholar answered, with the answers, and the open ones still waiting. The file's own fence
    (`_file_for`: another organisation's, unknown or no file is 404) AND the survey makers' roles."""

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        if not svc.may_make(admin):
            return self._deny_role()
        return Response(survey_results.scholar_file_payload(app))
