"""Rewrite the Vircle relay sheet (My Drive / 03 Vircle) from the database.

The sheet is a generated MIRROR, not a store: every run clears and rewrites it, so it can never
drift from the database, is safe to hand-edit (nothing reads it back), and can be deleted and
regenerated. It is the list handed to Vircle to switch accounts on, and the chase list for
students who haven't confirmed.

Read-only against our data — this command never writes to the database.

Runs on demand, at the end of ``send_vircle_install_emails``, or on a schedule (cron job
'sync-vircle-sheet') to pick up confirmations as students make them.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.vircle import awarded_applications, relay_rows, sync_relay_sheet


class Command(BaseCommand):
    help = 'Rewrite the Vircle relay sheet in Google Drive from the database.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Print the rows; write nothing to Drive.')

    def handle(self, *args, **options):
        apps = list(awarded_applications())
        rows = relay_rows(apps)
        if options['dry_run']:
            self.stdout.write(f'[DRY RUN] {len(rows)} row(s):')
            for r in rows:
                self.stdout.write('  ' + ' | '.join(str(c) for c in r))
            return
        url = sync_relay_sheet(apps)
        if url:
            self.stdout.write(self.style.SUCCESS(f'Relay sheet updated ({len(rows)} rows): {url}'))
        else:
            self.stdout.write(self.style.WARNING(
                'Relay sheet NOT written — Drive unreachable or unconfigured. The database is '
                'still the record; check GOOGLE_MEET_SA_JSON, the drive+spreadsheets scopes on '
                'the service account, and that the folder exists.'))
