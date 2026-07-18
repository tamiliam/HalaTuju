"""Contract module Sprint 5 — execution distribution.

Once an agreement is fully executed, distribute_executed_agreement emails the signed
PDF to the student + witness contact + org admins and files it in Drive, idempotently
via two stamps, best-effort (a storage/Drive/email failure never blocks execution). All
external seams (storage.download_object, sheets.write_contract_pdf, email) are mocked.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import bursary
from apps.scholarship.models import BursaryAgreement, ScholarshipApplication, ScholarshipCohort

from apps.scholarship.tests.contract_helpers import brightpath_org


def _executed_agreement(*, suffix='1', with_org=False, **overrides):
    org = brightpath_org()
    cohort = ScholarshipCohort.objects.create(
        code=f'di-{suffix}', name='B40', year=2026, owning_organisation=org)
    referring = None
    if with_org:
        referring = PartnerOrganisation.objects.create(
            code=f'di-ref-{suffix}', name='Ref Org', contact_email='partner@example.test')
    profile = StudentProfile.objects.create(
        supabase_user_id=f'di-{suffix}', name='Stu', contact_email='stu@e.test',
        referred_by_org=referring)
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='active', notify_email='stu@e.test',
        chosen_programme={'course_name': 'Diploma in Nursing'})
    ag = BursaryAgreement.objects.create(
        application=app, version='2026-v1', pdf_storage_path=f'{app.id}/agreement.pdf',
        student_signed_at=timezone.now(), guarantor_signed_at=timezone.now(),
        foundation_signed_at=timezone.now(), witness_org=referring, **overrides)
    return ag, app


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   FOUNDATION_NOTIFY_EMAIL='fo@example.test')
class TestDistribution(TestCase):
    @patch('apps.scholarship.sheets.write_contract_pdf', return_value='https://drive/xyz')
    @patch('apps.scholarship.storage.download_object', return_value=b'%PDF-1.4 signed')
    def test_emails_pdf_to_all_parties_and_files_in_drive(self, _dl, mock_drive):
        mail.outbox = []
        ag, _app = _executed_agreement(with_org=True)
        bursary.distribute_executed_agreement(ag)
        ag.refresh_from_db()
        tos = [m.to[0] for m in mail.outbox]
        self.assertIn('stu@e.test', tos)          # student "in effect" notice
        self.assertIn('partner@example.test', tos)  # witness copy
        self.assertIn('fo@example.test', tos)       # org-admin copy
        # the signed PDF is attached
        self.assertTrue(any(m.attachments for m in mail.outbox))
        self.assertIsNotNone(ag.executed_pdf_emailed_at)
        self.assertEqual(ag.drive_file_url, 'https://drive/xyz')
        mock_drive.assert_called_once()

    @patch('apps.scholarship.sheets.write_contract_pdf', return_value='https://drive/xyz')
    @patch('apps.scholarship.storage.download_object', return_value=b'%PDF')
    def test_idempotent(self, _dl, mock_drive):
        ag, _app = _executed_agreement(suffix='idem')
        bursary.distribute_executed_agreement(ag)
        mail.outbox = []
        mock_drive.reset_mock()
        bursary.distribute_executed_agreement(ag)   # second run: stamps already set
        self.assertEqual(mail.outbox, [])
        mock_drive.assert_not_called()

    @patch('apps.scholarship.sheets.write_contract_pdf')
    @patch('apps.scholarship.storage.download_object', side_effect=Exception('no blob'))
    def test_storage_failure_still_notifies_and_never_uploads(self, _dl, mock_drive):
        mail.outbox = []
        ag, _app = _executed_agreement(suffix='sf')
        bursary.distribute_executed_agreement(ag)   # must not raise
        ag.refresh_from_db()
        self.assertIn('stu@e.test', [m.to[0] for m in mail.outbox])  # plain notice still sent
        self.assertIsNotNone(ag.executed_pdf_emailed_at)
        self.assertEqual(ag.drive_file_url, '')     # no PDF → no Drive
        mock_drive.assert_not_called()

    @patch('apps.scholarship.sheets.write_contract_pdf', return_value=None)   # Drive down
    @patch('apps.scholarship.storage.download_object', return_value=b'%PDF')
    def test_drive_failure_still_emails(self, _dl, _drive):
        mail.outbox = []
        ag, _app = _executed_agreement(suffix='df')
        bursary.distribute_executed_agreement(ag)
        ag.refresh_from_db()
        self.assertIn('stu@e.test', [m.to[0] for m in mail.outbox])
        self.assertIsNotNone(ag.executed_pdf_emailed_at)
        self.assertEqual(ag.drive_file_url, '')

    @override_settings(BURSARY_AGREEMENT_ENABLED=True)
    @patch('apps.scholarship.sheets.write_contract_pdf', return_value='https://drive/late')
    @patch('apps.scholarship.storage.download_object', return_value=b'%PDF')
    def test_signing_reminder_retries_incomplete_distribution(self, _dl, _drive):
        # An executed agreement whose distribution never completed (no stamps).
        ag, _app = _executed_agreement(suffix='retry')
        self.assertIsNone(ag.executed_pdf_emailed_at)
        summary = bursary.send_signing_reminders()
        ag.refresh_from_db()
        self.assertEqual(summary['distributed'], 1)
        self.assertIsNotNone(ag.executed_pdf_emailed_at)
        self.assertEqual(ag.drive_file_url, 'https://drive/late')
