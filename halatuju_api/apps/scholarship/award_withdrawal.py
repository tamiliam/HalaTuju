"""Withdrawing an award: WHAT the withdrawal does — A1.13 (TD-198 / CO-09), maker and checker since A1.13b.

WHO may withdraw is `award_withdrawal_chain` (owner rulings 2026-11-08): one person asks with a required
explanation, a DIFFERENT person approves, and only the approval runs `_apply` here, under the locks the
chain has taken. A super can read requests but never sits in either seat. (Until A1.13b a super withdrew
alone, with a reason, through `withdraw-award/`; that route is gone.)

It mirrors the sponsor's own withdrawal (`sponsorship.cancel_offer` → `award_revert.revert_to_pool`):
the holding sponsorship is cancelled (so its whole amount returns to the sponsor's balance — the
balance is confirmed donations minus HOLDING allocations), the case returns to `recommended` (or to
QC, `interviewed`, on the TD-376 birth-state diversion), and every unpaid scheduled / due tranche is
withheld so nothing more goes out. The student is told by the "award withdrawn" email, after commit.

⚠ PAID MONEY IS NEVER CLAWED BACK, AND A PAID CASE IS REFUSED (lead ruling, A1.13): the balance
model frees a cancelled sponsorship's FULL amount, so withdrawing a case that has been paid (the
live cohort is paid by payment runs while still `awarded`) would hand the sponsor back money that
has already gone to the student. Such a case answers ``has_payments`` (TD-591, with TD-366: the
owner decides what a paid withdrawal means). The check runs UNDER THE APPLICATION ROW LOCK that the
approval holds, and both money writers (`payments.complete`, `disbursement.release_tranche`) take
that same lock first (lock order, `status_lock.py`), so a payment cannot slip in between the check
and the withdrawal; a payment run completing after it sees the case no longer payable and refuses
the whole run (`not_payable_in_run`).

Where the texts live: the request row (`award_withdrawal_requests`) holds both people and both texts,
and the student's activity log holds them again as an INTERNAL row: ``event='award_withdrawn'``,
``body`` = the maker's explanation, ``actor_email`` = the checker, meta = both people and the note.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import activity
from .agreement_guard import void_on_withdrawal
from .award_revert import revert_to_pool
from .models import Disbursement, Sponsorship
from .models.activity import EVENT_AWARD_WITHDRAWN

logger = logging.getLogger('apps.scholarship.award_withdrawal')

#: What a withdrawal may act on. Only an awarded case: an active / maintenance student is funded
#: (the agreement has bound) and is ended by a close, not by this.
WITHDRAWABLE = ('awarded',)

#: A tranche whose money has gone out (``Disbursement.PAID``) or came back after going out
#: ('returned' — it WAS paid). Either refuses the withdrawal (TD-591).
_PAID_OR_RETURNED = tuple(Disbursement.PAID) + ('returned',)

class AwardWithdrawalError(Exception):
    """A stable refusal code; `award_withdrawal_chain` raises it, the view maps it to a status."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def has_payments(application):
    """Has any money been paid on this case (a released or returned tranche, a run's payout too)?"""
    return application.disbursements.filter(status__in=_PAID_OR_RETURNED).exists()


def can_withdraw(application):
    """The cockpit's hint (the server decides again under the lock): awarded and never paid."""
    return application.status in WITHDRAWABLE and not has_payments(application)


def _student_was_told(sponsorships):
    """Was the student told of this award? A sponsor's award email stamps ``offer_emailed_at``; while
    every holding offer is still in its cool-off (none stamped) she was never told, and a "withdrawn"
    email would be the first she heard of an award. An awarded case with NO holding sponsorship (an
    imported / grandfathered award) was told outside this ledger, so it is treated as told."""
    if not sponsorships:
        return True
    return any(sp.offer_emailed_at is not None for sp in sponsorships)


