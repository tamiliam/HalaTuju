"""Programme Overview — "how is this gift doing?", answered once and shaped by role.

The page a person lands on after clicking a gift card: the funnel, the money, what needs
attention, and the charts over time. Every figure is READ from data the
system already records — each status stamps a date, every spend row has a date, an amount and a
category — so this module computes nothing new and stores nothing at all. There is no migration
behind it and no new field collected.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **THE FENCE IS `application_scope`, AND THERE IS EXACTLY ONE OF IT.** Every figure below is
derived from that one queryset — disbursements and spend rows are reached only through
`application_id__in=scope`, never from their own managers with their own filters. The same
reasoning `spend_report` states: an allowlist serializer protects a COLUMN and does nothing about
a ROW, so the fence has to be on the query, once.

⚠⚠ **ROLE SHAPING IS A SECOND GATE, NOT A COSMETIC ONE.** `SECTIONS_BY_ROLE` decides which keys
are BUILT, server-side, before anything is serialised. A reviewer's payload has no `money` key to
hide; a finance admin's has no `funnel`. A page that fetched everything and rendered a subset
would be a side door into Applications/Payments/Spending for roles the menu already withholds
those pages from.

⚠ **FINANCE SEES AGGREGATE MONEY HERE THOUGH NOT ON THE SPENDING PAGE** (`_SPENDING_ROLES`
excludes it). That is a deliberate widening, recorded in `docs/decisions.md` and the role matrix:
what finance gains is TOTALS — committed, paid, remaining, spent, per category, per month. It
never gains a name, a file or a verdict, because none of those is in a section it is given.

⚠ **MONEY IS `Decimal` HERE AND A STRING ON THE WIRE.** `build` stringifies at the edge, the way
`_spending_gaps` does, because a bare `Decimal` in a plain dict is rendered by DRF as a FLOAT —
that is how `30.00` reached a sponsor's screen as `30.0` in S5. Nothing in this module returns a
float, and no display value is ever fed back into arithmetic.

⚠ **TD-209 — EVERY `DateTime` GROUPING GOES THROUGH `timezone.localtime()`.** `submitted_at`,
`awarded_at` and `released_at` are aware UTC instants: `.date()` on one of them gives the UTC
date, so everything between Malaysian midnight and 08:00 lands in yesterday's bucket — and a test
that reads the same clock as the code cannot see it. `txn_date` is a `DateField` (the hour was
discarded at import, deliberately and for ever) and is therefore NEVER converted; converting a
date would be its own bug.

⚠ **GROUPING HAPPENS IN PYTHON, OVER `values_list` ROWS.** Not `annotate()` — two counts over two
multi-valued relations multiply each other, and `Sum(distinct=True)`, the reflex cure, is wrong
for a sum. `_reviewer_workloads` states this at length; a few hundred rows grouped in a dict
cannot fan out at all, so the class of bug is absent rather than guarded against.

⚠ **SPEND WEEKS STOP AT `data_to`; APPLICATION WEEKS RUN TO TODAY.** The spend series ends at the
newest `txn_date` we hold, because extending it to today draws zeros for weeks whose file simply
has not been imported yet — a chart that reports "they stopped spending" when it means "we
stopped importing". Applications have no import window, so theirs runs to this week.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils import timezone

from . import payments, spend_report
from .spending_import import TX_SPEND

_ZERO = Decimal('0.00')
_CENTS = Decimal('0.01')

#: Everything a full-scope console role sees. Kept as one tuple so the three roles that get it
#: cannot drift apart by a copy-paste.
FULL = ('funnel', 'money', 'attention', 'applications_series', 'money_series')

#: ⚠⚠ **THE SERVER DECIDES WHAT A ROLE RECEIVES.** A key absent here is a key never built, so it
#: is not in the payload at all — absent, never zeroed. Zeroing would be its own leak: "your
#: organisation has committed RM0" is still an answer about money to somebody who may not ask.
#:
#: ⚠ `reviewer` and `qc` get NO money and NO programme-wide funnel, by decision: the menu already
#: withholds Payments and Spending from them, and an Overview that handed over the same figures
#: through a different route would make that withholding decorative.
#:
#: (The `intake` block that was on every row until 2026-09-18 is gone — owner: "doesn't add much
#: value". A round's state lives on Configuration; this page is the work and the money.)
SECTIONS_BY_ROLE = {
    'super': FULL,
    'org_admin': FULL,
    'admin': FULL,
    # See the module docstring: aggregate money, never a person.
    'finance': ('money', 'money_series'),
    'qc': ('qc',),
    'reviewer': ('mine',),
}


def may_customise(admin):
    """Who edits the organisation's layout: `org_admin`, and super (who passes every role
    check — `PartnerAdminMixin.has_role`'s rule, spelled out here so this module stays free of
    the view layer). The same answer `AdminOverviewLayoutView.ROLES` gives to a PUT."""
    return bool(admin) and (admin.is_super or admin.role == 'org_admin')


def sections_for(admin):
    """Which sections this admin's role may receive. `()` for anyone unlisted.

    ⚠ The EFFECTIVE role, not `admin.role` — a legacy super carries `is_super_admin` with some
    other role string in the column, and `has_role` would answer True to every check. An unknown
    or unlisted role gets nothing rather than a default, which is the safe direction: a new role
    added to `ROLE_CHOICES` without a decision here is REFUSED by the view (which turns an empty
    tuple into a 403), never handed somebody else's sections.
    """
    if admin is None:
        return ()
    role = 'super' if getattr(admin, 'is_super', False) else getattr(admin, 'role', '')
    return SECTIONS_BY_ROLE.get(role, ())


# ── the fence ─────────────────────────────────────────────────────────────────────────────────

def application_scope(org, programme=None, cohort=None):
    """The applications this request may see. **THE fence — nothing here reaches around it.**

    ⚠⚠ **`programme` AND `cohort` NARROW ALONGSIDE THE ORGANISATION FILTER, NEVER INSTEAD OF
    IT.** The same wording `payments.eligible_rows` and `spend_report._txns` carry, and it is
    load-bearing: the organisation is the SECURITY fence and the gift (and, since 2026-09-18, the
    intake round inside it) is a restriction inside it. If a future edit ever makes these an
    either/or, a caller naming a gift or a round escapes the tenant wall. The view has already
    refused a cohort from another tenant or another gift with a 404 (`_intake_narrowing`), so
    `cohort` here is one the caller may see; the filter still sits INSIDE the fence.

    ⚠ **THE GIFT FILTER IS THE APPLICATIONS LIST'S OWN PAIR** (`views_admin.py:380`).
    `ScholarshipApplication.programme` is a denormalised copy set once at first save, so a cohort
    later moved between gifts leaves its old applications pointing at the OLD gift; filtering on
    the column alone would show a gift's own round as empty. Both sides are single-valued FK
    chains, so this cannot multiply rows. It matters here specifically because the funnel on this
    page and the list one click away must count the same cases.
    """
    from .models import ScholarshipApplication

    if org is spend_report.ALL_ORGS:
        # ⚠ THE PRAGMA SITS DIRECTLY ABOVE THE QUERY BECAUSE THE GUARD LOOKS 200 CHARACTERS.
        # org-fence: DELIBERATELY UNFENCED — the platform scope, reachable only through the view's
        # super branch, which hands out `spend_report.ALL_ORGS` (a sentinel object, never `None`).
        qs = ScholarshipApplication.objects.all()
    else:
        # org-fence: owning_organisation — the same fence `_org_scoped` and `spend_report` use.
        # A caller with no organisation is refused `no_org` by the view before reaching here.
        qs = ScholarshipApplication.objects.filter(owning_organisation=org)
    if programme is not None:
        qs = qs.filter(Q(programme=programme) | Q(cohort__programme=programme))
    if cohort is not None:
        qs = qs.filter(cohort=cohort)
    return qs


def intakes_for(org, programme):
    """The rounds the intake picker offers: the chosen gift's, newest year first.

    ⚠ ON EVERY ROLE'S PAYLOAD. A round's code, name, year and state is the same class of fact the
    old `intake` block put on every row (2026-09-15) — a date, not a person and not a sum — so a
    reviewer populating a picker from it discloses nothing. This is what makes the org_admin-only
    intake-years endpoint irrelevant here.

    With no gift chosen: a tenant sees every round inside its fence; the platform scope sees `[]`
    (there is no organisation to fence on, and the picker hides itself).
    """
    from .models import ScholarshipCohort
    from .views_admin import round_state

    if programme is not None:
        # org-fence: the gift was resolved inside the caller's organisation by `_gift_narrowing`.
        qs = ScholarshipCohort.objects.filter(programme=programme)
    elif org is spend_report.ALL_ORGS:
        return []
    else:
        # org-fence: owning_organisation — the cohort's own tenancy column.
        qs = ScholarshipCohort.objects.filter(owning_organisation=org)
    return [_intake_row(c, round_state(c)) for c in qs.order_by('-year', 'code')]


def _intake_row(cohort, state):
    return {'id': cohort.id, 'code': cohort.code, 'name': cohort.name,
            'year': cohort.year, 'state': state}


def _txns(scope, *, spend_only=True):
    """The scope's Vircle rows. Reached ONLY through `scope`, so the fence above covers them."""
    from .models import BursarySpendTxn

    # There is no organisation filter of its own here on purpose — a second, independent fence
    # is a second place to get it wrong (TD-201). The explanation goes ABOVE the pragma, never
    # between it and the query: the guard looks 200 characters, so a pragma pushed further than
    # that away fails, correctly.
    # org-fence: application_id restricted to `scope`, which the caller already fenced.
    qs = BursarySpendTxn.objects.filter(application_id__in=scope.values_list('id', flat=True))
    return qs.filter(tx_type=TX_SPEND) if spend_only else qs


