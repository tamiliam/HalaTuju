"""Organisation → Settings → Student communications (student maintenance S4b, 2026-10-29).

GET/PUT `admin/scholarship/organisation/student-emails/` — the wording of the emails a FUNDED student
receives about her results (`student_comms`), per kind and language, for the caller's OWN organisation.

⚠ THE ORGANISATION IS DERIVED, NEVER SENT — the Configuration tab's fence, reused by inheritance
(`_gate` + `_organisation_for`: a non-super reaches only its own organisation; a super with several
tenants is asked to choose with `?org=`). Writers: `super` and `org_admin`, as for every
organisation setting. Both verbs below override the parent's, so no stray verb is inherited.

PUT `{kind, language, subject, body}` stores the organisation's wording (refusals: 400 with `code`
unknown_template / empty / subject_too_long / unknown_placeholders / banned_phrase, naming the
offending `placeholders` / `phrases`);
`{kind, language, reset: true}` deletes it so the platform default applies again. Each write leaves an
`AUDIT student_email_template_set` line.

S6a (2026-10-30, owner rulings): the page lists EVERY email a student receives
(`student_email_catalogue.payload` — headings, languages, the lock or the switch, the platform flag,
last sent and, where the copy is a plain dict, the wording). POST `.../student-emails/switch/`
`{key, enabled}` (`AdminStudentEmailSwitchView`, its own class so no verb is shared between the two
urls) turns one of the owner's SAFE emails on or off for this organisation; any other key is 400
`not_switchable`. Same fence, same writers (`super`, `org_admin`); `AUDIT student_email_switch_set`.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .. import student_comms, student_email_catalogue
from .org_config import AdminOrganisationConfigurationView

logger = logging.getLogger('apps.scholarship.views_admin')


class AdminStudentEmailsView(AdminOrganisationConfigurationView):

    def _payload(self, org):
        return {'organisation': {'code': org.code, 'name': org.name},
                'enabled': student_comms.enabled(),
                'groups': list(student_email_catalogue.GROUPS),
                'catalogue': student_email_catalogue.payload(org),
                'templates': student_comms.templates_payload(org)}

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
        data = request.data if isinstance(request.data, dict) else {}
        kind, lang = str(data.get('kind') or ''), str(data.get('language') or '')
        try:
            if data.get('reset') is True:
                if kind not in student_comms.KINDS or lang not in student_comms.LANGUAGES:
                    raise student_comms.StudentCommsError('unknown_template')
                student_comms.reset(org, kind, lang)
            else:
                student_comms.save(org, kind, lang, data.get('subject'), data.get('body'),
                                   by_email=admin.email or '')
        except student_comms.StudentCommsError as e:
            # `placeholders` / `phrases` name the offending items (the shared TemplateEditor reads them).
            extra = {'placeholders': e.detail} if e.code == 'unknown_placeholders' else (
                {'phrases': e.detail} if e.code == 'banned_phrase' else {})
            return Response({'error': e.code, 'code': e.code, **extra}, status=status.HTTP_400_BAD_REQUEST)
        logger.warning('AUDIT student_email_template_set org=%s kind=%s lang=%s by=%s reset=%s',
                       org.code, kind, lang, admin.email, data.get('reset') is True)
        return Response(self._payload(org))


class AdminStudentEmailSwitchView(AdminStudentEmailsView):
    """POST `admin/scholarship/organisation/student-emails/switch/` `{key, enabled}` — S6a.

    POST ONLY (`http_method_names`): the GET / PUT of the parent belong to the other url, and one view
    answering two url shapes is how a wrong verb becomes a 500 (lessons, Billing 2026-10-29). The
    rule is the server's: `student_email_catalogue.set_switch` refuses every key that is not on the
    owner's list, so the page's lock is a reading of this answer, never a second copy of it."""
    http_method_names = ['post', 'options']

    def post(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        key, enabled = str(data.get('key') or ''), data.get('enabled')
        try:
            student_email_catalogue.set_switch(org, key, enabled, by_email=admin.email or '')
        except student_email_catalogue.NotSwitchable:
            return Response({'error': 'not_switchable', 'code': 'not_switchable'},
                            status=status.HTTP_400_BAD_REQUEST)
        logger.warning('AUDIT student_email_switch_set org=%s key=%s enabled=%s by=%s',
                       org.code, key, enabled, admin.email)
        return Response(self._payload(org))
