"""Organisation Payments module — monthly Vircle payment runs (money OUT to students).

Service layer for the Payments module (plan docs/plans/2026-07-16-payments-module-plan.md).
Follows the ``disbursement.py`` shape: pure service functions + a ``PaymentsError(code)``.

The model (D1): a ``PaymentRun`` + ``PaymentRunItem`` pair holds the WORKING state (draft
amounts, per-student exclusions, the two typed signatures) on top of the immutable
``Disbursement`` ledger. Released ``Disbursement`` rows are created ONLY at countersignature
(``complete``), so **"paid to date" is always SUM(released disbursements)** — one source of
truth shared by history, the backfill, and future runs.

Sign-off (D2) is a maker→checker chain: ``draft → admin_signed → completed`` (+ ``cancelled``).
The two signers must be different people; the typed name must match the signer's
``PartnerAdmin.name`` (trimmed, case-insensitive), mirroring the bursary agreement.

Deliberately WIDER than ``disbursement.release_tranche`` (D3): ``complete`` writes ``released``
rows for an application in ``('awarded','active','maintenance')`` — the real cohort is paid
while still at ``'awarded'`` (the bursary-agreement chain isn't live in-app). **This module
NEVER flips application status** (the ``active → maintenance`` flip stays ``release_tranche``'s
business).
"""
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from .models import Disbursement, PaymentRun, PaymentRunItem, ScholarshipApplication

logger = logging.getLogger(__name__)

# Single flat rate for EVERY student (D6, owner 2026-07-16). STPM is not a higher rate — its
# RM3,000 award simply runs longer (15 months vs the standard 10).
MONTHLY_RATE = Decimal('200')

# Application statuses that may appear in / be paid by a run (D3/D4-2). Wider than
# pool.FUNDED_STATES because the cohort is paid while at 'awarded'.
PAYABLE_STATUSES = ('awarded', 'active', 'maintenance')

# D4-3 (owner 2026-07-16) — the MONTH a pathway's payments FIRST open, as a HARD floor applied
# even to continuing students: STPM/Matric/Asasi → July, Poly/UA Diploma (`university`) →
# August, PISMP → September. (There is no UA degree — every BrightPath student is post-SPM, so
# `university` is always the UA Diploma.) A run before a student's floor never pays them; and a
# student is never paid before they've physically reported (`reporting_date`), so a late arrival
# isn't paid early. Default is July for any unmapped pathway.
PATHWAY_PAYMENT_START_MONTH = {
    'stpm': 7, 'matric': 7, 'asasi': 7,   # July
    'poly': 8, 'university': 8,           # August (Poly + UA Diploma)
    'pismp': 9,                           # September
}
_DEFAULT_PAYMENT_START_MONTH = 7

_ZERO = Decimal('0')
_CENTS = Decimal('0.01')


class PaymentsError(Exception):
    """Raised by the service with a machine code for the view (e.g. 'past_date',
    'name_mismatch', 'same_signer', 'not_draft', 'amount_over_cap')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


# ── amounts ───────────────────────────────────────────────────────────────────

def _money(value):
    """Normalise to a non-negative 2dp Decimal (0 is allowed — a credit line can be RM0)."""
    try:
        v = Decimal(str(value)).quantize(_CENTS)
    except (InvalidOperation, ValueError, TypeError):
        raise PaymentsError('bad_amount')
    if v < 0:
        raise PaymentsError('bad_amount')
    return v


def paid_to_date(application):
    """SUM(amount) of the application's RELEASED disbursements — the one truth for history."""
    total = (application.disbursements.filter(status='released')
             .aggregate(s=Sum('amount'))['s'])
    return (total or _ZERO)


def _remaining(application):
    award = application.award_amount or _ZERO
    rem = award - paid_to_date(application)
    return rem if rem > 0 else _ZERO


def _schedule_row(application):
    """The versioned contract-template schedule row governing this application (the
    signed agreement's pinned template, else the org's active template), or ``None``
    → the legacy flat behaviour (``MONTHLY_RATE`` + ``PATHWAY_PAYMENT_START_MONTH``,
    byte-identical to pre-cutover). This is the ONE seam the payments module reads the
    contract module through."""
    from . import contracts
    template = contracts.template_for_application(application)
    if template is None:
        return None
    return contracts.schedule_row_for(template, application)


