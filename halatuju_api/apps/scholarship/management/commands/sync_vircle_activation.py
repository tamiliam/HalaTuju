"""Sync the Vircle relay sheet's manual 'Activated On' column into the database.

One-way sheet→DB mirror: for every relay-sheet row that carries an 'Activated On' date, stamp the
matching application's ``vircle_activated_at`` (set-if-null, joined on the eWallet ID). The owner's
sheet stays the source of truth; this only makes activation an auditable fact the payment surface
can read. ADVISORY — it never gates payment eligibility.

Also folded into the ``vircle_activation_request`` cron (one stamp per run), so this standalone
command is mainly for the first backfill / an on-demand refresh.

  python manage.py sync_vircle_activation            # stamp newly-activated accounts
  python manage.py sync_vircle_activation --dry-run  # report the sheet's activated set, write nothing

Cron job slug 'vircle-activation-sync' (optional — the 48h activation cron already syncs).
"""
from django.core.management.base import BaseCommand

from apps.scholarship import vircle


class Command(BaseCommand):
    help = "Mirror the relay sheet's 'Activated On' column into ScholarshipApplication.vircle_activated_at."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report the sheet-activated eWallet IDs; write nothing.')

    def handle(self, *args, **opts):
        rows = vircle.activated_rows()
        self.stdout.write(f'{len(rows)} account(s) marked activated in the relay sheet.')
        if opts['dry_run']:
            for r in rows:
                self.stdout.write(f"  {r['ewallet']} | activated {r['activated_raw']}")
            self.stdout.write(self.style.WARNING('[DRY RUN] nothing written.'))
            return
        stamped = vircle.sync_activation_status()
        self.stdout.write(self.style.SUCCESS(
            f'Stamped vircle_activated_at on {stamped} newly-activated application(s).'))
