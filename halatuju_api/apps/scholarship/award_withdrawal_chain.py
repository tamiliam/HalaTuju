"""WHO may withdraw an award, and in what order — the MAKER and CHECKER of A1.13b (owner rulings
2026-11-08, TD-198). WHAT a withdrawal does is `award_withdrawal._apply`; this module is its only caller.

    (no request) --request_withdrawal (MAKER: `award_withdraw_request`, a required explanation)--> pending
    pending --approve_withdrawal (CHECKER: `award_withdraw_approve`, an optional note)--> approved + _apply
    pending --refuse_withdrawal (CHECKER, a required reason)--------------------------> refused
    pending --cancel_withdrawal (the MAKER only)----------------------------------------> cancelled
    pending, older than EXPIRY_DAYS --(read as expired; the next action writes it)------> expired

* **Nothing changes until the approval.** A request writes its own row and a staff-activity line; the
  case, its sponsorships, its tranches and its agreement are untouched until a checker approves.
* **Two different people.** The checker is never the maker — by account, and by email compared
  case-insensitively (`same_person`). A SUPER never sits in either seat (`wrong_role`): a super can read
  requests but holds neither seat. `staff_permissions.holders` never answers a super, and a holder who has
  never signed in cannot act (the payment chain's `_signed_in`), so neither is counted as a checker.
* **Who holds the seats.** The two catalogue keys. NO preset holds either; the organisation admin's fixed
  lead tier holds the approve seat only. A request needs at least one eligible checker other than the maker
  (`no_checker`), so a request can never wait for nobody.
* `next_step_for` is the ONE predicate behind the gate (each action) and the screen (`your_step` in the case
  detail, the Overview's `award_withdrawals` card), so the two cannot disagree.
* **Expiry is lazy** (no scheduler job): a pending request older than `EXPIRY_DAYS` reads as expired
  everywhere (`live_pending`, the list filter, `my_pending`); the next action that locks it writes
  ``expired`` and is answered ``not_pending`` (a new request on the case is allowed at once).

LOCK ORDER (`status_lock.py`, the house order): (1) the APPLICATION row (`lock_application_for`), (2) the
REQUEST row, (3) the holding SPONSORSHIPS in pk order (approval only, inside `_apply`'s preconditions). Every
action here takes (1) before (2), even refuse and cancel, which never touch the case.

Emails go AFTER COMMIT and are best-effort (`emails.withdrawal_mail`): the checkers when a request is made,
the maker when it is approved or refused; the student's notice is `_apply`'s, through Student comms.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import award_withdrawal as wd
from .award_withdrawal import AwardWithdrawalError

REQUEST_KEY = 'award_withdraw_request'
APPROVE_KEY = 'award_withdraw_approve'
#: A pending request nobody decides within this many days expires (owner ruling 2026-11-08).
EXPIRY_DAYS = 14
#: The explanation, the refusal reason and the approval note are stored whole, never cut short.
TEXT_MAX = 5000

#: `next_step_for`'s answers, served as `your_step`.
STEP_REQUEST, STEP_DECIDE, STEP_CANCEL = 'request', 'decide', 'cancel'

#: The case statuses the case detail asks about a request for (the 38-query pin: no query otherwise).
#: ``recommended`` is where an approved withdrawal leaves the case, so its outcome stays readable.
RELEVANT_STATUSES = tuple(wd.WITHDRAWABLE) + ('recommended',)

_ALL_STATUSES = None   # filled lazily: every application status (a lock for ORDER only)


def _model():
    from .models import AwardWithdrawalRequest
    return AwardWithdrawalRequest


def _email_key(admin_or_text):
    text = admin_or_text if isinstance(admin_or_text, str) else getattr(admin_or_text, 'email', '')
    return (text or '').strip().casefold()


def _signed_in(admin):
    from .payments_chain import _signed_in as signed_in
    return signed_in(admin)


def _checked_text(text, *, code, required):
    """The text, trimmed; ``<code>_required`` when empty and required, ``<code>_too_long`` past TEXT_MAX
    (refused, never cut)."""
    value = text.strip() if isinstance(text, str) else ''
    if required and not value:
        raise AwardWithdrawalError(f'{code}_required')
    if len(value) > TEXT_MAX:
        raise AwardWithdrawalError(f'{code}_too_long')
    return value


def expiry_cutoff(now=None):
    """A pending request made BEFORE this moment is expired."""
    return (now or timezone.now()) - timedelta(days=EXPIRY_DAYS)


def is_expired(row, now=None):
    return row.status == row.PENDING and row.requested_at < expiry_cutoff(now)


def live_pending_q(now=None):
    """A `Q` (on `AwardWithdrawalRequest`) for the requests still waiting: pending and not expired."""
    from django.db.models import Q
    return Q(status='pending', requested_at__gte=expiry_cutoff(now))


def is_maker(row, admin):
    """Did ``admin`` make this request — by account, or by email (case-insensitive)?"""
    if admin is None:
        return False
    if row.requested_by_id is not None and row.requested_by_id == getattr(admin, 'pk', None):
        return True
    asked_by = _email_key(row.requested_by_email)
    return bool(asked_by) and asked_by == _email_key(admin)


def _in_org(admin, organisation_id):
    return organisation_id is not None and getattr(admin, 'owning_organisation_id', None) == organisation_id


def _seat_refusal(admin, key, organisation_id):
    """Why ``admin`` may not take the ``key`` seat in this organisation — ``wrong_role`` — or None. A super
    never sits in a seat; a holder must have signed in and belong to the case's organisation."""
    if admin is None or getattr(admin, 'is_super', False):
        return 'wrong_role'
    if not (admin.has_perm(key) and _signed_in(admin) and _in_org(admin, organisation_id)):
        return 'wrong_role'
    return None


