"""Run ONE whitelisted cron job the way `CronRunView` does, but from a Cloud Run JOB.

Why it exists (2026-11-12): the weekly `backup-documents` run had outgrown the web request. Every
Monday since at least 18 Oct it was cut off at the service's 300 s request timeout (504), so it never
finished, never recorded a success, and the System health light read "has not run". About 1,100
documents had no off-platform copy. A Cloud Run job has no request timeout (its task timeout is set
on the execution, up to hours), so the Scheduler now fires the `release-decisions` job with
`--args=manage.py,run_cron_job,backup-documents` instead of POSTing the endpoint.

The job name is looked up in `CronRunView.JOBS`, the same registry the endpoint uses, so flags still
come from the registry and never from the caller, and the run goes through `cron_health.run_job`,
so the light records it exactly as it records an endpoint run. Nothing else changes for the jobs that
stay on the endpoint.

A failed run exits non-zero (after recording it), so the execution shows as failed in Cloud Run.
⚠ The `release-decisions` job has `maxRetries: 1`, so a failure is retried once. That is safe for an
idempotent job such as `backup-documents` (it skips what is already copied); think before pointing a
job that sends anything at this command.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run one whitelisted cron job (CronRunView.JOBS) and record it for the System health light."

    def add_arguments(self, parser):
        parser.add_argument('job', help="A key of CronRunView.JOBS, e.g. backup-documents.")

    def handle(self, *args, **options):
        from apps.scholarship import cron_health
        from apps.scholarship.views.cron import CronRunView

        job = options['job']
        command = CronRunView.JOBS.get(job)
        if not command:
            raise CommandError(f'Unknown cron job: {job}')
        cmd_args = []
        if isinstance(command, tuple):
            command, cmd_args = command[0], list(command[1])

        body = cron_health.run_job(job, command, cmd_args)
        if 'error' in body:
            raise CommandError(f'Cron job {job} failed: {body["error"]}')
        self.stdout.write(body.get('output', ''))
