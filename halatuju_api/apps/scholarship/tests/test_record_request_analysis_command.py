"""TD-204 — the command that stages an analysis, and the guard that justifies its existence.

The command's reason to exist is NOT transport. A cockpit form would carry the prose just as well.
It exists because it runs INSIDE the repo, so it can check that every cited path actually resolves
— and an unchecked citation is decoration, not evidence. That check is what these tests protect.
"""
import json
import os
import tempfile
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import OrgRequest

# A real file in this repo, and a shape that will never exist.
A_REAL_FILE = 'halatuju_api/apps/scholarship/org_requests.py'
A_FICTION = 'halatuju_api/apps/scholarship/does_not_exist_xyz.py'


class TestRecordRequestAnalysisCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='cmd', name='Command Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='cmd-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='d@cmd.test')
        cls.req = OrgRequest.objects.create(
            organisation=cls.org, submitted_by=cls.oa, kind='feature',
            title='Add a link', description='d', status='triaged', triaged_kind='feature')

    def _payload(self, **over):
        data = {
            'request_id': self.req.id,
            'estimated_hours': '4.0',
            'cited_files': [A_REAL_FILE],
            'authored_by': 'claude-opus-5',
            'body': 'It reuses the existing invite engine.',
        }
        data.update(over)
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, fh)
        fh.close()
        self.addCleanup(lambda: os.path.exists(fh.name) and os.unlink(fh.name))
        return fh.name

    def test_report_only_by_default(self):
        # The house rule: a mutating command reports first and writes only on --apply.
        call_command('record_request_analysis', file=self._payload())
        self.assertEqual(self.req.analyses.count(), 0)

    def test_apply_stages_a_DRAFT_and_posts_nothing(self):
        call_command('record_request_analysis', file=self._payload(), apply=True)
        a = self.req.analyses.get()
        self.assertIsNone(a.approved_at, 'the owner approves; the command never does')
        self.assertEqual(self.req.comments.count(), 0)
        self.assertEqual(a.cited_files, [A_REAL_FILE])
        self.assertEqual(a.authored_by, 'claude-opus-5')

    def test_a_CITED_FILE_THAT_DOES_NOT_EXIST_IS_REFUSED(self):
        # The whole justification for the command. A hallucinated path must never reach the owner
        # dressed as evidence.
        with self.assertRaises(CommandError) as e:
            call_command('record_request_analysis',
                         file=self._payload(cited_files=[A_REAL_FILE, A_FICTION]), apply=True)
        self.assertIn(A_FICTION, str(e.exception))
        self.assertEqual(self.req.analyses.count(), 0)

    def test_the_check_runs_even_in_report_mode(self):
        # Otherwise the report would show a citation the apply would then reject.
        with self.assertRaises(CommandError):
            call_command('record_request_analysis', file=self._payload(cited_files=[A_FICTION]))

    def test_a_path_escaping_the_repo_is_refused(self):
        # `../../etc/passwd` exists on some machines; a citation is a pointer into THIS codebase.
        with self.assertRaises(CommandError) as e:
            call_command('record_request_analysis',
                         file=self._payload(cited_files=['../../../etc/passwd']), apply=True)
        self.assertIn('etc/passwd', str(e.exception))

    def test_the_repo_sha_is_captured(self):
        call_command('record_request_analysis', file=self._payload(), apply=True)
        sha = self.req.analyses.get().repo_sha
        # Git is available in this checkout; if it ever is not, the command degrades to '' rather
        # than failing, so accept either but pin the shape when present.
        self.assertTrue(sha == '' or len(sha) == 40, sha)

    def test_an_unknown_request_is_refused(self):
        with self.assertRaises(CommandError):
            call_command('record_request_analysis', file=self._payload(request_id=999999),
                         apply=True)

    def test_a_service_refusal_surfaces_as_its_CODE(self):
        # e.g. an empty body. The operator should see `body_required`, not a traceback.
        with self.assertRaises(CommandError) as e:
            call_command('record_request_analysis', file=self._payload(body='  '), apply=True)
        self.assertIn('body_required', str(e.exception))

    def test_citing_nothing_is_refused(self):
        with self.assertRaises(CommandError) as e:
            call_command('record_request_analysis', file=self._payload(cited_files=[]), apply=True)
        self.assertIn('files_required', str(e.exception))

    def test_unreadable_payload_is_a_clean_error(self):
        with self.assertRaises(CommandError):
            call_command('record_request_analysis', file='/no/such/payload.json')


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class TestApiMode(TestCase):
    """TD-206 (2026-08-01) — staging over the API so no database password reaches a laptop.

    Staging used to require exporting live DB_* from `gcloud run services describe`. Done twice in
    one sprint and deleted twice: a MANUAL mitigation, and the day you forget looks exactly like
    the day you remember. The super-only endpoint already existed; only the transport was wrong.

    What these tests hold: the citation guard still runs FIRST (it is the reason the command
    exists, so it must not be reachable-around by a transport), the token never becomes durable
    state, and the API's own refusal CODE survives the trip.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='api', name='API Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='api-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='d@api.test')
        cls.req = OrgRequest.objects.create(
            organisation=cls.org, submitted_by=cls.oa, kind='bug',
            title='Income card', description='d', status='triaged', triaged_kind='bug')

    def setUp(self):
        os.environ['HALATUJU_ADMIN_TOKEN'] = 'test-token'
        self.addCleanup(os.environ.pop, 'HALATUJU_ADMIN_TOKEN', None)
        self.calls = []

    def _payload(self, **over):
        data = {'request_id': self.req.id, 'estimated_hours': '4.0',
                'cited_files': [A_REAL_FILE], 'authored_by': 'claude-opus-5',
                'body': 'The card judged the declaration, not the evidence.'}
        data.update(over)
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, fh)
        fh.close()
        self.addCleanup(lambda: os.path.exists(fh.name) and os.unlink(fh.name))
        return fh.name

    def _http(self, *responses):
        """Patch the `requests` module the command imports lazily, recording every call."""
        queue = list(responses)

        def _request(method, url, **kw):
            self.calls.append((method, url, kw))
            return queue.pop(0) if queue else _FakeResponse()

        return mock.patch.dict(
            'sys.modules',
            {'requests': mock.Mock(request=_request, post=mock.Mock())})

    def test_apply_posts_to_the_api_and_writes_NOTHING_locally(self):
        detail = _FakeResponse(payload={'title': 'Income card', 'status': 'triaged',
                                        'organisation_name': 'API Org'})
        with self._http(detail, _FakeResponse(payload={'ok': True})):
            call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        # The local database is untouched — the row is created on the far side.
        self.assertEqual(self.req.analyses.count(), 0)
        methods = [c[0] for c in self.calls]
        self.assertEqual(methods, ['GET', 'POST'])
        self.assertTrue(self.calls[1][1].endswith(f'/requests/{self.req.id}/analysis/'))

    def test_the_token_travels_as_a_bearer_header_and_is_never_written_down(self):
        detail = _FakeResponse(payload={'title': 't', 'status': 'triaged',
                                        'organisation_name': 'API Org'})
        with self._http(detail, _FakeResponse()):
            call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        for _method, _url, kw in self.calls:
            self.assertEqual(kw['headers']['Authorization'], 'Bearer test-token')
        # Nothing persisted it: the whole security property of this change is that the credential
        # expires, which a cached copy would quietly undo.
        self.assertFalse(os.path.exists(os.path.join(os.getcwd(), '.halatuju_token')))

    def test_the_citation_guard_runs_BEFORE_any_network_call(self):
        # The guard is the reason this command exists rather than a form. A transport must never be
        # able to reach around it — not even by failing first and looking like the cause.
        with self._http(_FakeResponse()):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(cited_files=[A_FICTION]),
                             api=True, apply=True)
        self.assertIn('do not exist', str(e.exception))
        self.assertEqual(self.calls, [], 'it must not have called out at all')

    def test_report_only_still_reports_only(self):
        detail = _FakeResponse(payload={'title': 't', 'status': 'triaged',
                                        'organisation_name': 'API Org'})
        with self._http(detail):
            call_command('record_request_analysis', file=self._payload(), api=True)
        self.assertEqual([c[0] for c in self.calls], ['GET'], 'no POST without --apply')

    def test_an_api_refusal_surfaces_its_CODE_not_just_a_status(self):
        detail = _FakeResponse(payload={'title': 't', 'status': 'triaged',
                                        'organisation_name': 'API Org'})
        with self._http(detail, _FakeResponse(400, {'error': 'files_required'})):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        self.assertIn('files_required', str(e.exception))

    def test_an_expired_token_says_so_in_words(self):
        # The one failure this mode will actually produce in daily use. "401" alone sends someone
        # hunting for a permissions problem that isn't there.
        with self._http(_FakeResponse(401)):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        self.assertIn('expire', str(e.exception))

    def test_no_token_and_no_login_config_is_a_clean_refusal(self):
        os.environ.pop('HALATUJU_ADMIN_TOKEN', None)
        with mock.patch.dict(os.environ, {'SUPABASE_ANON_KEY': ''}, clear=False):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        self.assertIn('HALATUJU_ADMIN_TOKEN', str(e.exception))
