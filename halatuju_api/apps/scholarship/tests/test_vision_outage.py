"""Tests for the Google-Vision OCR outage detector + admin alert command."""
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import detect_vision_outage


class TestVisionOutage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id='vo', nric='030101-14-1234')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')

    def _doc(self, *, error='', nric='', name='', hours_ago=1, doc_type='ic'):
        d = ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path='x',
            vision_error=error, vision_nric=nric, vision_name=name,
            vision_run_at=timezone.now() - timedelta(hours=hours_ago))
        return d

    def test_no_attempts_is_not_down(self):
        is_down, stats = detect_vision_outage()
        self.assertFalse(is_down)
        self.assertEqual(stats['attempts'], 0)

    def test_all_service_failures_no_success_is_down(self):
        self._doc(error='API quota exceeded')
        self._doc(error='deadline exceeded', doc_type='parent_ic')
        is_down, stats = detect_vision_outage()
        self.assertTrue(is_down)
        self.assertEqual(stats['service_failures'], 2)
        self.assertEqual(stats['successes'], 0)

    def test_any_success_is_not_down(self):
        self._doc(error='API quota exceeded')
        self._doc(nric='030101-14-1234', name='Student')  # a success
        is_down, _ = detect_vision_outage()
        self.assertFalse(is_down)

    def test_only_bad_images_is_not_down(self):
        """Blurry/empty images are not a service outage."""
        self._doc(error='empty image')
        self._doc(error='', nric='', name='')  # OCR ran, read nothing
        is_down, stats = detect_vision_outage()
        self.assertFalse(is_down)
        self.assertEqual(stats['service_failures'], 0)

    def test_failures_outside_window_ignored(self):
        self._doc(error='API quota exceeded', hours_ago=48)  # older than 24h
        is_down, stats = detect_vision_outage(window_hours=24)
        self.assertFalse(is_down)
        self.assertEqual(stats['attempts'], 0)

    @override_settings(ADMIN_NOTIFY_EMAIL='tamiliam@gmail.com')
    def test_command_sends_email_when_down(self):
        self._doc(error='API quota exceeded')
        call_command('alert_vision_outage')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Vision', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['tamiliam@gmail.com'])

    @override_settings(ADMIN_NOTIFY_EMAIL='tamiliam@gmail.com')
    def test_command_no_email_when_ok(self):
        self._doc(nric='030101-14-1234', name='Student')  # a success → not down
        call_command('alert_vision_outage')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ADMIN_NOTIFY_EMAIL='tamiliam@gmail.com')
    def test_command_dry_run_sends_nothing(self):
        self._doc(error='API quota exceeded')
        call_command('alert_vision_outage', '--dry-run')
        self.assertEqual(len(mail.outbox), 0)