def _row_rate(row):
    return row.monthly_amount if row is not None else MONTHLY_RATE


def default_amount(application, row=None):
    """D6: amount_due = clamp(RATE − payment_credit, 0, award_amount − paid_to_date).
    RATE is the governing template row's ``monthly_amount`` when a contract template
    governs the app, else ``MONTHLY_RATE`` (seeded BrightPath v1 = RM200 → identical)."""
    if row is None:
        row = _schedule_row(application)
    credit = application.payment_credit or _ZERO
    due = _row_rate(row) - credit
    if due < 0:
        due = _ZERO
    rem = _remaining(application)
    if due > rem:
        due = rem
    return due.quantize(_CENTS)


def _credit_applied(application, rate=None):
    """How much of the paid-ahead credit this run consumes: min(credit, RATE) — the amount it
    offsets against the flat rate (rolls any excess over to the next run)."""
    credit = application.payment_credit or _ZERO
    if rate is None:
        rate = _row_rate(_schedule_row(application))
    return (credit if credit < rate else rate).quantize(_CENTS)


# ── eligibility (D4) ────────────────────────────────────────────────────────────

def _pathway_payment_start(application, row=None):
    """D4-3: the 1st-of-the-month a pathway's payments open, in the cohort year (the HARD floor —
    July / August / September). The month comes from the governing template row's ``start_month``
    when a template governs the app, else ``PATHWAY_PAYMENT_START_MONTH`` (seeded rows use the
    same 7/7/7/8/8/9 → identical)."""
    year = application.cohort.year if application.cohort_id else timezone.localdate().year
    if row is None:
        row = _schedule_row(application)
    if row is not None:
        month = row.start_month
    else:
        pathway = (application.chosen_pathway or '').strip().lower()
        month = PATHWAY_PAYMENT_START_MONTH.get(pathway, _DEFAULT_PAYMENT_START_MONTH)
    return date(year, month, 1)


def _has_started(application, payment_date, row=None):
    """D4-3 (owner 2026-07-16): payable on this run only when BOTH hold — (1) the pathway's
    payment window has opened (`payment_date >= the July/Aug/Sep floor`), applied even to a
    continuing student; AND (2) the student has physically reported (`reporting_date <=
    payment_date`, when set) so a late arrival is never paid early."""
    if payment_date < _pathway_payment_start(application, row):
        return False
    reporting = application.reporting_date
    return reporting is None or reporting <= payment_date


def _schedule_status(row, application, period_month):
    """Where ``period_month`` (the 1st of the covered month) falls in the template
    schedule: 'paid' | 'gap' (an exam/skip month within the span) | 'complete' (past
    the last paid month) | None (no template governs the app, or before the schedule
    — the start-month floor handles that). Drives the gap_month / schedule_complete
    greyed reasons; None means the legacy path adds no schedule reason (parity)."""
    if row is None or period_month is None:
        return None
    cohort_year = application.cohort.year if application.cohort_id else None
    if cohort_year is None:
        return None
    offset = (period_month.year - cohort_year) * 12 + (period_month.month - row.start_month)
    paid = {int(o) for o in (row.paid_offsets or [])}
    if offset in paid:
        return 'paid'
    if offset < 0:
        return None
    last = max(paid) if paid else -1
    return 'complete' if offset > last else 'gap'


def _is_on_hold(application):
    """D4-5: the only break-like signal in the data today — maintenance 'on_hold'."""
    return application.status == 'maintenance' and application.maintenance_substate == 'on_hold'


def _vircle_confirmation_pending(application):
    """D4-4 (owner 2026-07-16): the student was emailed the Vircle setup task but hasn't
    confirmed it yet — an `open` (unresolved) `vircle_setup_pending` resolution item. The 8
    legacy students onboarded outside that flow have NO such item and so are never "pending"
    (their eWallet ID alone is the payable fact); a student who resolved the task is confirmed.
    """
    from .resolution import VIRCLE_CODE
    return (application.resolution_items
            .filter(code=VIRCLE_CODE).exclude(status='resolved').exists())


def _already_paid_for_period(application, period_month):
    """True if the student already has a COMPLETED run for this month — so a month is never paid
    twice, even when the run dates differ (owner 2026-07-16: a run dated 30 Jun can pay for July,
    and a later July-dated run must not pay the same student again)."""
    if period_month is None:
        return False
    return PaymentRunItem.objects.filter(
        application=application, included=True,
        run__status='completed', run__period_month=period_month,
    ).exists()


