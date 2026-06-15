"""One-off backfill: (re)draft the sponsor profile for every reviewer-ASSIGNED
application — for students who were handed off to a reviewer before
``CHECK2_AUTO_GENERATE`` was switched on (the auto-draft fires only at the moment of
first assignment, so those handoffs never produced a profile), and to refresh any draft
generated under an earlier prompt onto the current one.

Assigned-only (matches the "profile is generated when a reviewer is assigned" rule —
NOT the broader ready-for-assignment sweep). Skips an officer-EDITED draft (never clobber
human edits). Flag-gated and billable (one Gemini Flash call per application). No args, so
it runs cleanly via the internal cron endpoint job 'backfill-assigned-profiles'.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import generate_ready_profile


class Command(BaseCommand):
    help = 'Draft profiles for reviewer-assigned applications (flag-gated, skips edited).'

    def handle(self, *args, **options):
        if not getattr(settings, 'CHECK2_AUTO_GENERATE', False):
            self.stdout.write('CHECK2_AUTO_GENERATE is off — nothing generated.')
            return
        qs = (ScholarshipApplication.objects
              .filter(assigned_to__isnull=False)
              .select_related('sponsor_profile', 'profile').order_by('id'))
        done, skipped, failed = [], [], []
        for app in qs:
            sp = getattr(app, 'sponsor_profile', None)
            if sp is not None and sp.edited_markdown:
                skipped.append(app.id)          # never overwrite an officer's edits
                continue
            _, err = generate_ready_profile(app)
            if err:
                failed.append((app.id, err))
            else:
                done.append(app.id)
        self.stdout.write(
            f'Backfill complete. generated={done} skipped_edited={skipped} failed={failed}')
