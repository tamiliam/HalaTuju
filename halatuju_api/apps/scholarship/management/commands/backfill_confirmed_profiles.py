"""One-off backfill (TD-210, 2026-10-05): bring the PROFILE pathway of students who confirmed an
offer BEFORE the fix into line with their confirmed application.

Since TD-210 ``confirm_pathway`` refreshes the profile whenever a confirm changes the pathway. A
student who confirmed earlier still has her original declaration on the profile, so her next
/profile edit can push the superseded pathway back (#43: application pismp, profile stpm). The
read-only count on 2026-10-05 found 14 confirmed applications and 5 whose profile disagreed.

For each student, the application used is her LATEST confirmed application that the profile
follows — the same rule as the confirm (``profile_follows``: no LATER application still open).
The four fields ``PROFILE_SYNCED_FIELDS`` are copied where they differ. A blank replaces a
populated profile value only for the pre-U stream / school, and only when the application's
pathway is set and is NOT pre-U (the type switch made them meaningless); any other blank never
erases a profile value (``copy_pathway``'s rule). No results, grades or identity are touched.

Dry run by default; ``--apply`` writes. Prints the application id and field NAMES only — no
names, no values, and no profile key (it is the student's auth uid). Idempotent: a second ``--apply`` finds nothing to change.

    python manage.py backfill_confirmed_profiles            # report only
    python manage.py backfill_confirmed_profiles --apply    # write

⚠ The production door is the cron job `backfill-confirmed-profiles`, which cannot pass a flag: it
is a DRY RUN unless `BACKFILL_CONFIRMED_PROFILES_APPLY=1` is set on the service. Set it, POST the
job, then UNSET it (the `backfill_verdict_engine_version` pattern).
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.scholarship import offer_pathway as op
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services.confirmation import profile_follows, sync_profile_pathway

_PRE_U_FIELDS = ('pre_u_track', 'pre_u_institution')


def _may_clear(app):
    pw = (app.chosen_pathway or '').strip().lower()
    return lambda f: f in _PRE_U_FIELDS and bool(pw) and not op.is_pre_u(pw)


class Command(BaseCommand):
    APPLY_ENV = 'BACKFILL_CONFIRMED_PROFILES_APPLY'
    help = "Copy each confirmed application's pathway onto its student's profile (TD-210 backfill)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')

    def handle(self, *args, **opts):
        write = opts['apply'] or os.environ.get(self.APPLY_ENV, '') == '1'
        chosen = {}                         # profile id -> the application it follows (latest wins)
        qs = (ScholarshipApplication.objects.select_related('profile')
              .filter(pathway_confirmed_at__isnull=False, profile__isnull=False).order_by('id'))
        for app in qs:
            if profile_follows(app):
                chosen[app.profile_id] = app
        changed_n = 0
        for app in sorted(chosen.values(), key=lambda a: a.id):
            with transaction.atomic():
                fields = sync_profile_pathway(app, may_clear=_may_clear(app), write=write)
            if fields:
                changed_n += 1
                verb = 'refreshed' if write else 'would refresh'
                self.stdout.write(f'  app {app.id}: profile {verb}: {", ".join(fields)}')
        self.stdout.write(self.style.SUCCESS(
            f'{"" if write else "[dry-run] "}confirmed-profile backfill: {len(chosen)} checked, '
            f'{changed_n} {"changed" if write else "to change"}.'))
