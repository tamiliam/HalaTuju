"""Email the admin an annual reminder to run the STPM/UPU catalogue refresh.

Wired as the CronRunView job 'refresh-reminder'; fire once a year via Cloud
Scheduler (≈ December, before the UPU application window opens). The refresh
itself is a manual local tool (`refresh_stpm` — needs Playwright), so this just
nudges the operator to run it.

Recipient: ``settings.COURSE_REFRESH_REMINDER_EMAIL`` (falls back to
``DEFAULT_FROM_EMAIL``). Config is read from ``django.conf.settings`` (Django
does not auto-load .env into os.environ). No recipient → clean no-op.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

SUBJECT = 'HalaTuju: time to refresh the STPM/UPU course catalogue'
BODY = (
    "It's time for the annual course-data refresh, before the UPU application window opens.\n\n"
    "On your machine (needs Playwright/Chromium), from halatuju_api/:\n"
    "    python manage.py refresh_stpm           # scrape -> sync (dry-run) -> audit\n"
    "    # review the dry-run report, then:\n"
    "    python manage.py refresh_stpm --apply   # guarded apply\n\n"
    "Guides: docs/roadmap-course-data-pipeline.md, docs/course-data-source-inventory.md,\n"
    "Settings/_workflows/stpm-requirements-update.md.\n\n"
    "(Automated annual reminder.)\n"
)


class Command(BaseCommand):
    help = 'Email the admin an annual reminder to run the STPM/UPU catalogue refresh.'

    def handle(self, *args, **options):
        to = (getattr(settings, 'COURSE_REFRESH_REMINDER_EMAIL', '') or
              getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '')
        if not to:
            self.stdout.write(self.style.WARNING(
                'No reminder recipient (COURSE_REFRESH_REMINDER_EMAIL / DEFAULT_FROM_EMAIL) — skipping.'))
            return
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or to
        sent = send_mail(SUBJECT, BODY, from_email, [to], fail_silently=True)
        if sent:
            self.stdout.write(self.style.SUCCESS('Refresh reminder emailed to %s' % to))
        else:
            logger.warning('Refresh reminder email did not send (to=%s)', to)
            self.stdout.write(self.style.WARNING('Reminder email did not send (see logs).'))
