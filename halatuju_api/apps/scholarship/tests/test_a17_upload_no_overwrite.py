"""Audit fix A1.7 (TD-467 / SEC-18, SEC-07 folded in; TD-173): uploads cannot overwrite or smuggle files.

1. The student document door and the request-attachment door sign their upload URLs with
   ``x-upsert: false`` (``create_signed_upload_url(path, upsert=False)``), as the development-module
   uploads already do. A signed URL can then never write over an object already at its key.
2. A wrong-type or oversize file is refused at the record step, where the server checks it (the
   bucket's own type / size limit is the live step in ``docs/security/b40-documents-bucket-limits.sql``).
3. TD-173: a HEIC / HEIF request attachment is converted to JPEG on record, by the same
   ``imaging.convert_heic_to_jpeg`` the document door uses.

The Supabase storage seams are mocked: ``storage._post`` is replaced by a small fake bucket, never a
live call.
"""
import sys
from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import ApplicantDocument, OrgRequest
from apps.scholarship.tests.doc_keys import issued_key
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.doc_upload import post_doc   # A2.3: upload, then the read

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
STUDENT = 'a17-student'
SIGN_PREFIX = '/object/upload/sign/b40-documents/'
REQUESTS = '/api/v1/admin/scholarship/requests/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class FakeBucket:
    """Just enough of Supabase Storage to show the overwrite rule. ``sign`` stands in for
    ``storage._post`` on the upload-sign route and remembers the ``x-upsert`` the URL was signed
    with; ``put`` is the browser's PUT. Only a URL signed with an explicit ``x-upsert: false`` is
    treated as no-overwrite: without it the behaviour is left to the storage version and the
    browser's own header (the audit's SEC-18 finding), so the fake lets it through."""

    def __init__(self):
        self.objects = {}
        self.tokens = {}

    def sign(self, path, payload=None, headers=None):
        assert path.startswith(SIGN_PREFIX), path
        key = path[len(SIGN_PREFIX):]
        token = f't{len(self.tokens)}'
        self.tokens[token] = (key, (headers or {}).get('x-upsert'))
        return {'url': f'{SIGN_PREFIX}{key}?token={token}'}

    def put(self, url, data):
        token = url.rsplit('token=', 1)[1]
        key, upsert = self.tokens[token]
        if key in self.objects and upsert == 'false':
            return 400   # Supabase: "The resource already exists"
        self.objects[key] = data
        return 200


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='a17', name='B40', year=2026)
        cls.student = make_student(supabase_user_id=STUDENT, nric='030101-14-1717')
        cls.app = make_application('shortlisted', cohort=cls.cohort, student=cls.student)
        cls.org = PartnerOrganisation.objects.create(code='a17-org', name='Org A17')
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='a17-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin', email='a17oa@x.com')
        cls.req = OrgRequest.objects.create(
            organisation=cls.org, submitted_by=cls.org_admin, kind='bug',
            title='A bug', description='a screen crashed')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _sign_document(self):
        self._auth(STUDENT)
        r = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _sign_attachment(self):
        self._auth('a17-oa')
        r = self.client.post(f'{REQUESTS}{self.req.id}/attachments/sign-upload/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        return r.json()


@override_settings(SUPABASE_URL='https://storage.test')
class TestSignedUploadsNeverOverwrite(_Base):
    def test_both_doors_sign_with_x_upsert_false(self):
        with patch('apps.scholarship.storage._post', return_value={'url': '/x'}) as post:
            self._sign_document()
            self._sign_attachment()
        self.assertEqual([c.kwargs['headers'] for c in post.call_args_list],
                         [{'x-upsert': 'false'}, {'x-upsert': 'false'}])

    def test_both_doors_call_the_signer_with_upsert_false(self):
        with patch('apps.scholarship.storage.create_signed_upload_url',
                   return_value='https://storage.test/up') as sign:
            self._sign_document()
            self._sign_attachment()
        self.assertEqual([c.kwargs for c in sign.call_args_list], [{'upsert': False}, {'upsert': False}])

    def test_a_second_put_to_the_same_signed_path_is_refused(self):
        bucket = FakeBucket()
        with patch('apps.scholarship.storage._post', side_effect=bucket.sign):
            for door in (self._sign_document, self._sign_attachment):
                with self.subTest(door=door.__name__):
                    signed = door()
                    url = signed['upload_url']
                    self.assertEqual(bucket.put(url, b'the checked file'), 200)
                    self.assertEqual(bucket.put(url, b'a swapped file'), 400)
                    self.assertEqual(bucket.objects[signed['storage_path']], b'the checked file')

    def test_each_upload_gets_a_fresh_key(self):
        """Why no flow breaks: a re-upload or a replaced document always signs a NEW key, so
        nothing relies on writing over the same path."""
        with patch('apps.scholarship.storage.create_signed_upload_url',
                   return_value='https://storage.test/up'):
            docs = {self._sign_document()['storage_path'] for _ in range(2)}
            atts = {self._sign_attachment()['storage_path'] for _ in range(2)}
        self.assertEqual((len(docs), len(atts)), (2, 2))


class TestWrongTypeOrOversizeRefusedAtRecord(_Base):
    def test_document_record_refuses_a_video_and_an_oversize_file(self):
        from django.conf import settings
        self._auth(STUDENT)
        cases = (({'original_filename': 'ic.mp4', 'content_type': 'video/mp4', 'size': 1000},
                  'unsupported_format'),
                 ({'original_filename': 'ic.html', 'content_type': 'text/html', 'size': 1000},
                  'unsupported_format'),
                 ({'original_filename': 'ic.pdf', 'content_type': 'application/pdf',
                   'size': settings.MAX_DOC_SIZE_BYTES + 1}, 'file_too_large'))
        for extra, code in cases:
            with self.subTest(code=code, ct=extra['content_type']):
                r = post_doc(self.client, {
                    'doc_type': 'ic', 'storage_path': issued_key(self.app, 'ic', code), **extra,
                }, format='json')
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.json().get('code', r.json().get('error')), code)
        self.assertFalse(ApplicantDocument.objects.filter(application=self.app).exists())

    def test_attachment_record_refuses_a_non_image_and_an_oversize_file(self):
        from django.conf import settings
        from apps.scholarship.storage import build_request_attachment_key
        self._auth('a17-oa')
        path = build_request_attachment_key(self.org.id, self.req.id, 'a' * 32)
        cases = (({'original_filename': 'x.html', 'content_type': 'text/html', 'size': 10},
                  'unsupported_format'),
                 ({'original_filename': 'x.pdf', 'content_type': 'application/pdf', 'size': 10},
                  'unsupported_format'),
                 ({'original_filename': 'x.png', 'content_type': 'image/png',
                   'size': settings.MAX_DOC_SIZE_BYTES + 1}, 'file_too_large'))
        for extra, code in cases:
            with self.subTest(code=code, ct=extra['content_type']):
                r = self.client.post(f'{REQUESTS}{self.req.id}/attachments/',
                                     {'storage_path': path, **extra}, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(self.req.attachments.count(), 0)


class TestHeicRequestAttachmentIsConverted(_Base):
    """TD-173: the same conversion the document door runs (imaging.convert_heic_to_jpeg)."""

    def _record(self, name, ct):
        from apps.scholarship.storage import build_request_attachment_key
        self._auth('a17-oa')
        path = build_request_attachment_key(self.org.id, self.req.id, 'b' * 32)
        r = self.client.post(f'{REQUESTS}{self.req.id}/attachments/',
                             {'storage_path': path, 'original_filename': name,
                              'content_type': ct, 'size': 2000}, format='json')
        self.assertEqual(r.status_code, 201)
        return path

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://x/dl')
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'fake-heic-bytes')
    @patch('PIL.Image.open')
    def test_a_heic_attachment_is_stored_and_recorded_as_jpeg(self, mock_open, _fetch, upload, _dl):
        img = MagicMock()
        img.convert.return_value = img
        img.save.side_effect = lambda buf, *a, **k: buf.write(b'jpeg-bytes')
        mock_open.return_value = img
        path = self._record('IMG_0001.HEIC', 'image/heic')
        upload.assert_called_once()
        self.assertEqual((upload.call_args[0][0], upload.call_args[0][2]), (path, 'image/jpeg'))
        att = self.req.attachments.get()
        self.assertEqual((att.content_type, att.original_filename), ('image/jpeg', 'IMG_0001.jpg'))

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://x/dl')
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'fake-heic-bytes')
    @patch('PIL.Image.open')
    def test_a_typeless_heic_is_known_by_its_name(self, mock_open, _fetch, upload, _dl):
        img = MagicMock()
        img.convert.return_value = img
        img.save.side_effect = lambda buf, *a, **k: buf.write(b'jpeg-bytes')
        mock_open.return_value = img
        self._record('photo.heif', 'application/octet-stream')
        upload.assert_called_once()
        self.assertEqual(self.req.attachments.get().content_type, 'image/jpeg')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://x/dl')
    @patch('apps.scholarship.storage.upload_object', return_value=True)
    def test_a_png_is_left_alone(self, upload, _dl):
        self._record('shot.png', 'image/png')
        upload.assert_not_called()
        self.assertEqual(self.req.attachments.get().content_type, 'image/png')

    @patch.dict(sys.modules, {'pillow_heif': MagicMock()})
    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://x/dl')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=None)
    def test_a_failed_conversion_still_records_the_original(self, _fetch, _dl):
        self._record('IMG_0002.HEIC', 'image/heic')
        self.assertEqual(self.req.attachments.get().content_type, 'image/heic')
