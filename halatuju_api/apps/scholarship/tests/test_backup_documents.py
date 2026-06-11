"""Tests for the backup_documents command (off-platform GCS backup of the doc vault).

The Supabase list/download and the GCS upload + existing-listing are mocked, so
these run with no network, no credentials, and without google-cloud-storage.
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

CMD = 'apps.scholarship.management.commands.backup_documents'

# A 3-file bucket with a root file and a nested folder, to exercise the recursive walk.
_TREE = {
    '': [
        {'name': 'app-1', 'id': None},  # folder
        {'name': 'orphan.pdf', 'id': 'f0', 'metadata': {'mimetype': 'application/pdf', 'size': 10}},
    ],
    'app-1': [
        {'name': 'ic.jpg', 'id': 'f1', 'metadata': {'mimetype': 'image/jpeg', 'size': 20}},
        {'name': 'sub', 'id': None},  # nested folder
    ],
    'app-1/sub': [
        {'name': 'str.png', 'id': 'f2', 'metadata': {'mimetype': 'image/png', 'size': 30}},
    ],
}


def _fake_list(prefix='', limit=1000):
    return _TREE.get(prefix, [])


@override_settings(DOCUMENT_BACKUP_BUCKET='backup-bkt', SUPABASE_SERVICE_ROLE_KEY='svc-key')
class BackupDocumentsTests(TestCase):
    @patch(f'{CMD}._existing_gcs', return_value={})  # nothing backed up yet
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=b'filebytes')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_mirrors_every_file_with_namespaced_blob_paths(self, _list, _dl, up, _ex):
        out = StringIO()
        call_command('backup_documents', stdout=out)

        uploaded = {call.args[1] for call in up.call_args_list}  # blob_path is arg #2
        self.assertEqual(uploaded, {
            'b40-documents/orphan.pdf',
            'b40-documents/app-1/ic.jpg',
            'b40-documents/app-1/sub/str.png',
        })
        self.assertEqual(up.call_count, 3)
        self.assertIn('3 copied, 0 unchanged, 3 total', out.getvalue())

    @patch(f'{CMD}._existing_gcs', return_value={'b40-documents/orphan.pdf': 10})  # already backed up, same size
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=b'x')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_skips_objects_already_backed_up_at_same_size(self, _list, _dl, up, _ex):
        out = StringIO()
        call_command('backup_documents', stdout=out)
        uploaded = {call.args[1] for call in up.call_args_list}
        self.assertNotIn('b40-documents/orphan.pdf', uploaded)  # skipped
        self.assertEqual(up.call_count, 2)  # only the two new ones
        self.assertIn('2 copied, 1 unchanged, 3 total', out.getvalue())

    @patch(f'{CMD}._existing_gcs')
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=b'x')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_dry_run_lists_nothing_and_uploads_nothing(self, _list, dl, up, ex):
        out = StringIO()
        call_command('backup_documents', '--dry-run', stdout=out)
        ex.assert_not_called()  # dry-run doesn't even list the GCS bucket
        dl.assert_not_called()
        up.assert_not_called()
        self.assertIn('DRY RUN', out.getvalue())
        self.assertIn('3 objects', out.getvalue())

    @patch(f'{CMD}._existing_gcs', return_value={})
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.download_object', return_value=None)  # download fails
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_download_failure_is_counted_and_upload_skipped(self, _list, _dl, up, _ex):
        out = StringIO()
        call_command('backup_documents', stdout=out)
        up.assert_not_called()
        self.assertIn('0 copied, 0 unchanged, 3 total', out.getvalue())
        self.assertIn('3 FAILED', out.getvalue())


class BackupDocumentsConfigTests(TestCase):
    @override_settings(DOCUMENT_BACKUP_BUCKET='', SUPABASE_SERVICE_ROLE_KEY='svc-key')
    @patch(f'{CMD}._upload_to_gcs')
    @patch(f'{CMD}.storage.list_objects', side_effect=_fake_list)
    def test_no_dest_bucket_is_a_clean_noop(self, lst, up):
        out = StringIO()
        call_command('backup_documents', stdout=out)
        lst.assert_not_called()  # bails before walking
        up.assert_not_called()
        self.assertIn('not set', out.getvalue())
