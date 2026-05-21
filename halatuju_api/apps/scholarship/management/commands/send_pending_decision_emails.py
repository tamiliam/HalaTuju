"""
Send the courteous "not this round" email to rejected B40 applicants once the
cohort's configured delay has elapsed.

Pass emails are sent immediately at submit; fail emails are deliberately delayed
(``ScholarshipCohort.fail_email_delay_days``) so a rejection never lands seconds
after applying. Schedule this command (e.g. Cloud Scheduler, daily) once the
service is deployed.

    python manage.py send_pending_decision_emails [--dry-run]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.emails import send_fail_email
from apps.scholarship.models import ScholarshipApplication


class Command(BaseCommand):
    help = "Send delayed 'not this round' emails to rejected applicants past the cohort delay."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List who would be emailed without sending or stamping anything.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        db = connection.settings_dict
        # Transparency: which database are we acting on? (per the management-command lessons)
        self.stdout.write(
            f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}"
        )

        now = timezone.now()
        qs = ScholarshipApplication.objects.filter(
            status='rejected',
            decision_email_sent_at__isnull=True,
            shortlisted_at__isnull=False,
        ).select_related('cohort', 'profile')

        sent = skipped = 0
        for app in qs:
            due = app.shortlisted_at + timedelta(days=app.cohort.fail_email_delay_days)
            if now < due:
                skipped += 1
                continue
            if not app.notify_email:
                self.stdout.write(f"  skip app #{app.pk}: no notify_email on file")
                skipped += 1
                continue
            if dry:
                self.stdout.write(f"  [dry-run] would email {app.notify_email} (app #{app.pk})")
                sent += 1
                continue
            ok = send_fail_email(
                to_email=app.notify_email,
                applicant_name=getattr(app.profile, 'name', '') if app.profile else '',
                programme_name=app.cohort.name,
                lang=app.locale,
            )
            if ok:
                app.decision_email_sent_at = now
                app.save(update_fields=['decision_email_sent_at'])
                sent += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Decision emails: {sent} {'would be ' if dry else ''}sent, {skipped} skipped"
        ))
