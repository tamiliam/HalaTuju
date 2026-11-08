"""The assignment's two emails, sent after the request (A2.3, TD-519).

Before A2.3, ``services.assignment.assign_reviewer`` sent the reviewer's "you have a new applicant"
email and the student's "who will interview you" email INSIDE the assign request, one network round
trip each, so the officer waited on Brevo (assign p95 about 45 s with the first-assign profile
draft). Now the assignment writes its ``AssignmentEvent`` queued (``notify_state='pending'``) in the
same insert, and the ``assign-emails`` cron (``send_pending_assign_emails``, every 15 minutes) sends
both, with the SAME gates and the SAME content (moved verbatim below):

* **Who gets mail is unchanged.** The reviewer on every real assignment (never an unassign — that
  writes no queued row); the student only while ``STUDENT_ASSIGNMENT_EMAIL_ENABLED`` is on AND the
  organisation's own switch allows ``interviewer_assigned`` — both asked at SEND time, as late as
  the gate can be asked. An event whose reviewer no longer holds the case when the cron runs
  (reassigned or unassigned since) is closed unsent: only the current reviewer is mailed.
* **The review-by date is the assignment's.** It is computed from the case's ``assigned_at`` while
  this event is still the case's assignment, else from the event's own time — never from when the
  cron happened to run.
* **Claim before the send; each email once.** A conditional UPDATE claims the event and counts the
  attempt, so two overlapping runs never send twice. Each email is tried once (a failed one is
  logged, as the inline send's best-effort was meant to be); only a run killed mid-send leaves a
  claim, which is claimable again after ``STALE_CLAIM``; after ``MAX_ATTEMPTS`` it is 'failed'. A row the old image wrote reads '' and is never sent (it
  already sent inline).
"""
import logging
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from .models import AssignmentEvent

logger = logging.getLogger(__name__)

PENDING = 'pending'
FAILED = 'failed'
MAX_ATTEMPTS = 3
STALE_CLAIM = timedelta(minutes=10)
#: Per cron run: two short Brevo calls each, well inside the cron endpoint's 300 s.
BATCH = 50


def send_assignment_emails(event):
    """The two emails for one assignment. MOVED VERBATIM from ``assign_reviewer`` (A2.3); only the
    reviewer, the case and the assignment time now come from ``event``."""
    from django.conf import settings as _settings
    from . import usage as _usage
    application = event.application
    reviewer = event.to_admin
    if reviewer is None:
        return
    assigned_at = (application.assigned_at if application.assigned_to_id == reviewer.id
                   and application.assigned_at else event.created_at)
    # Notify the reviewer they have a new applicant to review. Only on an actual
    # assignment (not an unassign); the no-op short-circuit in assign_reviewer means an unchanged
    # assignee never queues a row, so we never re-send. Best-effort.
    if getattr(reviewer, 'email', ''):
        from . import review_sla
        from .emails import send_reviewer_assigned_email
        from .pool import pool_ref
        # Per-organisation SLA (Org Config Sprint C). This read used to carry its own dead
        # default of 7 against the sweep's 10 — base.py always defined the setting so it never
        # fired, but the review-by date in this email and the nudge sweep's due date now come
        # from the ONE delegation and cannot drift.
        # ⚠ AND SINCE 2026-09-15 THE ARITHMETIC IS SHARED TOO, not just the number: `review_sla`
        # is the one home for `assigned_at + sla`, so the date a reviewer is promised here is
        # computed by the same line the nudge sweep and the Overview's bands use.
        review_by = review_sla.review_due(assigned_at, application.owning_organisation).date()
        try:   # each email on its own: a failed one never re-sends the other on a retry
            with _usage.usage_context(application=application):
                send_reviewer_assigned_email(
                    to_email=reviewer.email,
                    reviewer_name=getattr(reviewer, 'name', ''),
                    ref=pool_ref(application.id),
                    programme=getattr(application.cohort, 'name', '') if application.cohort else '',
                    review_by=review_by.strftime('%d %b %Y'),
                )
        except Exception:
            logger.warning('reviewer assigned email failed event=%s', event.id, exc_info=True)

    # F7: advance notice to the STUDENT — who will interview them + how, so they expect the
    # call and pick up. Gated by STUDENT_ASSIGNMENT_EMAIL_ENABLED (OFF until reviewers give
    # non-objection to sharing their contact). The reviewer's phone is included unless they
    # opted out (ReviewerProfile.share_phone_with_students). Best-effort; never blocks assignment.
    from . import student_email_catalogue as _catalogue   # S6a: the organisation's own switch
    if (getattr(_settings, 'STUDENT_ASSIGNMENT_EMAIL_ENABLED', False)
            and _catalogue.may_send(application, 'interviewer_assigned')):
        from .emails import english_only_email, send_student_assigned_reviewer_email
        profile = application.profile
        student_email = (application.notify_email
                         or getattr(profile, 'contact_email', '') or '')
        try:
            with _usage.usage_context(application=application):
                send_student_assigned_reviewer_email(
                    student_email,
                    student_name=getattr(profile, 'name', '') if profile else '',
                    reviewer_name=getattr(reviewer, 'name', ''),
                    english_only=english_only_email(application),
                )
        except Exception:
            logger.warning('student assigned email failed event=%s', event.id, exc_info=True)


