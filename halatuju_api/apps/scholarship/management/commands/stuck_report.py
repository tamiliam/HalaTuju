"""Read-only diagnostic: why can't a shortlisted student submit yet?

Prints the exact `consent_blockers` for every application that is `shortlisted` and NOT yet
submitted (`profile_completed_at IS NULL`) — the same list the consent gate enforces, so an
owner can see per-student why the submit button is refused (a doc gap, a mismatch, an
offer-not-official, an incomplete section) rather than guessing.

READ-ONLY: computes verdicts from STORED vision fields; never re-extracts, never writes.

    python manage.py stuck_report                 # all stuck shortlisted apps
    python manage.py stuck_report --ids 5,19,28   # just these
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import consent_blockers


class Command(BaseCommand):
    help = "Report consent_blockers for shortlisted applications not yet submitted (read-only)."

    def add_arguments(self, parser):
        parser.add_argument('--ids', default='',
                            help='Comma-separated application ids to limit the report to.')

    def handle(self, *args, **opts):
        qs = ScholarshipApplication.objects.filter(
            status='shortlisted', profile_completed_at__isnull=True)
        ids = [int(x) for x in (opts['ids'] or '').split(',') if x.strip()]
        if ids:
            qs = qs.filter(id__in=ids)
        ready = 0
        for a in qs.select_related('profile').order_by('id'):
            name = (getattr(a.profile, 'name', '') or '').strip()
            blockers = consent_blockers(a)
            if not blockers:
                ready += 1
                self.stdout.write(f"{a.id}\t{name}\tREADY")
            else:
                self.stdout.write(f"{a.id}\t{name}\t{','.join(blockers)}")
        self.stdout.write(self.style.SUCCESS(f"\n{ready} ready to submit (no blockers)."))
