"""
A2.3 / TD-519 — read the uploads nobody asked to read.

The upload no longer runs the paid read (Vision OCR, Gemini extraction) inside the request: it
records the document queued, and the web asks for the read at once (``documents/<id>/read/``). This
command (the `read-documents` cron, every 15 minutes) reads any it never asked for — a dropped phone,
a closed tab. Billable Vision/Gemini calls, at most `upload_read.BATCH` a run. See
`apps/scholarship/upload_read.py`.

    python manage.py run_pending_reads
"""
from django.core.management.base import BaseCommand

from apps.scholarship import upload_read


class Command(BaseCommand):
    help = "Read the uploads still queued for their read (A2.3; billable Vision/Gemini)."

    def handle(self, *args, **options):
        counts = upload_read.run_pending()
        self.stdout.write(self.style.SUCCESS(
            'Read: ' + ', '.join(f'{k}={v}' for k, v in counts.items())))
