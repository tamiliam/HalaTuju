"""TD-204 — the command that stages an analysis, and the guard that justifies its existence.

The command's reason to exist is NOT transport. A cockpit form would carry the prose just as well.
It exists because it runs INSIDE the repo, so it can check that every cited path actually resolves
— and an unchecked citation is decoration, not evidence. That check is what these tests protect.
"""
import json
import os
import tempfile

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
