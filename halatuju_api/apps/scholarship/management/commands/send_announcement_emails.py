"""Hourly 'announcement-emails' (student maintenance S8, 2026-11-01): email each published announcement
staff asked to email, once per scholar of its audience.

Flips scheduled announcements whose time has passed to published first (idempotent; what scholars SEE
never waits for this job), then sends (`announcements.send_due_emails`): only while the organisation's
`announcement` switch is on, one `AnnouncementEmail` row claimed per scholar BEFORE the send (a second run
sends nothing twice), metered and logged like every student email. A withdrawn one stops at once.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import announcements


class Command(BaseCommand):
    help = 'Email the published announcements staff asked to email, once per scholar.'

    def handle(self, *args, **options):
        sent = announcements.send_due_emails()
        self.stdout.write(f'announcement emails sent: {sent}')