def decide_refusal(row, admin):
    """Why ``admin`` may NOT approve or refuse ``row`` — ``wrong_role`` / ``same_person`` — or None."""
    refusal = _seat_refusal(admin, APPROVE_KEY, row.organisation_id)
    if refusal is None and is_maker(row, admin):
        return 'same_person'
    return refusal


def eligible_checkers(organisation_id, maker):
    """The people who could decide a request made by ``maker`` in this organisation: active holders of
    the approve seat (`staff_permissions.holders`: never a super), signed in, never the maker."""
    from apps.courses import staff_permissions
    if organisation_id is None:
        return []
    maker_email = _email_key(maker)
    return [a for a in staff_permissions.holders(organisation_id, APPROVE_KEY)
            if _signed_in(a) and a.pk != getattr(maker, 'pk', None) and _email_key(a) != maker_email]


def may_request(application, admin):
    """The maker's seat on this case (the gate's first question and the screen's ``request`` step)."""
    return (application.status in wd.WITHDRAWABLE
            and _seat_refusal(admin, REQUEST_KEY, application.owning_organisation_id) is None)


def next_step_for(application, row, admin, now=None):
    """The step ``admin`` may take NOW — ``'request'``, ``'decide'``, ``'cancel'`` — or None. ``row`` is
    the case's latest request (or None). THE ONE PREDICATE behind the gates and ``your_step``."""
    if admin is None or getattr(admin, 'is_super', False):
        return None
    if row is None or row.status != row.PENDING or is_expired(row, now):
        return STEP_REQUEST if may_request(application, admin) else None
    if is_maker(row, admin):
        return STEP_CANCEL if _in_org(admin, row.organisation_id) else None
    return STEP_DECIDE if decide_refusal(row, admin) is None else None


# ── the reads ──────────────────────────────────────────────────────────────────────────────────

def latest_for(application):
    return _model().objects.filter(application_id=application.pk).order_by('-requested_at', '-pk').first()


def _status_of(row, now=None):
    return row.EXPIRED if is_expired(row, now) else row.status


