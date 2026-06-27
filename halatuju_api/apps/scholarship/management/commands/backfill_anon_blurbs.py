"""Backfill the sponsor-pool CARD blurb for already-published anonymous profiles.

From this sprint on, ``SponsorProfile.anon_blurb`` (the ≤20-word card-strict one-liner)
is generated at publish. Profiles published BEFORE this predate the field, so this
command generates + identifier-scans a blurb for each published profile still missing one.

BILLABLE — one Gemini call per profile. Must run ON the service (needs the prod DB +
Gemini): the cron endpoint job ``backfill-anon-blurbs`` or ``manage.py backfill_anon_blurbs``.
Idempotent: only fills blanks unless ``--force``.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import pool
from apps.scholarship.models import SponsorProfile
from apps.scholarship.profile_engine import generate_anon_blurb


class Command(BaseCommand):
    help = 'Generate the sponsor-pool card blurb for published anon profiles missing one (billable).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100,
                            help='Max profiles to process in one run.')
        parser.add_argument('--force', action='store_true',
                            help='Regenerate even when a blurb already exists.')

    def handle(self, *args, **opts):
        qs = SponsorProfile.objects.filter(anon_published=True).select_related(
            'application', 'application__profile')
        if not opts['force']:
            qs = qs.filter(anon_blurb='')
        done = skipped = 0
        for sp in qs.order_by('id')[:opts['limit']]:
            app = sp.application
            blurb = generate_anon_blurb(app, sp.anon_markdown)
            if blurb and not pool.scan_anon_for_identifiers(blurb, getattr(app, 'profile', None)):
                sp.anon_blurb = blurb
                sp.save(update_fields=['anon_blurb'])
                done += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f'anon_blurb backfill: set={done} skipped={skipped}'))
