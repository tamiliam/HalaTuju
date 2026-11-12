"""`run_cron_job` (2026-11-12): a whitelisted cron job run from a Cloud Run JOB is recorded for the
System health light exactly like an endpoint run, and only registry jobs can run.

Why: the weekly `backup-documents` outgrew the web request (504 at 300 s every Monday), so the
Scheduler now fires the `release-decisions` job with this command. Without the recording the light
would stay red even when the backup succeeds."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.scholarship import cron_health
from apps.scholarship import system_health_store as store
from apps.scholarship.models import SystemHealthStatus
from apps.scholarship.views.cron import CronRunView


def _data(key):
    row = SystemHealthStatus.objects.filter(key=key).first()
    return row.data if row else None


class RunCronJob(TestCase):
    def setUp(self):
        store._since_seen = False

    def test_a_good_run_calls_the_registry_command_and_is_recorded_ok(self):
        out = StringIO()
        with patch.object(cron_health, 'call_command') as cc:
            with self.captureOnCommitCallbacks(execute=True):
                call_command('run_cron_job', 'backup-documents', stdout=out)
        self.assertEqual(cc.call_args.args[0], CronRunView.JOBS['backup-documents'])
        data = _data('cron:backup-documents')
        self.assertIn('last_ok_at', data)
        self.assertEqual(data['consecutive_errors'], 0)

    def test_registry_flags_are_passed_and_never_taken_from_the_caller(self):
        command, flags = CronRunView.JOBS['supplier-bills-report']
        with patch.object(cron_health, 'call_command') as cc:
            with self.captureOnCommitCallbacks(execute=True):
                call_command('run_cron_job', 'supplier-bills-report', stdout=StringIO())
        self.assertEqual(cc.call_args.args, (command, *flags))

    def test_a_failed_run_is_recorded_and_exits_non_zero(self):
        with patch.object(cron_health, 'call_command', side_effect=RuntimeError('boom')):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(CommandError):
                    call_command('run_cron_job', 'backup-documents', stdout=StringIO())
        data = _data('cron:backup-documents')
        self.assertEqual((data['consecutive_errors'], data['last_error']), (1, 'RuntimeError'))
        self.assertNotIn('last_ok_at', data)

    def test_an_unknown_job_is_refused_and_records_nothing(self):
        with patch.object(cron_health, 'call_command') as cc:
            with self.assertRaises(CommandError):
                call_command('run_cron_job', 'not-a-job', stdout=StringIO())
        cc.assert_not_called()
        self.assertIsNone(_data('cron:not-a-job'))

    def test_the_backup_job_stays_watched_weekly(self):
        # The Scheduler entry moved from the endpoint to the job; the light must still expect it.
        self.assertEqual(cron_health.EXPECTED_CADENCE['backup-documents'], cron_health.WEEKLY)
