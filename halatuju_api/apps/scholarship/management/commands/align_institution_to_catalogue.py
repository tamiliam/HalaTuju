"""Align chosen_programme.institution to the recommender CATALOGUE for catalogue-linked
(tertiary) applications — the single source of truth. Where a programme carries a real
course_id, the institution name is taken from course_id → Institution (ironing out
offer-letter OCR variants like "…(POLITEKNIK PREMIER)", address tails, casing). Idempotent;
only touches the institution sub-key; leaves a row alone when the catalogue is ambiguous or
the course_id is unknown (e.g. a private course not in the catalogue). Going forward,
autofill_pathway_from_offer keeps it aligned on every offer extraction.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication, ApplicantDocument
from apps.scholarship import offer_pathway as op


def _offer_institution(app):
    o = (ApplicantDocument.objects.filter(
            application=app, doc_type='offer_letter', superseded_at__isnull=True)
         .order_by('-uploaded_at').first())
    if not o or not isinstance(o.vision_fields, dict):
        return ''
    f = o.vision_fields.get('fields', {})
    return (f.get('institution') or '').strip() if isinstance(f, dict) else ''


class Command(BaseCommand):
    help = "Align chosen_programme.institution to the recommender catalogue (course_id → Institution)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        updated = skipped = ambiguous = 0
        for app in ScholarshipApplication.objects.select_related('profile').all():
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            cur = (cp.get('institution') or '').strip()
            pw = (app.chosen_pathway or '').strip().lower()
            if pw == 'matric':
                # Matric colleges are 12 STATE-unique rows → catalogue-matching is safe.
                cid = op.preu_course_id(pw, app.pre_u_track)
                hint = cur or (app.pre_u_institution or '').strip() or _offer_institution(app)
            elif pw == 'stpm':
                # STPM schools are NOT catalogue-matched: ~250 near-identically-named schools per
                # bidang, and token-matching can't distinguish SMK from SMJK or "Tun Hussein Onn"
                # from "Bandar Tun Hussein Onn 2" — it would change which school a student attends.
                # The recorded school is authoritative; standardise its CASING separately.
                skipped += 1
                continue
            else:
                # Tertiary: the stored catalogue course_id; disambiguate a multi-campus course
                # against the OFFER's institution when the stored one is blank.
                cid = (cp.get('course_id') or '').strip()
                hint = cur or _offer_institution(app)
            if not cid:
                skipped += 1
                continue
            canon = op.catalogue_institution(cid, hint)
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
