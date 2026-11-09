"""A student must never be told a decision by silence (audit sprint A2.6: TD-355, TD-357, TD-358).

Two decision emails go out AFTER the status they announce is already visible: the engine's reveal
(`intake.release_decision`: the invitation, or the pre-shortlist decline) and a decline with no
embargo (the org-admin drop, a zero cool-off, the QC reject). A failed send used to leave a status on
her screen and no email, for ever. No column holds "owed", so the state is DERIVED from the stamps the
sends already write, in ONE rule (`untold_reason`), read three ways:

  * the sweep (`retry_unsent_decisions`, run by the decision cron) retries what is `UNSENT`, for
    `decline.RETRY_CAP` after the decision, then stops;
  * the cockpit says so to an officer (`decision_mail` on the admin read, TD-358) — for good after the
    cap, and for a case with no address at all, which no retry can fix;
  * nothing else: the weekly partner mail and the student read keep their own rules.

⚠ The embargoed decline (a pending marker) is retried by its OWN cron, which keeps it hidden from the
student until the email has gone (`decline.release_pending_declines`, TD-349) — never released without
it. Only the OFFICER's reading lives here: once its release is due and no email is stamped, the
cockpit says so, so the officer can tell her another way while she still sees her old stage.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import ScholarshipApplication
from .decline import (
    RETRY_CAP, RETRY_SLOT, _decline_address, _send_decline_for, _told_of_this_decline, retry_slot,
)
from .intake import send_verdict_email

logger = logging.getLogger('apps.scholarship.services')

NO_ADDRESS = 'no_address'     # nothing to send to: an officer must tell her another way
UNSENT = 'unsent'             # an address, no email gone: the sweep retries it within the cap

#: A send this young is probably still in its own request (the QC reject sends after its commit).
RETRY_GRACE = RETRY_SLOT
#: How far back the cockpit looks for an untold decision: older rows pre-date these stamps and would
#: only be noise on a closed file.
NOT_TOLD_LOOKBACK = timedelta(days=90)


def _decided_at(app, now):
    """`(when, address)` of the decision email this application is owed, or None when it is owed none.

    Two shapes, told apart by `rejected_at` (the engine's reveal never sets it; every decline that
    can carry an email does — `decline._record_reject`):
      * a decline: `rejected`, not under reopen, and no email stamped for THIS decline
        (`_told_of_this_decline`, the rule the cancel also reads). An embargoed one (a pending marker)
        counts once its release is due (`decline_due_at` + `RETRY_GRACE`): she still sees nothing, the
        officer sees it;
      * an engine reveal: the status IS the verdict, released, and `decision_email_sent_at` empty.
    """
    if app.status == 'rejected' and app.rejected_at:
        if app.decision_reopened_at is not None or _told_of_this_decline(app):
            return None
        if app.pending_rejection_category or app.decline_due_at:
            if (not app.pending_rejection_category or app.decline_due_at is None
                    or now - app.decline_due_at < RETRY_GRACE):
                return None
            return app.decline_due_at, _decline_address(app)
        return app.rejected_at, _decline_address(app)
    if (app.decision_released_at and app.verdict and app.status == app.verdict
            and not app.rejected_at and app.decision_email_sent_at is None):
        return app.decision_released_at, app.notify_email or ''
    return None


def untold_reason(app, now=None):
    """'' when she was told (or owes no email), else `NO_ADDRESS` or `UNSENT` (see the module)."""
    now = now or timezone.now()
    owed = _decided_at(app, now)
    if owed is None:
        return ''
    decided, address = owed
    # An embargoed decline still unsent is never aged out: it stays hidden from her, so the officer's
    # banner must not vanish while it does.
    if not app.pending_rejection_category and now - decided > NOT_TOLD_LOOKBACK:
        return ''
    return UNSENT if address else NO_ADDRESS


def _owed_pks(now):
    """Pks that MAY be owed an email inside the retry window (the rule re-checks each, locked)."""
    low, high = now - RETRY_CAP - RETRY_SLOT / 2, now - RETRY_SLOT / 2
    qs = ScholarshipApplication.objects
    declines = qs.filter(status='rejected', rejected_at__gte=low, rejected_at__lte=high,
                         pending_rejection_category='', decline_due_at__isnull=True)
    reveals = qs.filter(status__in=('shortlisted', 'rejected'), rejected_at__isnull=True,
                        decision_released_at__gte=low, decision_released_at__lte=high,
                        decision_email_sent_at__isnull=True)
    return (list(declines.values_list('pk', flat=True))
            + list(reveals.values_list('pk', flat=True)))


def retry_unsent_decisions(now=None):
    """Send each decision email that failed, on the `decline.retry_slot` schedule (15 min, 1 h, 6 h, 24 h,
    48 h, 72 h after the decision, each slot centred on its offset, so a failing send is metered
    about six times), then stop.
    Returns `{'sent': n, 'failed': n}`. One application's trouble never stops the rest: each is
    claimed under a row lock and RE-READ (a cancel, a reopen or another run may have moved it)."""
    now = now or timezone.now()
    sent = failed = 0
    for pk in _owed_pks(now):
        try:
            with transaction.atomic():
                app = (ScholarshipApplication.objects.select_for_update(skip_locked=True, of=('self',))
                       .select_related('cohort', 'profile').filter(pk=pk).first())
                # `of=('self',)`: the joins are nullable, and PostgreSQL refuses FOR UPDATE on those.
                if (app is None or app.pending_rejection_category
                        or untold_reason(app, now) != UNSENT
                        or not retry_slot(now - _decided_at(app, now)[0])):
                    continue
                went = (_send_decline_for(app) if app.status == 'rejected' and app.rejected_at
                        else send_verdict_email(app))
            sent, failed = sent + went, failed + (not went)
            if not went:
                logger.error('retry_unsent_decisions: app %s — the decision email did not go; '
                             'retried until %s after the decision.', pk, RETRY_CAP)
        except Exception:
            failed += 1
            logger.error('retry_unsent_decisions: app %s — the retry raised.', pk, exc_info=True)
    return {'sent': sent, 'failed': failed}

