"""The first-assign profile draft, written in the BACKGROUND (A2.3b, TD-586).

Before A2.3b, the FIRST assignment of a case called Gemini for the sponsor-profile draft
(``generate_ready_profile``) inside the assign request, when ``CHECK2_AUTO_GENERATE`` is on, so
that one assign stayed slow after A2.3 moved its emails out. Now ``assign_reviewer`` only QUEUES the
draft (``queue_first_draft``) and the ``finalise-profiles`` cron (``run_pending_finalise``, every 5
minutes) writes it (``draft_pending``), after the verdict finalises of the same run.

No new columns: the queue is the A2.1 finalise queue on ``sponsor_profiles`` with its own state,
``'drafting'``. A row can be drafting only while it has never been drafted (``generated_at`` null),
and a finalise needs a draft, so the two never share a row at the same time. The rules, each pinned
in ``tests/test_assign_draft.py``:

* **Same gate, same store.** Queued only on a first assignment, only while the flag is on, never for
  a profile already drafted. The worker calls the same ``generate_ready_profile`` the inline code
  called, so the stored draft is exactly what it was.
* **Never twice.** A row already drafting (a re-assign, or assign, unassign and assign again) is
  left as it is; a row a person drafted meanwhile (the Generate button) is dropped, with no call.
* **Claim before the paid call**, the A2.1 way: a conditional UPDATE claims the row and counts the
  attempt, and a claim older than ``STALE_CLAIM`` is claimable again.
* **Retry, then stop.** An engine error leaves the row drafting for the next run; after
  ``MAX_ATTEMPTS`` the row goes back to plain (no draft), which is where the inline code left a
  failed draft: the reviewer can still press Generate. The batch is skipped while
  ``outage.gemini_reads_down``, and dropped while the flag is off (the flag is the off switch).
* **Inside the cron's time.** At most ``BATCH`` rows, and none claimed once the run is
  ``DEADLINE_SECONDS`` old (the cron endpoint has 300 s).
"""
import logging
import time

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import SponsorProfile
from .profile_finalise import MAX_ATTEMPTS, QUEUE_FIELDS, STALE_CLAIM, _claimable

logger = logging.getLogger(__name__)

DRAFTING = 'drafting'
#: Per cron run, after the finalises. A draft is one Flash call (well under a minute), so no new row
#: is claimed once the run (finalises included) is DEADLINE_SECONDS old: it ends inside 300 s.
BATCH = 3
DEADLINE_SECONDS = 210


def queue_first_draft(application):
    """Queue the first-assign draft. True when queued; False when the flag is off, the profile is
    already drafted, or the row is busy (already drafting, or a finalise owns it)."""
    if not getattr(settings, 'CHECK2_AUTO_GENERATE', False):
        return False
    sp, _ = SponsorProfile.objects.get_or_create(application=application)
    if sp.generated_at is not None or sp.finalise_state:
        return False
    sp.finalise_state = DRAFTING
    sp.finalise_language = ''
    sp.finalise_requested_at = timezone.now()
    sp.finalise_claimed_at = None
    sp.finalise_attempts = 0
    sp.save(update_fields=QUEUE_FIELDS)
    return True


def _release(sp_id, token, *, give_up):
    """Let the row go: back to plain (done, dropped or given up), or unclaimed for a retry."""
    fields = {'finalise_claimed_at': None}
    if give_up:
        fields['finalise_state'] = ''
    SponsorProfile.objects.filter(
        pk=sp_id, finalise_state=DRAFTING, finalise_requested_at=token).update(**fields)


def run_draft(sp_id):
    """Claim, draft, release. Returns 'done', 'retry', 'failed', 'superseded' or 'not_claimed'."""
    now = timezone.now()
    if not SponsorProfile.objects.filter(
        _claimable(now), pk=sp_id, finalise_state=DRAFTING, finalise_attempts__lt=MAX_ATTEMPTS,
    ).update(finalise_claimed_at=now, finalise_attempts=F('finalise_attempts') + 1):
        return 'not_claimed'
    sp = SponsorProfile.objects.select_related('application').get(pk=sp_id)
    token = sp.finalise_requested_at
    if sp.generated_at is not None:          # drafted meanwhile: never a second paid call
        _release(sp_id, token, give_up=True)
        return 'superseded'
    from .services import generate_ready_profile
    try:
        _, error = generate_ready_profile(sp.application)
    except Exception as e:  # never raise into the cron: count it as one failed attempt
        logger.warning('first-assign draft raised app_id=%s', sp.application_id, exc_info=True)
        error = type(e).__name__
    if error is None:
        _release(sp_id, token, give_up=True)
        return 'done'
    logger.warning('first-assign draft error app_id=%s attempt=%s', sp.application_id,
                   sp.finalise_attempts)
    spent = sp.finalise_attempts >= MAX_ATTEMPTS
    _release(sp_id, token, give_up=spent)
    return 'failed' if spent else 'retry'


def draft_pending(started, limit=BATCH, deadline=DEADLINE_SECONDS, clock=time.monotonic):
    """The cron body, run after the finalises: draft up to ``limit`` queued profiles, oldest first,
    claiming none once ``deadline`` seconds have gone since ``started`` (the run's start, on
    ``clock``). Never raises."""
    counts = {'done': 0, 'retry': 0, 'failed': 0, 'superseded': 0, 'not_claimed': 0, 'error': 0,
              'deferred': 0}
    now = timezone.now()
    queued = SponsorProfile.objects.filter(finalise_state=DRAFTING)
    if not getattr(settings, 'CHECK2_AUTO_GENERATE', False):
        dropped = queued.update(finalise_state='', finalise_claimed_at=None)
        return {**counts, 'dropped_flag_off': dropped, 'skipped_outage': False}
    # A run killed mid-call on its LAST attempt can never be claimed again: let it go.
    counts['failed'] += queued.filter(
        finalise_attempts__gte=MAX_ATTEMPTS, finalise_claimed_at__lt=now - STALE_CLAIM,
    ).update(finalise_state='', finalise_claimed_at=None)
    from .services.outage import gemini_reads_down
    if gemini_reads_down():
        return {**counts, 'dropped_flag_off': 0, 'skipped_outage': True}
    ids = list(queued.filter(_claimable(now)).order_by('finalise_requested_at')
               .values_list('pk', flat=True)[:limit])
    for sp_id in ids:
        if clock() - started >= deadline:
            counts['deferred'] += 1
            continue
        try:
            counts[run_draft(sp_id)] += 1
        except Exception:  # one bad row never stops the batch
            logger.warning('first-assign draft run failed sp_id=%s', sp_id, exc_info=True)
            counts['error'] += 1
    return {**counts, 'dropped_flag_off': 0, 'skipped_outage': False}
