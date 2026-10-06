"""Manual closure (the terminal step) — post-award lifecycle S6, widened by TD-352.

An application is CLOSED by hand by an officer, with a ``closure_reason`` recorded. Closure is
deliberately manual (owner decisions): there is no auto-close on graduation or on the last
tranche, and no clock on a stalled case — a human confirms the relationship has ended and WHY.

``closure_reason`` distinguishes the positive endings (``graduated`` = finished the programme;
``completed`` = the contractual support period was fulfilled, the programme may continue) from
the negative ones (``withdrawn`` / ``lapsed`` / ``terminated`` / ``stalled``).

TD-352 (owner ruling, option A, 2026-10-06): an application in play blocks a new one
(``services/apply_gate.py``), so a case that has STALLED — the student stopped answering, or the
case stopped moving — would hold her place for ever. An officer may now close it from ANY in-play
status, and once closed she may apply again (``closed`` is a FINISHED status for the apply gate).

Closure is terminal within this lifecycle (no reopen path here). The graduation thank-you relay is
re-gated to remain available AFTER closure (see ``in_programme`` — ``submit_graduation_message``
accepts ``closed`` too), so a graduated student can still write to their sponsor once the file is
closed.
"""
import logging

from django.db import transaction
from django.utils import timezone

from . import usage as _usage
from .emails import send_application_closed_email
from .models import Disbursement, ScholarshipApplication, Sponsorship
from .services.apply_gate import IN_PLAY_STATUSES

#: ⚠ THE MODULE NAME, WRITTEN OUT (the `services/decline.py` convention): the AUDIT line's logger
#: is part of what the tests pin, so it must not move if this file ever does.
logger = logging.getLogger('apps.scholarship.closure')

#: A close is valid from EVERY in-play status — the same set the apply gate treats as holding the
#: student's place. ONE definition: it is imported, never copied (test_closure asserts the identity).
CLOSEABLE_FROM = IN_PLAY_STATUSES

#: Before a funder has committed. A close here frees the student to apply again and emails her.
PRE_AWARD_STATUSES = frozenset({
    'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'recommended',
})
#: A funder has committed (awarded) or the student is funded (active / maintenance).
POST_AWARD_STATUSES = frozenset({'awarded', 'active', 'maintenance'})

#: Statuses that carry a live sponsorship BY NATURE: the agreement has bound and the student is
#: funded. The pre-existing funded close (S6) has always closed these with the sponsorship left as
#: it is, and still does — the sponsorship refusal below does not apply to them.
FUNDED_STATUSES = frozenset({'active', 'maintenance'})

#: The reasons-by-stage table (the web mirrors it in ``src/lib/closeOffer.ts``; a drift test reads
#: this file). Before an award only "no movement" or "the student withdrew" can be true; the
#: post-award reasons (graduated, completed, lapsed, terminated) describe a funded relationship.
PRE_AWARD_REASONS = ('stalled', 'withdrawn')
POST_AWARD_REASONS = ('graduated', 'completed', 'withdrawn', 'lapsed', 'terminated', 'stalled')

# The valid closure reasons (mirror ScholarshipApplication.CLOSURE_REASONS).
VALID_REASONS = {code for code, _label in ScholarshipApplication.CLOSURE_REASONS}

# Positive closures (finished well) vs negative — used for student/sponsor copy.
POSITIVE_REASONS = ('graduated', 'completed')

#: The sentence for ``sponsorship_open`` (the web shows its own translated copy of it).
SPONSORSHIP_OPEN_MESSAGE = (
    "This application holds a sponsor's offer or paid money. It cannot be closed here. "
    '(Releasing an awarded student is an owner decision — TD-366.)')


