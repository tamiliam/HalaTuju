"""Daily 'results-due-reminders' (student maintenance S4b): "your next result is due by …".

Keeps the result terms up to date first (idempotent), then — only with `MAINTENANCE_REMINDERS_ENABLED`
on — emails each student whose open term is within the organisation's reminder lead, at most once
every `results_reminder_every_days`, never while a result of hers is waiting for review
(`results_expectations.send_due_reminders`; `reminded_at` is stamped only when the email went out).
"""
from django.core.management.base import BaseCommand

from apps.scholarship import results_expectations


class Command(BaseCommand):
    help = 'Remind each funded student whose semester result is due soon.'

    def handle(self, *args, **options):
        results_expectations.ensure_all()
        sent = results_expectations.send_due_reminders()
        self.stdout.write(f'results-due reminders sent: {sent}')