def payload_for(application, admin, now=None):
    """The case detail's ``withdrawal_request``: the latest request (or ``status`` None) and ``your_step``.
    None — and NO query — unless the case is in `RELEVANT_STATUSES` (the case-detail query pin)."""
    if application.status not in RELEVANT_STATUSES:
        return None
    now = now or timezone.now()
    row = latest_for(application)
    step = next_step_for(application, row, admin, now)
    if row is None:
        return {'id': None, 'status': None, 'your_step': step} if step else None
    snap = row.snapshot or {}
    return {
        'id': row.pk, 'status': _status_of(row, now), 'your_step': step,
        'requested_by_name': row.requested_by_name, 'requested_at': row.requested_at,
        'expires_at': row.requested_at + timedelta(days=EXPIRY_DAYS),
        'explanation': row.explanation,
        'amount_freed': snap.get('amount_freed'),
        'sponsorship_count': len(snap.get('sponsorships') or ()),
        'tranches_to_withhold': len(snap.get('tranches_to_withhold') or ()),
        'decided_by_name': row.decided_by_name, 'decided_at': row.decided_at,
        'decision_note': row.decision_note,
    }


def narrow_list(qs, value, now=None):
    """The Applications list's ``?withdrawal=pending``: the cases with a live (unexpired) pending request.
    Any other value leaves ``qs`` alone. It narrows INSIDE the caller's fence (an EXISTS, no extra rows)."""
    if value != 'pending':
        return qs
    from django.db.models import Exists, OuterRef
    live = _model().objects.filter(live_pending_q(now), application_id=OuterRef('pk'))
    return qs.filter(Exists(live))


def waiting_for(admin, now=None):
    """How many live requests wait for ``admin``'s decision (the Overview's ``award_withdrawals`` card).
    org-fence: the caller's own organisation only; a super decides none."""
    if admin is None or getattr(admin, 'is_super', False) or not admin.has_perm(APPROVE_KEY):
        return 0
    rows = (_model().objects.filter(live_pending_q(now))
            .filter(organisation_id=admin.owning_organisation_id))
    return sum(1 for r in rows if decide_refusal(r, admin) is None)


# ── the locks ──────────────────────────────────────────────────────────────────────────────────

def _every_status():
    from .models import ScholarshipApplication
    return tuple(c for c, _ in ScholarshipApplication.STATUS_CHOICES)


def _lock_row(pk):
    """Step (2): the request row, locked and re-read. None when it has gone."""
    return _model().objects.select_for_update().filter(pk=pk).first()


def _expire_or_refuse(row, now):
    """Under the request lock: a pending row past its time is WRITTEN expired. Returns the refusal code
    (``not_pending``) or None. The caller raises it AFTER its transaction commits, so the write stays."""
    if row.status == row.PENDING and is_expired(row, now):
        row.status = row.EXPIRED
        row.save(update_fields=['status'])
        return 'not_pending'
    return None if row.status == row.PENDING else 'not_pending'


def _application_id_of(pk):
    app_id = _model().objects.filter(pk=pk).values_list('application_id', flat=True).first()
    if app_id is None:
        raise AwardWithdrawalError('not_found')
    return app_id


def _holding_matches(holding, snapshot):
    """Do the case's holding sponsorships still match what the maker saw (ids and amounts)?"""
    want = sorted((int(s['id']), Decimal(str(s['amount']))) for s in (snapshot or {}).get('sponsorships', ()))
    return sorted((sp.pk, Decimal(sp.amount)) for sp in holding) == want


def _who(admin):
    return (getattr(admin, 'email', '') or '')[:254], (getattr(admin, 'name', '') or '').strip()[:255]


# ── the actions ────────────────────────────────────────────────────────────────────────────────