class ClosureError(Exception):
    """Raised by close_application with a machine code for the view: 'not_closeable',
    'bad_reason', 'reason_not_allowed' or 'sponsorship_open'."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


def reasons_for(status):
    """The closure reasons an officer may record from ``status`` — () when it cannot be closed."""
    if status in PRE_AWARD_STATUSES:
        return PRE_AWARD_REASONS
    if status in POST_AWARD_STATUSES:
        return POST_AWARD_REASONS
    return ()


def has_live_money(application):
    """True when ``application`` carries a LIVE sponsorship: a ``Sponsorship`` row whose status is
    in ``Sponsorship.HOLDING`` ('offered' — the offer is out, not yet cancelled / lapsed /
    declined; or 'active' — accepted), OR any ``Disbursement`` whose status is in
    ``Disbursement.PAID`` ('released' — money paid out, e.g. a grandfathered student paid before
    her in-app acceptance). 'cancelled' / 'lapsed' sponsorships and scheduled / due / withheld /
    returned tranches do not count."""
    return (application.sponsorships.filter(status__in=Sponsorship.HOLDING).exists()
            or application.disbursements.filter(status__in=Disbursement.PAID).exists())


def _send_closed_email(application, closure_reason):
    """Best-effort: tell the student her application is closed and she may start again. The
    sender answers False on failure (or a missing address); that is logged, never raised."""
    name = getattr(application.profile, 'name', '') if application.profile else ''
    with _usage.usage_context(application=application):
        sent = send_application_closed_email(
            to_email=application.notify_email, applicant_name=name,
            programme_name=application.cohort.name, lang=application.locale,
            closure_reason=closure_reason)
    if not sent:
        logger.warning('close_application: app %s is closed but the closed email did not go '
                       '(no address, or the send failed) — tell the student by hand.',
                       application.id)
    return sent


def _release_interview(row):
    """A pre-award close must not leave an interview live: a BOOKED one is voided (the Meet event
    cancelled, the booking cleared, the reviewer told) and any PROPOSED times are withdrawn, so
    the student can neither attend nor book one. The existing teardown
    (`scheduling.release_for_unassign`), WITHOUT its student notice — the close emails her itself."""
    from . import scheduling
    if row.interview_status == 'booked' or row.interview_slots.filter(is_active=True).exists():
        scheduling.release_for_unassign(
            row, student_notice=False, reason='Application closed by an officer',
            reviewer_reason='The application was closed by an officer.')


def close_application(application, *, closure_reason, by_email=''):
    """Manually close an application. Stamps closed_at / closed_by, flips status to 'closed' and
    returns the application. Checked in this order, each a ``ClosureError`` code:

      1. ``not_closeable`` — the status is not in CLOSEABLE_FROM (every in-play status). A finished
         application (rejected / withdrawn / closed / expired) cannot be closed again.
      2. ``bad_reason`` — blank, or not one of ``CLOSURE_REASONS``.
      3. ``reason_not_allowed`` — the reason does not fit the stage. The table:

           from submitted / shortlisted / profile_complete / interviewing / interviewed /
                recommended                       -> stalled, withdrawn
           from awarded / active / maintenance    -> graduated, completed, withdrawn, lapsed,
                                                     terminated, stalled

      4. ``sponsorship_open`` — ONE DOOR PER JOB. From any status OTHER than active / maintenance,
         the close REFUSES while ``has_live_money`` holds (a HOLDING sponsorship, or a released
         tranche). Closing never cancels or lapses a sponsorship. In practice an 'awarded'
         application always carries a HOLDING sponsorship (``sponsorship.fund_student`` writes
         both), so an awarded case CANNOT be closed here — and there is today no admin door that
         releases it either once the offer email has gone (TD-366, an owner decision: the sponsor's
         ``cancel_offer`` refuses after notification, the lapse runs only on an armed deadline, the
         contractual reject is barred from 'awarded', and released tranches keep the money live).
         The cockpit therefore does not offer the Close card at 'awarded' at all. Active and
         maintenance carry a live sponsorship by nature and close exactly as before (S6): no
         money side effect — the disbursement ledger is historical, and
         ``disbursement.release_tranche`` refuses to pay a closed student, so a leftover
         scheduled tranche simply becomes un-releasable.

    The status is re-read under a row lock (``select_for_update``; a no-op on SQLite) so the
    checks judge the row as it is now, and the in-memory ``application`` is refreshed from the
    database afterwards. A PRE-award close also releases any interview inside the same
    transaction (``_release_interview``: a booking voided, proposed times withdrawn).

    After the write: one AUDIT log line naming the status it was closed FROM (no DB field holds
    it); then, for a close from a PRE-award status only, the student is sent
    ``send_application_closed_email`` in its OFFICER variant (``closure_reason`` given: "closed by
    our team … you may apply again in a later round" — never the auto-expiry "not completed in
    time"), best-effort, with a WARNING when it answers False. No email from awarded / active / maintenance: that notice invites a fresh application
    and does not fit a student who was funded or holds an award — her closure is told through the
    in-programme page as before. The email is sent OUTSIDE the transaction, so it never goes for
    a close that rolled back (the one caller, the admin view, is not inside an outer atomic).
    """
    if application is None or application.pk is None:
        raise ClosureError('not_closeable')
    with transaction.atomic():
        row = (ScholarshipApplication.objects.select_for_update()
               .filter(pk=application.pk).first())
        if row is None or row.status not in CLOSEABLE_FROM:
            raise ClosureError('not_closeable')
        closed_from = row.status
        if closure_reason not in VALID_REASONS:
            raise ClosureError('bad_reason')
        if closure_reason not in reasons_for(closed_from):
            raise ClosureError('reason_not_allowed')
        if closed_from not in FUNDED_STATUSES and has_live_money(row):
            raise ClosureError('sponsorship_open', SPONSORSHIP_OPEN_MESSAGE)
        row.status = 'closed'
        row.closure_reason = closure_reason
        row.closed_at = timezone.now()
        row.closed_by = (by_email or '')[:254]
        row.save(update_fields=['status', 'closure_reason', 'closed_at', 'closed_by'])
        if closed_from in PRE_AWARD_STATUSES:
            _release_interview(row)
    application.refresh_from_db()
    logger.info('AUDIT application_closed app_id=%s from=%s reason=%s by=%s',
                application.id, closed_from, closure_reason, by_email or '?')
    if closed_from in PRE_AWARD_STATUSES:
        _send_closed_email(application, closure_reason)
    return application
