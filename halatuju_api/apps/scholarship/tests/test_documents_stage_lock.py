"""The documents stage lock (student-help H4): no student upload or delete once querying is locked.

Allowed while the case is still being worked (interviewing); refused with 409 `documents_locked` from
the interview's conclusion onward (interviewed; funded states; recommended and later already have no live application for this view); a reopened decision unlocks it.
The post-award bank statement and the two late higher-results asks stay open (the case asks for them).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'
SIGN = DOCS + 'sign-upload/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentsStageLock(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='lk', name='Lock', year=2026)

    def _case(self, stage, **kw):
        student = make_student()
        app = make_application(stage, cohort=self.cohort, student=student, **kw)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='ic'):
        return client.post(DOCS, {
            'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
            'original_filename': 'a.pdf', 'size': 1000,
        }, format='json')

    # ── before the lock ─────────────────────────────────────────────
    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/u')
    def test_sign_upload_allowed_while_interviewing(self, _m):
        _app, client = self._case('interviewing')
        self.assertEqual(client.post(SIGN, {'doc_type': 'ic'}, format='json').status_code, 200)

    def test_delete_allowed_while_interviewing(self):
        app, client = self._case('interviewing')
        doc = ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='x')
        self.assertEqual(client.delete(f'{DOCS}{doc.id}/').status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())

    @patch('apps.scholarship.storage.object_exists', return_value=True)
    def test_record_not_locked_while_interviewing(self, _m):
        app, client = self._case('interviewing')
        resp = self._post(client, app)
        self.assertNotEqual(resp.json().get('code'), 'documents_locked')

    # ── at and after the lock ───────────────────────────────────────
    def test_refused_at_and_after_the_lock(self):
        for stage, kw in (('awaiting_qc', {'outcome': 'recommend'}), ('awarded', {}), ('maintenance', {})):
            with self.subTest(stage=stage):
                app, client = self._case(stage, **kw)
                doc = ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='x')
                for resp in (client.post(SIGN, {'doc_type': 'ic'}, format='json'),
                             self._post(client, app),
                             client.delete(f'{DOCS}{doc.id}/')):
                    self.assertEqual(resp.status_code, 409)
                    body = resp.json()
                    self.assertEqual(body['code'], 'documents_locked')
                    self.assertTrue(body['message'])
                self.assertTrue(ApplicantDocument.objects.filter(id=doc.id).exists())

    def test_reopened_decision_unlocks(self):
        app, client = self._case('awaiting_qc', outcome='recommend')
        ScholarshipApplication.objects.filter(pk=app.pk).update(decision_reopened_at=timezone.now())
        doc = ApplicantDocument.objects.create(application=app, doc_type='ic', storage_path='x')
        self.assertEqual(client.delete(f'{DOCS}{doc.id}/').status_code, 200)

    # ── what stays open after the lock ──────────────────────────────
    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/u')
    def test_post_award_bank_statement_stays_open(self, _m):
        _app, client = self._case('awarded')
        self.assertEqual(client.post(SIGN, {'doc_type': 'bank_statement'}, format='json').status_code, 200)

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/u')
    def test_bank_statement_refused_once_maintenance(self, _m):
        _app, client = self._case('maintenance')
        self.assertEqual(client.post(SIGN, {'doc_type': 'bank_statement'}, format='json').status_code, 409)

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/u')
    def test_late_higher_results_ask_stays_open_while_interviewed(self, _m):
        _app, client = self._case('awaiting_qc', outcome='recommend')
        self.assertEqual(client.post(SIGN, {'doc_type': 'higher_results'}, format='json').status_code, 200)
        self.assertEqual(client.post(SIGN, {'doc_type': 'ic'}, format='json').status_code, 409)

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/u')
    def test_funded_student_semester_results_stay_open(self, _m):
        _app, client = self._case('maintenance')
        self.assertEqual(client.post(SIGN, {'doc_type': 'semester_result'}, format='json').status_code, 200)

    # ── H4 review carry-overs, and what the list serves (H5) ────────
    @patch('apps.scholarship.storage.object_exists', return_value=True)
    def test_exempt_type_can_be_recorded_after_the_lock(self, _m):
        app, client = self._case('awarded')
        resp = self._post(client, app, 'bank_statement')
        self.assertNotEqual(resp.json().get('code'), 'documents_locked')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self._post(client, app, 'ic').json().get('code'), 'documents_locked')

    def test_exempt_type_can_be_deleted_after_the_lock(self):
        app, client = self._case('awarded')
        doc = ApplicantDocument.objects.create(application=app, doc_type='bank_statement', storage_path='x')
        self.assertEqual(client.delete(f'{DOCS}{doc.id}/').status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())

    def test_delete_of_a_slip_says_slip_locked_before_the_lock(self):
        app, client = self._case('awarded')
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='semester_result', storage_path='x', request_code='in_programme')
        resp = client.delete(f'{DOCS}{doc.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()['code'], 'slip_locked')

    def test_list_serves_the_lock_state(self):
        _app, client = self._case('interviewing')
        self.assertEqual(client.get(DOCS).json()['lock'], {'locked': False, 'open_doc_types': []})
        _app, client = self._case('awaiting_qc', outcome='recommend')
        lock = client.get(DOCS).json()['lock']
        self.assertTrue(lock['locked'])
        self.assertIn('higher_results', lock['open_doc_types'])
        self.assertNotIn('ic', lock['open_doc_types'])
        _app, client = self._case('awarded')
        lock = client.get(DOCS).json()['lock']
        self.assertEqual(lock['locked'], True)
        self.assertIn('bank_statement', lock['open_doc_types'])
        self.assertIn('semester_result', lock['open_doc_types'])

    def test_funded_states_are_not_copied(self):
        from apps.scholarship.views import common, document_lock
        self.assertIs(document_lock._FUNDED_STATES, common._FUNDED_STATES)
        self.assertFalse(hasattr(document_lock, 'FUNDED_STATES'))
