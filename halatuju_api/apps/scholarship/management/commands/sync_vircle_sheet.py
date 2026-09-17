"""Rewrite the Vircle relay sheet (My Drive / 03 Vircle) from the database.

The sheet is a generated MIRROR, not a store: every run clears and rewrites it, so it can never
drift from the database, is safe to hand-edit (nothing reads it back), and can be deleted and
regenerated. It is the list handed to Vircle to switch accounts on, and the chase list for
students who haven't confirmed.

Read-only against our data — this command never writes to the database.

Runs on demand, at the end of ``send_vircle_install_emails``, and as a DAILY SAFETY NET (cron
job 'sync-vircle-sheet', 07:05 MYT — it was every 15 minutes until 2026-09-18).

⚠ The sheet no longer WAITS for this job to show a wallet or an activation: the inbound webhook
refreshes it the moment it stores one (``vircle_airtable._refresh_relay_sheet``). This job
exists for what the webhook cannot see — a student's own 'installed' confirmation, a status
change, a row the webhook refresh failed to write — so it must stay a REWRITE FROM THE
DATABASE and must never become conditional on anything the webhook knows.
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