def data_to(scope):
    """The newest day any spending data covers, or `None`. Shown at the top of the page.

    ⚠ It counts EVERY transaction type, not just spends — the question is "how far does the file
    reach", and a wallet top-up is as much evidence of that as a purchase.
    """
    from django.db.models import Max
    return _txns(scope, spend_only=False).aggregate(d=Max('txn_date'))['d']


# ── dates ─────────────────────────────────────────────────────────────────────────────────────

def _week(d: date) -> date:
    """The ISO-week MONDAY of `d`. One spelling, so every series bins identically."""
    return d - timedelta(days=d.weekday())


def _local_date(dt):
    """The Malaysian date of an aware instant. **TD-209 lives here.**

    ⚠ NEVER call `.date()` on one of these instants directly. `timezone.now()` is UTC, and a case
    submitted at 23:30 UTC on a Sunday is a MONDAY case in Kuala Lumpur — the next week's bucket.
    """
    return timezone.localtime(dt).date() if dt is not None else None


def _week_span(first: date, last: date):
    """Every ISO-week Monday from `first`'s week to `last`'s week, contiguous."""
    cur, end, out = _week(first), _week(last), []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=7)
    return out


def _month_key(d: date) -> str:
    return f'{d.year:04d}-{d.month:02d}'


#: ⚠⚠ **A RELEASE ON OR AFTER THE 27th IS NEXT MONTH'S PAYMENT.** Owner ruling, 2026-09-15:
#: the monthly payment is released a few days BEFORE the month it pays for (July's money goes out
#: on 30 June), so comparing it with June's spending charges June with money June never had. The
#: rule is on the DAY, not on intent: released on the 27th or later → the following month; any
#: earlier day → that month. A late payment (July's, released in September) therefore lands in
#: September, which is where the wallet actually got it — the owner's own example.
#:
#: ⚠ ONLY `money_per_month` uses this. The money strip, the Payments footer and the Spending page
#: all read the release date as-is; this rule exists so that one chart compares like with like.
PAYMENT_MONTH_CUTOFF_DAY = 27