def eligibility(application, payment_date, period_month=None):
    """Per-student eligibility for a run on ``payment_date`` paying for ``period_month`` (the 1st
    of the covered month). Returns ``{eligible, reasons, remaining, vircle_ready, started}``.
    ``reasons`` names the D4-4/5/6 + already-paid failures (the greyed-out list); status/started
    failures are handled by the caller (not listed at all)."""
    row = _schedule_row(application)
    started = _has_started(application, payment_date, row)
    reasons = []
    # Contract-schedule greying (D5): a template exam/skip month or a month past the
    # schedule end is greyed with a reason. None (no template) adds nothing → the legacy
    # run is byte-identical for every paid month.
    sched = _schedule_status(row, application, period_month)
    if sched == 'gap':
        reasons.append('gap_month')             # exam-month skip (e.g. STPM Dec/Jun)
    elif sched == 'complete':
        reasons.append('schedule_complete')     # past the last scheduled payment
    has_id = bool((application.vircle_id or '').strip())
    # eWallet-ready (D4-4) = has an ID AND no unconfirmed setup task pending.
    vircle_ready = has_id and not _vircle_confirmation_pending(application)
    if not has_id:
        reasons.append('no_vircle_id')          # D4-4
    elif not vircle_ready:
        reasons.append('vircle_unconfirmed')    # D4-4 — emailed but not yet confirmed
    if _already_paid_for_period(application, period_month):
        reasons.append('already_paid')          # no double-paying a month
    if _is_on_hold(application):
        reasons.append('on_hold')               # D4-5
    remaining = _remaining(application)
    if remaining <= 0:
        reasons.append('no_balance')            # D4-6
    # D4-7 (future, flag-gated): agreement fully executed. Built off, default disabled.
    if getattr(settings, 'BURSARY_AGREEMENT_ENABLED', False):
        agr = getattr(application, 'bursary_agreement', None)
        if agr is None or getattr(agr, 'foundation_signed_at', None) is None:
            reasons.append('agreement_unsigned')
    return {
        'eligible': started and not reasons,
        'reasons': reasons,
        'remaining': remaining,
        'vircle_ready': vircle_ready,
        'started': started,
    }


def eligible_rows(organisation, payment_date, period_month=None):
    """The single choke-point (D5) for a run's candidate students, org-fenced (D4-1).
    Returns a list of ``{application, eligible, reasons, remaining, vircle_ready}`` for every
    org application that is payable-status (D4-2) AND has started (D4-3). Rows failing 4–6 (or
    already paid for ``period_month``) come back with ``eligible=False`` + reasons (shown
    greyed-out); status/not-started are excluded entirely."""
    qs = (ScholarshipApplication.objects
          .filter(owning_organisation=organisation, status__in=PAYABLE_STATUSES)
          .select_related('cohort', 'profile').order_by('id'))
    rows = []
    for app in qs:
        elig = eligibility(app, payment_date, period_month=period_month)
        if not elig['started']:
            continue   # D4-3 failure → not listed at all
        rows.append({
            'application': app,
            'eligible': elig['eligible'],
            'reasons': elig['reasons'],
            'remaining': elig['remaining'],
            'vircle_ready': elig['vircle_ready'],
        })
    return rows


# ── run lifecycle ───────────────────────────────────────────────────────────────

def _next_reference(payment_date):
    """A unique, human-readable run reference carrying the actual pay DATE, e.g.
    'PR-2026-07-17' (owner 2026-07-16: the old 'PR-2026-07-001' read like a date). A second run
    on the same date gets '…-02'."""
    base = f'PR-{payment_date:%Y-%m-%d}'
    if not PaymentRun.objects.filter(reference=base).exists():
        return base
    n = 1
    while True:
        n += 1
        ref = f'{base}-{n:02d}'
        if not PaymentRun.objects.filter(reference=ref).exists():
            return ref


