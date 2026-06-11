"""Tests for the backup_documents command (off-platform GCS backup of the doc vault).

The Supabase list/download and the GCS upload are mocked, so these run with no
network, no credentials, and without google-cloud-storage installed.
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

CMD = 'apps.scholarship.management.commands.backup_documents'

# A 3-file bucket with one root file and a nested folder, to exercise the recursive walk.
_TREE = {
    '': [
        {'name': 'app-1', 'id': None},  # folder
        {'name': 'orphan.pdf', 'id': 'f0', 'metadata': {'mimetype': 'application/pdf'}},
    ],
    'app-1': [
        {'name': 'ic.jpg', 'id': 'f1', 'metadata': {'mimetype': 'image/jpeg'}},
        {'name': 'sub', 'id': None},  # nested folder
    ],
    'app-1/sub': [
        {'name': 'str.png', 'id': 'f2', 'metadata': {'mimetype': 'image/png'}},
    ],
}


def _fake_list(prefix='', limit=1000):
    return _TREE.get(prefix, [])


@override_settings(DOCUMENT_BACKUP_BUCKET='backup-bkt', SUPABASE_SERVICE_ROLE_KEY='svc-key')
class BackupDocumentsTests(TestCase):
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=b'filebytes')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_mirrors_every_file_with_namespaced_blob_paths(self, _list, _dl, up):
        out = StringIO()
        call_command('backup_documents', stdout=out)

        uploaded = {call.args[1] for call in up.call_args_list}  # blob_path is arg #2
        self.assertEqual(uploaded, {
            'b40-documents/orphan.pdf',
            'b40-documents/app-1/ic.jpg',
            'b40-documents/app-1/sub/str.png',
        })
        self.assertEqual(up.call_count, 3)
        self.assertIn('3/3 copied', out.getvalue())

    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=b'x')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_dry_run_downloads_and_uploads_nothing(self, _list, dl, up):
        out = StringIO()
        call_command('backup_documents', '--dry-run', stdout=out)
        dl.assert_not_called()
        up.assert_not_called()
        self.assertIn('DRY RUN', out.getvalue())
        self.assertIn('3 objects', out.getvalue())

    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=None)  # download fails
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_download_failure_is_counted_and_upload_skipped(self, _list, _dl, up):
        out = StringIO()
        call_command('backup_documents', stdout=out)
        up.assert_not_called()                 # nothing uploaded when bytes can't be fetched
        self.assertIn('0/3 copied', out.getvalue())
        self.assertIn('3 FAILED', out.getvalue())


class BackupDocumentsConfigTests(TestCase):
    @override_settings(DOCUMENT_BACKUP_BUCKET='', SUPABASE_SERVICE_ROLE_KEY='svc-key')
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_no_dest_bucket_is_a_clean_noop(self, lst, up):
        out = StringIO()
        call_command('backup_documents', stdout=out)
        lst.assert_not_called()  # bails before even walking
        up.assert_not_called()
        self.assertIn('not set', out.getvalue())
