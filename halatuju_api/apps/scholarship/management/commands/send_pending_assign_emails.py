"""
A2.3 / TD-519 — send the assignment emails that assign queued.

Assigning a reviewer no longer sends the reviewer's and the student's emails inside the request: it
writes the AssignmentEvent 'pending', and this command (the `assign-emails` cron, every 15 minutes)
sends both, with the same gates and content. See `apps/scholarship/assign_notify.py`.

    python manage.py send_pending_assign_emails
"""
from django.core.management.base import BaseCommand

from apps.scholarship import assign_notify


class Command(BaseCommand):
    help = "Send the reviewer + student emails for queued assignments (A2.3)."

    def handle(self, *args, **options):
        counts = assign_notify.send_pending()
        self.stdout.write(self.style.SUCCESS(
            'Assignment emails: ' + ', '.join(f'{k}={v}' for k, v in counts.items())))
