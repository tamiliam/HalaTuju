"""Contract module Sprint 3 — admin API (author → generate-quiz → vet → submit →
deploy) + the org fence.

Access: super / org_admin only (reviewer/qc/admin/partner → 403); org-fenced
(cross-org read/write → 404, never 403); deploy is super-only (org_admin → 403).
The full lifecycle is drivable over the API; generate-quiz is draft-only and the
Gemini seam is mocked (never a live call).
"""
import datetime
import json
from unittest.mock import patch

import jwt
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import contracts
from apps.scholarship.models import ContractTemplate

from apps.scholarship.tests.contract_helpers import brightpath_org, make_deployable, seed_draft

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/contract-templates/'
VALID_QUIZ = {'tag': 't', 'plain': 'p', 'question': 'q',
              'options': ['a', 'b', 'c'], 'correct': 1, 'why': 'w'}


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = brightpath_org()   # migration 0098 seeds 'brightpath'
        cls.org_b = PartnerOrganisation.objects.create(code='ct-b', name='Org B')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='ct-super', is_super_admin=True, is_active=True,
            name='Super', email='ctsuper@x.com')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='ct-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OA', email='ctoa@x.com')
        cls.oa_b = PartnerAdmin.objects.create(
            supabase_user_id='ct-oa-b', role='org_admin', is_active=True,
            owning_organisation=cls.org_b, name='OAB', email='ctoab@x.com')
        for role in ('reviewer', 'qc', 'admin', 'partner'):
            PartnerAdmin.objects.create(
                supabase_user_id=f'ct-{role}', role=role, is_active=True,
                owning_organisation=cls.org_a, name=role, email=f'ct{role}@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


class TestAccessGate(_Base):
    def test_super_and_org_admin_may_list(self):
        for uid in ('ct-super', 'ct-oa'):
            self._auth(uid)
            self.assertEqual(self.client.get(BASE).status_code, 200, uid)

    def test_other_roles_forbidden(self):
        for role in ('reviewer', 'qc', 'admin', 'partner'):
            self._auth(f'ct-{role}')
            self.assertEqual(self.client.get(BASE).status_code, 403, role)

    def test_unauthenticated_denied(self):
        self.assertIn(self.client.get(BASE).status_code, (401, 403))


class TestCreateAndAuthor(_Base):
    def test_org_admin_creates_own_org_draft(self):
        self._auth('ct-oa')
        r = self.client.post(BASE, {'version': '2026-a'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'draft')
        self.assertEqual(r.data['organisation'], 'brightpath')

    def test_super_needs_organisation(self):
        self._auth('ct-super')
        self.assertEqual(self.client.post(BASE, {'version': 'x'}, format='json').status_code, 400)
        r = self.client.post(BASE, {'version': 'x', 'organisation': 'brightpath'}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_duplicate_version_400(self):
        self._auth('ct-oa')
        self.client.post(BASE, {'version': 'dup'}, format='json')
        r = self.client.post(BASE, {'version': 'dup'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'version_exists')

    def test_patch_config_and_put_clauses_and_schedule(self):
        self._auth('ct-oa')
        pk = self.client.post(BASE, {'version': 'build'}, format='json').data['id']
        # config
        r = self.client.patch(f'{BASE}{pk}/', {'counterparty_name': 'Suresh',
                              'parent_role': 'co_signer_all'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['counterparty_name'], 'Suresh')
        # clauses
        r = self.client.put(f'{BASE}{pk}/clauses/', {'clauses': [
            {'heading_en': 'One', 'body_en': 'Body one', 'is_quiz_candidate': True,
             'quiz_en': VALID_QUIZ, 'quiz_ms': VALID_QUIZ, 'quiz_ta': VALID_QUIZ},
            {'heading_en': 'Two', 'body_en': 'Body two'},
        ]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['clauses']), 2)
        self.assertEqual(r.data['clauses'][0]['order'], 1)
        # schedule
        r = self.client.put(f'{BASE}{pk}/schedule/', {'rows': [
            {'pathway': 'default', 'variant': '', 'monthly_amount': '200',
             'start_month': 7, 'paid_offsets': list(range(10))},
        ]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['schedule'][0]['total'], '2000.00')


class TestOrgFence(_Base):
    def setUp(self):
        super().setUp()
        self.t_b = ContractTemplate.objects.create(organisation=self.org_b, version='b1')

    def test_cross_org_read_404(self):
        self._auth('ct-oa')   # org A admin
        self.assertEqual(self.client.get(f'{BASE}{self.t_b.id}/').status_code, 404)

    def test_cross_org_write_404(self):
        self._auth('ct-oa')
        r = self.client.patch(f'{BASE}{self.t_b.id}/', {'counterparty_name': 'x'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_own_org_admin_reads_own(self):
        self._auth('ct-oa-b')
        self.assertEqual(self.client.get(f'{BASE}{self.t_b.id}/').status_code, 200)

    def test_super_reads_any(self):
        self._auth('ct-super')
        self.assertEqual(self.client.get(f'{BASE}{self.t_b.id}/').status_code, 200)

    def test_list_is_org_scoped(self):
        # org A admin never sees org B's template in the list.
        self._auth('ct-oa')
        ids = [t['id'] for t in self.client.get(BASE).data['templates']]
        self.assertNotIn(self.t_b.id, ids)


class TestGenerateQuiz(_Base):
    def setUp(self):
        super().setUp()
        self.t = seed_draft('2026-q')
        # a non-candidate clause to (re)generate on
        self.order = self.t.clauses.filter(is_quiz_candidate=False).first().order

    @patch('apps.scholarship.contracts._gemini_generate')
    def test_generate_quiz_mocked(self, mock_gemini):
        mock_gemini.return_value = json.dumps({'en': VALID_QUIZ, 'ms': VALID_QUIZ, 'ta': VALID_QUIZ})
        self._auth('ct-oa')
        r = self.client.post(f'{BASE}{self.t.id}/clauses/{self.order}/generate-quiz/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['quiz_en']['question'], 'q')
        self.assertEqual(r.data['quiz_generated_model'], 'gemini-2.5-pro')
        self.assertEqual(mock_gemini.call_count, 1)

    @patch('apps.scholarship.contracts._gemini_generate')
    def test_generate_quiz_draft_only(self, mock_gemini):
        mock_gemini.return_value = json.dumps({'en': VALID_QUIZ, 'ms': VALID_QUIZ, 'ta': VALID_QUIZ})
        # push the template out of draft → generate-quiz must refuse
        t = make_deployable('2026-q2')
        contracts.submit_for_deployment(t)
        self._auth('ct-oa')
        order = t.clauses.filter(is_quiz_candidate=False).first().order
        r = self.client.post(f'{BASE}{t.id}/clauses/{order}/generate-quiz/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'not_draft')
        mock_gemini.assert_not_called()


class TestValidateMirrorsService(_Base):
    def test_validate_endpoint_matches_service(self):
        t = seed_draft('2026-v')   # bare draft: missing counterparty + vetting
        self._auth('ct-oa')
        r = self.client.get(f'{BASE}{t.id}/validate/')
        self.assertEqual(r.status_code, 200)
        api_codes = sorted(e['code'] for e in r.data['errors'])
        service_codes = sorted(contracts.validate_for_deployment(t).errors)
        self.assertEqual(api_codes, service_codes)
        self.assertIn('T1', api_codes)   # no counterparty
        self.assertIn('T2', api_codes)   # no attestation
        self.assertFalse(r.data['ok'])


class TestLifecycleOverApi(_Base):
    def _drive_to_pending(self, version):
        """Seed a fixture draft, then vet + submit it entirely over the API."""
        t = seed_draft(version)
        self._auth('ct-oa')
        self.client.patch(f'{BASE}{t.id}/',
                          {'counterparty_name': 'Suresh', 'counterparty_nric': '000000-00-0000'},
                          format='json')
        r = self.client.post(f'{BASE}{t.id}/vetting/',
                             {'vetted_by_name': 'Lawyer', 'vetted_on': '2026-07-01'}, format='json')
        self.assertEqual(r.status_code, 200)
        r = self.client.get(f'{BASE}{t.id}/validate/')
        self.assertTrue(r.data['ok'], r.data['errors'])
        r = self.client.post(f'{BASE}{t.id}/submit/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'pending_deployment')
        return t

    def test_full_author_vet_submit_deploy(self):
        t = self._drive_to_pending('2026-live')
        # org_admin CANNOT deploy → 403
        self._auth('ct-oa')
        self.assertEqual(self.client.post(f'{BASE}{t.id}/deploy/', {}, format='json').status_code, 403)
        t.refresh_from_db()
        self.assertEqual(t.status, 'pending_deployment')
        # super deploys → active
        self._auth('ct-super')
        r = self.client.post(f'{BASE}{t.id}/deploy/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'active')

    def test_deploy_archives_previous_active(self):
        t1 = self._drive_to_pending('2026-one')
        self._auth('ct-super')
        self.client.post(f'{BASE}{t1.id}/deploy/', {}, format='json')
        t2 = self._drive_to_pending('2026-two')
        self._auth('ct-super')
        self.client.post(f'{BASE}{t2.id}/deploy/', {}, format='json')
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t1.status, 'archived')
        self.assertEqual(t2.status, 'active')

    def test_revert_returns_pending_to_draft(self):
        t = self._drive_to_pending('2026-rev')
        self._auth('ct-oa')
        r = self.client.post(f'{BASE}{t.id}/revert/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'draft')

    def test_submit_refuses_invalid(self):
        t = seed_draft('2026-bad')   # no counterparty / vetting
        self._auth('ct-oa')
        r = self.client.post(f'{BASE}{t.id}/submit/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'not_deployable')
        self.assertIn('T1', r.data['errors'])


def _docx_bytes(paragraphs):
    """A minimal in-memory .docx with the given paragraphs."""
    import io
    import docx
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class TestImportDocx(_Base):
    def setUp(self):
        super().setUp()
        self.t = seed_draft('2026-imp')
        self._auth('ct-oa')

    @patch('apps.scholarship.contracts._gemini_generate')
    def test_import_returns_proposed_clauses(self, mock_gemini):
        mock_gemini.return_value = json.dumps([
            {'heading': 'The Bursary Award', 'body': 'The Foundation agrees to award...'},
            {'heading': 'Payment Schedule', 'body': 'Paid monthly...'},
        ])
        docx_file = SimpleUploadedFile(
            'contract.docx', _docx_bytes(['1. The Bursary Award', 'Body text here.']),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        r = self.client.post(f'{BASE}{self.t.id}/import-docx/', {'file': docx_file}, format='multipart')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['clauses']), 2)
        self.assertEqual(r.data['clauses'][0]['heading'], 'The Bursary Award')
        self.assertEqual(mock_gemini.call_count, 1)
        # It only PROPOSES — the draft's own clauses are untouched until a clauses PUT.
        self.assertEqual(self.t.clauses.count(), 16)

    def test_import_requires_a_file(self):
        r = self.client.post(f'{BASE}{self.t.id}/import-docx/', {}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'no_file')

    @patch('apps.scholarship.contracts._gemini_generate')
    def test_import_segmentation_failure_degrades(self, mock_gemini):
        mock_gemini.return_value = 'not json'
        docx_file = SimpleUploadedFile(
            'contract.docx', _docx_bytes(['Some text']),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        r = self.client.post(f'{BASE}{self.t.id}/import-docx/', {'file': docx_file}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'segmentation_failed')

    @patch('apps.scholarship.contracts._gemini_generate')
    def test_import_draft_only(self, mock_gemini):
        mock_gemini.return_value = json.dumps([{'heading': 'H', 'body': 'B'}])
        t = make_deployable('2026-imp2')
        contracts.submit_for_deployment(t)
        docx_file = SimpleUploadedFile(
            'c.docx', _docx_bytes(['x']),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        r = self.client.post(f'{BASE}{t.id}/import-docx/', {'file': docx_file}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'not_draft')
        mock_gemini.assert_not_called()

    def test_import_cross_org_404(self):
        other = ContractTemplate.objects.create(organisation=self.org_b, version='imp-b')
        docx_file = SimpleUploadedFile(
            'c.docx', _docx_bytes(['x']),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        r = self.client.post(f'{BASE}{other.id}/import-docx/', {'file': docx_file}, format='multipart')
        self.assertEqual(r.status_code, 404)


class TestPreviewEndpoints(_Base):
    def setUp(self):
        super().setUp()
        self.t = seed_draft('2026-prev')

    def test_preview_html(self):
        self._auth('ct-oa')
        r = self.client.get(f'{BASE}{self.t.id}/preview/?locale=en')
        self.assertEqual(r.status_code, 200)
        self.assertIn('PREVIEW', r.content.decode())

    def test_quiz_preview(self):
        self._auth('ct-oa')
        r = self.client.get(f'{BASE}{self.t.id}/quiz-preview/?locale=en')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['checkpoints']), 8)
        self.assertEqual(r.data['template_version'], '2026-prev')
