"""Backfill: settle the chosen pathway from already-uploaded, verified offer letters.

The silent auto-fill (``services.autofill_pathway_from_offer``) runs on offer-letter
upload + admin re-run. This command applies the SAME logic to offers that were uploaded
*before* the feature existed — so a student who's already decided (has a verified offer)
stops showing as "still exploring / —" on the cockpit.

Idempotent + safe: the auto-fill skips wrong-person / unreadable / genuinely-clashing
offers and never overwrites a precise existing pick. Dry-run by default.

    python manage.py backfill_offer_pathways [--apply]
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services import autofill_pathway_from_offer


class Command(BaseCommand):
    help = "Settle chosen pathway from existing verified offer letters (auto-fill backfill)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist the changes. Without it, only reports what WOULD change.')

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        apply = options['apply']

        app_ids = (ApplicantDocument.objects
                   .filter(doc_type='offer_letter')
                   .values_list('application_id', flat=True).distinct())
        changed = 0
        for app in ScholarshipApplication.objects.filter(id__in=list(app_ids)).select_related('profile'):
            if apply:
                if autofill_pathway_from_offer(app):
                    changed += 1
                    self._report(app)
            else:
                # Dry-run: re-read what the auto-fill WOULD do without saving.
                offer = (ApplicantDocument.objects
                         .filter(application=app, doc_type='offer_letter')
                         .order_by('-uploaded_at').first())
                chk = student_offer_check(offer) if offer else {}
                cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
                would = (offer is not None
                         and chk.get('ic') != 'mismatch' and chk.get('name') != 'mismatch'
                         and ((chk.get('programme') or '').strip() or (chk.get('institution') or '').strip())
                         and chk.get('pathway') != 'mismatch'
                         and not (cp.get('course_id') and app.pathway_certainty == 'sure'))
                if would:
                    changed += 1
                    self.stdout.write(
                        f"  [dry-run] app #{app.pk}: would settle -> "
                        f"{(chk.get('programme') or '').strip() or '(no programme)'} @ "
                        f"{(chk.get('institution') or '').strip() or '(no institution)'}")

        verb = 'settled' if apply else 'would settle'
        self.stdout.write(self.style.SUCCESS(f"Offer-pathway backfill: {changed} {verb}"))

    def _report(self, app):
        cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
        self.stdout.write(
            f"  app #{app.pk}: pathway={app.chosen_pathway or '-'} "
            f"programme={cp.get('course_name') or '-'} "
            f"institution={cp.get('institution') or app.pre_u_institution or '-'} "
            f"course_id={cp.get('course_id') or '-'}")
