"""Weekly partner-organisation emails: the stage summary + the chase list (2026-07-26).

Cron slug `partner-digests` (Mondays 08:00 Asia/KL). A thin wrapper — every decision lives in
`partner_comms`, every send in `partner_notify`.

`--dry-run` prints the recipient, subject and full plain-text body for each organisation and sends
nothing, so the wording can be read before a real run.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import partner_notify


class Command(BaseCommand):
    help = 'Send the weekly partner summary + chase list to every qualifying organisation.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be sent (recipient, subject, body) and send nothing.',
        )

    def handle(self, *args, **options):
        summary = partner_notify.send_partner_digests(
            dry_run=options['dry_run'], out=self.stdout)
        for kind, row in summary.items():
            if row.get('off'):
                continue
            self.stdout.write(f'{kind}: sent={row["sent"]} skipped={row["skipped"]}')
