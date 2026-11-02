"""Hourly 'survey-emails' (student maintenance S9, 2026-11-02): each survey's two optional emails, once per
scholar — "it is open" once it opens, and "you have not answered" 3 days before it closes, to those who have
not answered.

`survey_emails.send_due_emails`: only while the organisation's `survey_open` switch is on, one `SurveyEmail` row
claimed per scholar per kind BEFORE the send (a second run, or the Results page's "Remind" button, sends
nothing twice), metered and logged like every student email. A survey closed or taken back to draft stops at
once.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import survey_emails


class Command(BaseCommand):
    help = 'Email the survey openings and reminders staff asked for, once per scholar.'

    def handle(self, *args, **options):
        sent = survey_emails.send_due_emails()
        self.stdout.write(f'survey emails sent: {sent}')
