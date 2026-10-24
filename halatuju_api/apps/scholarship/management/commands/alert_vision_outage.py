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

2026-10-24: it also checks GEMINI document reads (Gemini's prepaid credit ran out for ~20 hours
and this check, then IC-only, said nothing), one email per service that is down. ``--hourly`` is
the start-edge mode for an HOURLY job: a 2-hour window, and only an outage that was not already
visible to the run an hour earlier is mailed — so the hour it starts, not every hour after.

    python manage.py alert_vision_outage --hourly [--window-hours 2] [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.scholarship.emails import send_vision_outage_alert_email
from apps.scholarship.services import detect_service_outages


class Command(BaseCommand):
    help = 'Email the admin if a document-read service (Vision OCR, Gemini) is failing.'

    def add_arguments(self, parser):
        parser.add_argument('--window-hours', type=int, default=None,
                            help='Look-back window (default 24; 2 with --hourly).')
        parser.add_argument('--hourly', action='store_true',
                            help='Start-edge mode for an hourly job: mail only an outage that '
                                 'was not already down for the run an hour earlier.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report the verdict without sending the email.')

    def handle(self, *args, **opts):
        hourly = opts['hourly']
        window = opts['window_hours'] or (2 if hourly else 24)
        down = detect_service_outages(window, start_edge=hourly)
        if not down:
            self.stdout.write(self.style.SUCCESS(
                f'Read services OK (or an outage already reported) — window {window}h'))
            return
        for stats in down:
            name = stats['service']
            if opts['dry_run']:
                self.stdout.write(self.style.WARNING(f'[dry-run] Would alert: {name} DOWN — {stats}'))
                continue
            sent = send_vision_outage_alert_email(stats)
            msg = f'{name} DOWN — alert {"sent" if sent else "skipped (no ADMIN_NOTIFY_EMAIL)"} — {stats}'
            self.stdout.write((self.style.WARNING if sent else self.style.ERROR)(msg))
