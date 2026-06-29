"""Align chosen_programme.institution to the recommender CATALOGUE for catalogue-linked
(tertiary) applications — the single source of truth. Where a programme carries a real
course_id, the institution name is taken from course_id → Institution (ironing out
offer-letter OCR variants like "…(POLITEKNIK PREMIER)", address tails, casing). Idempotent;
only touches the institution sub-key; leaves a row alone when the catalogue is ambiguous or
the course_id is unknown (e.g. a private course not in the catalogue). Going forward,
autofill_pathway_from_offer keeps it aligned on every offer extraction.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship import offer_pathway as op


class Command(BaseCommand):
    help = "Align chosen_programme.institution to the recommender catalogue (course_id → Institution)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        updated = skipped = ambiguous = 0
        for app in ScholarshipApplication.objects.select_related('profile').all():
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else None
            cid = (cp.get('course_id') or '').strip() if cp else ''
            if not cid:
                skipped += 1
                continue
            cur = (cp.get('institution') or '').strip()
            canon = op.catalogue_institution(cid, cur)
            if not canon:
                ambiguous += 1          # course offered at several / unknown — don't guess
                continue
            if canon == cur:
                skipped += 1
                continue
            nm = (getattr(app.profile, 'name', '') or '').strip()[:24]
            self.stdout.write(f"  app {app.id} {nm} [{cid}]: {cur!r} -> {canon!r}")
            if not dry:
                cp = dict(cp)
                cp['institution'] = canon
                app.chosen_programme = cp
                app.save(update_fields=['chosen_programme'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}institution align: {updated} updated, '
            f'{skipped} unchanged, {ambiguous} ambiguous/unknown (left as-is).'))
