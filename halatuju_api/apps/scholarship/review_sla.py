"""The verdict clock — ONE home for "when is this review due, and how late is it?".

⚠⚠ **THIS MODULE EXISTS BECAUSE THE SAME ARITHMETIC WAS WRITTEN THREE TIMES.** `assigned_at +
review_sla_days` lived inline in the nudge sweep, in the assignment email and in the interview
reminder's verdict-due line. Three copies of one rule is three places for it to drift, and the
Programme Overview's attention panel would have been a FOURTH — a helper added beside three
surviving copies is not a consolidation, it is one more copy (the "count the callers" lesson,
`docs/lessons.md`). All three callers were migrated in the same commit that created this file,
and each is held there by a test that patches `review_due` to raise and asserts the caller
raises.

⚠ **THE BANDS ARE THE SWEEP'S OWN BOUNDARIES, COPIED EXACTLY.** `send_review_nudges` fires the
overdue nudge at `now >= due` and the approaching nudge over `due - soon_days <= now < due`.
`review_band` says `overdue` and `due_soon` on exactly those conditions, so a case the Overview
calls overdue is a case the sweep would have emailed about. If the two ever disagree, a reviewer
reads one story on screen and another in their inbox.

⚠ **THE CLOCKS ARE PER-ORGANISATION** (Org Config Sprint C). A caller sweeping many applications
should read them ONCE per organisation and pass them in as `clocks=` — the sweep keeps its own
per-org cache and this module must not force it to give that up.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.courses import org_config

#: Statuses where a verdict is no longer expected (terminal / already-decided).
#:
#: ⚠ MOVED HERE FROM `send_review_nudges._TERMINAL`, which now imports it. The nudge population
#: and the Overview's attention panel are the same population by definition; two literals would
#: let them part company the first time a status was added.
TERMINAL = {'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected',
            'withdrawn', 'expired'}

#: Assigned, not yet decided, and not terminal — **the population with a verdict clock running**.
#: The same three conditions `send_review_nudges` builds its queryset from.
AWAITING_VERDICT = (
    Q(assigned_to__isnull=False)
    & Q(assigned_at__isnull=False)
    & Q(verdict_decided_at__isnull=True)
    & ~Q(status__in=TERMINAL)
)

#: The QC stage: a reviewer has submitted and the case waits for a checker. Never the reviewer's turn.
QC_STAGE = {'interviewed'}

#: ⚠ **THE REVIEWER'S TURN — the "My open" population (requests #81 + #86, 27 Nov 2026).** Assigned,
#: not terminal, not at QC, and EITHER no verdict saved, OR reopened by QC and not yet re-decided
#: (`decision_reopened_at` is cleared by the re-decision, `reopen.close_reopen_with_change`), OR a
#: verdict saved that never moved the case to QC (case 513: the Approve's submit was refused).
#: `AWAITING_VERDICT` missed the last two because both keep their `verdict_decided_at` stamp, so
#: both cases dropped off the reviewer's list while still theirs to finish.
#:
#: ⚠ ONLY `programme_overview.mine` (the count and its rows) and `in_band(..., 'open')` read this.
#: The nudges (`send_review_nudges`) and the due-soon / overdue bands stay on `AWAITING_VERDICT`:
#: their clock is `assigned_at`, which would call a case QC returned today "overdue" at once and
#: email the reviewer so (TD-NEW-REOPEN-NUDGE).
#:
#: ⚠ NO VERDICT TEST, ON PURPOSE. The three arms are, between them, every verdict state a case
#: before QC can be in (none saved / saved and reopened / saved and stuck), so their union is just
#: "before QC": a verdict test here could only drop one of them again, which is the bug.
REVIEWERS_TURN = (
    Q(assigned_to__isnull=False)
    & Q(assigned_at__isnull=False)
    & ~Q(status__in=TERMINAL | QC_STAGE)
)


def returned_by_qc(queryset):
    """``queryset`` with ``returned_by_qc``: the case is the REVIEWER'S TURN (`REVIEWERS_TURN`) AND
    an OPEN reopen took it back from AWAITING QC (`reopened_from='interviewed'`, the QC's send-back).
    Served for the "Returned by QC" mark on My open and the admin list (#86); one column, no query
    per row.

    ⚠ THE TURN TEST IS PART OF THE FLAG (review round 1). A reopen can stay open while the case
    moves on (`reopen.py` TD-486 note; a submit-decline does not close it), so the reopen alone
    would mark a resubmitted (`interviewed`) or `rejected` case "Returned by QC" for ever. The list
    and My open read this one column, so they share one rule."""
    from django.db.models import BooleanField, Case, Exists, OuterRef, Value, When

    from .models import DecisionReopen
    open_send_back = Exists(DecisionReopen.objects.filter(
        application=OuterRef('pk'), closed_at__isnull=True, reopened_from='interviewed'))
    return queryset.annotate(returned_by_qc=Case(
        When(REVIEWERS_TURN, then=open_send_back), default=Value(False), output_field=BooleanField()))


def clocks(org):
    """`(sla_days, soon_days, grace_days)` for one organisation.

    A blank org config means the platform's own REVIEW_* settings — `org_config.value`
    already delegates, so `None` is a valid argument and yields the platform clocks.
    """
    return (
        org_config.value(org, 'review_sla_days'),
        org_config.value(org, 'review_nudge_soon_days'),
        org_config.value(org, 'review_escalate_grace_days'),
    )


#: ⚠ A MODULE-PRIVATE ALIAS, not a duplicate. The public spelling of the keyword argument is
#: `clocks=` (that is what the callers read best), and a parameter of that name shadows the
#: function inside the body — so the functions below reach the resolver through this alias.
_resolve_clocks = clocks


def review_due(assigned_at, org=None, *, clocks=None):
    """When the verdict is due: `assigned_at + review_sla_days` for the owning organisation.

    Returns `None` for an unassigned application — "never assigned" and "due right now" must
    not render the same. Pass `clocks=` (the tuple from `clocks()`) to reuse a cached read
    rather than hitting `org_config` once per row.
    """
    if assigned_at is None:
        return None
    sla_days = (clocks or _resolve_clocks(org))[0]
    return assigned_at + timedelta(days=sla_days)


def review_band(assigned_at, org=None, *, now=None, clocks=None):
    """`'open' | 'due_soon' | 'overdue'` for one case's clock — or `None` if it has none.

    ⚠ **`now == due` IS OVERDUE, NOT DUE-SOON.** The sweep sends the overdue email at
    `now >= due`, so the boundary belongs to the later band. A `>` here would leave a case
    reading "due soon" on screen in the same minute its reviewer was emailed "overdue".

    ⚠ This bands the CASE'S CLOCK, never the person. Nothing here is a score, and the
    reviewer surface must not render it as one (`reviewerDetail.ts`).
    """
    if clocks is None:
        clocks = _resolve_clocks(org)
    due = review_due(assigned_at, org, clocks=clocks)
    if due is None:
        return None
    if now is None:
        now = timezone.now()
    if now >= due:
        return 'overdue'
    if due - timedelta(days=clocks[1]) <= now:
        return 'due_soon'
    return 'open'


def in_band(queryset, band, *, now, clocks):
    """The cases of `queryset` whose verdict clock is in `band` (`'overdue'`, `'due_soon'` or `'open'`).

    ⚠ THE SAME POPULATION AND THE SAME `review_band` AS `programme_overview.attention` / `mine`,
    so an Overview card's count equals the list it opens. The clock is one organisation's
    `(sla, soon)` pair, so each band is a plain range on `assigned_at` (TD-505: no id list, no
    Python pass): overdue is `assigned_at + sla <= now`, due-soon is `assigned_at + sla - soon <= now`
    but not overdue. The boundaries are `review_band`'s own, `now == due` being overdue.

    `band='open'` is the WHOLE awaiting-verdict population (the `my_open` card's count: every band
    is a subset of it), so it is the `REVIEWERS_TURN` filter itself, not a copy of it (#81 + #86: a
    case QC returned, or one whose verdict saved without reaching QC, is still the reviewer's)."""
    if band == 'open':
        return queryset.filter(REVIEWERS_TURN)
    qs = queryset.filter(AWAITING_VERDICT)
    sla, soon = clocks[0], clocks[1]
    overdue_at = now - timedelta(days=sla)
    if band == 'overdue':
        return qs.filter(assigned_at__lte=overdue_at)
    if band == 'due_soon':
        return qs.filter(assigned_at__gt=overdue_at,
                         assigned_at__lte=now - timedelta(days=sla - soon))
    return qs.none()
