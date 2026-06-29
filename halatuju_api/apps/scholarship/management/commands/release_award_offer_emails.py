"""Cool-off release of the award good-news email.

A sponsor award does not email inline; this command — run hourly by the scheduler (job
``release-award-offer-emails``) — sends the email once the award has been held for
``AWARD_OFFER_EMAIL_COOLOFF_HOURS`` (default 24), giving a window to reconsider. Cancelling
the award before then stops it (only offered/active awards are sent). Idempotent via
``Sponsorship.offer_emailed_at``. Billable (one email per due award)."""
from django.core.management.base import BaseCommand

from apps.scholarship import sponsorship as svc


class Command(BaseCommand):
    help = 'Send award good-news emails whose cool-off window has elapsed (idempotent).'

    def handle(self, *args, **options):
        sent = svc.release_award_offer_emails()
        self.stdout.write(f'Award-offer cool-off release: sent={sent}')
