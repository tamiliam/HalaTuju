"""Tests for the orphan-blob cleanup command (TD-062)."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


def _file(name):
    """A Supabase 'file' list item (non-null id)."""
    return {'name': name, 'id': f'id-{name}', 'metadata': {'size': 1}}


def _folder(name):
    """A Supabase 'folder' list item (id=None)."""
    return {'name': name, 'id': None, 'metadata': None}


class TestCleanupOrphanBlobs(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id='u1', nric='030101-14-1234')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')
        # One known doc the DB references.
        ApplicantDocument.objects.create(
            application=cls.app, doc_type='ic',
            storage_path=f'{cls.app.id}/ic/keep123')

    def _walk_side_effect(self):
        """list_objects(prefix=...) responses simulating one app folder with an
        'ic' folder holding the referenced blob + one orphan."""
        app = self.app.id
        responses = {
            '': [_folder(str(app))],
            f'{app}/': [_folder('ic')],
            f'{app}/ic/': [_file('keep123'), _file('orphan456')],
        }
        return lambda prefix='', limit=1000: responses.get(prefix, [])

    def test_dry_run_lists_orphans_without_deleting(self):
        out = StringIO()
        with patch('apps.scholarship.storage.list_objects',
                   side_effect=self._walk_side_effect()), \
             patch('apps.scholarship.storage.delete_objects', return_value=True) as mock_del:
            call_command('cleanup_orphan_blobs', stdout=out)
        output = out.getvalue()
        self.assertIn('orphan456', output)
        self.assertNotIn('keep123', output)  # referenced blob is not an orphan
        mock_del.assert_not_called()  # dry run never deletes

    def test_apply_deletes_only_orphans(self):
        out = StringIO()
        with patch('apps.scholarship.storage.list_objects',
                   side_effect=self._walk_side_effect()), \
             patch('apps.scholarship.storage.delete_objects', return_value=True) as mock_del:
            call_command('cleanup_orphan_blobs', '--apply', stdout=out)
        mock_del.assert_called_once()
        deleted = mock_del.call_args.args[0]
        self.assertEqual(deleted, [f'{self.app.id}/ic/orphan456'])

    def test_no_orphans_is_clean(self):
        app = self.app.id
        responses = {
            '': [_folder(str(app))],
            f'{app}/': [_folder('ic')],
            f'{app}/ic/': [_file('keep123')],  # only the referenced blob
        }
        out = StringIO()
        with patch('apps.scholarship.storage.list_objects',
                   side_effect=lambda prefix='', limit=1000: responses.get(prefix, [])), \
             patch('apps.scholarship.storage.delete_objects', return_value=True) as mock_del:
            call_command('cleanup_orphan_blobs', '--apply', stdout=out)
        self.assertIn('No orphan blobs', out.getvalue())
        mock_del.assert_not_called()