def _payment_month(d: date) -> date:
    """The FIRST DAY of the month a release counts towards — see `PAYMENT_MONTH_CUTOFF_DAY`."""
    if d.day >= PAYMENT_MONTH_CUTOFF_DAY:
        return date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
    return date(d.year, d.month, 1)


def _month_span(first: date, last: date):
    """Every `YYYY-MM` from `first`'s month to `last`'s month, contiguous."""
    y, m = first.year, first.month
    out = []
    while (y, m) <= (last.year, last.month):
        out.append(f'{y:04d}-{m:02d}')
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


# ── the sections ──────────────────────────────────────────────────────────────────────────────

def funnel(scope):
    """`total` plus one count per status — **all thirteen, zero-filled.**

    ⚠ ZERO-FILLED RATHER THAN OMITTED. A funnel that only lists the statuses somebody happens to
    be in reads as though the missing stages do not exist; a stage at zero is information.
    """
    from .models import ScholarshipApplication

    by_status = {code: 0 for code, _ in ScholarshipApplication.STATUS_CHOICES}
    total = 0
    for status in scope.values_list('status', flat=True):
        total += 1
        if status in by_status:
            by_status[status] += 1
    return {'total': total, 'by_status': by_status}


def money(scope):
    """The headline money strip — **byte-equal to the Payments funding-summary footer.**

    ⚠ The population is `payments.PAYABLE_STATUSES`, the same three states the funding summary
    lists, and `remaining` is floored per ROW (`max(award − paid, 0)`) before summing, exactly as
    that serializer does. Flooring the total instead would let one over-paid student silently
    cancel out another's outstanding balance. `test_the_money_headline_equals_the_payments_footer`
    calls both endpoints on one fixture.

    ⚠ "Paid" is SUM(released disbursements) and nothing else — `payments.py` calls that the one
    truth for history, and `spend_report._released_by_application` is the aggregated read of it.

    ⚠⚠ **THE ACCUMULATOR SEEDS ARE LOAD-BEARING AND THERE IS NO `quantize` HERE.** Byte equality
    means the STRING, and a `Decimal`'s scale survives arithmetic: `Decimal('0.00') + x` forces
    two places, `Decimal('0') + x` keeps whatever `x` had. SQLite's `Sum` over a `numeric(10,2)`
    hands back `Decimal('1500')` where Postgres hands back `Decimal('1500.00')`, so a quantize
    here would make this agree with the Payments footer on production and disagree on the test
    database — the worst of both. The three award-side figures therefore mirror that footer's own
    bare `sum()` exactly, and `spent` mirrors `spend_report.totals`, which seeds at `0.00`.
    """
    payable = scope.filter(status__in=payments.PAYABLE_STATUSES)
    awards = dict(payable.values_list('id', 'award_amount'))
    released = spend_report._released_by_application(payable)
    bare = Decimal('0')
    committed = paid = remaining = bare
    for app_id, award in awards.items():
        award = award or bare
        got = released.get(app_id, (bare, None))[0] or bare
        committed += award
        paid += got
        rem = award - got
        remaining += rem if rem > bare else bare
    spent = _ZERO
    for amount in _txns(scope).values_list('amount', flat=True):
        spent += amount or _ZERO
    return {
        'students': len(awards),
        'committed': committed,
        'paid': paid,
        'remaining': remaining,
        # Equal to the Spending page's `totals.spent` on the same scope — pinned by
        # `test_the_spent_figure_equals_the_spending_total`.
        'spent': spent,
    }


