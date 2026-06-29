"""Casing-only standardisation of STPM students' recorded school name (no catalogue lookup —
the school IDENTITY is never changed). Picks the address-free, fullest of the recorded values
(chosen_programme.institution / pre_u_institution), expands a leading acronym (SMK/SMJK/KTE…)
and Title-cases it. Seeds existing rows; going forward, autofill_pathway_from_offer keeps new
STPM offers normalised. Idempotent; pass --apply to write.
"""
from django.core.management.base import BaseCommand
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship import offer_pathway as op


class Command(BaseCommand):
    help = "Standardise STPM chosen_programme.institution casing (identity-preserving; no catalogue lookup)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write changes (default: dry-run).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        updated = skipped = 0
        for app in ScholarshipApplication.objects.filter(chosen_pathway='stpm').select_related('profile'):
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            cur = (cp.get('institution') or '').strip()
            clean = op.clean_school_name(cur, (app.pre_u_institution or ''))
            if not clean or clean == cur:
                skipped += 1
                continue
            nm = (getattr(app.profile, 'name', '') or '').strip()[:24]
            self.stdout.write(f"  app {app.id} {nm}: {cur!r} -> {clean!r}")
            if apply:
                cp = dict(cp)
                cp['institution'] = clean
                app.chosen_programme = cp
                app.save(update_fields=['chosen_programme'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[APPLIED] " if apply else "[dry-run] "}STPM institution casing: {updated} updated, {skipped} unchanged.'))
