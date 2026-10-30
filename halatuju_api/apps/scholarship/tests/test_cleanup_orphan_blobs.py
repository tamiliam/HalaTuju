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


class TestEveryKnownPathIsKept(TestCase):
    """S6b review 4: a letter PDF, a signed agreement PDF and a request's screenshot all live in this
    bucket. The sweep once knew only `ApplicantDocument`, so `--apply` would have deleted every one."""

    def test_letters_agreements_and_request_attachments_are_known(self):
        import datetime
        from django.utils import timezone
        from apps.courses.models import PartnerAdmin
        from apps.scholarship.management.commands.cleanup_orphan_blobs import known_paths
        from apps.scholarship.models import BursaryAgreement, Letter, OrgRequest, OrgRequestAttachment
        from apps.scholarship.tests.factories import make_application
        app = make_application('maintenance')
        org = app.owning_organisation
        now = timezone.now()
        BursaryAgreement.objects.create(application=app, version='2026-v1',
                                        pdf_storage_path=f'{org.id}/{app.id}/agreement.pdf',
                                        student_signed_at=now, guarantor_signed_at=now, foundation_signed_at=now)
        Letter.objects.create(application=app, kind='general', language='en', subject='S', body='B',
                              response_due_on=datetime.date(2026, 11, 13),
                              pdf_path=f'{org.id}/{app.id}/letters/1.pdf')
        admin = PartnerAdmin.objects.create(supabase_user_id='orphan-admin', owning_organisation=org,
                                            role='org_admin', is_active=True, email='o@example.test')
        req = OrgRequest.objects.create(organisation=org, submitted_by=admin, kind='feature', title='t',
                                        description='d')
        OrgRequestAttachment.objects.create(org_request=req, storage_path=f'requests/{org.id}/{req.id}/abc',
                                            original_filename='a.png', content_type='image/png', size=1,
                                            uploaded_by=admin)
        known = known_paths()
        for path in (f'{org.id}/{app.id}/agreement.pdf', f'{org.id}/{app.id}/letters/1.pdf',
                     f'requests/{org.id}/{req.id}/abc'):
            with self.subTest(path=path):
                self.assertIn(path, known)

    def test_apply_never_deletes_a_letter_pdf(self):
        import datetime
        from apps.scholarship.models import Letter
        from apps.scholarship.tests.factories import make_application
        app = make_application('maintenance')
        org = app.owning_organisation
        Letter.objects.create(application=app, kind='general', language='en', subject='S', body='B',
                              response_due_on=datetime.date(2026, 11, 13),
                              pdf_path=f'{org.id}/{app.id}/letters/7.pdf')
        tree = {'': [_folder(str(org.id))], f'{org.id}/': [_folder(str(app.id))],
                f'{org.id}/{app.id}/': [_folder('letters')],
                f'{org.id}/{app.id}/letters/': [_file('7.pdf')]}
        with patch('apps.scholarship.storage.list_objects', side_effect=lambda prefix='', **kw: tree.get(prefix, [])), \
                patch('apps.scholarship.storage.delete_objects') as delete:
            out = StringIO()
            call_command('cleanup_orphan_blobs', '--apply', stdout=out)
        delete.assert_not_called()
        self.assertIn('No orphan blobs', out.getvalue())
