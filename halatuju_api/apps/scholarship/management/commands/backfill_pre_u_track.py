"""Backfill ScholarshipApplication.pre_u_track into the canonical pre-U vocabulary
(Matrikulasi: sains/kejuruteraan/sains_komputer/perakaunan; STPM: sains/sains_sosial) for
STPM/Matrikulasi applicants whose track is blank or 'not_sure'. Idempotent — fills blanks
only, never overwrites a deliberate pick. Going forward the track is kept current by
``autofill_pathway_from_offer`` on every offer (re)extraction; this seeds the existing rows.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication, ApplicantDocument
from apps.scholarship import offer_pathway as op
from apps.scholarship.pathway_engine import student_offer_check


def _offer_programme(app):
    offer = (ApplicantDocument.objects.filter(application=app, doc_type='offer_letter')
             .order_by('-uploaded_at').first())
    if offer is None:
        return ''
    try:
        return (student_offer_check(offer).get('programme') or '').strip()
    except Exception:
        return ''


class Command(BaseCommand):
    help = "Backfill pre_u_track (STPM bidang / Matrikulasi track) for pre-U applicants."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        qs = (ScholarshipApplication.objects
              .filter(chosen_pathway__in=['stpm', 'matric'])
              .select_related('profile'))
        updated = skipped = 0
        for app in qs:
            cur = (app.pre_u_track or '').strip().lower()
            if cur not in ('', 'not_sure'):
                skipped += 1
                continue
            prog = _offer_programme(app)
            pw = app.chosen_pathway.lower()
            if pw == 'matric':
                track = op.parse_matric_track(prog)
            else:
                track = op.parse_stpm_stream(prog) or op.infer_stpm_bidang(
                    getattr(app.profile, 'grades', None),
                    getattr(app.profile, 'stream_subjects', None))
            if not track or track == cur:
                skipped += 1
                continue
            self.stdout.write(f'  app {app.id} ({pw}): {app.pre_u_track!r} -> {track!r}')
            if not dry:
                app.pre_u_track = track
                app.save(update_fields=['pre_u_track'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}pre_u_track backfill: {updated} updated, {skipped} unchanged.'))
