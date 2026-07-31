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
from apps.scholarship.management.commands import record_request_analysis as cmd
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
        self.assertIn('expired', str(e.exception))

    def test_a_403_repeats_what_the_API_said_and_does_NOT_blame_expiry(self):
        # Real incident, 2026-08-01. A token minted from a browser-copied refresh token verified
        # perfectly and was refused "Admin access required" — it belonged to an ANONYMOUS session.
        # The command answered "tokens expire after about an hour", which is a confident lie that
        # sends someone to fetch a second token with the identical problem.
        with self._http(_FakeResponse(403, {'error': 'Admin access required'})):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        self.assertIn('Admin access required', str(e.exception))
        self.assertIn('ANONYMOUS', str(e.exception))
        self.assertNotIn('expired', str(e.exception))

    def test_no_token_and_no_login_config_is_a_clean_refusal(self):
        os.environ.pop('HALATUJU_ADMIN_TOKEN', None)
        with mock.patch.object(cmd, '_env_value', return_value=''):
            with self.assertRaises(CommandError) as e:
                call_command('record_request_analysis', file=self._payload(), api=True, apply=True)
        self.assertIn('SUPABASE_URL', str(e.exception))


class TestStoredRefreshToken(TestCase):
    """TD-206 follow-up (2026-08-01) — the owner fetches a token by hand exactly ONCE.

    An access token dies in about an hour, which made the first cut a "do this again every
    session" chore. A stored refresh token mints them instead. It IS durable, and that is the
    deliberate, smaller concession: scoped to one admin's cockpit role rather than the whole
    database, granting nothing that logging in does not, and revoked by "sign out everywhere".
    """

    def setUp(self):
        os.environ.pop('HALATUJU_ADMIN_TOKEN', None)
        self.env = {'SUPABASE_URL': 'https://x.supabase.co', 'SUPABASE_ANON_KEY': 'sb_publishable_x',
                    'HALATUJU_REFRESH_TOKEN': 'refresh-1'}
        self.written = []
        self.posts = []

    def _patched(self, post_response):
        def _post(url, **kw):
            self.posts.append((url, kw))
            return post_response
        return (
            mock.patch.object(cmd, '_env_value', side_effect=lambda k: self.env.get(k, '')),
            mock.patch.object(cmd, '_env_write', side_effect=self.written.append),
            mock.patch.dict('sys.modules', {'requests': mock.Mock(post=_post)}),
        )

    def _acquire(self, post_response):
        a, b, c = self._patched(post_response)
        with a, b, c:
            return cmd._acquire_token(mock.Mock())

    def _minting_env(self):
        return {'SUPABASE_URL': 'https://x.supabase.co', 'SUPABASE_ANON_KEY': 'sb_publishable_x',
                'SUPABASE_SERVICE_ROLE_KEY': 'service-key',
                'HALATUJU_ADMIN_EMAIL': 'tamiliam@gmail.com'}

    def test_a_session_is_MINTED_with_the_service_role_and_nothing_is_stored(self):
        """The only route that survives this project's settings (2026-08-01).

        The password grant sits behind CAPTCHA and a command line cannot answer one; the super
        account signs in with Google; and a refresh token copied from a browser dies the moment the
        browser rotates it. Minting a fresh session per run sidesteps all three, and because
        nothing is persisted there is nothing to go stale a month from now.
        """
        self.env = self._minting_env()
        a, b, c = self._patched(_FakeResponse(payload={'hashed_token': 'h'}))
        # generate_link, then verify.
        posts = [_FakeResponse(payload={'hashed_token': 'h'}),
                 _FakeResponse(payload={'access_token': 'minted-jwt', 'refresh_token': 'r'})]
        def _post(url, **kw):
            self.posts.append((url, kw))
            return posts.pop(0)
        with mock.patch.object(cmd, '_env_value', side_effect=lambda k: self.env.get(k, '')),                 mock.patch.object(cmd, '_env_write', side_effect=self.written.append),                 mock.patch.dict('sys.modules', {'requests': mock.Mock(post=_post)}):
            token = cmd._acquire_token(mock.Mock())
        self.assertEqual(token, 'minted-jwt')
        self.assertIn('/auth/v1/admin/generate_link', self.posts[0][0])
        self.assertIn('/auth/v1/verify', self.posts[1][0])
        self.assertEqual(self.written, [], 'a minted session is never persisted')

    def test_the_verify_call_does_NOT_use_the_service_role_key(self):
        # The exchange is the public half, exactly as a browser following the link would do it.
        # Sending the service key there would put an all-powerful credential on a call that does
        # not need it.
        self.env = self._minting_env()
        posts = [_FakeResponse(payload={'hashed_token': 'h'}),
                 _FakeResponse(payload={'access_token': 'minted-jwt'})]
        def _post(url, **kw):
            self.posts.append((url, kw))
            return posts.pop(0)
        with mock.patch.object(cmd, '_env_value', side_effect=lambda k: self.env.get(k, '')),                 mock.patch.object(cmd, '_env_write'),                 mock.patch.dict('sys.modules', {'requests': mock.Mock(post=_post)}):
            cmd._acquire_token(mock.Mock())
        self.assertEqual(self.posts[1][1]['headers']['apikey'], 'sb_publishable_x')
        self.assertNotIn('Authorization', self.posts[1][1]['headers'])

    def test_minting_is_SKIPPED_when_it_is_not_configured(self):
        # A machine without the service key falls through to the stored refresh token rather than
        # failing — the older path still works where it is the only one available.
        self.env = {'SUPABASE_URL': 'https://x.supabase.co', 'SUPABASE_ANON_KEY': 'sb_publishable_x',
                    'HALATUJU_REFRESH_TOKEN': 'refresh-1'}
        token = self._acquire(_FakeResponse(payload={'access_token': 'from-refresh',
                                                     'refresh_token': 'refresh-1'}))
        self.assertEqual(token, 'from-refresh')
        self.assertIn('grant_type=refresh_token', self.posts[0][0])

    def test_a_stored_refresh_token_mints_an_access_token(self):
        token = self._acquire(_FakeResponse(payload={'access_token': 'fresh-jwt',
                                                     'refresh_token': 'refresh-1'}))
        self.assertEqual(token, 'fresh-jwt')
        self.assertIn('grant_type=refresh_token', self.posts[0][0])

    def test_the_ROTATED_refresh_token_is_persisted(self):
        # Supabase rotates on every use: the reply carries a new token and the old one stops
        # working. Not storing it turns a set-up-once credential into a single-use one that breaks
        # on the SECOND run, when nobody is watching. This is the test that catches that.
        self._acquire(_FakeResponse(payload={'access_token': 'fresh-jwt',
                                             'refresh_token': 'refresh-2'}))
        self.assertEqual(self.written, [{'HALATUJU_REFRESH_TOKEN': 'refresh-2'}])

    def test_an_unchanged_refresh_token_is_not_rewritten(self):
        self._acquire(_FakeResponse(payload={'access_token': 'fresh-jwt',
                                             'refresh_token': 'refresh-1'}))
        self.assertEqual(self.written, [])

    def test_an_explicit_env_token_still_wins_and_touches_nothing(self):
        os.environ['HALATUJU_ADMIN_TOKEN'] = 'override'
        self.addCleanup(os.environ.pop, 'HALATUJU_ADMIN_TOKEN', None)
        self.assertEqual(self._acquire(_FakeResponse()), 'override')
        self.assertEqual(self.posts, [], 'no exchange when a token was handed in')

    def test_a_spent_refresh_token_says_what_to_do(self):
        with self.assertRaises(CommandError) as e:
            self._acquire(_FakeResponse(400, {}))
        self.assertIn('re-bootstrap', str(e.exception))

    def test_supabases_OWN_reason_survives_the_trip(self):
        # Learned the hard way, 2026-08-01. The first cut reported "(400). Check the email and
        # password" and sent the owner looking for a typo in a password that does not exist — the
        # super account is Google-only, so the password grant could never have worked. A guessed
        # cause attached to a status code is worse than the bare code: it is confidently wrong.
        self.env.pop('HALATUJU_REFRESH_TOKEN')
        a, b, c = self._patched(_FakeResponse(400, {'error_description': 'Invalid login credentials'}))
        with a, b, c, mock.patch('builtins.input', return_value='x@y.z'), \
                mock.patch.object(cmd.getpass, 'getpass', return_value='pw'):
            with self.assertRaises(CommandError) as e:
                cmd._acquire_token(mock.Mock())
        self.assertIn('Invalid login credentials', str(e.exception))
        self.assertIn('GOOGLE', str(e.exception))

    def test_bootstrap_stores_the_token_and_DELETES_the_source(self):
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump({'refresh_token': 'r-boot', 'supabase_url': 'https://x.supabase.co',
                   'supabase_anon_key': 'sb_publishable_x'}, fh)
        fh.close()
        with mock.patch.object(cmd, '_env_write', side_effect=self.written.append):
            call_command('record_request_analysis', bootstrap_file=fh.name)
        self.assertEqual(self.written[0]['HALATUJU_REFRESH_TOKEN'], 'r-boot')
        self.assertFalse(os.path.exists(fh.name), 'the copy must not outlive the move')

    def test_bootstrap_can_carry_the_config_alone(self):
        # The two-step setup: the config goes in first (neither value is a real secret), then the
        # owner logs in ONCE to mint a refresh token of the command's own.
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump({'supabase_url': 'https://x.supabase.co',
                   'supabase_anon_key': 'sb_publishable_x'}, fh)
        fh.close()
        with mock.patch.object(cmd, '_env_write', side_effect=self.written.append):
            call_command('record_request_analysis', bootstrap_file=fh.name)
        self.assertEqual(sorted(self.written[0]), ['SUPABASE_ANON_KEY', 'SUPABASE_URL'])

    def test_a_RAW_token_file_is_accepted_so_it_need_never_be_read_aloud(self):
        # The credential goes browser -> text file -> .env without passing through a chat, a
        # command line or anyone's eyes. Every one of those leaves a copy that outlives the move.
        fh = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
        fh.write('  a-raw-refresh-token\n')
        fh.close()
        with mock.patch.object(cmd, '_env_write', side_effect=self.written.append):
            call_command('record_request_analysis', bootstrap_file=fh.name)
        self.assertEqual(self.written[0], {'HALATUJU_REFRESH_TOKEN': 'a-raw-refresh-token'})
        self.assertFalse(os.path.exists(fh.name))

    def test_an_empty_bootstrap_file_is_refused(self):
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump({}, fh)
        fh.close()
        self.addCleanup(lambda: os.path.exists(fh.name) and os.unlink(fh.name))
        with self.assertRaises(CommandError):
            call_command('record_request_analysis', bootstrap_file=fh.name)

    def test_bootstrap_login_IGNORES_a_spent_refresh_token(self):
        # The trap this exists to avoid: the ordinary order tries the stored refresh token first,
        # so a SPENT one fails with "Already Used" and the bootstrap meant to REPLACE it never
        # reaches the prompt. A recovery path must not depend on the thing it recovers from.
        a, b, c = self._patched(_FakeResponse(payload={'access_token': 'a', 'refresh_token': 'r'}))
        self.env['HALATUJU_REFRESH_TOKEN'] = 'spent-token'
        with a, b, c, mock.patch('builtins.input', return_value='x@y.z'),                 mock.patch.object(cmd.getpass, 'getpass', return_value='pw'):
            call_command('record_request_analysis', bootstrap_login=True)
        self.assertIn('grant_type=password', self.posts[0][0])
        self.assertEqual(len(self.posts), 1, 'it must not have tried the spent token at all')

    def test_bootstrap_login_creates_its_OWN_session_not_the_browsers(self):
        # The reason this exists rather than "paste your browser's refresh token": Supabase rotates
        # within a session family, so a shared token means the first client to refresh signs the
        # other one out. The owner would be logged out of the cockpit by their own tooling.
        a, b, c = self._patched(_FakeResponse(payload={'access_token': 'a', 'refresh_token': 'r-new'}))
        self.env.pop('HALATUJU_REFRESH_TOKEN')
        with a, b, c, mock.patch('builtins.input', return_value='tamiliam@gmail.com'), \
                mock.patch.object(cmd.getpass, 'getpass', return_value='pw'):
            call_command('record_request_analysis', bootstrap_login=True)
        self.assertIn('grant_type=password', self.posts[0][0])
        self.assertEqual(self.written, [{'HALATUJU_REFRESH_TOKEN': 'r-new'}])
