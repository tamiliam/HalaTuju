"""The ONE choke-point for a write that depends on an application's status (TD-383, sprint A1.4).

WHY. A money writer used to judge the status on a copy it read earlier — the view's object, or a
row loaded before the transaction began. A close, a hold or another writer could commit in
between, and the money moved anyway: a payment run paid a CLOSED student (TD-367), a sponsor's
fund wrote ``awarded`` over ``closed`` (TD-365), a tranche went out to a student put on hold a
moment before (TD-420).

WHAT. ``lock_application_for`` takes the application row ``select_for_update`` INSIDE the caller's
transaction, re-reads it, refuses unless the status is one the caller names, and copies the fresh
row onto the caller's instance, so everything the writer reads afterwards (status, sub-state,
award amount, payment credit) is the committed value under the lock. ``lock_applications_for`` is
the same for many rows at once, locked in primary-key order.

LOCK ORDER (one order everywhere, so two writers can never deadlock):
  1. a payment RUN (``payments_chain._lock``; ``maintenance.set_substate`` takes the run locks
     before it writes the application);
  2. the APPLICATION row(s), in primary-key order;
  3. the SPONSOR row (``lock_sponsor_wallet``, A1.5), before a wallet balance is read for a spend;
  4. the rows that hang off them (a Sponsorship, a Disbursement / tranche).
A writer may skip a step, never reverse two. ``closure.close_application`` takes only the
application row. ``sponsorship.cancel_offer`` and the offer-lapse job (``lapse_expired_offers``)
lock a Sponsorship together with its application and never take the sponsor row, so they cannot
wait on a fund that holds it. The sponsor lock is FOR NO KEY UPDATE: a Sponsorship insert's
foreign-key check (FOR KEY SHARE on the sponsor) does not wait on it.

⚠ SQLite (the test database) ignores ``select_for_update``. The tests therefore prove the RE-READ
(a stale copy is refused), which is what makes the lock count on PostgreSQL: there a second writer
waits on the row and then reads the committed value.
"""
from django.db import transaction

from .models import ScholarshipApplication


class StatusRefused(Exception):
    """The locked row's status is not one the caller allows. ``status`` is what the row holds now
    (None when the row has gone). Each caller turns this into its own stable error code."""
    def __init__(self, status):
        self.status = status
        super().__init__(f'status_refused:{status}')


def _require_atomic():
    if not transaction.get_connection().in_atomic_block:
        # A lock outside a transaction is released at once and protects nothing.
        raise RuntimeError('lock_application_for must run inside transaction.atomic')


def _copy_onto(instance, row):
    """Every concrete field of the fresh ``row`` onto the caller's ``instance`` (cached relations,
    e.g. a select_related profile, are kept)."""
    if instance is row:
        return
    for f in ScholarshipApplication._meta.concrete_fields:
        setattr(instance, f.attname, getattr(row, f.attname))


def lock_application_for(application, allowed_statuses):
    """Lock and re-read ``application`` (an instance or a pk); refuse unless its status is in
    ``allowed_statuses``. Returns the caller's instance refreshed from the locked row (or the
    locked row when a pk was passed). Raises ``StatusRefused``."""
    _require_atomic()
    pk = getattr(application, 'pk', application)
    row = ScholarshipApplication.objects.select_for_update().filter(pk=pk).first()
    if row is None:
        raise StatusRefused(None)
    if row.status not in allowed_statuses:
        raise StatusRefused(row.status)
    if isinstance(application, ScholarshipApplication):
        _copy_onto(application, row)
        return application
    return row


def lock_applications_for(applications, allowed_statuses):
    """Lock and re-read several application INSTANCES in primary-key order, refreshing each in
    place. Returns the list of those whose locked status is not in ``allowed_statuses`` (or whose
    row has gone); the caller decides whether that refuses the whole write. Never raises."""
    _require_atomic()
    by_pk = {}
    for app in applications:
        by_pk.setdefault(app.pk, []).append(app)
    rows = {r.pk: r for r in ScholarshipApplication.objects.select_for_update()
            .filter(pk__in=list(by_pk)).order_by('pk')}
    refused = []
    for pk, instances in by_pk.items():
        row = rows.get(pk)
        for app in instances:
            if row is None:
                refused.append(app)
                continue
            _copy_onto(app, row)
            if row.status not in allowed_statuses:
                refused.append(app)
    return refused


def lock_sponsor_wallet(sponsor):
    """Lock the SPONSOR row inside the caller's transaction before a spend reads the wallet
    balance (A1.5). Two funds by one sponsor (two tabs, or the Support button against the
    standing-gift job) then run one after the other, and the second reads a balance that already
    counts the first. Step 3 of the lock order above: after the application row. No-op on SQLite."""
    _require_atomic()
    from .models import Sponsor
    list(Sponsor.objects.select_for_update(no_key=True).filter(pk=sponsor.pk).values_list('pk', flat=True))
