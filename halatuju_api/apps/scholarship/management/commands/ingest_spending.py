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

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import spending_import


class Command(BaseCommand):
    help = 'Import Vircle bursary spending reports (report-only unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--file', action='append', default=[],
                            help='A single .xlsx export. Repeatable.')
        parser.add_argument('--dir', default='',
                            help='A folder; every .xlsx in it is read, oldest name first.')
        parser.add_argument('--apply', action='store_true',
                            help='Write the new transactions. Without it, nothing is stored.')

    def handle(self, *args, **options):
        paths = list(options['file'])
        folder = options['dir']
        if folder:
            if not os.path.isdir(folder):
                raise CommandError(f'--dir is not a folder: {folder}')
            # ⚠ Skip Excel's `~$…` lock files: they are not spreadsheets, and openpyxl refuses
            # them with a permission error that reads like a corrupt export.
            paths += sorted(p for p in glob.glob(os.path.join(folder, '*.xlsx'))
                            if not os.path.basename(p).startswith('~$'))
        if not paths:
            raise CommandError('nothing to read - pass --file or --dir')

        sources, unreadable = [], []
        for path in paths:
            name = os.path.basename(path)
            try:
                rows, unknown = spending_import.rows_from_xlsx(path)
            except spending_import.UnreadableReport as exc:
                unreadable.append((name, str(exc)))
                continue
            sources.append((name, rows, unknown))

        report = spending_import.ingest(sources, apply=options['apply'])
        report.unreadable_files.extend(unreadable)

        mode = 'APPLIED' if options['apply'] else 'REPORT ONLY - nothing was written'
        self.stdout.write(f'--- ingest_spending ({mode}) ---')
        for line in report.lines():
            self.stdout.write(line)
        if report.needs_attention:
            self.stdout.write(self.style.WARNING(
                'NEEDS ATTENTION - see the sections above.'))
        else:
            self.stdout.write(self.style.SUCCESS('Nothing needs a human.'))
