"""The final sponsor profile, written in the BACKGROUND after a verdict is recorded (A2.1, TD-517).

Before A2.1, record-verdict with ``finalise`` ran the Gemini refine (``refine_sponsor_profile``) and
the card blurb (``generate_anon_blurb``) INSIDE the request: p95 about 50 s, so reviewers hit
timeouts and submitted twice (org request 61). Now the view only QUEUES the work
(``queue_finalise``) in the same transaction as the verdict, and the ``finalise-profiles`` cron
(``run_pending_finalise``, every 5 minutes through ``CronRunView``) writes it (``run_pending``).

What the worker writes is what the view used to write: the final profile, its mirror onto the pool
fields, and (for a clean APPROVE only) the identifier-scanned card blurb. The rules, each pinned in
``tests/test_profile_finalise.py``:

* **Only QC-Accept publishes.** QC-Accept refuses while a profile is pending (``profile_pending``),
  so QC always reads the final text it puts in front of sponsors. The worker never publishes, and
  never changes the sponsor text of a published profile (or one a reopen holds back to republish):
  there it writes the reviewer's ``final_markdown`` only.

* **Claim before the paid call.** A conditional UPDATE claims the row and counts the attempt, so two
  overlapping runs never refine the same profile. A claim older than ``STALE_CLAIM`` (a process
  killed mid-call) is claimable again.
* **Never a lock across a network call.** Gemini runs outside any transaction; the write is one short
  atomic block that locks the application first, then the profile (the QC-Accept order).
* **The newest verdict wins.** ``finalise_requested_at`` is the claim token. A re-record restamps it,
  so a run started for an older verdict drops its result; a re-record without finalise drops the
  queued job (``supersede_pending``).
* **Retry, then stop.** An engine error leaves the row pending for the next run; after
  ``MAX_ATTEMPTS`` it is 'failed', the card says so and System health counts it. The
  finalise-profile endpoint re-queues it (the retry). The whole batch is skipped while
  ``outage.gemini_reads_down``.
* **Inside the cron's time.** At most ``BATCH`` rows a run, and none claimed after
  ``TIME_BUDGET_SECONDS``.
"""
import logging
import time
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from . import pool
from .models import ScholarshipApplication, SponsorProfile
from .profile_engine import generate_anon_blurb, refine_sponsor_profile

logger = logging.getLogger(__name__)

PENDING = 'pending'
FAILED = 'failed'
MAX_ATTEMPTS = 3
STALE_CLAIM = timedelta(minutes=10)
#: Per cron run. A refine takes up to about 50 s and the cron endpoint has 300 s: at most BATCH
#: rows, and no new row is claimed once TIME_BUDGET_SECONDS have gone, so a run ends well inside it.
BATCH = 3
TIME_BUDGET_SECONDS = 150
#: The columns `queue_finalise` sets; the view saves only these (never a stale full row).
QUEUE_FIELDS = ['finalise_state', 'finalise_language', 'finalise_requested_at',
                'finalise_claimed_at', 'finalise_attempts', 'updated_at']


def queue_finalise(app, language):
    """Check the preconditions the inline finalise had, and queue the profile. Returns
    ``(finalise_result, sp_to_save)``; the caller saves ``sp_to_save`` (``QUEUE_FIELDS``) in the
    verdict's own transaction, so a verdict and its queued profile cannot half-apply."""
    sp = SponsorProfile.objects.filter(application=app).first()
    if sp is None or not sp.current_markdown.strip():
        return {'ok': False, 'code': 'no_draft'}, None
    if not app.interview_sessions.filter(status='submitted').exists():
        return {'ok': False, 'code': 'no_interview'}, None
    sp.finalise_state = PENDING
    sp.finalise_language = (language if isinstance(language, str) else '')[:20]
    sp.finalise_requested_at = timezone.now()
    sp.finalise_claimed_at = None
    sp.finalise_attempts = 0
    # published:False ALWAYS — QC-Accept publishes. `pending` tells the FE the profile is on its way.
    return {'ok': True, 'pending': True, 'published': False}, sp


def supersede_pending(app):
    """A verdict re-recorded WITHOUT finalise: drop a profile still queued for the older verdict,
    so the worker never writes text for a verdict that has changed. Returns the row to save
    (``QUEUE_FIELDS``, in the verdict's transaction), or None when nothing was queued."""
    sp = SponsorProfile.objects.filter(application=app, finalise_state=PENDING).first()
    if sp is None:
        return None
    sp.finalise_state = ''
    sp.finalise_claimed_at = None
    return sp


def _claimable(now):
    return (Q(finalise_claimed_at__isnull=True) | Q(finalise_claimed_at__lt=now - STALE_CLAIM))


def _claim_row(sp_id, now):
    """Atomically claim one pending row and count the attempt. True iff this caller won it."""
    return SponsorProfile.objects.filter(
        _claimable(now), pk=sp_id, finalise_state=PENDING, finalise_attempts__lt=MAX_ATTEMPTS,
    ).update(finalise_claimed_at=now, finalise_attempts=F('finalise_attempts') + 1) == 1


def _still_ours(sp, token):
    return sp.finalise_state == PENDING and sp.finalise_requested_at == token


def _record_failure(sp_id, token):
    """An engine error: retry on the next run, or 'failed' once the attempts are spent."""
    with transaction.atomic():
        sp = SponsorProfile.objects.select_for_update().get(pk=sp_id)
        if not _still_ours(sp, token):
            return 'superseded'
        outcome = 'failed' if sp.finalise_attempts >= MAX_ATTEMPTS else 'retry'
        if outcome == 'failed':
            sp.finalise_state = FAILED
        sp.finalise_claimed_at = None
        sp.save(update_fields=['finalise_state', 'finalise_claimed_at', 'updated_at'])
    return outcome


