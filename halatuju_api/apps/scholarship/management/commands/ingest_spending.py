"""Read Vircle "Bursary Usage Report" exports and store the transactions.

    python manage.py ingest_spending --file "…/2026-08-30 … .xlsx"      # one file, REPORT ONLY
    python manage.py ingest_spending --dir "…/Downloads/spending"       # every .xlsx in a folder
    python manage.py ingest_spending --dir "…" --apply                  # …and write them

⚠ **REPORT MODE IS THE DEFAULT AND IT CANNOT WRITE.** `--apply` is the only path to a database
write, and `spending_import.ingest` holds the single `bulk_create` behind that flag. Read the
report before applying it: a prediction in a plan is a claim, not a result.

⚠ **THE DRIVE FETCH REUSES `spending_import.ingest` UNCHANGED** by handing it rows from the Sheets
API instead of from openpyxl. Nothing about the drift rules or the wallet join lives here.

⚠ **AN `--apply` RUN FINISHES BY SORTING WHAT IT STORED** (`spend_category.sort_transactions`), so
the daily job remains ONE Cloud Scheduler entry. `--no-sort` opts out. The standalone
`sort_spending` command is the same ladder by hand, for re-sorting after a keyword rule is tuned.

⚠ **AN UNREADABLE HEADER REFUSES THAT FILE AND THE RUN CONTINUES.** One bad export must not stop
the other seven from loading, and the refusal has to reach a person rather than a log nobody reads
— so it lands in the report, which S2's alert email is built from.
"""
from __future__ import annotations

import glob
import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import emails, spend_category, spend_summary, spending_import

logger = logging.getLogger(__name__)


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
        parser.add_argument('--reread', action='store_true',
                            help='With --drive, read EVERY file in the folder rather than only '
                                 'the new or changed ones. For recovering rows a parser bug '
                                 'dropped from a file we have already marked as read. Safe '
                                 '(ingest dedups on txn_id) but expensive, so never the default.')
        parser.add_argument('--no-email', action='store_true',
                            help='Never send the alert, whatever is found. For a manual run.')
        parser.add_argument('--no-sort', action='store_true',
                            help='Do not sort the new rows into categories afterwards. Without '
                                 'this, an --apply run finishes by running the ladder.')
        parser.add_argument('--no-summary', action='store_true',
                            help='Do not file the written summary back to Drive. Without this, '
                                 'an --apply run that stored something files one.')

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
            sources, unreadable = spending_import.drive_sources(
                drive_folder, reread=options['reread'])
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
            # ⚠⚠ **ALSO TO THE LOG, AND THIS IS NOT DUPLICATION.** Under cron this command's
            # stdout is captured into the HTTP response body — which Cloud Scheduler reads and
            # throws away. So on the live service the report existed nowhere a person could
            # reach: when the owner asked on 2026-09-12 why five students had no spending, the
            # answer (unknown wallets? unparsed dates?) had already been discarded by every run
            # that could have said. The alert email only fires when something needs attention,
            # and a question is not always a fault. WARNING when a human is wanted so it shows
            # up in a severity filter; INFO otherwise so a quiet week costs nothing to read.
            level = logging.WARNING if report.needs_attention else logging.INFO
            logger.log(level, 'spending import (%s)\n%s', mode, '\n'.join(report.lines()))
            if report.needs_attention:
                self.stdout.write(self.style.WARNING('NEEDS ATTENTION - see the sections above.'))
            else:
                self.stdout.write(self.style.SUCCESS('Nothing needs a human.'))

            # ⚠ THE SORTER RUNS HERE SO THE DAILY JOB STAYS ONE SCHEDULER ENTRY. It is deliberately
            # gated on `--apply` AND on rows having actually landed: a report run must stay unable
            # to write, and a run that stored nothing has nothing new to place. `sort_spending` is
            # the same ladder, by hand, for when a keyword rule is tuned.
            if options['apply'] and not options['no_sort'] and report.rows_stored:
                sort_report = spend_category.sort_transactions(apply=True)
                self.stdout.write('--- sorting the new rows ---')
                for line in sort_report.lines():
                    self.stdout.write(line)

            # ⚠ THE SUMMARY IS THE LAST THING THE RUN DOES, AND THAT IS THE WHOLE CONTRACT.
            # Everything above it has already been stored and sorted, so a Drive hiccup here
            # costs a document and nothing else. It never raises; `file_summary` returns what
            # happened and the failure is PRINTED, because a summary that silently never
            # appears is indistinguishable from a week nobody opened the folder.
            # ⚠ Gated on `--apply` AND on rows having landed: a report run must stay unable to
            # write anything at all, including to Drive.
            if options['apply'] and not options['no_summary'] and report.rows_stored:
                filed = spend_summary.file_summary(report)
                if filed['filed']:
                    self.stdout.write(
                        f"summary filed        : {filed['filename']}"
                        f"{'' if filed['prose'] else ' (figures only - no prose)'}")
                else:
                    self.stdout.write(self.style.WARNING(
                        f"summary NOT filed    : {filed['error'] or 'unknown reason'}"))

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
