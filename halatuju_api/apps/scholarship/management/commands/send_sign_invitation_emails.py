"""TEMPORARY owner-controlled send of the "your bursary agreement is ready to sign" email.

The follow-up to the award/bank-details email: it invites an AWARDED student to log in and
sign their bursary agreement (Action Centre → comprehension quiz → signing). Like the
award-offer send, this is decoupled from any automatic trigger — the owner sends it
deliberately, to an explicit list of application IDs.

Scope via env (argless cron job 'send-sign-invitation-emails'):
  SIGN_INVITE_APP_IDS  — comma-separated application IDs to email

Only emails an application that actually holds an award (an 'offered'/'active' Sponsorship),
so a stray id can't message a non-awarded student. NO amount, NO sponsor identity.
**Billable: one email per id.** There is NO sent-tracking — re-running re-sends, so list only
the students you intend to notify this run.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship.emails import send_sign_invitation_email
from apps.scholarship.models import ScholarshipApplication, Sponsorship


def _ids(raw):
    return [int(x) for x in str(raw or '').replace(' ', '').split(',') if x.isdigit()]


class Command(BaseCommand):
    help = 'Send the "ready to sign" follow-up email to explicit awarded application IDs (env SIGN_INVITE_APP_IDS).'

    def handle(self, *args, **options):
        app_ids = _ids(getattr(settings, 'SIGN_INVITE_APP_IDS', ''))
        if not app_ids:
            self.stdout.write('SIGN_INVITE_APP_IDS not set — nothing sent.')
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
            ok = send_sign_invitation_email(
                to_email=app.notify_email, applicant_name=name, lang=app.locale or 'en')
            (sent if ok else failed).append(aid if ok else (aid, 'send_failed'))
        self.stdout.write(
            f'Sign-invitation emails. sent={sent} skipped_no_award={skipped_no_award} failed={failed}')
