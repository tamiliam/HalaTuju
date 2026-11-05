"""Audit SEC-01 — a document records only the storage key its own upload step issued.

The document POST used to accept any ``storage_path`` the browser sent, so a student could record a
row pointing at ANOTHER applicant's blob (same organisation or another one), at an offer letter or a
bursary agreement, and then read it back through the signed download link — or delete it.

Rule (``storage.is_issued_doc_key``): the path must be exactly
``build_doc_key(app, app.id, doc_type)`` + ``/`` + 32 lowercase hex — the shape
``DocumentSignUploadView`` issues — for THIS application and THIS doc type. Anything else is a 400
``bad_storage_path`` and saves nothing. ``DocumentDetailView.delete`` deletes a blob only inside the
application's own prefix; a foreign stored path keeps its blob (row deleted, warning logged).

Personal data is obviously fake.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import storage
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.doc_keys import issued_key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'
SIGN = '/api/v1/scholarship/documents/sign-upload/'
HEX = 'a' * 32
ALL_DOC_TYPES = [c[0] for c in ApplicantDocument.DOC_TYPES]


class IssuedKeyUnit(SimpleTestCase):
    """The helper on its own: the exact shape, nothing near it."""
    org_app = SimpleNamespace(owning_organisation_id=7, id=42)
    bare_app = SimpleNamespace(owning_organisation_id=None, id=42)

    def test_the_issued_shape_passes_for_both_key_layouts(self):
        self.assertTrue(storage.is_issued_doc_key(self.org_app, 'ic', f'7/42/ic/{HEX}'))
        self.assertTrue(storage.is_issued_doc_key(self.bare_app, 'ic', f'42/ic/{HEX}'))

    def test_everything_near_it_fails(self):
        for path in (
            f'7/43/ic/{HEX}',              # another application, same organisation
            f'8/42/ic/{HEX}',              # the same application id under another organisation
            f'42/ic/{HEX}',                # the legacy shape on an org application
            f'7/42/epf/{HEX}',             # another doc type's folder
            '7/42/letters/1.pdf',          # an offer letter
            '7/42/bursary_v1.pdf',         # a bursary agreement
            f'7/42/ic/../ic/{HEX}',        # a parent step
            f'/7/42/ic/{HEX}',             # a leading slash
            f'7/42/ic/{HEX}/x',            # an extra segment
            f'7/42/ic/{HEX[:31]}',         # a short tail
            f'7/42/ic/{"A" * 32}',         # upper-case hex is never issued
            f'7/42/ic/{"g" * 32}',         # not hex
            '', None, 123,
        ):
            with self.subTest(path=path):
                self.assertFalse(storage.is_issued_doc_key(self.org_app, 'ic', path))

    def test_inside_the_app_prefix(self):
        self.assertTrue(storage.is_inside_app_prefix(self.org_app, '7/42/ic/abc'))
        self.assertTrue(storage.is_inside_app_prefix(self.org_app, '7/42/bursary_v1.pdf'))
        for path in ('7/43/ic/abc', '7/42', '7/42/../43/ic/abc', '/7/42/ic/abc',
                     '7/42//ic', '7/42/./ic', '', None):
            with self.subTest(path=path):
                self.assertFalse(storage.is_inside_app_prefix(self.org_app, path))

    def test_the_legacy_three_part_key_of_this_app_is_its_own(self):
        """L1: the ~1,114 rows recorded before the org prefix hold ``<app>/<doc_type>/<name>``."""
        self.assertTrue(storage.is_inside_app_prefix(self.org_app, '42/ic/abc'))
        self.assertTrue(storage.is_inside_app_prefix(self.org_app, f'42/results_slip/{HEX}'))
        self.assertTrue(storage.is_inside_app_prefix(self.bare_app, '42/ic/abc'))
        for path in (
            '43/ic/abc',              # another application's legacy key
            '4/ic/abc', '420/ic/abc',  # app 42 never matches app 4 or app 420
            '042/ic/abc',             # a padded id is not this id
            '42/letters/1.pdf',       # not a document type
            '42/ic/abc/x',            # an extra segment
            '42/ic',                  # too short
            '42/ic/..', '42/../abc', '42/ic/.', '42//abc', '/42/ic/abc', '42\\ic\\abc',
            '42/bursary_v1.pdf',      # a legacy bursary key is not a document
        ):
            with self.subTest(path=path):
                self.assertFalse(storage.is_inside_app_prefix(self.org_app, path))

    def test_an_org_prefixed_key_naming_this_app_in_the_middle_is_not_a_legacy_key(self):
        """``<org>/<app>/<file>`` (an org-prefixed bursary key) is three parts too: with this app's id in
        the middle its first part is an org id, and with this id first its middle is no doc type."""
        app_5 = SimpleNamespace(owning_organisation_id=9, id=5)
        self.assertFalse(storage.is_inside_app_prefix(app_5, '3/5/bursary_v1.pdf'))
        self.assertFalse(storage.is_inside_app_prefix(app_5, '5/42/bursary_v1.pdf'))   # org 5, app 42
        self.assertFalse(storage.is_inside_app_prefix(app_5, '5/42/letters/1.pdf'))
        self.assertFalse(storage.is_inside_app_prefix(app_5, f'5/42/ic/{HEX}'))       # org 5, app 42's doc
        self.assertTrue(storage.is_inside_app_prefix(app_5, f'5/ic/{HEX}'))           # its own legacy key


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class RecordOnlyTheIssuedKey(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()                       # an organisation-owned gift
        cls.other_org_cohort = make_cohort()             # a second organisation
        cls.me = make_student(name='Siti Test')
        cls.app = make_application('shortlisted', cohort=cls.cohort, student=cls.me)
        cls.same_org = make_application('shortlisted', cohort=cls.cohort)
        cls.cross_org = make_application('shortlisted', cohort=cls.other_org_cohort)

    def setUp(self):
        self.client = authed_client(self.me.supabase_user_id)

    def _post(self, path, doc_type='ic'):
        with patch('apps.scholarship.storage.object_exists', return_value=True):
            return self.client.post(DOCS, {'doc_type': doc_type, 'storage_path': path,
                                           'original_filename': 'f.pdf', 'size': 1000}, format='json')

    def _refused(self, path, doc_type='ic'):
        before = ApplicantDocument.objects.count()
        r = self._post(path, doc_type)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json().get('code'), 'bad_storage_path')
        self.assertEqual(ApplicantDocument.objects.count(), before)   # nothing saved

    def test_the_fixture_apps_really_are_in_two_organisations(self):
        self.assertIsNotNone(self.app.owning_organisation_id)
        self.assertEqual(self.same_org.owning_organisation_id, self.app.owning_organisation_id)
        self.assertNotEqual(self.cross_org.owning_organisation_id, self.app.owning_organisation_id)

    def test_another_applicants_key_in_the_same_organisation_is_refused(self):
        self._refused(issued_key(self.same_org, 'ic', 'theirs'))

    def test_another_organisations_applicants_key_is_refused(self):
        self._refused(issued_key(self.cross_org, 'ic', 'theirs'))

    def test_an_offer_letter_path_is_refused(self):
        self._refused(storage.build_doc_key(self.app, self.app.id, 'letters', '12.pdf'))
        self._refused(storage.build_doc_key(self.same_org, self.same_org.id, 'letters', '12.pdf'))

    def test_a_bursary_agreement_path_is_refused(self):
        self._refused(storage.build_doc_key(self.app, self.app.id, 'bursary_v1.pdf'))

    def test_a_parent_step_a_leading_slash_and_an_extra_segment_are_refused(self):
        mine = issued_key(self.app, 'ic', 'mine')
        self._refused(storage.build_doc_key(self.app, self.app.id, 'ic', '..', str(self.same_org.id),
                                            'ic', HEX))
        self._refused('/' + mine)
        self._refused(mine + '/extra')

    def test_another_doc_types_folder_is_refused(self):
        self._refused(issued_key(self.app, 'epf', 'mine'), doc_type='ic')

    def test_the_legacy_unprefixed_shape_is_refused_on_an_org_application(self):
        self._refused(f'{self.app.id}/ic/{HEX}')

    @patch('apps.scholarship.vision.ocr_document_full', return_value={'text': '', 'error': None})
    @patch('apps.scholarship.vision.run_vision_match_for_document', return_value={})
    @patch('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields', return_value=None)
    @patch('apps.scholarship.vision.run_field_extraction_for_document', return_value=None)
    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://s/dl')
    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://s/up')
    def test_sign_upload_then_record_works_for_every_doc_type(self, *_):
        """The record step accepts EXACTLY what the upload step issues, for every doc type."""
        self.assertGreater(len(ALL_DOC_TYPES), 10)
        for doc_type in ALL_DOC_TYPES:
            with self.subTest(doc_type=doc_type):
                signed = self.client.post(SIGN, {'doc_type': doc_type}, format='json')
                self.assertEqual(signed.status_code, 200, signed.content)
                path = signed.json()['storage_path']
                self.assertTrue(storage.is_issued_doc_key(self.app, doc_type, path), path)
                r = self._post(path, doc_type)
                self.assertNotEqual(r.json().get('code') if r.status_code == 400 else None,
                                    'bad_storage_path', r.content)
                self.assertEqual(r.status_code, 201, (doc_type, r.content))
                self.assertTrue(ApplicantDocument.objects.filter(
                    application=self.app, storage_path=path).exists())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class DeleteKeepsAForeignBlob(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.me = make_student(name='Siti Test')
        cls.app = make_application('shortlisted', cohort=cls.cohort, student=cls.me)
        cls.other = make_application('shortlisted', cohort=cls.cohort)

    def _delete(self, path):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path=path)
        with patch('apps.scholarship.storage.delete_objects', return_value=True) as dele, \
                self.assertLogs('apps.scholarship.storage', level='WARNING') as logs:
            r = authed_client(self.me.supabase_user_id).delete(f'{DOCS}{doc.id}/')
            storage.logger.warning('sentinel')   # assertLogs needs one line even when none is due
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())   # the row goes
        return dele, [m for m in logs.output if 'sentinel' not in m]

    def test_a_row_holding_another_applicants_path_never_deletes_that_blob(self):
        foreign = issued_key(self.other, 'ic', 'theirs')
        dele, warnings = self._delete(foreign)
        for call in dele.call_args_list:
            self.assertNotIn(foreign, call.args[0] if call.args else call.kwargs.get('paths', []))
        self.assertTrue(any('doc_delete_foreign_path' in w for w in warnings), warnings)
        self.assertFalse(any(foreign in w for w in warnings))   # the path is never logged

    def test_a_row_holding_its_own_path_still_deletes_its_blob(self):
        mine = issued_key(self.app, 'ic', 'mine')
        dele, warnings = self._delete(mine)
        dele.assert_called_once_with([mine])
        self.assertEqual(warnings, [])

    def test_a_row_holding_its_own_legacy_three_part_key_deletes_its_blob(self):
        """L1: a document recorded before the org prefix (``<app>/<doc_type>/<uuid>``) loses its file too."""
        self.assertIsNotNone(self.app.owning_organisation_id)
        legacy = f'{self.app.id}/ic/{HEX}'
        dele, warnings = self._delete(legacy)
        dele.assert_called_once_with([legacy])
        self.assertEqual(warnings, [])

    def test_a_row_holding_another_apps_legacy_key_keeps_that_blob(self):
        foreign = f'{self.other.id}/ic/{HEX}'
        dele, warnings = self._delete(foreign)
        for call in dele.call_args_list:
            self.assertNotIn(foreign, call.args[0] if call.args else call.kwargs.get('paths', []))
        self.assertTrue(any('doc_delete_foreign_path' in w for w in warnings), warnings)

    def test_an_org_prefixed_key_with_this_app_id_in_the_middle_keeps_that_blob(self):
        """``<org>/<this app id>/<file>`` where the first part is ANOTHER organisation's id."""
        other_org = self.app.owning_organisation_id + 1000
        foreign = f'{other_org}/{self.app.id}/bursary_v1.pdf'
        dele, warnings = self._delete(foreign)
        for call in dele.call_args_list:
            self.assertNotIn(foreign, call.args[0] if call.args else call.kwargs.get('paths', []))
        self.assertTrue(any('doc_delete_foreign_path' in w for w in warnings), warnings)
