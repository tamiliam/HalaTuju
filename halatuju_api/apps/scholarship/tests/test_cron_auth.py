"""SEC-05 (A1.9): a cron key per job FAMILY, with the shared CRON_SECRET still accepted while set.

The four properties that make the split safe to deploy before the owner sets anything:
the shared key keeps working; a family key opens its own family and no other; an unset key
opens nothing; and every job in `CronRunView.JOBS` has a family.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.scholarship import cron_auth
from apps.scholarship.views import CronRunView

NO_FAMILY_KEYS = {f: '' for f in cron_auth.FAMILIES}
FAMILY_KEYS = {'money': 'k-money', 'paid': 'k-paid', 'email': 'k-email',
               'maintenance': 'k-maint'}


class TestEveryJobHasAFamily(SimpleTestCase):
    def test_the_two_registries_name_the_same_jobs(self):
        self.assertEqual(set(CronRunView.JOBS), set(cron_auth.JOB_FAMILY),
                         'a job in CronRunView.JOBS has no family in cron_auth._BY_FAMILY '
                         '(or a family names a job that no longer exists)')

    def test_no_job_is_in_two_families(self):
        listed = [j for jobs in cron_auth._BY_FAMILY.values() for j in jobs]
        self.assertEqual(len(listed), len(set(listed)))

    def test_money_jobs_are_not_in_the_email_family(self):
        for job in ('award-students-batch', 'auto-sponsor', 'issue-monthly-invoices',
                    'lapse-expired-offers', 'spending-ingest'):
            self.assertEqual(cron_auth.JOB_FAMILY[job], 'money', job)


class TestOpenedBy(SimpleTestCase):
    @override_settings(CRON_SECRET='shared', CRON_FAMILY_SECRETS=NO_FAMILY_KEYS)
    def test_before_the_owner_sets_anything_the_shared_key_opens_every_job(self):
        for job in CronRunView.JOBS:
            self.assertEqual(cron_auth.opened_by(job, 'shared'), 'shared', job)
        self.assertIsNone(cron_auth.opened_by('vision-outage', ''))
        self.assertIsNone(cron_auth.opened_by('vision-outage', 'wrong'))

    @override_settings(CRON_SECRET='shared', CRON_FAMILY_SECRETS=FAMILY_KEYS)
    def test_a_family_key_opens_its_family_only(self):
        self.assertEqual(cron_auth.opened_by('decision-emails', 'k-email'), 'email')
        self.assertIsNone(cron_auth.opened_by('auto-sponsor', 'k-email'))
        self.assertIsNone(cron_auth.opened_by('reextract-offers', 'k-money'))
        self.assertEqual(cron_auth.opened_by('auto-sponsor', 'k-money'), 'money')
        # The shared key still opens everything while it is set.
        self.assertEqual(cron_auth.opened_by('auto-sponsor', 'shared'), 'shared')

    @override_settings(CRON_SECRET='', CRON_FAMILY_SECRETS=FAMILY_KEYS)
    def test_after_the_shared_key_is_removed_only_the_family_key_opens(self):
        self.assertEqual(cron_auth.opened_by('auto-sponsor', 'k-money'), 'money')
        self.assertIsNone(cron_auth.opened_by('auto-sponsor', 'shared'))
        self.assertIsNone(cron_auth.opened_by('auto-sponsor', ''))

    @override_settings(CRON_SECRET='', CRON_FAMILY_SECRETS=NO_FAMILY_KEYS)
    def test_nothing_set_opens_nothing_even_an_empty_header(self):
        self.assertIsNone(cron_auth.opened_by('vision-outage', ''))

    @override_settings(CRON_SECRET='shared', CRON_FAMILY_SECRETS=FAMILY_KEYS)
    def test_an_unknown_job_opens_only_with_the_shared_key(self):
        # So the view still answers 404 (not 403) to the shared key for a mistyped job.
        self.assertEqual(cron_auth.opened_by('not-a-job', 'shared'), 'shared')
        self.assertIsNone(cron_auth.opened_by('not-a-job', 'k-money'))

    @override_settings(CRON_SECRET='shared', CRON_FAMILY_SECRETS=NO_FAMILY_KEYS)
    def test_a_non_ascii_header_is_refused_not_a_500(self):
        self.assertIsNone(cron_auth.opened_by('vision-outage', 'shäred'))

    @override_settings(CRON_SECRET='shared', CRON_FAMILY_SECRETS=NO_FAMILY_KEYS)
    def test_the_shared_key_use_is_logged_without_the_key(self):
        with self.assertLogs('apps.scholarship.cron_auth', level='INFO') as logs:
            self.assertTrue(cron_auth.allowed('vision-outage', 'shared'))
        self.assertIn('vision-outage', logs.output[0])
        self.assertNotIn('shared\'', logs.output[0])


@override_settings(ROOT_URLCONF='halatuju.urls', CRON_SECRET='',
                   CRON_FAMILY_SECRETS=FAMILY_KEYS)
class TestTheEndpointUsesTheFamilyKey(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post(self, job, key):
        with patch('apps.scholarship.cron_health.run_job', return_value={'job': job}) as run:
            resp = self.client.post(f'/api/v1/internal/cron/{job}/', HTTP_X_CRON_SECRET=key)
        return resp, run

    def test_the_family_key_runs_the_job(self):
        resp, run = self._post('decision-emails', 'k-email')
        self.assertEqual(resp.status_code, 200)
        run.assert_called_once()

    def test_another_familys_key_is_forbidden_and_runs_nothing(self):
        resp, run = self._post('issue-monthly-invoices', 'k-email')
        self.assertEqual(resp.status_code, 403)
        run.assert_not_called()