def request_withdrawal(application, *, by_admin, explanation):
    """The MAKER asks for ``application``'s award to be withdrawn. Writes the pending row (with
    `award_withdrawal.snapshot_of`) and a staff-activity line; NOTHING ELSE CHANGES. The checkers are
    emailed after commit. Returns the row. Raises ``AwardWithdrawalError``: ``wrong_role``,
    ``explanation_required`` / ``explanation_too_long``, ``not_awarded``, ``has_payments``,
    ``already_pending``, ``no_checker``."""
    from . import staff_activity
    from .status_lock import StatusRefused, lock_application_for
    if _seat_refusal(by_admin, REQUEST_KEY, application.owning_organisation_id):
        raise AwardWithdrawalError('wrong_role')
    text = _checked_text(explanation, code='explanation', required=True)
    now = timezone.now()
    with transaction.atomic():
        try:
            lock_application_for(application, wd.WITHDRAWABLE)            # (1)
        except StatusRefused:
            raise AwardWithdrawalError('not_awarded')
        if wd.has_payments(application):
            raise AwardWithdrawalError('has_payments')
        for row in _model().objects.select_for_update().filter(            # (2) the pending one, if any
                application_id=application.pk, status='pending'):
            if not is_expired(row, now):
                raise AwardWithdrawalError('already_pending')
            row.status = row.EXPIRED                                        # lazily expired, then replaced
            row.save(update_fields=['status'])
        checkers = eligible_checkers(application.owning_organisation_id, by_admin)
        if not checkers:
            raise AwardWithdrawalError('no_checker')
        email, name = _who(by_admin)
        try:
            with transaction.atomic():      # the database's own one-pending-per-case backstop
                row = _model().objects.create(
                    application=application, organisation_id=application.owning_organisation_id,
                    explanation=text, requested_by=by_admin, requested_by_email=email,
                    requested_by_name=name, snapshot=wd.snapshot_of(application))
        except IntegrityError:
            raise AwardWithdrawalError('already_pending')
        staff_activity.record(by_admin, staff_activity.WITHDRAWAL_REQUESTED, application,
                              meta={'withdrawal': row.pk})
        transaction.on_commit(lambda: _mail_checkers(row.pk, [a.pk for a in checkers]))
    return row


def approve_withdrawal(pk, *, by_admin, note=''):
    """The CHECKER approves request ``pk``: the withdrawal runs (`award_withdrawal._apply`), in ONE
    transaction, in the house lock order. Returns the row. Raises ``AwardWithdrawalError``:
    ``note_too_long``, ``not_found``, ``not_awarded``, ``not_pending``, ``wrong_role`` / ``same_person``,
    ``stale``, ``has_payments``."""
    from . import staff_activity
    from .status_lock import StatusRefused, lock_application_for
    text = _checked_text(note, code='note', required=False)
    app_id = _application_id_of(pk)
    refusal = None
    with transaction.atomic():
        try:
            application = lock_application_for(app_id, wd.WITHDRAWABLE)     # (1)
        except StatusRefused:
            raise AwardWithdrawalError('not_awarded')
        row = _lock_row(pk)                                                 # (2)
        if row is None:
            raise AwardWithdrawalError('not_found')
        now = timezone.now()
        refusal = _expire_or_refuse(row, now)
        if refusal is None:
            refusal = decide_refusal(row, by_admin)                         # (3)
            if refusal is None:
                if not _holding_matches(wd.holding_sponsorships(application), row.snapshot):   # (4)
                    raise AwardWithdrawalError('stale')
                if wd.has_payments(application):                            # (5)
                    raise AwardWithdrawalError('has_payments')
                holding = wd.holding_sponsorships(application, lock=True)   # (6)
                if not _holding_matches(holding, row.snapshot):
                    raise AwardWithdrawalError('stale')
                email, name = _who(by_admin)
                row.status, row.decided_by, row.decided_at = row.APPROVED, by_admin, now
                row.decided_by_email, row.decided_by_name, row.decision_note = email, name, text
                row.save(update_fields=['status', 'decided_by', 'decided_at', 'decided_by_email',
                                        'decided_by_name', 'decision_note'])
                wd._apply(application, holding, by_admin=by_admin, explanation=row.explanation, meta={
                    'withdrawal': row.pk,
                    'requested_by_email': row.requested_by_email, 'requested_by_name': row.requested_by_name,
                    'requested_at': row.requested_at.isoformat(), 'explanation': row.explanation,
                    'approved_by_email': email, 'approved_by_name': name, 'decision_note': text})
                staff_activity.record(by_admin, staff_activity.WITHDRAWAL_APPROVED, application,
                                      meta={'withdrawal': row.pk})
                transaction.on_commit(lambda: _mail_maker(row.pk))
    if refusal:
        raise AwardWithdrawalError(refusal)
    return row


