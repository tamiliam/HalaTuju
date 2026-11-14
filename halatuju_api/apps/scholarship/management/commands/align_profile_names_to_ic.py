"""One-off pass (request #67 scope 3, D5, 2026-11-14): make each student's profile name the name on
their own MyKad, where that is safe.

Since #67 scope 3 every IC read aligns the name as it lands (``identity.align_name_to_ic``, called
from ``vision.ic.run_vision_for_document`` just before the IC lock). A card read EARLIER never went
through that step — application 177's profile still holds a 3-word edit of the 5-word name its
signature and its card agree on. This runs the same rule, once, over every profile's latest live
student IC (``identity.latest_live_ic``): the card's number exactly the typed one, a clean read, and
the card's name the same words as the profile name or one of the profile's signatures (a word glued
or split by OCR does not count).
Anything else is left alone. The signature (``declaration_name``) is never touched.

Dry run by default; ``--apply`` writes (each write leaves an internal ``name_aligned_to_ic``
activity row with the old value, ``source: backfill``). Prints counts and application ids only —
never a name or an NRIC. Idempotent: a second ``--apply`` finds every aligned profile ``already``.

    python manage.py align_profile_names_to_ic            # report only
    python manage.py align_profile_names_to_ic --apply    # write
"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.scholarship import identity
from apps.scholarship.models import ApplicantDocument


class Command(BaseCommand):
    help = "Align each profile's name to its latest live student IC read (request #67 scope 3)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')

    def handle(self, *args, **opts):
        write = bool(opts['apply'])
        profile_ids = (ApplicantDocument.objects
                       .filter(doc_type='ic', superseded_at__isnull=True,
                               application__profile__isnull=False)
                       .exclude(vision_name='')
                       .values_list('application__profile_id', flat=True)
                       .distinct().order_by('application__profile_id'))
        from apps.courses.models import StudentProfile
        counts = Counter()
        aligned_apps = []
        for pid in profile_ids:
            profile = StudentProfile.objects.filter(pk=pid).first()
            doc = identity.latest_live_ic(profile)
            if doc is None:
                continue
            outcome = identity.align_name_to_ic(doc, write=write, source='backfill')
            counts[outcome] += 1
            if outcome == identity.ALIGNED:
                aligned_apps.append(doc.application_id)
        verb = 'aligned' if write else 'would align'
        for app_id in aligned_apps:
            self.stdout.write(f'  app {app_id}: name {verb}')
        detail = ', '.join(f'{k} {v}' for k, v in sorted(counts.items())) or 'nothing to check'
        self.stdout.write(self.style.SUCCESS(
            f'{"" if write else "[dry-run] "}ic name alignment: {sum(counts.values())} checked, '
            f'{len(aligned_apps)} {"aligned" if write else "to align"} ({detail}).'))