@transaction.atomic
def create_run(organisation, payment_date, period_month, by_email=''):
    """Create a DRAFT run for ``organisation`` on ``payment_date`` paying for ``period_month``
    (any day of the covered month; stored normalised to the 1st) — D4/D6. Rejects a past date
    (``past_date``). Snapshots one PaymentRunItem per ELIGIBLE student. Greyed-out students (incl.
    those already paid for ``period_month``) are NOT items — they surface on the detail view."""
    if payment_date < timezone.localdate():
        raise PaymentsError('past_date')
    pm = period_month.replace(day=1)
    run = PaymentRun.objects.create(
        organisation=organisation, payment_date=payment_date, period_month=pm,
        reference=_next_reference(payment_date),
        created_by=(by_email or '')[:254],
    )
    for erow in eligible_rows(organisation, payment_date, period_month=pm):
        if not erow['eligible']:
            continue
        app = erow['application']
        sched_row = _schedule_row(app)
        PaymentRunItem.objects.create(
            run=run, application=app, included=True,
            amount=default_amount(app, sched_row),
            credit_applied=_credit_applied(app, _row_rate(sched_row)),
            award_amount_snapshot=(app.award_amount or _ZERO),
            paid_to_date_snapshot=paid_to_date(app),
            vircle_id_snapshot=(app.vircle_id or ''),
        )
    return run


def _revert_to_draft(run):
    """Editing an admin_signed run reverts it to draft and clears the maker signature (D2 —
    'nobody signs one list and sends another')."""
    run.status = 'draft'
    run.admin_signed_name = ''
    run.admin_signed_email = ''
    run.admin_signed_at = None
    run.save(update_fields=[
        'status', 'admin_signed_name', 'admin_signed_email', 'admin_signed_at', 'updated_at'])


def set_item(run_item, *, included=None, exclude_reason=None, amount=None):
    """Edit a run item (draft only, or admin_signed → reverts to draft). Enforces: an excluded
    item needs a reason (``reason_required``); the amount is floored at 0 and capped at the
    snapshotted remaining award (``amount_over_cap``). Returns the item."""
    run = run_item.run
    if run.status not in ('draft', 'admin_signed'):
        raise PaymentsError('not_editable')
    if run.status == 'admin_signed':
        _revert_to_draft(run)

    if included is not None:
        run_item.included = bool(included)
    if run_item.included:
        run_item.exclude_reason = ''
    elif exclude_reason is not None:
        run_item.exclude_reason = (exclude_reason or '').strip()[:200]
    if not run_item.included and not run_item.exclude_reason:
        raise PaymentsError('reason_required')

    if amount is not None:
        val = _money(amount)
        cap = run_item.award_amount_snapshot - run_item.paid_to_date_snapshot
        if cap < 0:
            cap = _ZERO
        if val > cap:
            raise PaymentsError('amount_over_cap')
        run_item.amount = val
    run_item.save()
    return run_item


def _name_matches(admin, typed_name):
    return bool((typed_name or '').strip()) and \
        (typed_name or '').strip().casefold() == (admin.name or '').strip().casefold()


@transaction.atomic
def sign(run, admin, typed_name):
    """The maker→checker sign-off (D2). On a DRAFT run: the MAKER (role ``admin``, or super)
    signs → ``admin_signed``. On an ADMIN_SIGNED run: the APPROVER (role ``org_admin``, or
    super) countersigns → ``complete(run)`` → ``completed``. The two signers must be different
    people (``same_signer``); the typed name must match the signer's PartnerAdmin.name
    (``name_mismatch``); a wrong role → ``wrong_role``. Returns the run."""
    if run.status not in ('draft', 'admin_signed'):
        raise PaymentsError('bad_state')
    if not _name_matches(admin, typed_name):
        raise PaymentsError('name_mismatch')
    is_super = bool(getattr(admin, 'is_super', False))
    now = timezone.now()

    if run.status == 'draft':
        if not (is_super or admin.role == 'admin'):
            raise PaymentsError('wrong_role')
        run.admin_signed_name = (admin.name or '').strip()[:200]
        run.admin_signed_email = (admin.email or '')[:254]
        run.admin_signed_at = now
        run.status = 'admin_signed'
        run.save(update_fields=[
            'admin_signed_name', 'admin_signed_email', 'admin_signed_at', 'status', 'updated_at'])
        # Tell the organisation admin(s) the run awaits their countersignature (owner
        # 2026-07-16). Best-effort — the function never raises.
        from . import emails
        emails.send_payment_countersign_email(run)
        return run

    # admin_signed → countersign
    if not (is_super or admin.role == 'org_admin'):
        raise PaymentsError('wrong_role')
    if (admin.email or '').strip().casefold() == (run.admin_signed_email or '').strip().casefold():
        raise PaymentsError('same_signer')
    run.org_admin_signed_name = (admin.name or '').strip()[:200]
    run.org_admin_signed_email = (admin.email or '')[:254]
    run.org_admin_signed_at = now
    run.status = 'completed'
    run.save(update_fields=[
        'org_admin_signed_name', 'org_admin_signed_email', 'org_admin_signed_at',
        'status', 'updated_at'])
    complete(run)
    return run


