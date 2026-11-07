"""A super admin withdraws an award — A1.13 (TD-198 / CO-09; owner ruling D3, 2026-11-08).

The owner's rule: ONLY a super admin may withdraw an award, at any time, with a REQUIRED reason.
The reason is stored with who and when, and it is INTERNAL — the student never sees it.

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
withdrawal holds, and both money writers (`payments.complete`, `disbursement.release_tranche`) take
that same lock first (lock order, `status_lock.py`), so a payment cannot slip in between the check
and the withdrawal; a payment run completing after it sees the case no longer payable and refuses
the whole run (`not_payable_in_run`).

Where the reason lives: the student's activity log (the ``student_activity`` table, an existing audit table —
no migration), as an INTERNAL row: ``event='award_withdrawn'``, ``body`` = the reason,
``actor_email`` = the super, ``created_at`` = when.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import activity
from . import usage as _usage
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

#: The reason is stored whole in the activity row's body, never cut short.
REASON_MAX = activity.BODY_MAX


class AwardWithdrawalError(Exception):
    """``reason_required`` / ``reason_too_long`` (the view answers 400), ``not_awarded`` /
    ``has_payments`` (409)."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def clean_reason(reason):
    """The reason, trimmed; refuses an empty or over-long one."""
    text = (reason or '').strip() if isinstance(reason, str) else ''
    if not text:
        raise AwardWithdrawalError('reason_required')
    if len(text) > REASON_MAX:
        raise AwardWithdrawalError('reason_too_long')
    return text


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
    """AFTER COMMIT, best-effort: the "award withdrawn" notice. Never carries the reason."""
    from .branding import for_application
    from .emails import send_award_withdrawn_email
    name = getattr(application.profile, 'name', '') if application.profile else ''
    try:
        with _usage.usage_context(application=application):
            sent = send_award_withdrawn_email(
                to_email=application.notify_email, applicant_name=name,
                lang=application.locale, branding=for_application(application))
    except Exception:   # an email must never undo, or appear to undo, a committed withdrawal
        logger.exception('withdraw_award: app %s withdrawn but the email raised', application.id)
        return False
    if not sent:
        logger.warning('withdraw_award: app %s is withdrawn but the email did not go (no address, '
                       'or the send failed) — tell the student by hand.', application.id)
    return sent


def withdraw_award(application, *, by_admin, reason):
    """Withdraw ``application``'s award (the caller has checked that ``by_admin`` is a super).

    Returns the refreshed application. Raises ``AwardWithdrawalError``. Safe against a double
    click: the second press finds the case no longer awarded under the lock (``not_awarded``)."""
    from .disbursement import withhold_tranche
    from .status_lock import StatusRefused, lock_application_for
    text = clean_reason(reason)
    actor_email = getattr(by_admin, 'email', '') or ''
    with transaction.atomic():
        try:
            lock_application_for(application, WITHDRAWABLE)
        except StatusRefused:
            raise AwardWithdrawalError('not_awarded')
        # Under the SAME lock as the withdrawal (lead, A1.13): a release cannot slip in between.
        if has_payments(application):
            raise AwardWithdrawalError('has_payments')
        now = timezone.now()
        holding = list(Sponsorship.objects.select_for_update()
                       .filter(application=application, status__in=Sponsorship.HOLDING)
                       .order_by('pk'))
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
        revert_to_pool(application)
        activity.log_event(
            application, EVENT_AWARD_WITHDRAWN, actor_email=actor_email, body=text, internal=True,
            meta={'sponsorship_ids': [sp.pk for sp in holding], 'amount_freed': str(freed),
                  'tranches_withheld': withheld, 'to': application.status,
                  'student_emailed': told})
        if told:
            pk = application.pk
            transaction.on_commit(lambda: _send_withdrawn_email(_reload(pk)))
    # No reason, name or IC in a log line (house rule); the activity row holds the reason.
    logger.info('AUDIT award_withdrawn app_id=%s to=%s sponsorships=%s tranches_withheld=%s by=%s',
                application.id, application.status, len(holding), len(withheld),
                getattr(by_admin, 'pk', '?'))
    return application


def _reload(pk):
    from .models import ScholarshipApplication
    return ScholarshipApplication.objects.select_related('profile', 'cohort').get(pk=pk)