def attention(scope, *, now, clocks):
    """What needs a human: the nudge population, banded by the SWEEP'S OWN boundaries.

    ⚠ `due_soon` and `overdue` are SUBSETS of `with_reviewer`, not a partition of it. The strip
    reads "2 with a reviewer, 1 due soon, 0 overdue"; making them exclusive would mean a case
    stopped being with its reviewer the moment it got late.

    ⚠ `unassigned` is the one band OUTSIDE the nudge population, because by definition nobody has
    been nudged: no reviewer, no verdict, not terminal. It is the work that has not started.

    ⚠ `awaiting_qc` is `status == 'interviewed'` — the reviewer has submitted, so its verdict
    clock has stopped and it is NOT double-counted in `with_reviewer`.
    """
    from .review_sla import AWAITING_VERDICT, TERMINAL, review_band

    unassigned = scope.filter(
        assigned_to__isnull=True, verdict_decided_at__isnull=True
    ).exclude(status__in=TERMINAL).count()
    with_reviewer = due_soon = overdue = 0
    for assigned_at in scope.filter(AWAITING_VERDICT).values_list('assigned_at', flat=True):
        with_reviewer += 1
        band = review_band(assigned_at, now=now, clocks=clocks)
        if band == 'overdue':
            overdue += 1
        elif band == 'due_soon':
            due_soon += 1
    return {
        'unassigned': unassigned,
        'with_reviewer': with_reviewer,
        'due_soon': due_soon,
        'overdue': overdue,
        'awaiting_qc': scope.filter(status='interviewed').count(),
    }


def applications_per_week(scope, *, today):
    """Applications submitted, by ISO week — contiguous to THIS week, zero-filled.

    ⚠ Runs to today's week, unlike the spend series: an application needs no import, so a quiet
    week genuinely was quiet.
    """
    dates = [_local_date(dt) for dt in scope.values_list('submitted_at', flat=True)
             if dt is not None]
    if not dates:
        return []
    counts = {}
    for d in dates:
        counts[_week(d)] = counts.get(_week(d), 0) + 1
    return [{'week': w.isoformat(), 'count': counts.get(w, 0)}
            for w in _week_span(min(dates), today)]


def awards_per_month(scope, *, today):
    """Awards made, by month — contiguous to the current month, zero-filled."""
    dates = [_local_date(dt) for dt in scope.values_list('awarded_at', flat=True)
             if dt is not None]
    if not dates:
        return []
    counts = {}
    for d in dates:
        counts[_month_key(d)] = counts.get(_month_key(d), 0) + 1
    return [{'month': m, 'count': counts.get(m, 0)} for m in _month_span(min(dates), today)]


