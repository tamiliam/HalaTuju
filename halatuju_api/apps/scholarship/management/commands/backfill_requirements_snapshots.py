"""
One-off: freeze the requirement set for applications submitted BEFORE the snapshot existed.

From 2026-08-30 `confirm_profile` freezes what the programme asked for at the Step-4 Submit
(`ScholarshipApplication.requirements_snapshot`), so a later configuration change can never
re-gate a submitted student. Shipping that freezes nobody: the 90-odd applications already
submitted have NULL there and still read the LIVE catalogue — exactly the exposure the column
exists to close. This writes their snapshot once, from the resolution in force today.

Today there are zero programme overrides, so every row freezes to the seeded defaults — which
are the literals the gates enforced on the day each student submitted. Nothing about their
standing changes; the value is that from now on it CANNOT change.

**No API calls, no re-extraction, no completeness re-check.** It reads the catalogue through
`requirements.resolve` (the live path) and writes one JSON column. A row that already carries a
snapshot is left alone — `requirements.freeze` is idempotent — so a repeat run is a no-op.

Only applications that have actually submitted (`profile_completed_at` set) are candidates: a
`shortlisted` student is still editing and must keep following the live configuration.

    python manage.py backfill_requirements_snapshots              # report only
    python manage.py backfill_requirements_snapshots --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship import requirements
from apps.scholarship.models import ScholarshipApplication


class Command(BaseCommand):
    help = 'Freeze the requirement set on already-submitted applications. Report by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the snapshots. Without it, report only.')

    def handle(self, *args, **options):
        # The cron endpoint calls a command with no arguments, so on the live service the write
        # is switched on by the env var (set it, run the job, UNSET it — the seed-partner-emails
        # pattern). Locally the flag is the honest way.
        import os
        apply = options['apply'] or os.environ.get('REQUIREMENTS_SNAPSHOT_APPLY') == '1'
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        qs = (ScholarshipApplication.objects
              .filter(profile_completed_at__isnull=False)
              .select_related('programme')
              .order_by('id'))
        tally = Counter()
        shapes = Counter()
        for app in qs.iterator():
            if isinstance(app.requirements_snapshot, dict) and app.requirements_snapshot.get('captured_at'):
                tally['already frozen'] += 1
                continue
            snap = requirements.freeze(app, save=apply)
            # Group by the frozen SHAPE so the report says "these N rows all got the same answer"
            # — a second shape appearing would mean an override exists that nobody expected.
            key = (tuple(sorted(c for c, s in snap['documents'].items() if s == 'required')),
                   tuple(sorted(c for c, s in snap['questions'].items() if s == 'required')))
            shapes[key] += 1
            tally['frozen' if apply else 'would freeze'] += 1

        for label, n in sorted(tally.items()):
            self.stdout.write(f'  {label}: {n}')
        for (docs, qs_), n in shapes.items():
            self.stdout.write(f'  shape x{n}: documents required={list(docs)} questions required={list(qs_)}')
        if not apply:
            self.stdout.write(self.style.WARNING('report only — nothing written (use --apply)'))
        else:
            self.stdout.write(self.style.SUCCESS('done'))
