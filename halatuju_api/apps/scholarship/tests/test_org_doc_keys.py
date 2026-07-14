"""Platform Sprint 4 — org-prefixed document storage keys + signing fence.

New uploads carry an org prefix (<org_id>/<app_id>/<doc_type>/<uuid>); legacy keys
stay unprefixed and resolve to org #1. The signing seams refuse to sign a doc whose
key-org disagrees with its row-org (belt-and-braces). The orphan-blob walk handles
both key shapes so an org-prefixed live blob is never mistaken for an orphan.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import storage
from apps.scholarship.management.commands.cleanup_orphan_blobs import _walk_bucket
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.serializers import ApplicantDocumentSerializer


class TestBuildDocKey(TestCase):
    def test_org_prefixed_when_app_has_org(self):
        app = SimpleNamespace(owning_organisation_id=7, id=42)
        self.assertEqual(storage.build_doc_key(app, app.id, 'ic', 'abc'), '7/42/ic/abc')

    def test_legacy_when_no_org(self):
        app = SimpleNamespace(owning_organisation_id=None, id=42)
        self.assertEqual(storage.build_doc_key(app, app.id, 'ic', 'abc'), '42/ic/abc')

    def test_bursary_two_tail_prefixed(self):
        app = SimpleNamespace(owning_organisation_id=7, id=42)
        self.assertEqual(storage.build_doc_key(app, app.id, 'bursary_v1.pdf'), '7/42/bursary_v1.pdf')


class TestResolveOrgForPath(TestCase):
    def test_four_segment_doc_key_gives_org(self):
        self.assertEqual(storage.resolve_org_for_path('7/42/ic/abc'), 7)

    def test_legacy_three_segment_is_none(self):
        self.assertIsNone(storage.resolve_org_for_path('42/ic/abc'))

    def test_bursary_two_or_three_segment_is_none(self):
        self.assertIsNone(storage.resolve_org_for_path('42/bursary_v1.pdf'))
        self.assertIsNone(storage.resolve_org_for_path('7/42/bursary_v1.pdf'))

    def test_empty_is_none(self):
        self.assertIsNone(storage.resolve_org_for_path(''))
        self.assertIsNone(storage.resolve_org_for_path(None))


class TestSigningFence(TestCase):
    """The serializer refuses to sign a doc whose key-org contradicts its row-org."""
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='sk-a', name='A')
        cls.org_b = PartnerOrganisation.objects.create(code='sk-b', name='B')
        cls.cohort = ScholarshipCohort.objects.create(
            code='sk', name='B40', year=2026, owning_organisation=cls.org_a)
        cls.prof = StudentProfile.objects.create(supabase_user_id='sk-u', nric='030101-14-9', name='X')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.prof)

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed/x')
    def test_matching_org_signs(self, _mock):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic',
            storage_path=f'{self.org_a.id}/{self.app.id}/ic/abc')
        self.assertEqual(ApplicantDocumentSerializer().get_download_url(doc), 'https://signed/x')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed/x')
    def test_cross_org_key_refused(self, _mock):
        """Key claims org B, but the row is owned by org A → do NOT sign."""
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic',
            storage_path=f'{self.org_b.id}/{self.app.id}/ic/abc')
        self.assertIsNone(ApplicantDocumentSerializer().get_download_url(doc))

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed/x')
    def test_legacy_key_signs(self, _mock):
        """A legacy unprefixed key is unresolvable → falls back to the row FK → signs."""
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path=f'{self.app.id}/ic/abc')
        self.assertEqual(ApplicantDocumentSerializer().get_download_url(doc), 'https://signed/x')


class TestMixedShapeOrphanWalk(TestCase):
    """The walk recurses to leaves, so it yields blobs in BOTH the legacy 3-level and
    the org-prefixed 4-level layout — a live prefixed blob is never a false orphan."""

    def _file(self, name):
        return {'name': name, 'id': f'id-{name}', 'metadata': {'size': 1}}

    def _folder(self, name):
        return {'name': name, 'id': None, 'metadata': None}

    def test_walk_yields_both_shapes(self):
        # Bucket root holds: a legacy app folder '42' and an org folder '7'.
        responses = {
            '': [self._folder('42'), self._folder('7')],
            '42/': [self._folder('ic')],
            '42/ic/': [self._file('legacyblob')],
            '7/': [self._folder('99')],
            '7/99/': [self._folder('str')],
            '7/99/str/': [self._file('prefixedblob')],
        }
        with patch('apps.scholarship.storage.list_objects',
                   side_effect=lambda prefix='', limit=1000: responses.get(prefix, [])):
            leaves = set(_walk_bucket())
        self.assertEqual(leaves, {'42/ic/legacyblob', '7/99/str/prefixedblob'})
