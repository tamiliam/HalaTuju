"""TD-252 — lapse every armed award offer whose accept deadline has passed.

Schedule DAILY (Cloud Scheduler → the cron endpoint, job ``lapse-expired-offers``). A thin
wrapper: every rule lives in ``sponsorship.lapse_expired_offers`` — ARMED offers only (a NULL
``accept_deadline`` is never a candidate), and an application with released money is REFUSED
and returned in ``flagged``, never lapsed. A lapsed offer returns its amount to the sponsor's
balance and the student to the pool. Idempotent: a second run finds nothing new to lapse.

    python manage.py lapse_expired_offers
"""
from django.core.management.base import BaseCommand

from apps.scholarship.sponsorship import lapse_expired_offers


class Command(BaseCommand):
    help = "Lapse armed award offers past their accept deadline (paid applications are flagged, never lapsed)."

    def handle(self, *args, **options):
        lapsed_ids = []
        result = lapse_expired_offers(lapsed_ids=lapsed_ids)
        self.stdout.write(
            f"lapse_expired_offers: lapsed={result['lapsed']} {lapsed_ids} "
            f"flagged={len(result['flagged'])} {result['flagged']}")
