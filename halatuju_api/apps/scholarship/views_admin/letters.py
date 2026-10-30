"""The scholar file's Letters tab, and an organisation's letter wording (student maintenance S6b, 2026-10-31).

Part of the `views_admin` package; re-exported from `views_admin/__init__.py`. The rules live in
`apps/scholarship/letters.py`; THIS module is the fence.

WHO (owner rulings, 2026-10-30):
  * READ — the scholar file's own fence (`_ScholarsBase._file_for`: the Applications rule; finance,
    partner and source users refused; another organisation 404).
  * ISSUE — suspension and termination: super or org_admin; general, discipline, close-out: anyone
    who may WRITE on the case (`_can_review_app`). RESEND — the same rights as issuing that kind.
  * WITHDRAW — super or org_admin, with a reason.
One class per url shape (lessons, Billing 2026-10-29: one view on two urls is how a wrong verb
becomes a 500). Nothing here writes a status, a sub-state or money: letters are documents only.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import letters as svc
from ..models import Letter
from .org_config import AdminOrganisationConfigurationView
from .scholars import _ScholarsBase

logger = logging.getLogger('apps.scholarship.views_admin')

_STATUS = {'forbidden': status.HTTP_403_FORBIDDEN, 'file_closed': status.HTTP_409_CONFLICT,
           'withdrawn': status.HTTP_409_CONFLICT}


def _letter_refusal(e):
    extra = {'placeholders': e.detail} if e.code == 'unknown_placeholders' else (
        {'phrases': e.detail} if e.code == 'banned_phrase' else {})
    return Response({'error': e.code, 'code': e.code, **extra},
                    status=_STATUS.get(e.code, status.HTTP_400_BAD_REQUEST))


def _data(request):
    return request.data if isinstance(request.data, dict) else {}


class _LettersBase(_ScholarsBase):
    @staticmethod
    def _senior(admin):
        return bool(getattr(admin, 'is_super', False) or getattr(admin, 'role', '') == 'org_admin')

    def _kinds_for(self, admin, app):
        """The kinds THIS admin may issue on THIS file — the one rule the dialog and the POST share."""
        if self._senior(admin):
            return svc.KINDS
        if self._can_review_app(admin, app):
            return tuple(k for k in svc.KINDS if k not in svc.SENIOR_KINDS)
        return ()

    def _letter(self, app, lid):
        return Letter.objects.filter(pk=lid, application=app).select_related('application').first()


class AdminScholarLettersView(_LettersBase):
    """GET/POST admin/scholarship/scholars/<pk>/letters/ — the tab; POST issues one letter
    `{kind, language, clause, note, confirm_name}` (201 with the letter)."""

    def get(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        rows = svc.for_file(app)
        kinds = self._kinds_for(admin, app)
        if app.status == 'closed':
            kinds = tuple(k for k in kinds if k in svc.CLOSED_FILE_KINDS)
        return Response({
            'letters': [svc.admin_dict(r) for r in rows],
            'can_issue': list(kinds),
            'can_withdraw': self._senior(admin),
            'prompt_close': svc.prompt_close(app, rows),
            'response_days': svc.response_days(app.owning_organisation),
            'student_name': svc.student_name(app),
            'default_language': 'ms' if (app.locale or '') == 'ms' else 'en',
            'file_closed': app.status == 'closed',
        })

    def post(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        data = _data(request)
        try:
            letter = svc.issue(app, kind=str(data.get('kind') or ''), language=str(data.get('language') or ''),
                               clause=data.get('clause') or '', note=data.get('note') or '',
                               confirm_name=data.get('confirm_name') or '', by_admin=admin,
                               allowed_kinds=self._kinds_for(admin, app))
        except svc.LetterError as e:
            return _letter_refusal(e)
        logger.warning('AUDIT letter_issued app=%s letter=%s kind=%s by=%s',
                       app.id, letter.id, letter.kind, admin.email)
        return Response(svc.admin_dict(letter), status=status.HTTP_201_CREATED)


class AdminScholarLetterPreviewView(_LettersBase):
    """POST admin/scholarship/scholars/<pk>/letters/preview/ — the dialog's draft. Writes nothing."""

    def post(self, request, pk):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        data = _data(request)
        try:
            return Response(svc.preview(app, kind=str(data.get('kind') or ''),
                                        language=str(data.get('language') or ''),
                                        clause=data.get('clause') or '', note=data.get('note') or '',
                                        allowed_kinds=self._kinds_for(admin, app)))
        except svc.LetterError as e:
            return _letter_refusal(e)


class AdminScholarLetterActionView(_LettersBase):
    """POST admin/scholarship/scholars/<pk>/letters/<lid>/withdraw/ `{reason}` (super / org_admin) and
    .../resend/ (the issuing rights for that kind)."""

    def post(self, request, pk, lid, action):
        app, admin, err = self._file_for(request, pk)
        if err:
            return err
        letter = self._letter(app, lid)
        if letter is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            if action == 'withdraw':
                if not self._senior(admin):
                    return self._deny_role()
                letter = svc.withdraw(letter, reason=_data(request).get('reason'), by_admin=admin)
                logger.warning('AUDIT letter_withdrawn app=%s letter=%s by=%s', app.id, letter.id, admin.email)
            elif action == 'resend':
                svc.resend(letter, allowed_kinds=self._kinds_for(admin, app))
                letter.refresh_from_db()
            else:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        except svc.LetterError as e:
            return _letter_refusal(e)
        return Response(svc.admin_dict(letter))


class AdminScholarLetterPdfView(_LettersBase):
    """GET admin/scholarship/scholars/<pk>/letters/<lid>/pdf/ — a 300-second link, minted on a click."""

    def get(self, request, pk, lid):
        app, _admin, err = self._file_for(request, pk)
        if err:
            return err
        letter = self._letter(app, lid)
        url = svc.pdf_url(letter) if letter is not None else None
        if not url:
            return Response({'error': 'no_pdf', 'code': 'no_pdf'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'url': url, 'expires_in': 300})


class AdminLetterTemplatesView(AdminOrganisationConfigurationView):
    """GET/PUT admin/scholarship/organisation/letter-templates/ — the organisation's wording for the
    five letters, English and Malay (S6b). The Configuration tab's fence and writers (super,
    org_admin), as the student emails beside it. PUT `{kind, language, subject, body}` or
    `{kind, language, reset: true}`; `AUDIT letter_template_set`."""

    def _payload(self, org):
        return {'organisation': {'code': org.code, 'name': org.name},
                'templates': svc.templates_payload(org), 'response_days': svc.response_days(org)}

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        return Response(self._payload(org))

    def put(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        data = _data(request)
        kind, lang = str(data.get('kind') or ''), str(data.get('language') or '')
        try:
            if data.get('reset') is True:
                svc.reset_template(org, kind, lang)
            else:
                svc.save_template(org, kind, lang, data.get('subject'), data.get('body'),
                                  by_email=admin.email or '')
        except svc.LetterError as e:
            return _letter_refusal(e)
        logger.warning('AUDIT letter_template_set org=%s kind=%s lang=%s by=%s reset=%s',
                       org.code, kind, lang, admin.email, data.get('reset') is True)
        return Response(self._payload(org))
