"""Standardise the pre-U course label in chosen_programme.course_name into the canonical
form — Matrikulasi → "Program Matrikulasi", STPM → "Tingkatan Enam" — for STPM/Matrikulasi
applicants. The specific stream/jurusan is carried by pre_u_track, so the course string
itself is uniform. Idempotent; only touches course_name (institution, course_id, source
untouched). Going forward, autofill_pathway_from_offer writes the canonical name directly.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship import offer_pathway as op


class Command(BaseCommand):
    help = "Standardise chosen_programme.course_name for STPM/Matrikulasi applicants."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        qs = (ScholarshipApplication.objects
              .filter(chosen_pathway__in=['stpm', 'matric'])
              .select_related('profile'))
        updated = skipped = 0
        for app in qs:
            canon = op.canonical_pre_u_course(app.chosen_pathway)
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else None
            if not canon or not isinstance(cp, dict) or cp.get('course_name') == canon:
                skipped += 1
                continue
            self.stdout.write(f"  app {app.id} ({app.chosen_pathway}): "
                              f"{cp.get('course_name')!r} -> {canon!r}")
            if not dry:
                cp = dict(cp)
                cp['course_name'] = canon
                app.chosen_programme = cp
                app.save(update_fields=['chosen_programme'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}pre_u course standardise: {updated} updated, {skipped} unchanged.'))
