"""Read Vircle "Bursary Usage Report" exports and store the transactions.

    python manage.py ingest_spending --file "…/2026-08-30 … .xlsx"      # one file, REPORT ONLY
    python manage.py ingest_spending --dir "…/Downloads/spending"       # every .xlsx in a folder
    python manage.py ingest_spending --dir "…" --apply                  # …and write them

⚠ **REPORT MODE IS THE DEFAULT AND IT CANNOT WRITE.** `--apply` is the only path to a database
write, and `spending_import.ingest` holds the single `bulk_create` behind that flag. Read the
report before applying it: a prediction in a plan is a claim, not a result.

⚠ **THIS SPRINT READS LOCAL FILES ONLY.** S2 adds the Drive fetch, which reuses
`spending_import.ingest` unchanged by handing it rows from the Sheets API instead. Nothing about
the drift rules or the wallet join lives here.

⚠ **AN UNREADABLE HEADER REFUSES THAT FILE AND THE RUN CONTINUES.** One bad export must not stop
the other seven from loading, and the refusal has to reach a person rather than a log nobody reads
— so it lands in the report, which S2's alert email is built from.
"""
from __future__ import annotations

import glob
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import emails, spending_import


class Command(BaseCommand):
    help = 'Import Vircle bursary spending reports (report-only unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--file', action='append', default=[],
                            help='A single .xlsx export. Repeatable.')
        parser.add_argument('--dir', default='',
                            help='A folder; every .xlsx in it is read, oldest name first.')
        parser.add_argument('--drive', action='store_true',
                            help='Read new/changed exports from VIRCLE_SPENDING_FOLDER in Drive. '
                                 'The cron mode; needs the service account, so it only works on '
                                 'the live service.')
        parser.add_argument('--apply', action='store_true',
                            help='Write the new transactions. Without it, nothing is stored.')
        parser.add_argument('--no-email', action='store_true',
                            help='Never send the alert, whatever is found. For a manual run.')

    def handle(self, *args, **options):
        use_drive = options['drive']
        paths = list(options['file'])
        folder = options['dir']
        if folder:
            if not os.path.isdir(folder):
                raise CommandError(f'--dir is not a folder: {folder}')
            # ⚠ Skip Excel's `~$…` lock files: they are not spreadsheets, and openpyxl refuses
            # them with a permission error that reads like a corrupt export.
            paths += sorted(p for p in glob.glob(os.path.join(folder, '*.xlsx'))
                            if not os.path.basename(p).startswith('~$'))
        if not paths and not use_drive:
            raise CommandError('nothing to read - pass --file, --dir or --drive')

        sources, unreadable = [], []
        if use_drive:
            drive_folder = getattr(settings, 'VIRCLE_SPENDING_FOLDER', '')
            sources, unreadable = spending_import.drive_sources(drive_folder)
        for path in paths:
            name = os.path.basename(path)
            try:
                rows, unknown = spending_import.rows_from_xlsx(path)
            except spending_import.UnreadableReport as exc:
                unreadable.append((name, str(exc)))
                continue
            sources.append((name, rows, unknown))

        # ⚠ A DRIVE RUN WITH NOTHING NEW DOES NOTHING AT ALL — no ingest, no log noise, no email.
        # The officer uploads by hand and not on a fixed day (owner, 2026-09-10), so most days
        # there is genuinely nothing to do and the job must be silent about it. The ONLY thing
        # that speaks on a quiet day is the staleness nudge below.
        quiet_run = use_drive and not sources and not unreadable
        if quiet_run:
            report = None
            self.stdout.write('--- ingest_spending (drive) --- nothing new to read.')
        else:
            report = spending_import.ingest(sources, apply=options['apply'])
            report.unreadable_files.extend(unreadable)
            mode = 'APPLIED' if options['apply'] else 'REPORT ONLY - nothing was written'
            self.stdout.write(f'--- ingest_spending ({mode}) ---')
            for line in report.lines():
                self.stdout.write(line)
            if report.needs_attention:
                self.stdout.write(self.style.WARNING('NEEDS ATTENTION - see the sections above.'))
            else:
                self.stdout.write(self.style.SUCCESS('Nothing needs a human.'))

        # The staleness nudge. Derived from the newest import, never stored — see
        # `spending_import.days_since_last_report`.
        quiet_days = getattr(settings, 'SPENDING_REPORT_QUIET_DAYS', 14)
        silent_for = spending_import.days_since_last_report()
        nudge = (use_drive and not sources
                 and spending_import.should_nudge(silent_for, quiet_days))
        if nudge:
            self.stdout.write(self.style.WARNING(
                f'No spending report has arrived for {silent_for} days.'))

        if options['no_email']:
            return
        # ⚠ ONE EMAIL PER RUN AT MOST, and only when a human is needed. Never an all-clear.
        if report is not None and report.needs_attention:
            emails.send_spending_alert_email(report.lines(), subject_hint='import findings')
        elif nudge:
            emails.send_spending_alert_email(
                [f'No spending report has arrived for {silent_for} days.',
                 'The weekly export is uploaded by hand, so this may simply have been missed.',
                 'Nothing is broken; there is just nothing new to read.'],
                subject_hint='no report for a while')
