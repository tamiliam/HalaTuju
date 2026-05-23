"""
Release due B40 decisions: reveal the verdict (flip status + send the email) for
applications whose ``decision_due_at`` has passed. Shortlist verdicts reveal at
+success_delay_hours (default 2h), declines at +decline_delay_hours (default 48h) —
both delays are baked into ``decision_due_at`` when the application is scored at
submit. Idempotent: an already-released application is skipped.

Schedule this (e.g. Cloud Scheduler → Cloud Run Job, every ~15 min) once deployed.

    python manage.py send_pending_decision_emails [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import release_decision


class Command(BaseCommand):
    help = "Release due B40 decisions (flip status + send invitation/decline email) past decision_due_at."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be released without changing anything.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        db = connection.settings_dict
        # Transparency: which database are we acting on? (management-command lesson)
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        now = timezone.now()
        qs = ScholarshipApplication.objects.filter(
            status='submitted',
            decision_released_at__isnull=True,
            decision_due_at__isnull=False,
            decision_due_at__lte=now,
        ).exclude(verdict='').select_related('cohort', 'profile')

        released = skipped = 0
        for app in qs:
            if dry:
                self.stdout.write(
                    f"  [dry-run] would release app #{app.pk}: {app.verdict} "
                    f"-> {app.notify_email or '(no email)'}"
                )
                released += 1
                continue
            if release_decision(app):
                released += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Decisions: {released} {'would be ' if dry else ''}released, {skipped} skipped"
        ))
