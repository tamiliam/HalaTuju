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
