"""Sponsorship: lapsing and reinstating holding sponsorships, and the expired-offer job.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
import logging

from django.db import transaction
from django.utils import timezone

from .. import status_lock as _status_lock
from ..award_revert import revert_to_pool as _revert_to_pool
from ..models import Sponsorship
from .wallet import sponsor_balance

logger = logging.getLogger('apps.scholarship.sponsorship')   # the package name, as before the split


def lapse_holding_sponsorships(application, *, now=None):
    """Lapse EVERY holding (offered/active) sponsorship on this application — each held
    amount returns to its sponsor's balance (balance = donations − holding allocations,
    so a lapsed row simply stops being subtracted). For a student who leaves the
    programme outside the normal offer-decline/closure flow — e.g. a contractual admin
    reject of a funded student (code-health S3 #6): without this, the sponsorship sat
    HOLDING forever, the sponsor's balance stayed reduced, and impact/statement surfaces
    kept reporting the rejected student as actively supported. Returns the rows lapsed."""
    now = now or timezone.now()
    lapsed = []
    for sp in application.sponsorships.filter(status__in=Sponsorship.HOLDING):
        sp.status = 'lapsed'
        sp.decided_at = now
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
        lapsed.append(sp)
    return lapsed


def reinstate_lapsed_sponsorship(application, *, since):
    """Best-effort undo of ``lapse_holding_sponsorships`` for a CANCELLED contractual
    decline: put the most recently lapsed sponsorship (lapsed at/after ``since``) back to
    'active' — but only when the sponsor's balance still covers the amount (they may have
    reallocated the returned money in the window). Returns the sponsorship on success,
    None when there is nothing to reinstate or the balance no longer covers it (the case
    then needs re-funding; the caller logs it)."""
    sp = (application.sponsorships.filter(status='lapsed', decided_at__gte=since)
          .order_by('-decided_at').select_related('sponsor').first())
    if sp is None:
        return None
    # Reinstatement spends from the wallet of the programme this student belongs to.
    from ..status_lock import lock_sponsor_wallet
    lock_sponsor_wallet(sp.sponsor)   # A1.5: the same wallet race as fund_student
    if sponsor_balance(sp.sponsor, application.programme) < sp.amount:
        return None
    sp.status = 'active'
    sp.decided_at = timezone.now()
    sp.save(update_fields=['status', 'decided_at', 'updated_at'])
    return sp


def _expired_offers(now):
    return list(Sponsorship.objects.filter(status='offered', accept_deadline__isnull=False,
                                           accept_deadline__lt=now).select_related('application'))


def lapse_expired_offers(lapsed_ids=None):
    """Lapse every 'offered' award whose ARMED accept_deadline has passed (the amount returns to
    the sponsor's balance; the application reverts to the pool). Intended for a scheduled job.

    Offer-lapse rework (go-live transition, 2026-07-19, owner decision 3):
      • ARMED-ONLY. A NULL ``accept_deadline`` (the sign-invitation clock never started) is NOT a
        lapse candidate (``isnull=False`` makes explicit what ``__lt=now`` already does).
      • PAID APPS NEVER AUTO-LAPSE. An application with any released disbursement (e.g. the
        grandfather cohort, already being paid while their in-app acceptance is back-filled) is
        REFUSED — it is logged and returned in ``flagged`` for an admin to handle by hand, never
        silently lapsed out from under real money.

    Returns ``{'lapsed': <count>, 'flagged': [<application_id>, ...]}``. Wired to the DAILY
    ``lapse-expired-offers`` cron job (command ``lapse_expired_offers``, TD-252, 2026-09-30) — and
    only ever against THESE semantics. Each refusal logs at INFO; the run logs ONE summary WARNING
    with the count, so a standing set of paid offers does not raise the same alarm line by line
    every day. A list passed as ``lapsed_ids`` receives the lapsed sponsorship ids. Each lapse
    re-reads its row UNDER A LOCK and proceeds only if still 'offered' with the same deadline, so
    an acceptance landing mid-sweep wins (review F4; unreachable while AWARD_ACCEPTANCE_ENABLED is
    unset, as today, since no student can accept)."""
    now = timezone.now()
    expired = _expired_offers(now)
    lapsed = 0
    flagged = []
    for sp in expired:
        app = sp.application
        if app.disbursements.filter(status='released').exists():
            # Released money against this application → never auto-lapse. Flag for admin review.
            flagged.append(app.id)
            logger.info(
                'lapse_expired_offers: REFUSED to lapse app %s (sponsorship %s) — it has released '
                'disbursements. Flagged for admin review.', app.id, sp.id)
            continue
        with transaction.atomic():
            # A1.13 third review: the case FIRST (house order), then OF the offer row only.
            _status_lock.lock_case_of_sponsorship(pk=sp.pk)
            sp = (Sponsorship.objects.select_for_update(of=('self',)).select_related('application')
                  .filter(pk=sp.pk, status='offered', accept_deadline=sp.accept_deadline).first())
            if sp is None:
                continue   # accepted / cancelled / re-armed since the list was read — leave it
            sp.status = 'lapsed'
            sp.decided_at = now
            sp.save(update_fields=['status', 'decided_at', 'updated_at'])
            _revert_to_pool(sp.application)   # offer expired unaccepted → back in the pool
        logger.info('lapse_expired_offers: LAPSED sponsorship %s (app %s)', sp.id, app.id)
        if lapsed_ids is not None:
            lapsed_ids.append(sp.id)
        lapsed += 1
    if flagged:
        logger.warning('lapse_expired_offers: %s expired offer(s) REFUSED — released money; '
                       'flagged for admin review: %s', len(flagged), flagged)
    return {'lapsed': lapsed, 'flagged': flagged}
