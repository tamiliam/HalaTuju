"""Label the predictions that were banked before the predictor had a version.

⚠ WHAT THIS DOES *NOT* DO: it does not re-run `build_verdict`. A snapshot is the historical record
of what the AI asserted at the time the officer decided; re-running it would overwrite that with
today's answer and destroy the only evidence the AI Reliability scorecard rests on. This command
writes ONE new column and reads nothing else.

Every decided application whose `ai_verdict_engine_version` is empty gets `PRE_VERSIONING`
('pre-versioning') — deliberately not a version number, so it can never be misread as an engine
generation. 88 such rows existed on 2026-09-11, decided between 2026-06-17 and 2026-09-01.

⚠ DRY RUN IS THE DEFAULT, on both routes. Pass `--apply` by hand, or set
`BACKFILL_VERDICT_VERSION_APPLY=1` for the cron door — which cannot pass a flag. ⚠ NEVER run this
from a local checkout: the database is reachable only from the running service (TD-206 retired
exporting DB_* onto a laptop). Its door is `CronRunView.JOBS['backfill-verdict-engine-version']`.

⚠ **THE 88 ROWS WERE ALREADY STAMPED on 2026-09-11**, via Supabase MCP rather than this command,
because the door as first registered could only dry-run — the gap this env var closes. The command
is idempotent and now reads 0, which is the correct steady state. It stays because the door test
is right that a repair must be reachable, and because the same gap can reopen: a future engine
change does NOT need this command (new decisions stamp themselves), but a future column might.
"""
import os

from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.verdict_engine import PRE_VERSIONING


class Command(BaseCommand):
    help = "Stamp 'pre-versioning' on decided verdicts that predate the engine-version column."

    #: ⚠ THE DOOR CANNOT PASS A FLAG, SO THE WRITE SWITCH IS AN ENV VAR — and that is the shape
    #: this project prescribes for a DANGEROUS ONE-OFF: *"a door you can close"* (see the comment
    #: on `CronRunView.JOBS`). Registering the job as `(command, ['--apply'])` would have made
    #: every call to the door write, which is the wrong default for a repair that runs once.
    #: Set `BACKFILL_VERDICT_VERSION_APPLY=1` on the service, POST the job, then UNSET it.
    APPLY_ENV = 'BACKFILL_VERDICT_VERSION_APPLY'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write. Without this the command only reports.')

    def handle(self, *args, **options):
        # Decided rows only: an undecided application has no snapshot to attribute, and must keep
        # its empty version so a future decision stamps the REAL engine.
        qs = (ScholarshipApplication.objects
              .filter(verdict_decided_at__isnull=False)
              .exclude(ai_verdict_engine_version=PRE_VERSIONING)
              .filter(ai_verdict_engine_version=''))
        total = qs.count()
        self.stdout.write(f'decided rows with no engine version: {total}')
        if total:
            sample = list(qs.order_by('id').values_list('id', flat=True)[:10])
            self.stdout.write(f'  first ids: {sample}')
        apply = options['apply'] or os.environ.get(self.APPLY_ENV, '') == '1'
        if not apply:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing written. Pass --apply to write.'))
            return
        updated = qs.update(ai_verdict_engine_version=PRE_VERSIONING)
        self.stdout.write(self.style.SUCCESS(f'stamped {updated} row(s) as {PRE_VERSIONING!r}'))
        # ⚠ VERIFY BY ABSENCE, not by counting what we wrote: the question is whether any decided
        # row is STILL unlabelled, which is the only thing that would leave the roll-up blending.
        left = (ScholarshipApplication.objects
                .filter(verdict_decided_at__isnull=False, ai_verdict_engine_version='').count())
        if left:
            self.stdout.write(self.style.ERROR(f'{left} decided row(s) STILL have no version'))
        else:
            self.stdout.write(self.style.SUCCESS('no decided row is left unlabelled'))