# ── The queue ────────────────────────────────────────────────────────────────

def _notify_claimable(now):
    return Q(notify_claimed_at__isnull=True) | Q(notify_claimed_at__lt=now - STALE_CLAIM)


def _claim_notify(event_id, now):
    return AssignmentEvent.objects.filter(
        _notify_claimable(now), pk=event_id, notify_state=PENDING, notify_attempts__lt=MAX_ATTEMPTS,
    ).update(notify_claimed_at=now, notify_attempts=F('notify_attempts') + 1) == 1


def _finish_notify(event_id, token, state=''):
    AssignmentEvent.objects.filter(pk=event_id, notify_claimed_at=token).update(
        notify_state=state, notify_claimed_at=None)


def send_one(event_id):
    """Claim and send one event. Returns 'sent', 'stale' (the case has another reviewer or none
    now: closed unsent), 'retry', 'failed' or 'not_claimed'."""
    now = timezone.now()
    if not _claim_notify(event_id, now):
        return 'not_claimed'
    event = (AssignmentEvent.objects
             .select_related('application__cohort', 'application__profile', 'to_admin')
             .get(pk=event_id))
    if event.application.assigned_to_id != event.to_admin_id:
        # Reassigned or unassigned before the cron ran: this reviewer no longer has the case, so
        # neither "new applicant" to them nor "your interviewer is ..." to the student. Closed as
        # done ('') unsent; the current assignment's own event (if any) mails the current reviewer.
        _finish_notify(event_id, now)
        logger.info('AUDIT assign_email_stale event=%s app=%s', event_id, event.application_id)
        return 'stale'
    try:
        send_assignment_emails(event)
    except Exception:  # never raise into the cron: one failed attempt
        logger.warning('assignment emails failed event=%s attempt=%s', event_id,
                       event.notify_attempts, exc_info=True)
        if event.notify_attempts >= MAX_ATTEMPTS:
            _finish_notify(event_id, now, FAILED)
            return 'failed'
        AssignmentEvent.objects.filter(pk=event_id, notify_claimed_at=now).update(
            notify_claimed_at=None)
        return 'retry'
    _finish_notify(event_id, now)
    return 'sent'


def send_pending(limit=BATCH):
    """The cron body: send up to ``limit`` queued assignments' emails, oldest first. Never raises."""
    counts = {'sent': 0, 'stale': 0, 'retry': 0, 'failed': 0, 'not_claimed': 0, 'error': 0}
    now = timezone.now()
    # A send killed mid-call on its LAST attempt can never be claimed again: close it as failed.
    counts['failed'] += AssignmentEvent.objects.filter(
        notify_state=PENDING, notify_attempts__gte=MAX_ATTEMPTS,
        notify_claimed_at__lt=now - STALE_CLAIM,
    ).update(notify_state=FAILED, notify_claimed_at=None)
    ids = list(AssignmentEvent.objects.filter(_notify_claimable(now), notify_state=PENDING,
                                              notify_attempts__lt=MAX_ATTEMPTS)
               .order_by('created_at', 'id').values_list('pk', flat=True)[:limit])
    for event_id in ids:
        try:
            counts[send_one(event_id)] += 1
        except Exception:  # one bad row never stops the batch
            logger.warning('assignment emails run failed event=%s', event_id, exc_info=True)
            counts['error'] += 1
    return counts