def money_per_month(scope, *, today):
    """Released vs spent by month, with the running gap between them.

    ⚠ `gap` MAY GO NEGATIVE and must not be floored. It is `released_cum − spent_cum`, and a
    negative reads "they have spent more than we released" — which is real: the wallet is the
    student's own and a parent may top it up. The officer is exactly the person who should notice
    that and ask, the same reasoning that leaves `spend_report.student_rows.balance` unfloored.

    ⚠ Two different date kinds meet here and are handled differently ON PURPOSE: `released_at` is
    an aware instant and is converted; `txn_date` is a `DateField` and is not.

    ⚠ A RELEASE IS FILED UNDER THE MONTH IT PAYS FOR (`_payment_month`), not the month of its
    date — so a release dated 30 June sits beside July's spending. The series therefore runs to
    the LATER of today's month and the last payment month: a release on the 28th of this month
    is next month's bar, and cutting the span at today would drop it.
    """
    from .models import Disbursement

    released_by_month, spent_by_month = {}, {}
    seen = []
    rows = (Disbursement.objects
            .filter(status='released',
                    application_id__in=scope.values_list('id', flat=True))
            .values_list('released_at', 'amount'))
    for released_at, amount in rows:
        d = _local_date(released_at)
        if d is None:
            continue
        month_first = _payment_month(d)
        seen.append(month_first)
        key = _month_key(month_first)
        released_by_month[key] = released_by_month.get(key, _ZERO) + (amount or _ZERO)
    for txn_date, amount in _txns(scope).values_list('txn_date', 'amount'):
        if txn_date is None:
            continue
        seen.append(txn_date)
        key = _month_key(txn_date)
        spent_by_month[key] = spent_by_month.get(key, _ZERO) + (amount or _ZERO)
    if not seen:
        return []
    out, released_cum, spent_cum = [], _ZERO, _ZERO
    for key in _month_span(min(seen), max(seen + [today])):
        rel = released_by_month.get(key, _ZERO)
        spent = spent_by_month.get(key, _ZERO)
        released_cum += rel
        spent_cum += spent
        out.append({
            'month': key,
            'released': rel.quantize(_CENTS),
            'spent': spent.quantize(_CENTS),
            'released_cum': released_cum.quantize(_CENTS),
            'spent_cum': spent_cum.quantize(_CENTS),
            'gap': (released_cum - spent_cum).quantize(_CENTS),
        })
    return out


def _per(numerator, denominator, places):
    """`numerator / denominator` to `places`, HALF-UP, and zero when there is no denominator —
    a week before anybody had a wallet (or a transaction) is '0.00', not a crash."""
    if not denominator:
        return Decimal('0').quantize(places)
    return (Decimal(numerator) / Decimal(denominator)).quantize(places, rounding=ROUND_HALF_UP)


def per_student_overall(scope):
    """The whole period in two figures: what a transaction cost on average, and how many
    transactions a student made in an average week.

    ⚠ THIS IS WHAT THE PAGE PRINTS BENEATH THE WEEKLY LINES, instead of every week's value. Owner,
    2026-09-15: the weekly list was clutter at eleven weeks and would be unreadable at fifty. The
    lines still show the movement; the figure a person quotes is the whole-period one.

    ⚠⚠ ONLY STUDENTS WHO HAVE SPENT ARE COUNTED, ANYWHERE ON THIS PAGE (owner, 2026-09-18).
    `students` (n) is the number of distinct students with a SPEND row — 47 on the live gift, not
    the 58 with a wallet: *"students who technically are not in the report, as they haven't yet
    spent and made their presence felt, shouldn't be counted."* Eleven wallets have no Vircle
    row at all, and TD-245 says we cannot tell "spent nothing" from "absent from the export".

    ⚠ TWO DIFFERENT DENOMINATORS, BOTH NAMED. `spent_per_transaction` is ringgit over ROWS —
    what a card payment tends to be. `weekly_transactions_per_student` is the MEAN OF THE
    WEEKLY AVERAGES — each week's rows over the students who spent THAT week (see
    `per_student_per_week`), averaged over the weeks that had one. `weeks` is the length of
    the weekly series. `None` when there is no spending at all, so the page says nothing rather
    than "RM0.00".

    ⚠⚠ WHY THE MEAN OF WEEKLY AVERAGES AND NOT total ÷ students ÷ weeks (owner, 2026-09-18, who
    caught it reading low): a single headcount charges every week with people who were not
    active in it, and the figure sinks as the programme grows. Each weekly average already uses
    the right denominator for its week, so their mean is the honest "how often does an active
    student pay in a week".
    """
    rows = [(app, d, a) for app, d, a in
            _txns(scope).values_list('application_id', 'txn_date', 'amount') if d is not None]
    if not rows:
        return None
    students = len({app for app, _, _ in rows})
    weekly = per_student_per_week(scope)
    ratios = [Decimal(w['transactions']) / w['students'] for w in weekly if w['students']]
    spent = sum(((a or _ZERO) for _, _, a in rows), _ZERO)
    transactions = len(rows)
    return {
        'students': students,
        'weeks': len(weekly),
        'spent': spent.quantize(_CENTS),
        'transactions': transactions,
        'spent_per_transaction': _per(spent, transactions, _CENTS),
        'weekly_transactions_per_student': _per(
            sum(ratios, Decimal('0')), len(ratios), Decimal('0.1')),
    }