def _send_withdrawn_email(application):
    """AFTER COMMIT, best-effort: the "award withdrawn" notice, in the organisation's wording (A1.13b:
    `student_comms`, its log and meter). Never carries the explanation or the note."""
    from . import student_comms
    try:
        sent = student_comms.send_student_email(application, 'award_withdrawn')
    except Exception:   # an email must never undo, or appear to undo, a committed withdrawal
        logger.exception('award_withdrawal: app %s withdrawn but the email raised', application.id)
        return False
    if not sent:
        logger.warning('award_withdrawal: app %s is withdrawn but the email did not go (no address, '
                       'or the send failed) — tell the student by hand.', application.id)
    return sent


def holding_sponsorships(application, *, lock=False):
    """The case's HOLDING sponsorships in pk order (``lock``: ``select_for_update``, step 4)."""
    qs = Sponsorship.objects.filter(application=application, status__in=Sponsorship.HOLDING)
    return list((qs.select_for_update() if lock else qs).order_by('pk'))


def snapshot_of(application):
    """What a withdrawal of ``application`` would do NOW — the request's snapshot, compared again at
    the approval (``stale``). Amounts as strings (JSON)."""
    holding = holding_sponsorships(application)
    unpaid = list(application.disbursements.filter(status__in=('scheduled', 'due'))
                  .order_by('pk').values_list('pk', flat=True))
    return {'sponsorships': [{'id': sp.pk, 'amount': str(sp.amount)} for sp in holding],
            'amount_freed': str(sum((sp.amount for sp in holding), Decimal('0'))),
            'tranches_to_withhold': unpaid}


def _apply(application, holding, *, by_admin, explanation, meta):
    """THE WITHDRAWAL ITSELF. ⚠ The caller holds the locks, in the house order, inside its transaction:
    the application (re-read, ``awarded``, never paid), the request row, then ``holding`` — the case's
    holding sponsorships, locked and in pk order. `award_withdrawal_chain.approve_withdrawal` is the one
    caller. ``meta`` (both people, the note, the request id) is added to the activity row's meta."""
    from .disbursement import withhold_tranche
    actor_email = getattr(by_admin, 'email', '') or ''
    now = timezone.now()
    told = _student_was_told(holding)
    freed = sum((sp.amount for sp in holding), Decimal('0'))
    for sp in holding:
        sp.status = 'cancelled'
        sp.decided_at = now
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
    withheld = []
    note = 'Award withdrawn (A1.13): this unpaid tranche stops.'
    for tranche in application.disbursements.filter(status__in=('scheduled', 'due')).order_by('pk'):
        withhold_tranche(tranche, by_email=actor_email, note=note, actor=by_admin)
        withheld.append(tranche.pk)
    # Review finding 1: the agreement dies with the award (signatures + sponsorship link
    # cleared), so it can be neither countersigned nor paid on after a re-award.
    agreement_was = void_on_withdrawal(application)
    revert_to_pool(application)
    activity.log_event(
        application, EVENT_AWARD_WITHDRAWN, actor_email=actor_email, body=explanation, internal=True,
        meta={'sponsorship_ids': [sp.pk for sp in holding], 'amount_freed': str(freed),
              'tranches_withheld': withheld, 'to': application.status,
              'student_emailed': told, 'agreement_voided': agreement_was, **meta})
    if told:
        pk = application.pk
        transaction.on_commit(lambda: _send_withdrawn_email(_reload(pk)))
    # No explanation, name or IC in a log line (house rule); the activity row holds the texts.
    logger.info('AUDIT award_withdrawn app_id=%s to=%s sponsorships=%s tranches_withheld=%s by=%s',
                application.id, application.status, len(holding), len(withheld),
                getattr(by_admin, 'pk', '?'))
    return application


def _reload(pk):
    from .models import ScholarshipApplication
    return ScholarshipApplication.objects.select_related('profile', 'cohort').get(pk=pk)
