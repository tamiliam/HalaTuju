"""Owner-controlled send of the Vircle eWallet setup email.

This is the follow-up to the award good-news email (which told students to sit tight). It says:
the bursary is paid through Vircle, install it, then confirm in your Action Centre. The
installation-guide PDF rides along as an attachment, and sending CREATES the student's
Action-Centre task, so the task appears exactly for the people who were emailed.

Scope via env (argless cron job 'send-vircle-install-emails'):
  VIRCLE_EMAIL_APP_IDS  — comma-separated application IDs to email

Guards, in order:
  * the application must be awarded/active (a stray id can't message a non-awarded student);
  * an id that already has the task is skipped (that's the idempotence — unlike the award-email
    command, re-running does NOT re-send).

A student born AFTER 2008 IS emailed. Vircle's age gate is by birth year, so they can't hold an
account in their own name — but they aren't stuck: a parent registers, the student is added to
that account as a child, and the email tells them to write to help@ so we can arrange it. They are
reported here (and labelled on the relay sheet) so you know to expect them by email rather than
through the normal in-app confirmation.

**Billable: one email per id.** Finishes by rewriting the relay sheet so it always reflects who
has been asked. Use --dry-run to see exactly who would be emailed, without sending.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship.emails import send_vircle_install_email
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.resolution import VIRCLE_CODE, VIRCLE_SETUP_STATES
from apps.scholarship.vircle import (birth_year_from_nric, can_register,
                                     raise_setup_task, sync_relay_sheet)


def _ids(raw):
    return [int(x) for x in str(raw or '').replace(' ', '').split(',') if x.isdigit()]


class Command(BaseCommand):
    help = ('Send the Vircle setup email (guide attached) + raise the Action-Centre confirmation '
            'task, for explicit awarded application IDs (env VIRCLE_EMAIL_APP_IDS).')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Report who would be emailed; send nothing, create nothing.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        app_ids = _ids(getattr(settings, 'VIRCLE_EMAIL_APP_IDS', ''))
        if not app_ids:
            self.stdout.write('VIRCLE_EMAIL_APP_IDS not set — nothing sent.')
            return

        sent, already, via_parent, not_awarded, failed = [], [], [], [], []
        for aid in app_ids:
            app = (ScholarshipApplication.objects.filter(id=aid)
                   .select_related('profile').first())
            if app is None:
                failed.append((aid, 'not_found'))
                continue
            if app.status not in VIRCLE_SETUP_STATES:
                not_awarded.append((aid, app.status))
                continue
            if not can_register(app):
                # Emailed like everyone else — the copy tells them a parent must register and to
                # write to help@. Recorded here only so you know who to expect.
                via_parent.append((aid, birth_year_from_nric(getattr(app.profile, 'nric', ''))))
            if app.resolution_items.filter(code=VIRCLE_CODE).exists():
                already.append(aid)
                continue
            if dry:
                sent.append(aid)
                continue
            name = getattr(app.profile, 'name', '') if app.profile else ''
            ok = send_vircle_install_email(
                to_email=app.notify_email, applicant_name=name, lang=app.locale or 'en')
            if not ok:
                failed.append((aid, 'send_failed'))
                continue
            # Raise the task ONLY on a successful send — a student who never got the email must
            # not find a mystery task waiting in their Action Centre.
            raise_setup_task(app)
            sent.append(aid)

        prefix = '[DRY RUN] would send' if dry else 'sent'
        self.stdout.write(
            f'Vircle setup emails. {prefix}={sent} already_asked={already} '
            f'not_awarded={not_awarded} failed={failed}')
        if via_parent:
            self.stdout.write(self.style.WARNING(
                f'BORN AFTER 2008 — emailed, but a PARENT must register and the student is added '
                f'as a child: {via_parent}. They were told to write to help@ — expect them there, '
                f'not through the in-app confirmation.'))
        if not dry:
            url = sync_relay_sheet()
            self.stdout.write(f'Relay sheet: {url}' if url
                              else 'Relay sheet: not written (Drive unreachable or unconfigured).')