@transaction.atomic
def complete(run):
    """Realise a completed run into the ledger (D3/D6). For each INCLUDED item: create a
    ``released`` Disbursement for a positive amount (``reference='vircle:<run.reference>'``,
    ``scheduled_for=payment_date``) and decrement the application's ``payment_credit`` by
    ``credit_applied`` (never below 0). Then best-effort write the CSV + send the (stub)
    email — a failure there never breaks the completed run (the DB is the record). Accepts
    'awarded'/'active'/'maintenance'.

    Maintenance flip (go-live transition, 2026-07-19): a released item for an application at
    'active' flips it to 'maintenance' (the recurring funded loop) — the FIRST payment only,
    never from 'awarded'. This mirrors ``disbursement._flip_to_maintenance`` (the same effect the
    ad-hoc release path already had); the payment RUN is the real cohort's first payout, so it must
    carry the same flip. Historically ``complete`` never touched status; that gap left the whole
    run cohort stuck at 'active' after their first run."""
    from . import sheets
    from . import emails
    from .disbursement import _flip_to_maintenance
    now = timezone.now()
    actioned_by = (run.org_admin_signed_email or run.created_by or '')[:254]

    for item in run.items.select_related('application'):
        if not item.included:
            continue
        app = item.application
        if item.amount and item.amount > 0:
            top = app.disbursements.aggregate(m=Max('sequence'))['m'] or 0
            disb = Disbursement.objects.create(
                application=app, amount=item.amount, status='released',
                sequence=top + 1, released_at=now, scheduled_for=run.payment_date,
                actioned_by=actioned_by, reference=f'vircle:{run.reference}'[:100],
                label=f'Vircle {run.payment_date:%b %Y}'[:100],
            )
            item.disbursement = disb
            item.save(update_fields=['disbursement', 'updated_at'])
            # First real payout → enter the recurring loop (active → maintenance). Idempotent
            # and a no-op from 'awarded'/'maintenance'/'closed' (see _flip_to_maintenance).
            _flip_to_maintenance(app)
        applied = item.credit_applied or _ZERO
        if applied > 0:
            new_credit = (app.payment_credit or _ZERO) - applied
            app.payment_credit = new_credit if new_credit > 0 else _ZERO
            app.save(update_fields=['payment_credit'])

    # Best-effort side effects — the DB is already the record.
    try:
        url = sheets.write_payment_csv(run)
    except Exception:
        logger.warning('Payments: CSV write failed for run %s', run.reference, exc_info=True)
        url = None
    if url:
        run.drive_file_url = url
        run.save(update_fields=['drive_file_url', 'updated_at'])
    try:
        emails.send_payment_run_email(run)
    except Exception:
        logger.warning('Payments: run-email stub failed for run %s', run.reference, exc_info=True)
    return run


def cancel(run, by=''):
    """Cancel a draft or admin_signed run (never a completed one)."""
    if run.status not in ('draft', 'admin_signed'):
        raise PaymentsError('bad_state')
    run.status = 'cancelled'
    run.note = (run.note or '')
    run.save(update_fields=['status', 'updated_at'])
    return run


# ── Vircle ID (D9) ────────────────────────────────────────────────────────────

def vircle_id_prefix():
    return getattr(settings, 'VIRCLE_ID_PREFIX', '8000400175')


def valid_vircle_id(value):
    """D9: a full 13-digit ID starting with the standard prefix. Shared by the Action-Centre
    resolve endpoint and the admin PATCH path."""
    v = (value or '').strip()
    return v.isdigit() and len(v) == 13 and v.startswith(vircle_id_prefix())
