"""
Alert the admin by email if Google Vision OCR appears to be down — i.e. every
IC / parent-IC OCR attempt in the recent window errored and none succeeded (a run
of blurry images alone does NOT trip it; only genuine service errors do).

The check is read-only and makes NO Vision API calls (it reads the cached OCR
outcome stored on each document at upload), so running it costs nothing.

Schedule this DAILY (e.g. Cloud Scheduler → Cloud Run Job) once deployed; it will
email settings.ADMIN_NOTIFY_EMAIL (contact@halatuju.xyz) once a day while an outage
persists. Pairs with the pending decision-emails scheduler.

    python manage.py alert_vision_outage [--window-hours 24] [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.scholarship.emails import send_vision_outage_alert_email
from apps.scholarship.services import detect_vision_outage


class Command(BaseCommand):
    help = 'Email the admin if Google Vision OCR has been failing for ~a day.'

    def add_arguments(self, parser):
        parser.add_argument('--window-hours', type=int, default=24,
                            help='Look-back window for OCR outcomes (default 24).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report the verdict without sending the email.')

    def handle(self, *args, **opts):
        is_down, stats = detect_vision_outage(opts['window_hours'])
        if not is_down:
            self.stdout.write(self.style.SUCCESS(f'Vision OK — {stats}'))
            return
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(f'[dry-run] Would alert: Vision DOWN — {stats}'))
            return
        sent = send_vision_outage_alert_email(stats)
        msg = f'Vision DOWN — alert {"sent" if sent else "skipped (no ADMIN_NOTIFY_EMAIL)"} — {stats}'
        self.stdout.write((self.style.WARNING if sent else self.style.ERROR)(msg))