def _close(pk, *, by_admin, status, verb, note, refusal_of, mail_maker):
    """Refuse or cancel: the same lock order as the approval — (1) the application (whatever its status:
    a lock for ORDER only), (2) the request — and NEITHER touches the case."""
    from . import staff_activity
    from .status_lock import lock_application_for
    app_id = _application_id_of(pk)
    refusal = None
    with transaction.atomic():
        application = lock_application_for(app_id, _every_status())          # (1)
        row = _lock_row(pk)                                                  # (2)
        if row is None:
            raise AwardWithdrawalError('not_found')
        now = timezone.now()
        refusal = _expire_or_refuse(row, now) or refusal_of(row, by_admin)
        if refusal is None:
            email, name = _who(by_admin)
            row.status, row.decided_by, row.decided_at = status, by_admin, now
            row.decided_by_email, row.decided_by_name, row.decision_note = email, name, note
            row.save(update_fields=['status', 'decided_by', 'decided_at', 'decided_by_email',
                                    'decided_by_name', 'decision_note'])
            staff_activity.record(by_admin, verb, application, meta={'withdrawal': row.pk})
            if mail_maker:
                transaction.on_commit(lambda: _mail_maker(row.pk))
    if refusal:
        raise AwardWithdrawalError(refusal)
    return row


def refuse_withdrawal(pk, *, by_admin, reason):
    """The CHECKER refuses request ``pk`` with a required reason; the award stands. The maker is emailed.
    Raises ``reason_required`` / ``reason_too_long``, ``not_found``, ``not_pending``, ``wrong_role`` /
    ``same_person``."""
    from . import staff_activity
    text = _checked_text(reason, code='reason', required=True)
    return _close(pk, by_admin=by_admin, status='refused', verb=staff_activity.WITHDRAWAL_REFUSED, note=text,
                  refusal_of=decide_refusal, mail_maker=True)


def _cancel_refusal(row, admin):
    if admin is None or getattr(admin, 'is_super', False) or not is_maker(row, admin):
        return 'wrong_role'
    return None if _in_org(admin, row.organisation_id) else 'wrong_role'


def cancel_withdrawal(pk, *, by_admin):
    """The MAKER takes back their own pending request (nobody else may). Raises ``not_found``,
    ``not_pending``, ``wrong_role``."""
    from . import staff_activity
    return _close(pk, by_admin=by_admin, status='cancelled', verb=staff_activity.WITHDRAWAL_CANCELLED,
                  note='', refusal_of=_cancel_refusal, mail_maker=False)


# ── after commit, best-effort ──────────────────────────────────────────────────────────────────

def _mail_checkers(pk, checker_ids):
    from apps.courses.models import PartnerAdmin
    from .emails import send_withdrawal_requested_email
    try:
        row = _model().objects.get(pk=pk)
        send_withdrawal_requested_email(row, list(PartnerAdmin.objects.filter(pk__in=checker_ids).order_by('pk')))
    except Exception:   # an email must never undo, or appear to undo, a committed request
        wd.logger.exception('award_withdrawal_chain: request %s saved but the checker email raised', pk)


def _mail_maker(pk):
    from .emails import send_withdrawal_outcome_email
    try:
        send_withdrawal_outcome_email(_model().objects.get(pk=pk))
    except Exception:   # never undoes the committed decision
        wd.logger.exception('award_withdrawal_chain: request %s decided but the maker email raised', pk)
