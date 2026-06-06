"""
One-time launch backfill for the completion-reminder system.

Sets ``reminder_anchor_at`` for the EXISTING shortlisted-but-incomplete cohort so the
reminder clock starts from "today minus 2 days" — meaning the very next daily run sends
them R1 immediately (day >= 2), then the normal cadence (R2 +9, R3 +23, R4 +53, close +58).
This is the agreed cutover: nobody in the in-flight backlog is ambushed by a final warning,
and since no fresh applications have arrived, starting them now (rather than waiting 2 idle
days) is the intent.

Idempotent + safe: only touches rows whose ``reminder_anchor_at`` is still NULL, only those
that are ``shortlisted`` AND not yet completed. Run ONCE, after migration 0041 is applied.
New shortlists going forward set their own anchor (= shortlisted_at) in release_decision and
are NOT affected by this command.

    python manage.py backfill_reminder_anchors [--dry-run]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication


class Command(BaseCommand):
    help = "One-time: anchor the existing shortlisted-incomplete cohort to today-2d (R1 fires next run)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='List who would be anchored without writing anything.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        anchor = timezone.now() - timedelta(days=2)          # today = day 2 -> R1 next run
        qs = (ScholarshipApplication.objects
              .filter(status='shortlisted', profile_completed_at__isnull=True,
                      reminder_anchor_at__isnull=True)
              .select_related('profile'))

        n = 0
        for app in qs:
            name = getattr(app.profile, 'name', '') if app.profile else ''
            sl = app.shortlisted_at.strftime('%Y-%m-%d') if app.shortlisted_at else 'n/a'
            self.stdout.write(f"  {'[dry-run] ' if dry else ''}anchor app #{app.pk} "
                              f"({name or 'unknown'}, shortlisted {sl}) -> day 2")
            if not dry:
                app.reminder_anchor_at = anchor
                app.save(update_fields=['reminder_anchor_at'])
            n += 1

        self.stdout.write(self.style.SUCCESS(
            f"{n} application(s) {'would be ' if dry else ''}anchored to today-2d "
            f"(R1 sends on the next daily reminder run)."
        ))
