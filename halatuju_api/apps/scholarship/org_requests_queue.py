"""The Requests LIST as a queue: which tab a request sits in, the filters, and the row tags.

Requests list R1 (2026-11-03). Split from `org_requests.py`, which has no line of room left in its
ledger, and because none of this is the request's LIFE — no transition, no permission, no e-mail.
It answers one question about a set of requests the caller may already read: *where on the list
does each one go?*

⚠ **NEEDS ACTION IS DECIDED HERE, ONCE.** The nav badge (`AdminOrgRequestCountView`) and the
list's "Needs action" tab both call `needs_action_q`, so the number on the badge that brought
somebody to the page is, by construction, the number on the tab they land on. Two copies of this
rule is how a badge says 3 while the tab says 2.

⚠ **THE TABS PARTITION THE LIST** (owner, option A, 2026-11-03). Every request sits in exactly one
of Needs action / In progress / Closed, and All is their sum. In progress is therefore "open and
NOT needs-action" — which includes an organisation's own untriaged request, waiting on nobody but
the engineer. Needs action is a subset of not-terminal for both roles today, and a test pins that.

⚠ **EVERY CHILD READ IS AN `Exists` SUBQUERY, NEVER A MULTI-VALUED JOIN.** The same `Q` sits
inside `.filter()` AND inside `aggregate(Count(..., filter=...))`; a join over `comments` or
`analyses` would multiply the rows it counts. Each subquery is correlated to the OUTER request by
`OuterRef('pk')`, so it can only ever see children of requests the caller's fenced queryset
already holds — the request's own org fence covers them.
"""
import re

from django.db.models import Count, Exists, OuterRef, Q

from .models import OrgRequestAnalysis, OrgRequestComment
from .org_requests import OPEN_FOR_SHAPING, TERMINAL_STATUSES

#: The four tabs, in display order. `all` is the server default, so a caller that names no group
#: (the old web, a test, a script) reads exactly the list the fence allows, as before.
GROUPS = ('action', 'progress', 'closed', 'all')
#: The EFFECTIVE kind — the triage ruling, falling back to what was filed (`_effective_kind`).
KINDS = ('bug', 'feature')

#: The row tags the list may carry. Names, never prose: the web maps each to an i18n key.
TAG_ANSWER_NEEDED = 'answer_needed'      # org_admin only
TAG_ANALYSIS_DRAFT = 'analysis_draft'    # super only
TAG_ANALYSED = 'analysed'                # super only

_ID_SEARCH = re.compile(r'#?(\d{1,9})')


def _awaiting_reply():
    """A comment on THIS request still waits for the requester (TD-201)."""
    # org-fence: correlated to the outer, already-fenced request by OuterRef('pk') — children only.
    return Exists(OrgRequestComment.objects.filter(org_request=OuterRef('pk'), awaiting_reply=True))


def _live_analyses():
    """Analyses on THIS request that nothing has superseded (drafts and approved alike)."""
    # org-fence: correlated to the outer, already-fenced request by OuterRef('pk') — children only.
    return OrgRequestAnalysis.objects.filter(org_request=OuterRef('pk'), superseded_at__isnull=True)


def needs_action_q(is_super):
    """The requests waiting on THIS reader — the badge's number and the first tab's rows.

    Super (TD-205): untriaged, OR a triaged FEATURE with no approved, live analysis — it cannot be
    quoted at all (`analysis_required`), so it is stuck by construction and nothing else says so.
    A triaged BUG is deliberately not counted: it is free and schedulable straight from triage.

    org_admin (TD-201): not terminal, AND a quote awaiting their decision OR a comment awaiting
    their reply. ⚠ This window (not terminal) is WIDER than the "Answer needed" tag's
    (`OPEN_FOR_SHAPING`) on purpose: an accepted request with a question still open IS waiting on
    the requester — a comment settles it — but it has no answer box, so it carries no tag.
    """
    if is_super:
        approved_live = Exists(_live_analyses().filter(approved_at__isnull=False))
        return (Q(status='submitted')
                | (Q(status='triaged', triaged_kind='feature') & ~Q(approved_live)))
    return (~Q(status__in=TERMINAL_STATUSES)
            & (Q(status='quoted') | Q(_awaiting_reply())))


