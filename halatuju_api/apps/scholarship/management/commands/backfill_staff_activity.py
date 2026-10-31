"""Rebuild every staff member's activity list from the records that already exist (common profile S4).

    python manage.py backfill_staff_activity --dry-run      # counts only, writes nothing
    python manage.py backfill_staff_activity --apply        # writes the rows (backfilled=True)
    python manage.py backfill_staff_activity --apply --before 2026-11-01T00:00:00+08:00

RUN IT AFTER THE API DEPLOY (migrate, then API, then this): it rebuilds only what happened BEFORE the
earliest live row, so an event that already has its live row never gets a rebuilt twin. Idempotent:
a second `--apply` writes nothing. The rules, the sources and the key are in
`apps/scholarship/staff_activity_backfill.py`.
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.scholarship import staff_activity_backfill as backfill


class Command(BaseCommand):
    help = 'Rebuild the staff activity list from existing records (dry run unless --apply).'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--dry-run', action='store_true', help='Count only; write nothing.')
        mode.add_argument('--apply', action='store_true', help='Write the rebuilt rows.')
        parser.add_argument('--before', help='Rebuild only events before this ISO moment '
                                             '(may only move the cut-off EARLIER).')

    def handle(self, *args, **opts):
        before = None
        if opts.get('before'):
            try:
                before = datetime.fromisoformat(opts['before'])
            except ValueError:
                raise CommandError('--before must be an ISO date-time')
            if timezone.is_naive(before):
                before = timezone.make_aware(before)
        report = backfill.run(apply=bool(opts['apply']), before=before)
        out = self.stdout.write
        out(f"Cut-off: {report['cutoff'].isoformat()} "
            f"({'the earliest live row' if report['live_rows_found'] else 'no live rows yet'}"
            f"{', or --before' if before else ''})")
        out('Rebuilt' if report['applied'] else 'Would rebuild (dry run — nothing written)')
        for verb, n in sorted(report['written'].items()):
            out(f'  {verb:30} {n}')
        out(f"  {'TOTAL':30} {sum(report['written'].values())}")
        out('Skipped')
        for (verb, reason), n in sorted(report['skipped'].items()):
            out(f'  {verb:30} {n:6}  {reason}')
        out(f"  {'TOTAL':30} {sum(report['skipped'].values()):6}")
