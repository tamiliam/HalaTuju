"""Tests for the internal Cloud-Scheduler cron endpoint (shared-secret auth)."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(ROOT_URLCONF='halatuju.urls', CRON_SECRET='test-cron-secret')
class TestCronEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_forbidden_without_secret(self):
        r = self.client.post('/api/v1/internal/cron/vision-outage/')
        self.assertEqual(r.status_code, 403)

    def test_forbidden_with_wrong_secret(self):
        r = self.client.post('/api/v1/internal/cron/vision-outage/', HTTP_X_CRON_SECRET='nope')
        self.assertEqual(r.status_code, 403)

    def test_unknown_job_404(self):
        r = self.client.post('/api/v1/internal/cron/not-a-job/', HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 404)

    def test_runs_vision_outage(self):
        r = self.client.post('/api/v1/internal/cron/vision-outage/', HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['job'], 'vision-outage')
        self.assertIn('output', r.json())

    def test_runs_decision_emails(self):
        r = self.client.post('/api/v1/internal/cron/decision-emails/', HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 200)

    @override_settings(CRON_SECRET='')
    def test_inert_when_secret_unset(self):
        # No CRON_SECRET configured → endpoint refuses everything (can't be hit blind).
        r = self.client.post('/api/v1/internal/cron/vision-outage/', HTTP_X_CRON_SECRET='')
        self.assertEqual(r.status_code, 403)
