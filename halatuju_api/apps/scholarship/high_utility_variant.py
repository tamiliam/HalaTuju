"""Which of the three high-utility clarifies a household is asked (TD-306, 2026-09-29).

One question — "why are your water and electricity bills this high?" — in three wordings:

  high_utility_expense_str       a valid-STR household: asked against its STR status, no figure.
  high_utility_expense           an income is on file: quotes "the household income of RM {income}
                                 a month you reported".
  high_utility_expense_noincome  NO income on file: the same ask without that clause.

The third exists because the second used to be raised with no income to quote, and the web painted
the literal "RM {income}" to the student. The rule is now made here, once: the copy that quotes a
figure is chosen only when the figure exists (``pick``), and ``params`` fills exactly what that
copy quotes.

``high_utility_expense`` and ``_noincome`` differ only in whether the income can be quoted, so they
are ONE question to the student (``PAIR``):

  * an OPEN item of the pair that no longer matches the household (a row raised before TD-306 with
    no income on it, or income reported / withdrawn since) is re-coded and re-filled IN PLACE by
    ``reconcile_open`` — same row, same slot under the cap, no new-item email;
  * an item of the pair that already EXISTS (open or answered) stands for the other, so the student
    is never asked the same question twice (``stand_ins``).

The STR variant is deliberately outside the pair: its switch to and from the plain one is older than
TD-306 and unchanged by it.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

#: The SYNC's logger, not this module's: a re-code is part of `sync_check2_queries`, and anything
#: that filters or scrapes Check-2 lines by logger name keeps finding it there.
log = logging.getLogger('apps.scholarship.check2_queries')

PLAIN = 'high_utility_expense'
NOINCOME = 'high_utility_expense_noincome'
STR = 'high_utility_expense_str'
CODES = (PLAIN, NOINCOME, STR)
PAIR = frozenset({PLAIN, NOINCOME})


def pick(ctx):
    """The variant for a high-utility context (``income_engine.high_utility_expense_context``)."""
    if ctx.get('on_str'):
        return STR
    return PLAIN if ctx.get('income') is not None else NOINCOME


def params(ctx, code):
    """What ``code``'s copy quotes: the bill total always; the income only on the PLAIN variant."""
    out = {}
    if ctx.get('amount') is not None:
        out['amount'] = ctx['amount']
    if code == PLAIN and ctx.get('income') is not None:
        out['income'] = ctx['income']
    return out


def _stale(item, live):
    """An OPEN pair item whose copy cannot be painted honestly for this household now."""
    return item.code != live or (item.code == PLAIN and 'income' not in (item.params or {}))


def alive(code, gaps):
    """Is ``code`` still a live question? A pair code stays alive while EITHER pair wording is in
    the gaps — the wording may be out of date, but the question is not answered by the data, so the
    sync's auto-resolve must not close it (the re-code fixes the wording where the machine may ask;
    where it may not, the row stays as asked — owner 2026-07-13: an open ask is not withdrawn)."""
    return code in gaps or (code in PAIR and bool(PAIR & set(gaps)))


def reconcile_open(application, existing, gaps, may_ask):
    """Bring an OPEN pair row into line with the live wording (see module doc). Mutates
    ``existing`` (code -> item) so the caller's create and auto-resolve passes see the result.

    * The live code already has a row (two syncs raced and both raised): the open stale row is a
      DUPLICATE of a question that row carries — closed as system, like any housekeeping close, at
      every stage. It is never re-coded: that is the UNIQUE clash (review F1).
    * Otherwise, and only while the machine may ask (review F2), it is re-coded / re-filled in place
      inside a savepoint; an ``IntegrityError`` (a row the caller's snapshot did not hold) is
      swallowed and the row left exactly as it was — the next sync takes the branch above.
    One log line per change on the sync's own logger."""
    live = next((c for c in PAIR if c in gaps), None)
    if live is None:
        return
    for code in sorted(PAIR):
        item = existing.get(code)
        if item is None or item.status != 'open' or item.kind != 'clarify' or not _stale(item, live):
            continue
        if code != live and live in existing:
            item.status, item.resolved_by, item.resolved_at = 'resolved', 'system', timezone.now()
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
            log.info('high-utility duplicate closed: application=%s item=%s code=%s kept=%s item=%s',
                     application.pk, item.pk, code, live, existing[live].pk)
            continue
        if not may_ask:
            continue
        from .income_engine import high_utility_expense_context
        before = (item.code, item.params)
        item.code = live
        item.params = params(high_utility_expense_context(application) or {}, live)
        try:
            with transaction.atomic():
                item.save(update_fields=['code', 'params'])
        except IntegrityError:
            item.code, item.params = before
            log.warning('high-utility re-code skipped (row already on file): application=%s '
                        'item=%s code=%s -> %s', application.pk, item.pk, code, live)
            continue
        log.info('high-utility re-coded: application=%s item=%s code=%s -> %s',
                 application.pk, item.pk, code, live)
        del existing[code]
        existing[live] = item
        return


def stand_ins(existing):
    """``existing`` with each pair code that has no row of its own mapped to its sibling's row, so
    'already asked' holds across the pair. A new dict; the argument is not changed. For the
    'is it already asked?' reads ONLY — never iterate it to auto-resolve, or one row is seen twice
    under two codes and the alias (not in the gaps) closes a live question."""
    out = dict(existing)
    for code in PAIR:
        sibling = next(iter(PAIR - {code}))
        if code not in out and sibling in out:
            out[code] = out[sibling]
    return out
