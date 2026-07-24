"""Requests space — screenshot attachment tests (Sprint 15.1, TD-172).

Every attachment security invariant proven by a test: foreign-path rejection, the ≤5 count cap at
BOTH sign and record, the images-only allowlist (no pdf), the signed-download-URL org assertion
(None on a cross-org key), org_admin can't touch another org's attachments (404), and the flag-off
404 on every new route. The Supabase storage seams are mocked — never a live call.
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import OrgRequest, OrgRequestAttachment

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='att-a', name='Org A')
        cls.org_b = PartnerOrganisation.objects.create(code='att-b', name='Org B')
        cls.oa_a = PartnerAdmin.objects.create(
            supabase_user_id='att-oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OrgAdmin A', email='aoaa@x.com')
        cls.oa_b = PartnerAdmin.objects.create(
            supabase_user_id='att-oa-b', role='org_admin', is_active=True,
            owning_organisation=cls.org_b, name='OrgAdmin B', email='aoab@x.com')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='att-sup', is_super_admin=True, is_active=True,
            name='Super', email='asup@x.com')
        cls.req_a = OrgRequest.objects.create(
            organisation=cls.org_a, submitted_by=cls.oa_a, kind='feature',
            title='A feature', description='org A wants a page')
        cls.req_b = OrgRequest.objects.create(
            organisation=cls.org_b, submitted_by=cls.oa_b, kind='bug',
            title='B bug', description='org B hit a crash')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _attach(self, req, uploaded_by, name='shot.png', ct='image/png'):
        from apps.scholarship.storage import build_request_attachment_key
        import uuid
        path = build_request_attachment_key(req.organisation_id, req.id, uuid.uuid4().hex)
        return OrgRequestAttachment.objects.create(
            org_request=req, storage_path=path, original_filename=name,
            content_type=ct, size=1000, uploaded_by=uploaded_by)


class TestSignUpload(_Base):
    @mock.patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://x/put')
    def test_sign_returns_url_and_prefixed_path(self, _m):
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['upload_url'], 'https://x/put')
        self.assertTrue(body['storage_path'].startswith(f'requests/{self.org_a.id}/{self.req_a.id}/'))

    @mock.patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://x/put')
    def test_count_cap_enforced_at_sign(self, _m):
        for _ in range(5):
            self._attach(self.req_a, self.oa_a)
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'attachment_limit')

    @mock.patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://x/put')
    def test_terminal_request_refuses_sign(self, _m):
        self.req_a.status = 'done'
        self.req_a.save(update_fields=['status'])
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'request_terminal')

    @mock.patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://x/put')
    def test_cross_org_sign_404(self, _m):
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_b.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 404)


def _good_payload(org_id, req_id, name='shot.png', ct='image/png', size=1000):
    return {'storage_path': f'requests/{org_id}/{req_id}/abc123',
            'original_filename': name, 'content_type': ct, 'size': size}


class TestRecord(_Base):
    @mock.patch('apps.scholarship.storage.create_signed_download_url',
                return_value='https://x/dl')
    def test_record_creates_row_and_returns_attachments(self, _m):
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/',
                             _good_payload(self.org_a.id, self.req_a.id), format='json')
        self.assertEqual(r.status_code, 201)
        atts = r.json()['attachments']
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]['download_url'], 'https://x/dl')
        self.assertEqual(atts[0]['content_type'], 'image/png')

    def test_foreign_path_rejected(self):
        # A path that belongs to org B's namespace must not record on org A's request.
        self._auth('att-oa-a')
        payload = _good_payload(self.org_a.id, self.req_a.id)
        payload['storage_path'] = f'requests/{self.org_b.id}/{self.req_b.id}/abc123'
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/', payload, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_path')
        self.assertEqual(self.req_a.attachments.count(), 0)

    def test_pdf_rejected(self):
        self._auth('att-oa-a')
        payload = _good_payload(self.org_a.id, self.req_a.id, name='doc.pdf', ct='application/pdf')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/', payload, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unsupported_format')

    def test_oversize_rejected(self):
        from django.conf import settings
        self._auth('att-oa-a')
        payload = _good_payload(self.org_a.id, self.req_a.id, size=settings.MAX_DOC_SIZE_BYTES + 1)
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/', payload, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'file_too_large')

    def test_count_cap_enforced_at_record(self):
        for _ in range(5):
            self._attach(self.req_a, self.oa_a)
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/',
                             _good_payload(self.org_a.id, self.req_a.id), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'attachment_limit')

    def test_terminal_request_refuses_record(self):
        self.req_a.status = 'declined'
        self.req_a.save(update_fields=['status'])
        self._auth('att-oa-a')
        r = self.client.post(f'{BASE}{self.req_a.id}/attachments/',
                             _good_payload(self.org_a.id, self.req_a.id), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'request_terminal')


class TestDownloadUrlOrgAssertion(_Base):
    def test_download_denied_when_key_org_mismatches(self):
        # A row whose stored key names org B but hangs off org A's request → download_url None.
        att = self.req_a.attachments.create(
            storage_path=f'requests/{self.org_b.id}/{self.req_a.id}/xyz',
            original_filename='x.png', content_type='image/png', size=10, uploaded_by=self.oa_a)
        from apps.scholarship.serializers_admin import _serialize_org_request_attachments
        with mock.patch('apps.scholarship.storage.create_signed_download_url',
                        return_value='https://x/dl') as m:
            out = _serialize_org_request_attachments(self.req_a)
        self.assertIsNone(out[0]['download_url'])
        m.assert_not_called()
        att.delete()

    def test_download_signed_when_key_org_matches(self):
        self._attach(self.req_a, self.oa_a)
        from apps.scholarship.serializers_admin import _serialize_org_request_attachments
        with mock.patch('apps.scholarship.storage.create_signed_download_url',
                        return_value='https://x/dl'):
            out = _serialize_org_request_attachments(self.req_a)
        self.assertEqual(out[0]['download_url'], 'https://x/dl')


class TestDelete(_Base):
    @mock.patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_own_org_delete(self, m):
        att = self._attach(self.req_a, self.oa_a)
        self._auth('att-oa-a')
        r = self.client.delete(f'{BASE}{self.req_a.id}/attachments/{att.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.req_a.attachments.count(), 0)
        m.assert_called_once()

    @mock.patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_cross_org_attachment_delete_404(self, _m):
        att_b = self._attach(self.req_b, self.oa_b)
        # org A admin cannot touch org B's attachment — the request id is org B's → 404.
        self._auth('att-oa-a')
        r = self.client.delete(f'{BASE}{self.req_b.id}/attachments/{att_b.id}/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.req_b.attachments.count(), 1)

    @mock.patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_delete_foreign_att_id_on_own_request_404(self, _m):
        # An attachment id that isn't on THIS request (it's org B's) → 404, even via own request pk.
        att_b = self._attach(self.req_b, self.oa_b)
        self._auth('att-oa-a')
        r = self.client.delete(f'{BASE}{self.req_a.id}/attachments/{att_b.id}/')
        self.assertEqual(r.status_code, 404)

    @mock.patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_delete_refused_when_terminal(self, _m):
        att = self._attach(self.req_a, self.oa_a)
        self.req_a.status = 'done'
        self.req_a.save(update_fields=['status'])
        self._auth('att-oa-a')
        r = self.client.delete(f'{BASE}{self.req_a.id}/attachments/{att.id}/')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'request_terminal')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=False)
class TestFlagOffDark(TestCase):
    """With the flag dark, EVERY attachment route 404s before any auth/role work."""
    def setUp(self):
        self.client = APIClient()
        self.org = PartnerOrganisation.objects.create(code='dk', name='D')
        self.oa = PartnerAdmin.objects.create(
            supabase_user_id='dk-oa', role='org_admin', is_active=True,
            owning_organisation=self.org, name='oa', email='dkoa@x.com')
        self.req = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='bug', title='t', description='d')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("dk-oa")}')

    def test_sign_dark(self):
        r = self.client.post(f'{BASE}{self.req.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_record_dark(self):
        r = self.client.post(f'{BASE}{self.req.id}/attachments/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_delete_dark(self):
        r = self.client.delete(f'{BASE}{self.req.id}/attachments/1/')
        self.assertEqual(r.status_code, 404)


class TestAiPromptNotesAttachments(_Base):
    def test_prompt_notes_attachment_count(self):
        from apps.scholarship import org_requests
        self._attach(self.req_a, self.oa_a)
        self._attach(self.req_a, self.oa_a)
        prompt = org_requests._build_review_prompt(self.req_a)
        self.assertIn('ATTACHMENTS: 2 image(s)', prompt)

    def test_prompt_silent_when_no_attachments(self):
        from apps.scholarship import org_requests
        prompt = org_requests._build_review_prompt(self.req_b)
        self.assertNotIn('ATTACHMENTS:', prompt)
