"""
A2.1 / TD-517 — write the final sponsor profiles that record-verdict queued.

Record-verdict no longer calls Gemini inside the request: it marks the profile 'pending', and this
command (the `finalise-profiles` cron, every 5 minutes) runs the refine and the card blurb, with
retry. Billable Gemini calls, at most `profile_finalise.BATCH` a run; skipped while Gemini reads are
down. See `apps/scholarship/profile_finalise.py`.

A2.3b / TD-586: the same run then writes the first-assign profile drafts the assign queued
(`assign_draft.draft_pending`, at most `assign_draft.BATCH`), inside the same 300 s.

    python manage.py run_pending_finalise
"""
import time

from django.core.management.base import BaseCommand

from apps.scholarship import assign_draft, profile_finalise


class Command(BaseCommand):
    help = "Write the final profiles record-verdict queued and the first-assign drafts (billable Gemini)."

    def handle(self, *args, **options):
        started = time.monotonic()
        counts = profile_finalise.run_pending()
        if counts.pop('skipped_outage'):
            self.stdout.write(self.style.WARNING('Gemini reads are down: nothing finalised this run.'))
        self.stdout.write(self.style.SUCCESS(
            'Finalised: ' + ', '.join(f'{k}={v}' for k, v in counts.items())))
        drafts = assign_draft.draft_pending(started)
        if drafts.pop('skipped_outage'):
            self.stdout.write(self.style.WARNING('Gemini reads are down: no draft written this run.'))
        self.stdout.write(self.style.SUCCESS(
            'Drafted: ' + ', '.join(f'{k}={v}' for k, v in drafts.items())))