def group_q(group, *, is_super):
    """One tab's rows. The three working tabs partition the list; `all` is everything."""
    terminal = Q(status__in=TERMINAL_STATUSES)
    if group == 'action':
        return needs_action_q(is_super)
    if group == 'progress':
        return ~terminal & ~needs_action_q(is_super)
    if group == 'closed':
        return terminal
    return Q()


def kind_q(kind):
    """The EFFECTIVE kind: `triaged_kind` when triage set one, else the kind that was filed.
    Untriaged is `''` on this column (blank, default ''); NULL is matched too, so a row written
    some other way cannot fall out of both kinds."""
    if not kind:
        return Q()
    untriaged = Q(triaged_kind='') | Q(triaged_kind__isnull=True)
    return Q(triaged_kind=kind) | (untriaged & Q(kind=kind))


def search_q(q):
    """Title contains `q`, OR the request's number is `q` (`12` or `#12`)."""
    q = (q or '').strip()
    if not q:
        return Q()
    found = Q(title__icontains=q)
    m = _ID_SEARCH.fullmatch(q)
    if m:
        found |= Q(pk=int(m.group(1)))
    return found


def parse_filters(params):
    """Read `?group=&kind=&q=` from a request's query params. Returns `(filters, ok)`.

    An unknown group or kind is REFUSED (the caller answers 400 `bad_filter`) rather than read as
    "all": a typo that silently showed everything is how the old `?status=` filter went unnoticed
    for months — the web sent it and the server never read it.
    """
    group = (params.get('group') or 'all').strip()
    kind = (params.get('kind') or '').strip()
    if group not in GROUPS or (kind and kind not in KINDS):
        return None, False
    return {'group': group, 'kind': kind, 'q': (params.get('q') or '').strip()}, True


def filters_q(filters, *, is_super):
    """The page's rows: one tab, narrowed by kind and search."""
    return (group_q(filters['group'], is_super=is_super)
            & kind_q(filters['kind']) & search_q(filters['q']))


def tab_counts(qs, *, is_super):
    """The four tab counts over `qs` — ONE query.

    ⚠ `qs` is the FENCED list (and the crumb's `?org=`), never the kind- or search-filtered one: a
    tab's count is of the WHOLE list (decisions.md, S7 2026-09-11). The filtered total is the
    paginator's own `count`, which the page prints as "Showing a–b of N".
    """
    terminal = Q(status__in=TERMINAL_STATUSES)
    action = needs_action_q(is_super)
    return qs.aggregate(
        action=Count('id', filter=action),
        progress=Count('id', filter=~terminal & ~action),
        closed=Count('id', filter=terminal),
        all=Count('id'),
    )


def annotate_tags(qs, *, is_super):
    """Add what `row_tags` reads, as `Exists` columns on the page query — a row costs nothing.

    Each role is given ONLY its own facts: the organisation's rows never carry an analysis column,
    so no serializer can render an owner-only tag for them, however it is written.
    """
    if is_super:
        live = _live_analyses()
        return qs.annotate(_tag_live_approved=Exists(live.filter(approved_at__isnull=False)),
                           _tag_live_any=Exists(live))
    return qs.annotate(_tag_awaiting=_awaiting_reply())


def row_tags(req, *, is_super):
    """The tags one row carries, for this role. Reads the `annotate_tags` columns.

    org_admin — `answer_needed`: a comment awaits their reply AND the request is still open for
      shaping, the SAME window as the answer box on the detail page (an accepted request with an
      open question is history to them, and badging the list for ever is noise).
    super — on a SUBMITTED request only: `analysed` when a live analysis is approved, else
      `analysis_draft` when a live one exists. Withdrawn drafts (superseded, never approved) do not
      count. Past submitted, the status itself says where the request is.
    """
    if is_super:
        if req.status != 'submitted':
            return []
        if getattr(req, '_tag_live_approved', False):
            return [TAG_ANALYSED]
        return [TAG_ANALYSIS_DRAFT] if getattr(req, '_tag_live_any', False) else []
    if getattr(req, '_tag_awaiting', False) and req.status in OPEN_FOR_SHAPING:
        return [TAG_ANSWER_NEEDED]
    return []