def _blurb_for(app, markdown, profile):
    """The card blurb, built exactly as the inline finalise built it: only for a clean APPROVE,
    then backstopped by the strict identifier scan. None = leave the stored blurb alone."""
    if (app.officer_verdict or {}).get('overall') != 'accept':
        return None
    if pool.scan_profile_pii(markdown, profile):
        return None
    try:
        blurb = generate_anon_blurb(app, markdown)
    except Exception:  # the blurb is optional: the card falls back to the course alone
        logger.warning('finalise blurb failed app_id=%s', app.pk, exc_info=True)
        blurb = ''
    return blurb if (blurb and not pool.scan_anon_for_identifiers(blurb, profile)) else ''


def _sponsors_saw_it(app, sp):
    """True when the sponsor text is QC-cleared and must not change under QC: it is published,
    or a reopen has held it back and its cancel would republish it as it stands."""
    return sp.anon_published or app.decision_reopens.filter(
        closed_at__isnull=True, was_published=True).exists()


def _write_result(sp_id, app_id, token, result, blurb):
    """Write the refined profile (the inline finalise's fields). It NEVER publishes, and never
    changes the sponsor text of a QC-cleared profile: only QC-Accept, which refuses while a
    profile is pending, puts a text in front of sponsors. App row first, then the profile: the
    QC-Accept lock order."""
    with transaction.atomic():
        app = ScholarshipApplication.objects.select_for_update().get(pk=app_id)
        sp = SponsorProfile.objects.select_for_update().get(pk=sp_id)
        if not _still_ours(sp, token):
            return 'superseded'
        now = timezone.now()
        fields = ['final_markdown', 'final_model_used', 'prompt_version', 'finalised_at',
                  'finalise_state', 'finalise_claimed_at', 'updated_at']
        sp.final_markdown = result['markdown']
        sp.final_model_used = result.get('model_used', '')
        sp.prompt_version = result.get('prompt_version', '')
        sp.finalised_at = now
        # One profile: the final IS the sponsor/pool version, mirrored only while QC has not
        # cleared it (the next QC-Accept reads and publishes it).
        if not _sponsors_saw_it(app, sp):
            sp.anon_markdown = result['markdown']
            sp.anon_model_used = result.get('model_used', '')
            sp.anon_generated_at = now
            fields += ['anon_markdown', 'anon_model_used', 'anon_generated_at']
            if blurb is not None:
                sp.anon_blurb = blurb
                fields.append('anon_blurb')
        sp.finalise_state = ''
        sp.finalise_claimed_at = None
        sp.save(update_fields=fields)
    return 'done'


def run_finalise(sp_id):
    """Claim, refine, write. Returns 'done', 'retry', 'failed', 'superseded' or 'not_claimed'."""
    if not _claim_row(sp_id, timezone.now()):
        return 'not_claimed'
    sp = SponsorProfile.objects.select_related('application').get(pk=sp_id)
    token, app = sp.finalise_requested_at, sp.application
    session = app.interview_sessions.filter(status='submitted').order_by('-submitted_at').first()
    draft = sp.current_markdown
    if session is None or not draft.strip():
        result = {'error': 'no draft or interview'}
    else:
        try:
            result = refine_sponsor_profile(app, draft=draft, session=session,
                                            language=sp.finalise_language or None)
        except Exception as e:  # never raise into the cron: count it as one failed attempt
            logger.warning('finalise refine raised app_id=%s', app.pk, exc_info=True)
            result = {'error': type(e).__name__}
    if not isinstance(result, dict) or 'error' in result or 'markdown' not in result:
        logger.warning('finalise engine error app_id=%s attempt=%s', app.pk, sp.finalise_attempts)
        return _record_failure(sp_id, token)
    blurb = _blurb_for(app, result['markdown'], getattr(app, 'profile', None))
    return _write_result(sp_id, app.pk, token, result, blurb)


def run_pending(limit=BATCH, budget=TIME_BUDGET_SECONDS, clock=time.monotonic):
    """The cron body: finalise up to ``limit`` queued profiles, oldest request first, and claim no
    new row once ``budget`` seconds have gone (the rest wait for the next run). Never raises."""
    started = clock()
    from .services.outage import gemini_reads_down
    counts = {'done': 0, 'retry': 0, 'failed': 0, 'superseded': 0, 'not_claimed': 0, 'error': 0,
              'deferred': 0}
    now = timezone.now()
    # A run killed mid-call on its LAST attempt can never be claimed again: close it as failed.
    counts['failed'] += SponsorProfile.objects.filter(
        finalise_state=PENDING, finalise_attempts__gte=MAX_ATTEMPTS,
        finalise_claimed_at__lt=now - STALE_CLAIM,
    ).update(finalise_state=FAILED, finalise_claimed_at=None)
    if gemini_reads_down():
        return {**counts, 'skipped_outage': True}
    ids = list(SponsorProfile.objects.filter(_claimable(now), finalise_state=PENDING)
               .order_by('finalise_requested_at').values_list('pk', flat=True)[:limit])
    for sp_id in ids:
        if clock() - started >= budget:
            counts['deferred'] += 1
            continue
        try:
            counts[run_finalise(sp_id)] += 1
        except Exception:  # one bad row never stops the batch
            logger.warning('finalise run failed sp_id=%s', sp_id, exc_info=True)
            counts['error'] += 1
    return {**counts, 'skipped_outage': False}
