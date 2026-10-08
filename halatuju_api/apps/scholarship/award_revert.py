"""Where a case goes when its award falls through before it became active — TD-376.

Moved out of `sponsorship.py` (which sits at its `oversize_files` allowance) when TD-376 gave it a
second landing. `sponsorship` imports it back as `_revert_to_pool`, so its five callers — the
sponsor's withdrawal (`cancel_offer`), the student's decline (`respond_to_award`), the hold
(`hold_pending_award`), the release cron's fall-through (`release_pending_awards`) and the lapse
(`lapse_expired_offers`) — are unchanged.
"""
import logging

from . import birth_state

logger = logging.getLogger(__name__)


def revert_to_pool(application):
    """An offer was declined / held / expired BEFORE it became active → the application returns to
    'recommended' (re-enters the discovery pool) and any award cool-off marker clears. No-op if the
    app already moved on (e.g. it was finalised to 'active').

    ⚠ TD-376 (owner ruling 2026-10-08, "yes"): a case whose CURRENT IC fails its intake's CURRENT
    "Born in" rule lands at `interviewed` (AWAITING QC) instead — QC accept then applies the floor
    and records any override. Its IC can have changed only after a super released the IC lock
    (TD-371 allows that from `awarded` on). It is NEVER a refusal: the sponsor's withdrawal, the
    student's decline, the hold and the lapse all go through exactly as before; only where the case
    lands differs. Nothing else is written for it: the pool and both sponsor alert sweeps read
    `status='recommended'` (`pool.eligible_pool_queryset` / `display_pool_queryset` /
    `is_pool_eligible`), so `interviewed` is neither visible nor fundable while the sponsor profile
    stays published; QC accept's `publish_profile_to_pool` is then a no-op and the realtime stamp
    still stands, so sponsors are not alerted a second time — as for a plain revert. No caller
    sends a student or sponsor email about the revert.

    ⚠ AN UNLOCKED IC ON A RULED INTAKE IS DIVERTED TOO (review round 7), even when it still passes:
    every other door into `recommended` on a ruled intake requires a LOCKED IC (QC accept and the
    reopen-cancel, `birth_state.ic_unlocked_for_rule`), and this one must not be the exception — an
    unlocked IC can still be changed before the next sponsor funds. At QC the reviewer
    verify-accepts it again (re-locks), then QC accepts."""
    fields = []
    reasons = []
    if application.status == 'awarded':
        reasons = divert_reasons(application)
        application.status = 'interviewed' if reasons else 'recommended'
        fields.append('status')
    if application.award_due_at is not None:
        application.award_due_at = None
        fields.append('award_due_at')
    if fields:
        application.save(update_fields=fields)
    if reasons:
        # No IC and no state name in a log line (house rule); the cockpit re-reads both.
        logger.info('AUDIT revert_to_qc_birth_state app_id=%s from=awarded to=interviewed '
                    'reason=%s', application.id, ','.join(reasons))


def divert_reasons(application):
    """Why a falling-through award must go to QC rather than back to the pool: `ic_unlocked`
    (a ruled intake and an unlocked IC) and/or `rule_fails` (the CURRENT IC fails the CURRENT
    rule). Empty — revert as before — on an unruled intake or a locked, passing IC."""
    reasons = []
    if birth_state.ic_unlocked_for_rule(application.profile,
                                        getattr(application.cohort, 'allowed_birth_states', None)):
        reasons.append('ic_unlocked')
    if fails_birth_state_rule(application):
        reasons.append('rule_fails')
    return reasons


def fails_birth_state_rule(application):
    """Does the CURRENT IC fail the intake's CURRENT "Born in" rule? The QC floor's own answer
    (`birth_state.meets_rule`); False when the intake has no rule."""
    profile = application.profile
    return birth_state.meets_rule(getattr(profile, 'nric', '') if profile else '',
                                  getattr(application.cohort, 'allowed_birth_states', None)) is False
