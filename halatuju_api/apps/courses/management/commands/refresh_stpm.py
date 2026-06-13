"""
One-command STPM/UPU catalogue refresh — orchestrates the manual ritual safely.

Runs the steps in order with a single end-of-run summary, and stops loudly if a
safety guard trips (scrape shortfall, or the sync mass-deactivation guard):

    scrape_mohe_stpm  (sanity-checked)  ->  [validate_stpm_urls]  ->  sync_stpm_mohe  ->  audit_data

This is a LOCAL operator tool — the scrape needs Playwright + Chromium on your
machine, so it can't run on Cloud Run. Sync defaults to **dry-run**; pass --apply
(guarded) only after reviewing the report. Each run archives the scraped CSV as
`data/stpm/archive/mohe_<date>.csv` and prunes to the newest --keep, so you can
diff or roll back a bad refresh.

Usage:
    python manage.py refresh_stpm                 # scrape -> sync (dry-run) -> audit
    python manage.py refresh_stpm --validate-urls # also run the (slow) link check
    python manage.py refresh_stpm --apply         # apply the sync (still guarded)
    python manage.py refresh_stpm --csv path.csv  # skip scrape, use an existing CSV
"""
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

ARCHIVE_DIR = os.path.join('data', 'stpm', 'archive')
DEFAULT_KEEP = 12


def dated_archive_name(now):
    """Archive CSV filename for a run at `now` (date-stamped; ISO so it name-sorts
    chronologically). Same-day re-runs overwrite that day's file."""
    return 'mohe_%s.csv' % now.strftime('%Y-%m-%d')


def prune_archive(dir_path, keep):
    """Keep the newest `keep` mohe_*.csv files in dir_path, delete the rest.
    Names are ISO-dated so a plain sort is chronological. Returns deleted basenames."""
    import glob
    if keep <= 0:
        return []
    files = sorted(glob.glob(os.path.join(dir_path, 'mohe_*.csv')))
    stale = files[:-keep] if len(files) > keep else []
    for f in stale:
        os.remove(f)
    return [os.path.basename(f) for f in stale]


class Command(BaseCommand):
    help = 'Run the STPM/UPU catalogue refresh end-to-end (scrape -> sync -> audit) with a summary.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Apply the sync (default: dry-run). Still subject to the mass-deactivation guard.')
        parser.add_argument('--validate-urls', action='store_true',
                            help='Also run the (slow, Selenium) MOHE link check.')
        parser.add_argument('--csv', type=str, default='',
                            help='Use an existing scraped CSV instead of scraping (skips scrape + archive).')
        parser.add_argument('--keep', type=int, default=DEFAULT_KEEP,
                            help='How many dated CSVs to keep in the archive (default %d).' % DEFAULT_KEEP)

    def handle(self, *args, **options):
        apply = options['apply']
        do_validate = options['validate_urls']
        csv_path = options['csv'].strip()
        keep = options['keep']
        summary = []

        # 1. Scrape (sanity-checked inside the command) — unless a CSV was supplied.
        if csv_path:
            summary.append(('scrape', 'SKIP', 'using %s' % csv_path))
        else:
            os.makedirs(ARCHIVE_DIR, exist_ok=True)
            csv_path = os.path.join(ARCHIVE_DIR, dated_archive_name(timezone.now()))
            try:
                call_command('scrape_mohe_stpm', output=csv_path)
            except CommandError as e:
                summary.append(('scrape', 'FAILED', str(e)))
                self._summary(summary)
                raise CommandError('Refresh aborted at scrape (see summary). Nothing was synced.')
            summary.append(('scrape', 'OK', '-> %s' % csv_path))
            pruned = prune_archive(ARCHIVE_DIR, keep)
            if pruned:
                summary.append(('archive', 'OK', 'pruned %d old (keep %d)' % (len(pruned), keep)))

        # 2. Link validation (optional, slow) — a WARN here never blocks the sync.
        if do_validate:
            try:
                call_command('validate_stpm_urls')
                summary.append(('validate-urls', 'OK', ''))
            except Exception as e:  # noqa: BLE001 — link-check problems must not abort the refresh
                summary.append(('validate-urls', 'WARN', str(e)))

        # 3. Sync — dry-run by default; --apply is guarded by sync_stpm_mohe itself.
        sync_kwargs = {'csv': csv_path}
        if apply:
            sync_kwargs['apply'] = True
        try:
            call_command('sync_stpm_mohe', **sync_kwargs)
        except CommandError as e:
            summary.append(('sync', 'BLOCKED', str(e)))
            self._summary(summary)
            raise CommandError('Refresh stopped at sync — the safety guard blocked it (see summary).')
        summary.append(('sync', 'APPLIED' if apply else 'DRY-RUN', ''))

        # 4. Audit — completeness report.
        call_command('audit_data')
        summary.append(('audit', 'OK', ''))

        # Record the STPM refresh for the Course Data dashboard (freshness).
        # Best-effort: telemetry must never break the refresh (or its no-DB orchestration tests).
        try:
            from apps.courses.course_data_status import record_status, EPANDUAN_STPM
            from apps.courses.models import StpmCourse
            record_status(EPANDUAN_STPM,
                          {'mode': 'apply' if apply else 'dry-run',
                           'stpm_total': StpmCourse.objects.count(),
                           'stpm_active': StpmCourse.objects.filter(is_active=True).count()},
                          detail='python manage.py refresh_stpm' + (' --apply' if apply else ''))
        except Exception:
            pass

        self._summary(summary)
        if not apply:
            self.stdout.write(self.style.NOTICE(
                'Dry run. Review the sync report above, then re-run with --apply to commit.'))

    def _summary(self, rows):
        self.stdout.write('\n=== refresh_stpm summary ===')
        for step, status, note in rows:
            line = '  %-14s %-8s %s' % (step, status, note)
            style = (self.style.SUCCESS if status in ('OK', 'DRY-RUN', 'APPLIED', 'SKIP')
                     else self.style.WARNING if status == 'WARN'
                     else self.style.ERROR)
            self.stdout.write(style(line))
