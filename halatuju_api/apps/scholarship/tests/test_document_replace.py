"""H6: a student may replace a sent / done document up to three times, counted in the database.

A document is its slot (type + household member + request code). Only an upload sent with `replace`
is counted; the 4th is refused 409 `replace_limit_reached`. The documents lock is checked first, and
the exempt types stay replaceable after it. A replaced copy stays superseded (version history).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

DOCS = '/api/v1/scholarship/documents/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@patch('apps.scholarship.upload_read.needs_read', return_value=True)    # recorded queued: no paid read
@patch('apps.scholarship.storage.object_exists', return_value=True)
class TestDocumentReplace(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rp', name='Replace', year=2026)

    def _case(self, stage='interviewing', **kw):
        student = make_student()
        app = make_application(stage, cohort=self.cohort, student=student, **kw)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='ic', replace=True, member=''):
        body = {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                'original_filename': 'a.pdf', 'size': 1000, 'household_member': member}
        if replace:
            body['replace'] = True
        return client.post(DOCS, body, format='json')

    def _first(self, app, doc_type='ic', member=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member=member, storage_path='first')

    def test_three_replaces_work_and_the_fourth_is_refused(self, _o, _n):
        app, client = self._case()
        self._first(app)
        for n in (1, 2, 3):
            resp = self._post(client, app)
            self.assertEqual(resp.status_code, 201, resp.content)
            self.assertEqual(ApplicantDocument.objects.filter(application=app).order_by('-id').first().replace_count, n)
        resp = self._post(client, app)
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertEqual(body['code'], 'replace_limit_reached')
        self.assertTrue(body['message'])
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 4)   # nothing recorded

    def test_the_count_is_per_document(self, _o, _n):
        app, client = self._case()
        self._first(app, 'salary_slip', 'father')
        self._first(app, 'salary_slip', 'mother')
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 201)
        self.assertEqual(self._post(client, app, 'salary_slip', member='father').status_code, 409)
        self.assertEqual(self._post(client, app, 'salary_slip', member='mother').status_code, 201)

    def test_a_plain_re_upload_is_never_counted_or_capped(self, _o, _n):
        app, client = self._case()
        self._first(app)
        for _ in range(5):
            self.assertEqual(self._post(client, app, replace=False).status_code, 201)
        self.assertEqual(self._post(client, app).status_code, 201)   # the first counted replace
        self.assertEqual(ApplicantDocument.objects.filter(application=app, replace_count=1).count(), 1)

    def test_a_first_upload_is_not_a_replace(self, _o, _n):
        app, client = self._case()
        self.assertEqual(self._post(client, app).status_code, 201)
        self.assertEqual(ApplicantDocument.objects.get(application=app).replace_count, 0)

    def test_list_serves_the_count_and_the_limit(self, _o, _n):
        app, client = self._case()
        self._first(app, 'bank_statement')
        self._post(client, app, 'bank_statement')
        docs = client.get(DOCS).json()['documents']
        self.assertEqual([(d['replace_count'], d['replace_limit']) for d in docs], [(1, 3)])

    def test_a_replaced_copy_stays_superseded(self, _o, _n):
        app, client = self._case()
        old = self._first(app, 'bank_statement')
        self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        old.refresh_from_db()
        self.assertIsNotNone(old.superseded_at)
        live = ApplicantDocument.objects.get(application=app, superseded_at__isnull=True)
        self.assertEqual((old.superseded_by_id, live.replace_count), (live.id, 1))

    def test_locked_refuses_a_replace(self, _o, _n):
        app, client = self._case('awaiting_qc', outcome='recommend')
        self._first(app)
        resp = self._post(client, app)
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'documents_locked'))

    def test_locked_but_exempt_type_can_still_be_replaced(self, _o, _n):
        app, client = self._case('awarded')
        self._first(app, 'bank_statement')
        for _ in range(3):
            self.assertEqual(self._post(client, app, 'bank_statement').status_code, 201)
        resp = self._post(client, app, 'bank_statement')
        self.assertEqual(resp.json()['code'], 'replace_limit_reached')
