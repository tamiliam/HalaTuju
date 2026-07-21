"""Vircle activation request (48h): email Vircle the accounts installed but not yet activated.

Reads the Vircle relay sheet, filters rows with an eWallet ID present AND the owner's MANUAL
'Activated On' column blank (installed but not activated), and — if any — emails Vircle the list
with a CSV attached, Bcc's the reference mailbox, and files a copy of the CSV to the Drive
activation folder for the record (owner's A+B: a Bcc copy AND a Drive archive).

READ-ONLY against our database. Gated by VIRCLE_ACTIVATION_ENABLED (default OFF).
  python manage.py vircle_activation_request --dry-run   # read + print, send/write nothing
  python manage.py vircle_activation_request              # send (only when the flag is on)
Cron job slug 'vircle-activation-request' (Cloud Scheduler, every 48h).
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scholarship import sheets, vircle
from apps.scholarship.emails import send_vircle_activation_email


class Command(BaseCommand):
    help = 'Email Vircle the accounts installed but not yet activated (48h reminder).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Read + print the pending set; send nothing, write nothing.')

    def handle(self, *args, **opts):
        rows = vircle.pending_activation_rows()
        if not rows:
            self.stdout.write('0 accounts awaiting activation — nothing sent.')
            return
        self.stdout.write(f'{len(rows)} account(s) awaiting activation:')
        for r in rows:
            self.stdout.write(f"  {r['name']} | {r['nric']} | {r['ewallet']} | "
                              f"{r['phone']} | installed {r['installed_on']}")
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY RUN] no email sent, no file written.'))
            return
        if not getattr(settings, 'VIRCLE_ACTIVATION_ENABLED', False):
            self.stdout.write(self.style.WARNING(
                'VIRCLE_ACTIVATION_ENABLED is off — not sending. Set it to 1 to enable, or use '
                '--dry-run to preview.'))
            return
        csv_text = vircle.activation_csv_text(rows)
        sent = send_vircle_activation_email(rows, csv_text)
        today = timezone.localdate()
        folder = getattr(settings, 'VIRCLE_ACTIVATION_FOLDER',
                         '01 BrightPath/03 Vircle/03 Activation')
        url = sheets.file_csv_to_folder(
            folder, f'vircle-activation-{today:%Y-%m-%d}.csv', csv_text)
        self.stdout.write(self.style.SUCCESS(
            f'Activation request: email {"sent" if sent else "FAILED"}; '
            + (f'archive filed: {url}' if url
               else 'archive NOT filed (folder missing or Drive unreachable).')))