def per_student_per_week(scope):
    """Spending per week with an HONEST denominator, and transactions counted as ROWS.

    ⚠⚠ **`transactions` IS A ROW COUNT, NOT A SUM.** A Vircle row is one card transaction and
    carries no item count, so "items purchased" is not a question this data can answer. Summing
    anything here would be inventing a quantity; the chart is named for what it actually counts.
    (It was called `purchases` until 2026-09-15; the owner asked for the honest word.)

    ⚠⚠ **THE DENOMINATOR IS STUDENTS WHO SPENT THAT WEEK** — distinct applications with at
    least one SPEND row dated inside the week (owner, 2026-09-18: *"if a student had 0
    transactions in that week, that student shouldn't be counted"*). The chart is therefore
    "transactions per ACTIVE student per week", and is named so. It replaced "students with a
    live wallet that week" (15–18 September), which charged every week with wallets that had
    never been used — eleven of the fifty-eight on the live gift have no Vircle row at all.

    ⚠ WEEKS STOP AT `data_to` (the newest `txn_date` we hold, of ANY transaction type), never
    today — see the module docstring. A zero week INSIDE the window is a real zero and stays; the
    weeks after it are the ones that would be fiction.
    """
    rows = list(_txns(scope).values_list('application_id', 'txn_date', 'amount'))
    rows = [(app, d, a) for app, d, a in rows if d is not None]
    if not rows:
        return []
    spent_by_week, transactions_by_week, spenders_by_week = {}, {}, {}
    for app_id, txn_date, amount in rows:
        w = _week(txn_date)
        spent_by_week[w] = spent_by_week.get(w, _ZERO) + (amount or _ZERO)
        transactions_by_week[w] = transactions_by_week.get(w, 0) + 1
        spenders_by_week.setdefault(w, set()).add(app_id)
    out = []
    last = data_to(scope) or max(d for _, d, _ in rows)
    for w in _week_span(min(d for _, d, _ in rows), last):
        students = len(spenders_by_week.get(w, ()))
        spent = spent_by_week.get(w, _ZERO)
        transactions = transactions_by_week.get(w, 0)
        out.append({
            'week': w.isoformat(),
            'students': students,
            'spent': spent.quantize(_CENTS),
            'transactions': transactions,
            # ⚠ What a card payment cost that week, on average — ringgit over ROWS (owner,
            # 2026-09-18: "what we are calculating is average spending per transaction").
            'spent_per_transaction': _per(spent, transactions, _CENTS),
            # ⚠ Guarded: a week nobody spent in is '0.0', not a crash.
            'transactions_per_student': _per(transactions, students, Decimal('0.1')),
        })
    return out


def by_category(scope):
    """Eleven slices, always all eleven, never merged.

    ⚠⚠ **`unsorted` AND `none` ARE DIFFERENT STATES AND BOTH STAY VISIBLE.** `unsorted` means the
    sorter looked and could not place the row; `''` (emitted as `none`) means nothing has looked
    at it yet. Folding either into "other" — or hiding them at zero — is what would let the other
    nine read as complete when they are not (`models.SPEND_CATEGORY_CHOICES` says so, and
    `spend_report.UNPLACED` is the pair).

    ⚠ Every slice is present AT ZERO. An absent slice cannot be told from a slice nobody drew.
    """
    from .models import SPEND_CATEGORY_CHOICES

    totals = {code: _ZERO for code, _ in SPEND_CATEGORY_CHOICES}
    counts = {code: 0 for code, _ in SPEND_CATEGORY_CHOICES}
    totals[''] = _ZERO
    counts[''] = 0
    for category, amount in _txns(scope).values_list('category', 'amount'):
        key = category if category in totals else ''
        totals[key] += amount or _ZERO
        counts[key] += 1
    out = [{'code': code, 'total': totals[code].quantize(_CENTS), 'transactions': counts[code]}
           for code, _ in SPEND_CATEGORY_CHOICES]
    # `''` is not a code anybody can read, so it travels as `none` — a NAME for "not yet sorted
    # by anyone", distinct from the sorter's own `unsorted` verdict above it.
    out.append({'code': 'none', 'total': totals[''].quantize(_CENTS), 'transactions': counts['']})
    return out


