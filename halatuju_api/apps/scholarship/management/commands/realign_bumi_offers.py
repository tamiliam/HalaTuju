"""Repair: realign Bumiputera-only offers, and fill a hostel-line institution from the issuer.

Owner, 2026-10-31: until the Bumi coverage sprints the pickers did not show Bumiputera-only courses,
so a student holding a UiTM (or other Bumi-only) offer may have picked something else. Her own pick
is not a real selection: the offer's course replaces it (``services.offer_sync.plan_bumi_realign``
holds every condition and names each skip). Going forward ``autofill_pathway_from_offer`` does this
on every offer upload and re-read; this command applies it to the letters already on file, and runs
the institution fill (``sync_institution_from_catalogue``) after it, which since the same day lets
the ISSUER stand in for a hostel institution line (#175, #252, #354, #395).

Every application with a LIVE offer letter is listed, one line each: the old and new course, or the
reason it was skipped. Reads ALREADY-STORED ``vision_fields`` only — nothing is re-read or sent to
an AI. Report by default; ``--apply`` writes. Idempotent: a realigned pick is a confirmed source, so
a second run lists it as ``same_course``.

    python manage.py realign_bumi_offers            # report only
    python manage.py realign_bumi_offers --apply    # persist
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.document_snapshot import SNAPSHOT_ORDER
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services.offer_sync import (
    institution_fill, plan_bumi_realign, realign_bumi_only_pick, sync_institution_from_catalogue,
)


def _pick(cp, pathway):
    cp = cp if isinstance(cp, dict) else {}
    return (f"{cp.get('course_id') or '-'} | {cp.get('course_name') or '-'} | "
            f"{cp.get('institution') or '-'} | pathway {pathway or '-'}")


class Command(BaseCommand):
    help = "Realign Bumiputera-only offers onto the application, and fill hostel-line institutions."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Persist. Without it, report only.')

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        apply = options['apply']
        app_ids = (ApplicantDocument.objects
                   .filter(doc_type='offer_letter', superseded_at__isnull=True)
                   .values_list('application_id', flat=True).distinct())
        counts = Counter()
        qs = (ScholarshipApplication.objects.filter(id__in=list(app_ids))
              .select_related('profile').order_by('id'))
        for app in qs:
            offer = (ApplicantDocument.objects
                     .filter(application=app, doc_type='offer_letter', superseded_at__isnull=True)
                     .order_by(*SNAPSHOT_ORDER).first())
            chk = student_offer_check(offer)
            reason, new_cp, new_pathway = plan_bumi_realign(app, offer, chk)
            head = f"#{app.pk} [{app.status}]"
            if not reason:
                counts['realign'] += 1
                old = _pick(app.chosen_programme, app.chosen_pathway)
                if apply:
                    realign_bumi_only_pick(app, offer, chk)
                new = _pick(new_cp, new_pathway or app.chosen_pathway)
                self.stdout.write(f"  {head} REALIGN{'' if apply else ' (would)'}: {old}  ->  {new}")
                continue
            counts[f'skip:{reason}'] += 1
            filled = self._institution_fill(app, offer, chk, apply)
            if filled:
                counts['institution_fill'] += 1
            self.stdout.write(f"  {head} SKIP {reason}: {_pick(app.chosen_programme, app.chosen_pathway)}"
                              + (f"  | institution {'filled' if apply else 'would fill'}: {filled}"
                                 if filled else ''))
        self.stdout.write(self.style.SUCCESS(
            f"\nBumi realign: {'applied' if apply else 'report only'}; "
            + ', '.join(f'{k}={v}' for k, v in sorted(counts.items()))))

    def _institution_fill(self, app, offer, chk, apply):
        """The institution the writer fills (or would fill), or ''. The report reads the writer's own
        READ-ONLY planner (``institution_fill``) and never runs the writer."""
        filled = institution_fill(app, offer=offer, offer_check=chk)
        if filled and apply:
            sync_institution_from_catalogue(app, offer=offer, offer_check=chk)
        return filled
