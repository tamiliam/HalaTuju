"""READ-ONLY audit of the offer-letter pathway chip and the Institution tick (request #9).

Writes nothing. For every application holding a live offer letter it prints what the officer's
screen derives now, beside what it derived BEFORE the request-#9 fix — the old behaviour is
reproduced by calling ``offer_pathway_match`` without the two catalogue verdicts, which is
literally what the code did.

This exists because the ticks are DERIVED on read, not stored: there is no column to diff, so
"before and after" can only be answered by re-deriving both. Doing both in ONE pass on the live
database is also stronger than two runs a deploy apart — same data, same instant, no drift.

    python manage.py audit_pathway_ticks              # every application with an offer
    python manage.py audit_pathway_ticks --pismp      # only the PISMP set (the request's subject)

Registered as the cron job ``audit-pathway-ticks`` so it can run on the service, which is where
the production database is reachable from.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.pathway_engine import (
    _field_status, offer_pathway_match, student_offer_check)


def _legacy_pathway(chk, app):
    """What the Pathway chip read BEFORE request #9 — the token comparison on both axes, with
    neither catalogue verdict passed in."""
    return offer_pathway_match(
        chk['declared_programme'], chk['declared_institution'],
        chk['programme'], chk['institution'],
        declared_track=(getattr(app, 'pre_u_track', '') or ''),
        offer_stream=chk.get('stream', ''),
    )


class Command(BaseCommand):
    help = 'Read-only: the Pathway chip and Institution tick, now vs before the request-#9 fix.'

    def add_arguments(self, parser):
        parser.add_argument('--pismp', action='store_true',
                            help='Only PISMP applications (request #9 subject).')

    def handle(self, *args, **opts):
        qs = ScholarshipApplication.objects.select_related('profile').order_by('id')
        if opts['pismp']:
            qs = qs.filter(chosen_pathway__iexact='pismp')
        changed = same = no_offer = 0
        for app in qs:
            offer = (ApplicantDocument.objects
                     .filter(application=app, doc_type='offer_letter', superseded_at__isnull=True)
                     .order_by('-uploaded_at').first())
            if offer is None:
                no_offer += 1
                continue
            try:
                chk = student_offer_check(offer)
            except Exception as e:      # noqa: BLE001 — an audit must never die on one row
                self.stdout.write(self.style.WARNING(f'  app {app.id}: could not read ({e})'))
                continue
            now_path, now_inst = chk['pathway'], chk['chosen_institution_status']
            was_path = _legacy_pathway(chk, app)
            # The legacy institution status. Only the UNLINKED case changed: with a course_id the
            # catalogue answered then and answers now, so the two are identical; without one, the
            # old code compared the recorded institution against the letter by tokens — which is
            # what this reproduces — where the new code refuses when that value CAME from the
            # letter.
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            if (cp.get('course_id') or '').strip():
                was_inst = now_inst
            else:
                was_inst = _field_status((cp.get('institution') or ''), chk['institution'])
            # The tick the officer sees: the institution agrees AND the chip is not red.
            now_tick = now_inst == 'match' and now_path != 'mismatch'
            was_tick = was_inst == 'match' and was_path != 'mismatch'
            if (now_path, now_tick) == (was_path, was_tick):
                same += 1
                continue
            changed += 1
            self.stdout.write(
                f'  app {app.id} ({app.chosen_pathway or "—"}, {app.status}): '
                f'pathway {was_path} -> {now_path}; institution tick '
                f'{"YES" if was_tick else "no"} -> {"YES" if now_tick else "no"}')
        self.stdout.write(self.style.SUCCESS(
            f'pathway-tick audit: {changed} changed, {same} unchanged, {no_offer} without an offer.'))