def mine(scope, admin, *, now, clocks, organisation_id=None, programme=None, cohort=None):
    """A reviewer's OWN cases, and nothing else.

    ⚠ `due_soon` and `overdue` are SUBSETS of `open`, matching `attention` — see its note.

    ⚠ **NO SCORE, NO PERCENTILE, NO BAND ON THE PERSON** (the `reviewerDetail.ts` ruling). These
    are volunteers. Only the CASE'S clock is banded, and `turnaround_days` is phrased on the page
    as how long a student waited, not as how fast this reviewer is.
    """
    from .pool import pool_ref
    from .review_sla import AWAITING_VERDICT, review_band, review_due
    from .views_admin import _reviewer_workloads

    cases = []
    counts = {'open': 0, 'due_soon': 0, 'overdue': 0}
    rows = (scope.filter(AWAITING_VERDICT, assigned_to=admin)
            .values_list('id', 'profile__name', 'status', 'assigned_at'))
    for app_id, name, status, assigned_at in rows:
        band = review_band(assigned_at, now=now, clocks=clocks)
        # ⚠ `open` IS THE WHOLE POPULATION, and the band names are NOT keys to index by — the
        # band `'open'` shares its name with the total, so `counts[band] += 1` would count an
        # untroubled case twice. Spelled out rather than clever.
        counts['open'] += 1
        if band == 'overdue':
            counts['overdue'] += 1
        elif band == 'due_soon':
            counts['due_soon'] += 1
        # ⚠ THROUGH `review_due`, NOT `assigned_at + clocks[0]`. Writing the arithmetic out here
        # would be exactly the fourth copy `review_sla` was created to prevent — and the one the
        # reviewer actually READS, so it is the worst place of all to let it drift.
        due_at = review_due(assigned_at, clocks=clocks)
        cases.append({
            'id': app_id,
            'ref': pool_ref(app_id) or '',
            'applicant_name': name or '',
            'status': status,
            'assigned_at': assigned_at.isoformat(),
            'due_at': due_at.isoformat(),
            'band': band,
        })
    cases.sort(key=lambda c: (c['due_at'], c['id']))
    work = _reviewer_workloads(
        [admin], organisation_id=organisation_id, programme=programme,
        cohort=cohort).get(admin.id, {})
    return {
        **counts,
        'cases': cases,
        'pace': {'completed': work.get('completed', 0),
                 'turnaround_days': work.get('turnaround_days')},
    }


def qc_queue(scope, admin, *, now):
    """The QC queue and this checker's own pace.

    ⚠⚠ **PACE IS KEYED ON EMAIL BECAUSE THERE IS NO QC STAMP COLUMN.** Nothing records "who QC'd
    this"; what the data holds is `recommended_by` (written when a QC ACCEPTS, moving the case to
    `recommended`) and `rejected_by` (written when a QC accepts a decline). Matching on the
    admin's email is the convention `_reviewer_workloads` already uses for `rejected_by`, and it
    is stated here rather than hidden because it is an approximation: a checker who changed email
    address loses their history, and a case decided by somebody sharing the address would be
    attributed wrongly. Adding a real stamp is a migration, which this page deliberately does not
    have.

    ⚠ `awaiting` is `status == 'interviewed'` ONLY — the single stage that means "a reviewer has
    submitted and nobody has checked it". Widening it to "anything undecided" would put cases in
    front of a checker that are not theirs to act on.
    """
    from .pool import pool_ref
    from .views_admin import _median_days

    email = (getattr(admin, 'email', '') or '').strip().lower()
    cases, oldest = [], None
    for app_id, name, since in scope.filter(status='interviewed').values_list(
            'id', 'profile__name', 'verdict_decided_at'):
        waiting = (now - since).days if since is not None else None
        if waiting is not None and (oldest is None or waiting > oldest):
            oldest = waiting
        cases.append({
            'id': app_id,
            'ref': pool_ref(app_id) or '',
            'applicant_name': name or '',
            'status': 'interviewed',
            'since': since.isoformat() if since is not None else None,
            'waiting_days': waiting,
        })
    cases.sort(key=lambda c: (-(c['waiting_days'] or 0), c['id']))

    completed, days = 0, []
    decided = scope.values_list(
        'status', 'recommended_by', 'recommended_at',
        'rejected_by', 'rejected_at', 'verdict_decided_at')
    for status, rec_by, rec_at, rej_by, rej_at, decided_at in decided:
        stamp = None
        if (rec_by or '').strip().lower() == email and email:
            stamp = rec_at
        elif status == 'rejected' and (rej_by or '').strip().lower() == email and email:
            stamp = rej_at
        else:
            continue
        completed += 1
        if stamp is not None and decided_at is not None:
            days.append((stamp - decided_at).total_seconds() / 86400.0)
    return {
        'awaiting': len(cases),
        'oldest_waiting_days': oldest,
        'cases': cases,
        'pace': {'completed': completed, 'turnaround_days': _median_days(days)},
    }


# ── assembly ──────────────────────────────────────────────────────────────────────────────────

def _money_str(value):
    """`Decimal` → string, at the edge and nowhere else. See the module docstring."""
    return str(value)


def _overall_payload(overall):
    """`per_student_overall` for the wire — `None` stays `None` (no spending: nothing to say)."""
    if overall is None:
        return None
    return {
        'students': overall['students'],
        'weeks': overall['weeks'],
        'spent': _money_str(overall['spent']),
        'transactions': overall['transactions'],
        'spent_per_transaction': _money_str(overall['spent_per_transaction']),
        'weekly_transactions_per_student': _money_str(overall['weekly_transactions_per_student']),
    }


