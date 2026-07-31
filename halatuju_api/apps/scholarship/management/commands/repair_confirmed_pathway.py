"""One-off repair (requests #7 + #8, 2026-08-01): re-settle the pre-U facts on applications
whose CONFIRMED offer never had them filled.

``confirm_pathway`` reconciles the pathway TYPE from the offer letter and normalises the pre-U
fields (stream, school, canonical course name) — but until today those two steps ran in the wrong
order, so a student who had declared no pathway had the normalisation skipped against her empty
declaration. Separately, a blank /profile edit could erase the fields after they were filled. Both
leave the same signature: an offer-CONFIRMED programme with no stream and no school.

The repair simply re-runs the (now fixed) ``confirm_pathway`` against the offer letter already on
file — no re-extraction, no Vision/Gemini call, no new document read. It restores the ORIGINAL
``pathway_confirmed_at`` afterwards: the student confirmed on the day she confirmed, and that date
drives nothing good if it silently becomes today.

Idempotent: the selector stops matching once a record is repaired, and re-running finds nothing.

    python manage.py repair_confirmed_pathway --dry-run     # report only
    python manage.py repair_confirmed_pathway               # apply (how cron runs it)

Scope it with ``PATHWAY_REPAIR_APP_IDS=32,119`` to limit a production run to known ids.
"""
import os

from django.core.management.base import BaseCommand

from apps.scholarship import offer_pathway as op
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import confirm_pathway

#: The fields the repair may change — reported before/after so the run is auditable.
_WATCHED = ('chosen_pathway', 'pre_u_track', 'pre_u_institution')


def needs_repair(app):
    """True when an offer-CONFIRMED programme is missing the pre-U facts that confirm should
    have settled. A non-pre-U pathway (pismp / poly / degree) legitimately has no stream and no
    pre-U school — those rows are NOT candidates."""
    cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
    if (cp.get('source') or '') != 'offer_letter_confirmed':
        return False
    pathway = (app.chosen_pathway or '').strip()
    if not pathway:
        return True                     # never typed at all — the #119 shape
    if not op.is_pre_u(pathway.lower()):
        return False                    # a tertiary pathway needs neither field
    return not (app.pre_u_track or '').strip() or not (app.pre_u_institution or '').strip()


class Command(BaseCommand):
    help = 'Re-settle the pre-U fields on applications whose confirmed offer left them blank.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; no writes.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        qs = ScholarshipApplication.objects.select_related('profile').order_by('id')
        scoped = (os.environ.get('PATHWAY_REPAIR_APP_IDS') or '').strip()
        if scoped:
            ids = [int(x) for x in scoped.replace(' ', '').split(',') if x]
            qs = qs.filter(id__in=ids)
            self.stdout.write(f'scoped to applications {ids}')

        repaired = unchanged = 0
        for app in qs:
            if not needs_repair(app):
                continue
            before = {f: getattr(app, f) for f in _WATCHED}
            before_cp = dict(app.chosen_programme) if isinstance(app.chosen_programme, dict) else {}
            stamp = app.pathway_confirmed_at
            if dry:
                self.stdout.write(f'  app {app.id}: would re-run confirm against its offer '
                                  f'(now {before})')
                repaired += 1
                continue
            if not confirm_pathway(app):
                self.stdout.write(self.style.WARNING(
                    f'  app {app.id}: SKIPPED — no live offer letter on file'))
                unchanged += 1
                continue
            if stamp is not None and app.pathway_confirmed_at != stamp:
                app.pathway_confirmed_at = stamp        # she confirmed when she confirmed
                app.save(update_fields=['pathway_confirmed_at'])
            app.refresh_from_db()
            after = {f: getattr(app, f) for f in _WATCHED}
            after_cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            if after == before and after_cp == before_cp:
                self.stdout.write(f'  app {app.id}: no change (the offer says nothing more)')
                unchanged += 1
                continue
            self.stdout.write(f'  app {app.id}: {before} -> {after}')
            if after_cp != before_cp:
                self.stdout.write(f'           programme: {before_cp} -> {after_cp}')
            repaired += 1

        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}confirmed-pathway repair: '
            f'{repaired} repaired, {unchanged} unchanged.'))
