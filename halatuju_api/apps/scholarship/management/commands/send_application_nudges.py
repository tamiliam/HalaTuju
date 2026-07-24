"""
One-time automatic "you haven't submitted yet" nudge.

Emails every SHORTLISTED student who has given consent but not pressed the final Review &
submit (their application is still a draft, ``profile_completed_at IS NULL``), once, about
30 minutes after they consented — while they are likely still at their device. A student is
never swept twice (``nudge_sent_at`` is stamped on send). This sits ALONGSIDE the generic
completion reminders (send_application_reminders), it does not replace them.

Schedule this FREQUENTLY (e.g. Cloud Scheduler -> the cron endpoint, every ~15 min).

    python manage.py send_application_nudges [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.nudge import _auto_delay, send_application_nudges


class Command(BaseCommand):
    help = "Send the one-time auto nudge to shortlisted, consented-but-unsubmitted students."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be nudged without sending or changing anything.',
        )

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        if options['dry_run']:
            cutoff = timezone.now() - _auto_delay()
            qs = (ScholarshipApplication.objects
                  .filter(status='shortlisted', profile_completed_at__isnull=True,
                          nudge_sent_at__isnull=True,
                          consents__is_active=True, consents__granted_at__lte=cutoff)
                  .select_related('profile').distinct())
            for app in qs:
                self.stdout.write(f"  [dry-run] would nudge app #{app.pk} -> {app.notify_email or '(no email)'}")
            self.stdout.write(self.style.SUCCESS(f"Nudges: {qs.count()} would be sent"))
            return
        result = send_application_nudges()
        self.stdout.write(self.style.SUCCESS(f"Nudges: {result['nudged']} sent"))
