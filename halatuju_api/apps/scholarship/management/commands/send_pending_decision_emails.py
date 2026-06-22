"""
Release due B40 decisions: reveal the verdict (flip status + send the email) for
applications whose ``decision_due_at`` has passed. Shortlist verdicts reveal at
+success_delay_hours, declines at +decline_delay_hours — per-cohort (b40-2026: 55 min
shortlist / 48 h decline; model default 48). Both delays are FloatFields (sub-hour OK)
baked into ``decision_due_at`` when the application is scored at submit. Idempotent: an
already-released application is skipped.

Schedule this (e.g. Cloud Scheduler → Cloud Run Job, every ~15 min) once deployed.

    python manage.py send_pending_decision_emails [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import release_decision, release_pending_declines
from apps.scholarship.sponsorship import release_pending_awards


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

        # Cool-off releases (#13 decline +7d, #14 award +2d): reveal what's now past its
        # cool-off. Not part of --dry-run (these mutate); they're idempotent + cheap.
        if not dry:
            declines = release_pending_declines(now=now)
            awards = release_pending_awards(now=now)
            self.stdout.write(self.style.SUCCESS(
                f"Cool-off: {declines} decline(s) revealed, {awards} award(s) finalised"
            ))
