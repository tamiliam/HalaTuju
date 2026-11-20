"""LL4 phase 2 - `record-verdict` stores the record of what fed the decision.

Pins: recording a verdict stores the record (documents, models, fingerprint) in the same save, and
the stored fingerprint is the one the saved row gives when rebuilt; a
builder that fails still lets the decision save, with `{schema, error}` stored; an old decided row
with an empty record still loads and serialises; re-recording replaces the record; and the column
is staff-internal: neither the admin detail response, the record-verdict response nor the
student's own application list carries it. All data is made up.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import verdict_context as vc
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.serializers.application import ApplicationCreateSerializer
from apps.scholarship.serializers.application_read import ApplicationReadSerializer
from apps.scholarship.serializers_admin.application_detail import AdminApplicationDetailSerializer
from apps.scholarship.serializers_admin.application_list import AdminApplicationListSerializer
from apps.scholarship.tests.factories import (
    RECOMMEND_VERDICT, TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

KEY = 'ai_verdict_context'
REASON = 'Made-up reason.'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRecordVerdictStoresTheContext(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def setUp(self):
        # A decided case AWAITING QC, as every row decided before LL4 is: its record is empty.
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort,
                                    reviewer=self.reviewer)
        self.doc = ApplicantDocument.objects.create(application=self.app, doc_type='ic',
                                                    storage_path='test/ic')

    def _url(self, door=''):
        return f'/api/v1/admin/scholarship/applications/{self.app.pk}/{door}'

    def _record(self):
        return authed_client(self.reviewer).post(
            self._url('record-verdict/'),
            {'officer_verdict': dict(RECOMMEND_VERDICT), 'reason': REASON}, format='json')

    def _stored(self):
        return ScholarshipApplication.objects.get(pk=self.app.pk)

    def test_recording_a_verdict_stores_the_record(self):
        r = self._record()
        self.assertEqual(r.status_code, 200, r.content)
        app = self._stored()
        record = app.ai_verdict_context
        self.assertEqual(set(record), set(vc.RECORD_KEYS))
        self.assertEqual([d['id'] for d in record['documents']], [self.doc.id])
        self.assertTrue(record['models'])
        self.assertRegex(record['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertEqual(record['key_check'], vc.key_check())
        self.assertEqual(len(app.ai_verdict_snapshot), 4)
        self.assertEqual(app.verdict_reason, REASON)

    def test_the_stored_fingerprint_matches_the_stored_row(self):
        """No false movement: rebuilt from the saved row straight after the decision, the
        fingerprint is the one stored (the engine ran first on the same instance and wrote no
        hashed field; the save wrote none either)."""
        self.assertEqual(self._record().status_code, 200)
        app = self._stored()
        self.assertEqual(vc.build_verdict_context(app)['fingerprint'],
                         app.ai_verdict_context['fingerprint'])

    def test_a_failed_builder_still_saves_the_decision(self):
        with mock.patch.object(vc, 'build_verdict_context', side_effect=RuntimeError('boom')):
            with self.assertLogs('apps.scholarship.verdict_context', level='WARNING'):
                r = self._record()
        self.assertEqual(r.status_code, 200, r.content)
        app = self._stored()
        self.assertEqual(app.ai_verdict_context, {'schema': vc.RECORD_SCHEMA, 'error': vc.BUILD_FAILED})
        self.assertEqual(app.officer_verdict['overall'], 'accept')
        self.assertEqual(app.verdict_reason, REASON)
        self.assertIsNotNone(app.verdict_decided_at)
        self.assertEqual(len(app.ai_verdict_snapshot), 4)

    def test_re_recording_replaces_the_record(self):
        self.assertEqual(self._record().status_code, 200)
        first = self._stored().ai_verdict_context
        added = ApplicantDocument.objects.create(application=self.app, doc_type='offer_letter',
                                                 storage_path='test/offer')
        self.assertEqual(self._record().status_code, 200)
        second = self._stored().ai_verdict_context
        self.assertEqual([d['id'] for d in second['documents']], sorted([self.doc.id, added.id]))
        self.assertNotEqual(second['fingerprint'], first['fingerprint'])

    def test_an_old_decided_row_with_an_empty_record_loads_and_serialises(self):
        app = self._stored()
        self.assertIsNotNone(app.verdict_decided_at)
        self.assertEqual(app.ai_verdict_context, {})
        self.assertIsInstance(ApplicationReadSerializer(app).data, dict)
        self.assertIsInstance(AdminApplicationDetailSerializer(app).data, dict)
        r = authed_client(self.reviewer).get(self._url())
        self.assertEqual(r.status_code, 200, r.content)

    def test_no_response_carries_the_record(self):
        recorded = self._record()
        self.assertEqual(recorded.status_code, 200, recorded.content)
        self.assertTrue(self._stored().ai_verdict_context)
        fingerprint = self._stored().ai_verdict_context['fingerprint']
        detail = authed_client(self.reviewer).get(self._url())
        self.assertEqual(detail.status_code, 200, detail.content)
        mine = authed_client(self.app.profile).get('/api/v1/scholarship/applications/')
        self.assertEqual(mine.status_code, 200, mine.content)
        self.assertEqual(len(mine.json()['applications']), 1)
        for name, response in (('record-verdict', recorded), ('admin detail', detail),
                               ('student list', mine)):
            with self.subTest(response=name):
                text = response.content.decode()   # anywhere in the body, at any depth
                self.assertNotIn(KEY, text)
                self.assertNotIn(fingerprint, text)

    def test_no_application_serializer_lists_the_column(self):
        for serializer in (ApplicationReadSerializer, AdminApplicationDetailSerializer,
                           AdminApplicationListSerializer, ApplicationCreateSerializer):
            with self.subTest(serializer=serializer.__name__):
                self.assertNotIn(KEY, serializer.Meta.fields)
