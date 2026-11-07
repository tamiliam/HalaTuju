"""
A2.1 / TD-517 — write the final sponsor profiles that record-verdict queued.

Record-verdict no longer calls Gemini inside the request: it marks the profile 'pending', and this
command (the `finalise-profiles` cron, every 15 minutes) runs the refine and the card blurb, with
retry. Billable Gemini calls, at most `profile_finalise.BATCH` a run; skipped while Gemini reads are
down. See `apps/scholarship/profile_finalise.py`.

    python manage.py run_pending_finalise
"""
from django.core.management.base import BaseCommand

from apps.scholarship import profile_finalise


class Command(BaseCommand):
    help = "Write the final sponsor profiles queued by record-verdict (A2.1; billable Gemini)."

    def handle(self, *args, **options):
        counts = profile_finalise.run_pending()
        if counts.pop('skipped_outage'):
            self.stdout.write(self.style.WARNING('Gemini reads are down: nothing finalised this run.'))
        self.stdout.write(self.style.SUCCESS(
            'Finalised: ' + ', '.join(f'{k}={v}' for k, v in counts.items())))
