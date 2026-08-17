"""One-off repair (2026-08-18): credit a submitted interview to the person who conducted it.

Until TD-216 (`01cb0c77`, 2026-08-13) ``AdminInterviewDraftView`` stamped
``InterviewSession.interviewer`` at ROW CREATION::

    session = InterviewSession(application=app, interviewer=admin, started_at=...)
    ...
    if session.interviewer_id is None:      # never true again
        session.interviewer = admin

So the FIRST person to touch a case's interview draft owned the credit permanently, and the
reviewer who actually wrote the findings days later could not take it back. During the July
triage sweep the owner opened case after case as super and deleted one agenda item apiece; each
click created the row and claimed the interview. Application #137 is the shape exactly: its
session's only finding is ``{"device_in_funding": {"verdict": "deleted"}}`` stamped 13 July,
while the findings text, the submit and the verdict are all 15 July and all somebody else's.

TD-216 fixed the rule going forward. It is not retroactive; this repairs the record behind it.

⚠ **THE FENCE IS THE CURRENT HOLDER, NOT THE DIVERGENCE.** It is perfectly legitimate for the
interviewer and the verdict-recorder to be different people — a reviewer interviews, a QC or the
owner records the decision (applications 12 and 51 are exactly that, and their credit is RIGHT).
Rewriting on divergence alone would destroy those. What marks the defect is that the credit sits
with one of the two accounts that ran the sweep, so those are the only rows in scope. Widening
`--from-email` past them re-opens that hole — don't, without reading this paragraph first.

⚠ **THE TARGET IS THE ASSIGNED REVIEWER FIRST, the verdict-recorder only as a fallback.**
Application #13 is why the order matters and not the other way round: Balan held the case and
conducted the interview, the owner recorded the verdict. Keying on the verdict would credit the
owner again — the very thing being repaired. The fallback exists for a case nobody was ever
assigned (#137, acted on by an org_admin), where the verdict-recorder is the only name on file.

Rows whose target resolves to the account already credited are left alone, so an interview the
owner genuinely did conduct (#31, #67, #84, #87) is a no-op rather than a special case.

``updated_at`` is deliberately NOT bumped (``update_fields``) — correcting a credit is not an
edit of the interview, and a moved timestamp would misreport when the findings were last written.

Idempotent: a repaired row no longer matches the fence, so a second run finds nothing.

    python manage.py repair_interview_credit                    # report only
    python manage.py repair_interview_credit --apply            # write
    python manage.py repair_interview_credit --app-ids 13,137   # scope to known ids
"""
import logging

from django.core.management.base import BaseCommand

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import InterviewSession

logger = logging.getLogger(__name__)

#: The two accounts that ran the July triage sweep — both named "Ve. Elanjelian", which is why
#: the screen could never show which one (or that neither had conducted the interview).
DEFAULT_FROM_EMAILS = ('tamiliam@gmail.com', 'elanjelian@me.com')


def intended_interviewer(app):
    """Who should be credited with this application's interview, and on what evidence.

    Returns ``(PartnerAdmin | None, reason)``. See the module docstring for why `assigned`
    outranks `verdict` — reversing them re-credits the owner on application #13.
    """
    if app.assigned_to_id:
        return app.assigned_to, 'assigned'
    decided_by = (app.verdict_decided_by or '').strip()
    if decided_by:
        admin = PartnerAdmin.objects.filter(email__iexact=decided_by).first()
        if admin:
            return admin, 'verdict'
        return None, f'no admin row for verdict_decided_by={decided_by!r}'
    return None, 'unassigned and no verdict recorded'


class Command(BaseCommand):
    help = 'Re-credit submitted interviews stamped to whoever opened the draft, not who wrote it.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the corrections (default: report only).')
        parser.add_argument('--from-email', action='append', default=None,
                            help='Only re-credit sessions currently held by this email '
                                 '(repeatable). Read the module docstring before widening.')
        parser.add_argument('--app-ids', default='',
                            help='Comma-separated application ids to limit the run to.')

    def handle(self, *args, **opts):
        apply_ = opts['apply']
        from_emails = opts['from_email'] or list(DEFAULT_FROM_EMAILS)

        qs = (InterviewSession.objects
              .filter(status='submitted', interviewer__email__in=from_emails)
              .select_related('interviewer', 'application', 'application__assigned_to')
              .order_by('application_id'))
        scoped = (opts['app_ids'] or '').replace(' ', '')
        if scoped:
            ids = [int(x) for x in scoped.split(',') if x]
            qs = qs.filter(application_id__in=ids)
            self.stdout.write(f'scoped to applications {ids}')

        recredited = unchanged = skipped = 0
        for session in qs:
            app = session.application
            held_by = session.interviewer.email
            target, reason = intended_interviewer(app)

            if target is None:
                self.stdout.write(self.style.WARNING(
                    f'  app {app.id}: SKIPPED — {reason}'))
                skipped += 1
                continue
            if target.pk == session.interviewer_id:
                self.stdout.write(f'  app {app.id}: no change — {held_by} is the {reason}')
                unchanged += 1
                continue

            self.stdout.write(f'  app {app.id}: {held_by} -> {target.email} '
                              f'({target.name}, by {reason})')
            if apply_:
                session.interviewer = target
                session.save(update_fields=['interviewer'])
                logger.info('AUDIT interview_credit_repair session=%s app=%s old=%s new=%s '
                            'basis=%s', session.pk, app.id, held_by, target.email, reason)
            recredited += 1

        self.stdout.write(self.style.SUCCESS(
            f'{"" if apply_ else "[report only] "}interview credit: {recredited} re-credited, '
            f'{unchanged} already correct, {skipped} skipped.'))
