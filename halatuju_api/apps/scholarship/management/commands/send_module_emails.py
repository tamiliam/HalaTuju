"""Hourly 'module-emails' (student maintenance S10, 2026-11-02): each development module's two optional emails,
once per scholar — "a new module is ready" once it is live, and "you have not finished it" 3 days before its due
date, to those not done.

`development_emails.send_due_module_emails`: only while the organisation's `module_published` switch is on, one
`ModuleEmail` row claimed per scholar per kind BEFORE the send (a second run, or the Progress page's "Remind
those not done", sends nothing twice), metered and logged like every student email. A module archived or taken
back to draft stops at once.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import development_emails


class Command(BaseCommand):
    help = 'Email the module announcements and reminders staff asked for, once per scholar.'

    def handle(self, *args, **options):
        sent = development_emails.send_due_module_emails()
        self.stdout.write(f'module emails sent: {sent}')
