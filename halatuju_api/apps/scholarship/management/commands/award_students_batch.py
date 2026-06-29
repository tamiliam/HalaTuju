"""Admin batch-award: award a list of pooled students to one sponsor via the REAL
award path, so the trail is correct and the students are notified.

Each application is put through ``sponsorship.award_and_notify`` — which creates the
'offered' Sponsorship (holding the amount against the sponsor's wallet), flips the
application to 'awarded', and sends the good-news / add-bank-details / await-offer
email (no amount, no sponsor identity). This is the same path the sponsor's "Support"
button uses, so a batch award and a click award are identical.

Scoped via env (so it runs through the argless internal cron endpoint, job
'award-students-batch'):
  SEED_SPONSOR_ID     — the Sponsor.id to award from (must have enough wallet balance)
  SEED_AWARD_APP_IDS  — comma-separated ScholarshipApplication IDs to award

Safe to leave wired: a no-op unless BOTH env vars are set. Per application it skips an
already-held / not-fundable one (reported) rather than erroring. **Billable side effect:
one email per successful award** — set the env, run once, then clear it.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship import sponsorship as svc
from apps.scholarship.models import ScholarshipApplication, Sponsor


def _ids(raw):
    return [int(x) for x in str(raw or '').replace(' ', '').split(',') if x.isdigit()]


class Command(BaseCommand):
    help = 'Batch-award listed applications to a sponsor (env-scoped; real award_and_notify path).'

    def handle(self, *args, **options):
        sponsor_id = str(getattr(settings, 'SEED_SPONSOR_ID', '') or '').strip()
        app_ids = _ids(getattr(settings, 'SEED_AWARD_APP_IDS', ''))
        if not sponsor_id.isdigit() or not app_ids:
            self.stdout.write('SEED_SPONSOR_ID / SEED_AWARD_APP_IDS not set — nothing done.')
            return
        sponsor = Sponsor.objects.filter(id=int(sponsor_id)).first()
        if sponsor is None:
            self.stdout.write(f'Sponsor {sponsor_id} not found — nothing done.')
            return

        awarded, skipped, failed = [], [], []
        for aid in app_ids:
            app = ScholarshipApplication.objects.filter(id=aid).select_related('profile', 'cohort').first()
            if app is None:
                failed.append((aid, 'not_found'))
                continue
            try:
                svc.award_and_notify(sponsor, app)
                awarded.append(aid)
            except svc.SponsorshipError as e:
                # not_fundable / insufficient_balance etc. — report, don't abort the batch.
                skipped.append((aid, e.code))

        bal = svc.sponsor_balance(sponsor)
        self.stdout.write(
            f'Batch award (sponsor {sponsor_id}). awarded={awarded} skipped={skipped} '
            f'failed={failed} balance_left={bal}')
