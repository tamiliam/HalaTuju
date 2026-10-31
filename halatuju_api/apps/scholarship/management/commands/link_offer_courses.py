"""Repair: link offer-sourced, labels-only picks to their catalogue course (owner, 2026-11-01).

A pick read off an offer letter before the matcher could see the degree catalogue has labels only —
no ``course_id`` — so the cockpit shows no course link and the institution as printed (a hostel
line included, #243). ``services.offer_link.plan_offer_link`` holds every rule and names each skip;
the source is KEPT. Its own command, not a mode of ``realign_bumi_offers``: that one REPLACES a
student's choice under the Bumiputera rule; this one replaces nothing, has its own population and
its own skips, and the two reports stay readable apart.

Every application with a live offer and an offer-sourced pick is listed, one line each; a pathway
change is listed again under PATHWAY CHANGES (the payment calendar reads it). Reads stored
``vision_fields`` only — nothing is re-read or sent to an AI. Report by default; ``--apply`` writes.
Idempotent: a linked pick reads ``has_course_id``.

    python manage.py link_offer_courses            # report only
    python manage.py link_offer_courses --apply    # persist
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.document_snapshot import SNAPSHOT_ORDER
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services.offer_link import OFFER_SOURCES, link_offer_course, plan_offer_link
from apps.scholarship.services.offer_sync import plan_bumi_realign, realign_basis, realign_bumi_only_pick


def _pick(cp):
    cp = cp if isinstance(cp, dict) else {}
    return f"{cp.get('course_id') or '-'} | {cp.get('course_name') or '-'} | {cp.get('institution') or '-'}"


class Command(BaseCommand):
    help = "Link offer-sourced, labels-only picks to their catalogue course."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist. Without it, report only.')

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")
        apply = options['apply']
        app_ids = (ApplicantDocument.objects
                   .filter(doc_type='offer_letter', superseded_at__isnull=True)
                   .values_list('application_id', flat=True).distinct())
        counts, pathway_changes = Counter(), []
        qs = (ScholarshipApplication.objects.filter(id__in=list(app_ids))
              .select_related('profile').order_by('id'))
        for app in qs:
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            if (cp.get('source') or '') not in OFFER_SOURCES:
                continue
            offer = (ApplicantDocument.objects
                     .filter(application=app, doc_type='offer_letter', superseded_at__isnull=True)
                     .order_by(*SNAPSHOT_ORDER).first())
            chk = student_offer_check(offer)
            realign = plan_bumi_realign(app, offer, chk)
            if not realign[0]:
                # The realignment's record first (round-3 review: one order, whatever runs first).
                counts['realign_first'] += 1
                basis = realign_basis(app, realign[1]['course_id'])
                if apply:
                    realign_bumi_only_pick(app, offer, chk)
                self.stdout.write(f"  #{app.pk} [{app.status}] ({cp.get('source')}) REALIGN-FIRST {basis}"
                                  f"{'' if apply else ' (would)'}: {_pick(cp)}  ->  {_pick(realign[1])}")
                continue
            reason, new_cp, new_pathway = plan_offer_link(app, offer, chk)
            head = f"#{app.pk} [{app.status}] ({cp.get('source')})"
            if reason:
                counts[f'skip:{reason}'] += 1
                self.stdout.write(f"  {head} SKIP {reason}: {_pick(cp)}")
                continue
            counts['link'] += 1
            old, old_pathway = _pick(cp), app.chosen_pathway or '-'
            if new_pathway and new_pathway != (app.chosen_pathway or '').strip().lower():
                pathway_changes.append(f"  #{app.pk}: {old_pathway} -> {new_pathway}")
            if apply:
                link_offer_course(app, offer, chk)
            self.stdout.write(f"  {head} LINK{'' if apply else ' (would)'}: {old}  ->  {_pick(new_cp)}"
                              f" | pathway {old_pathway}"
                              + (f" -> {new_pathway}" if new_pathway and new_pathway != old_pathway else ''))
        if pathway_changes:
            self.stdout.write(f"\nPATHWAY CHANGES ({len(pathway_changes)}):")
            for line in pathway_changes:
                self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS(
            f"\nOffer course link: {'applied' if apply else 'report only'}; "
            + ', '.join(f'{k}={v}' for k, v in sorted(counts.items()))))
