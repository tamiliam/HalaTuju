"""TEMPORARY owner-controlled send of the award good-news email.

Awarding is decoupled from the email (``AWARD_OFFER_EMAIL_ENABLED`` default OFF): a sponsor
pressing "Support", or the batch, funds + flips a student to 'awarded' but sends NOTHING. The
owner then sends the emails deliberately, here — to an explicit list of application IDs.

Scope via env (argless cron job 'send-award-offer-emails'):
  AWARD_EMAIL_APP_IDS  — comma-separated application IDs to email

Only emails an application that actually holds an award (an 'offered'/'active' Sponsorship), so a
stray id can't message a non-awarded student. The email states no amount and no sponsor identity
(good news + add bank details + await the formal offer). **Billable: one email per id.** There is
NO sent-tracking — re-running re-sends, so list only the students you intend to notify this run.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship.emails import send_award_offer_email
from apps.scholarship.models import ScholarshipApplication, Sponsorship


def _ids(raw):
    return [int(x) for x in str(raw or '').replace(' ', '').split(',') if x.isdigit()]


class Command(BaseCommand):
    help = 'Send the award good-news email to explicit awarded application IDs (env AWARD_EMAIL_APP_IDS).'

    def handle(self, *args, **options):
        app_ids = _ids(getattr(settings, 'AWARD_EMAIL_APP_IDS', ''))
        if not app_ids:
            self.stdout.write('AWARD_EMAIL_APP_IDS not set — nothing sent.')
            return
        sent, skipped_no_award, failed = [], [], []
        for aid in app_ids:
            app = (ScholarshipApplication.objects.filter(id=aid)
                   .select_related('profile').first())
            if app is None:
                failed.append((aid, 'not_found'))
                continue
            award = app.sponsorships.filter(status__in=Sponsorship.HOLDING).first()
            if award is None:
                skipped_no_award.append(aid)
                continue
            name = getattr(app.profile, 'name', '') if app.profile else ''
            ok = send_award_offer_email(
                to_email=app.notify_email, applicant_name=name, lang=app.locale or 'en')
            # Stamp the award as emailed so the cool-off cron never re-sends it (idempotent
            # across the manual force-send and the scheduled release).
            from django.utils import timezone
            award.offer_emailed_at = timezone.now()
            award.save(update_fields=['offer_emailed_at', 'updated_at'])
            (sent if ok else failed).append(aid if ok else (aid, 'send_failed'))
        self.stdout.write(
            f'Award-offer emails. sent={sent} skipped_no_award={skipped_no_award} failed={failed}')