def build(admin, org, programme, *, cohort=None, now=None):
    """The whole payload, shaped by role, narrowed and ordered by the organisation's layout,
    with every money value a STRING.

    ⚠ The sections are chosen FIRST and each is built only if chosen, so a role never pays for a
    query it may not read the answer to — and, more importantly, a bug in the serialisation below
    can never surface a section `sections_for` withheld.

    ⚠⚠ THE ORGANISATION'S LAYOUT NARROWS AND ORDERS; IT NEVER WIDENS (`overview_layout.apply`).
    `sections` is emitted in the layout's order and the page renders in that order. `mine` and
    `qc` are pages, not widgets, and pass through untouched. A layout that hides everything a
    role may see yields `sections: []` with a 200 — the view's 403 is about entitlement, which is
    a different question. The layout's organisation is the SLA organisation: the tenant, or the
    named gift's owner under the platform scope; with neither there is no layout to apply.

    ⚠ `layout` (keys and flags, never data) is on the payload for org_admin and super ONLY — it
    is what Customise mode edits, and the page shows the Customise button by its PRESENCE, never
    by a client-side role check.
    """
    from .review_sla import clocks as review_clocks
    from .views_admin import round_state
    from . import overview_layout

    now = now or timezone.now()
    today = timezone.localtime(now).date()
    scope = application_scope(org, programme, cohort)
    role_sections = sections_for(admin)

    # ⚠ THE SLA CLOCKS ARE PER-ORGANISATION, AND THE PLATFORM SCOPE HAS NO ORGANISATION. Under
    # `ALL_ORGS` we take the gift's owner when a gift was named, and the platform default
    # otherwise — the honest answer for a view spanning tenants whose SLAs may differ. Resolved
    # ONCE and passed down, so a page of 200 cases reads `org_config` once, not 200 times.
    sla_org = None if org is spend_report.ALL_ORGS else org
    if sla_org is None and programme is not None:
        sla_org = programme.organisation
    clocks = review_clocks(sla_org)

    layout = overview_layout.for_org(sla_org) if sla_org is not None else None
    sections = (overview_layout.apply(layout, role_sections)
                if layout is not None else list(role_sections))

    newest = data_to(scope)
    # These keys are on EVERY payload whatever the role. `data_to` is here rather than inside
    # `money_series` because it is the "as at" stamp for the whole page — and it is a DATE, not
    # money, so it discloses nothing a reviewer may not read. Likewise `intake`/`intakes`: a
    # round's name and year, see `intakes_for`.
    payload = {
        'programme': ({'code': programme.code, 'name': programme.name_en}
                      if programme is not None else None),
        # Malaysian local time with its offset, so the page never has to guess which clock the
        # stamp was taken on.
        'generated_at': timezone.localtime(now).isoformat(),
        'data_to': newest.isoformat() if newest else None,
        'sections': list(sections),
        'intake': _intake_row(cohort, round_state(cohort)) if cohort is not None else None,
        'intakes': intakes_for(org, programme),
    }
    if layout is not None and may_customise(admin):
        payload['layout'] = layout

    if 'funnel' in sections:
        payload['funnel'] = funnel(scope)
    if 'money' in sections:
        m = money(scope)
        payload['money'] = {
            'students': m['students'],
            'committed': _money_str(m['committed']),
            'paid': _money_str(m['paid']),
            'remaining': _money_str(m['remaining']),
            'spent': _money_str(m['spent']),
        }
    if 'attention' in sections:
        payload['attention'] = attention(scope, now=now, clocks=clocks)
    if 'applications_series' in sections:
        payload['applications_series'] = {
            'applications_per_week': applications_per_week(scope, today=today),
            'awards_per_month': awards_per_month(scope, today=today),
        }
    if 'money_series' in sections:
        payload['money_series'] = {
            'money_per_month': [
                {'month': r['month'],
                 'released': _money_str(r['released']), 'spent': _money_str(r['spent']),
                 'released_cum': _money_str(r['released_cum']),
                 'spent_cum': _money_str(r['spent_cum']),
                 'gap': _money_str(r['gap'])}
                for r in money_per_month(scope, today=today)],
            'per_student_per_week': [
                {'week': r['week'], 'students': r['students'],
                 'spent': _money_str(r['spent']), 'transactions': r['transactions'],
                 'spent_per_transaction': _money_str(r['spent_per_transaction']),
                 'transactions_per_student': _money_str(r['transactions_per_student'])}
                for r in per_student_per_week(scope)],
            'per_student_overall': _overall_payload(per_student_overall(scope)),
            'by_category': [
                {'code': r['code'], 'total': _money_str(r['total']),
                 'transactions': r['transactions']}
                for r in by_category(scope)],
        }
    if 'mine' in sections:
        payload['mine'] = mine(
            scope, admin, now=now, clocks=clocks,
            organisation_id=(None if org is spend_report.ALL_ORGS
                             else getattr(org, 'id', None)),
            programme=programme, cohort=cohort)
    if 'qc' in sections:
        payload['qc'] = qc_queue(scope, admin, now=now)
    return payload
