"""Daily SLA nudge for a stalled bursary signing chain.

For every binding-but-not-yet-executed agreement, re-nudges the party whose signature is
still pending (the partner witness first if a referring org with a contact email exists,
else the Foundation to countersign), no more often than ``BURSARY_SIGN_REMINDER_DAYS``.

No-op when ``BURSARY_AGREEMENT_ENABLED`` is off. Best-effort emails (a send failure is
swallowed and the agreement is retried next run). Run via the cron job
'bursary-signing-reminders' or directly:

    python manage.py send_bursary_signing_reminders
"""
from django.core.management.base import BaseCommand

from apps.scholarship import bursary


class Command(BaseCommand):
    help = 'Nudge any pending witness/countersignature on stalled bursary agreements (SLA).'

    def handle(self, *args, **options):
        summary = bursary.send_signing_reminders()
        self.stdout.write(
            f"Bursary signing reminders. witness={summary['witness']} "
            f"countersign={summary['countersign']}")
