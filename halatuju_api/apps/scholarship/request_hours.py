"""How recorded build hours relate to the REQUESTS they came from.

Moves only, split out of `platform_cost.py` on 2026-10-29 because that file reached 760 lines
against a 701-line allowance, and the 600-line standard asks for a split rather than for prose to
be trimmed until the number passes (`docs/lessons.md`, TD-413).

⚠ **A LEAF, deliberately.** Nothing here reads a rate, a margin or a cost; everything here answers
"which request is this row, and is it billable?". `platform_cost` imports it and re-exports every
name, so `platform_cost.billable_kind` and the rest keep working for every existing caller.

The one decision that lives here and matters: `billable_kind` is what decides whether work is
charged, because a bug is free. Only the owner's triage may move money.
"""


# ── The bill (2026-09-11) ─────────────────────────────────────────────────────

def request_module_tag(request_id) -> str:
    """The marker that ties an `OrgBuildHours` line back to the request it came from.

    A convention, not a foreign key, because `OrgBuildHours` deliberately predates this and
    holds hours that never came from a request at all. The tag is what makes a request
    countable as billed without narrowing the model to requests only.
    """
    return f'[REQ-{request_id}]'


def request_id_from_module(text):
    """The request id an `OrgBuildHours` row was recorded against, or None.

    The inverse of `request_module_tag`, kept beside it so the two spellings of the convention
    cannot drift. None means the hours were typed in without a request behind them, which
    `billable_kind` then has to make a pricing decision about.
    """
    import re

    found = re.search(r'\[REQ-(\d+)\]', text or '')
    return int(found.group(1)) if found else None


def billable_kind(module):
    """``'feature'`` (priced) or ``'bug'`` (free), for one `OrgBuildHours` row.

    ⚠ **THE OWNER'S TRIAGE DECIDES, NOT THE SUBMITTER AND NOT THE AI** (owner, 2026-10-29). A
    request carries three opinions — `ai_draft_kind` (Gemini's guess), `kind` (what the submitter
    filed it as) and `triaged_kind` (the owner's ruling). Only the third may move money. The
    adjudication rule is written on `OrgRequest`: matrix / manual = bug (free);
    working-as-documented-but-wanted-different = feature (priced).

    ⚠ **A ROW WITH NO REQUEST BEHIND IT IS A FEATURE.** Hours typed straight onto the build-hours
    screen are work a super deliberately decided to bill; reading them as free would silently
    discard them. This is the one place the module's usual "when unsure, do not charge" lean is
    reversed, and it is reversed because the human already made the call by typing the row.

    ⚠ **An untriaged request is a FEATURE too**, because `triaged_kind` is blank until the owner
    presses triage, and a blank is not a ruling that the work was free. It falls back to `kind` so
    the figure is never nothing at all — see the note in `development_charge` about why that
    fallback must stay visible on the screen rather than quietly priced.
    """
    from .models import OrgRequest

    request_id = request_id_from_module(module)
    if request_id is None:
        return 'feature'
    row = OrgRequest.objects.filter(pk=request_id).values('kind', 'triaged_kind').first()
    if row is None:
        return 'feature'
    return (row['triaged_kind'] or row['kind'] or 'feature').strip() or 'feature'


def unbilled_request_hours(organisation=None):
    """Finished request work that carries quoted hours and has NEVER been billed.

    The gap the owner found: *"You also need to include the work we do fulfilling requests,
    which are billed."* Requests carry `quote_hours`; `OrgBuildHours` carries what is billed;
    on production the first held 27.5 hours and the second held nothing at all. Nothing joined
    them, so finished work simply never reached an invoice.

    ⚠ **THE MONTH IS WHEN WE WORKED, NEVER WHEN THE REQUEST WAS RAISED** (owner, 2026-09-11:
    *"we should consider only when we worked and not when the request was raised."*). On
    production the two differ substantially — by raised date July carries 4.0 hours and August
    23.5; by worked date July carries **none at all** and August 27.0, because the two requests
    raised on 30 July were both scheduled and finished on 1 August. Billing by the raised date
    would have put four hours into a month where nobody worked.

    `scheduled_for` is the signal: a date field holding the day the work was slotted in. Where a
    request has none, `updated_at` stands in — it is weaker, because any later edit moves it, so
    `worked_basis` says which of the two was used and the recorded `basis` repeats it.

    ⚠ **This still does NOT bill anything.** It proposes a month; a person confirms it. The
    suggestion is good enough to prefill and not good enough to charge on unattended.

    A request counts as billed once an `OrgBuildHours` row names it — matched on the request id
    written into `module`, which is what the screen prefills.
    """
    from .models import OrgBuildHours, OrgRequest

    qs = OrgRequest.objects.filter(status='done').exclude(quote_hours=None)
    if organisation is not None:
        qs = qs.filter(organisation=organisation)

    recorded = list(OrgBuildHours.objects.values_list('module', flat=True))
    out = []
    for r in qs.select_related('organisation').prefetch_related('analyses').order_by('id'):
        tag = request_module_tag(r.id)
        if any(tag in m for m in recorded):
            continue
        worked_on, worked_basis = worked_date(r)
        # ⚠ THE PUBLISHED ACTUAL, NOT THE QUOTE. The owner read this very panel on 2026-10-29 and
        # found it proposing 7h for request 30 and 8h for request 31 — the plans — while the
        # closing reports had told BrightPath 4 and 5. Pressing Record filed the wrong number, and
        # the invoice then billed it. `hours` is None where no closing figure exists, and the
        # screen must offer no Record button for such a row.
        report = closing_report(r)
        hours = None if report is None else report.charged_hours
        out.append({
            'request_id': r.id,
            'organisation_id': r.organisation_id,
            'organisation': r.organisation.name,
            'title': r.title,
            'hours': hours,
            # Shown beside it so the owner can see the two and notice a surprise. The QUOTE is
            # still worth reading — it is what the organisation agreed to — it is simply not what
            # is billed.
            'quoted_hours': r.quote_hours,
            'actual_hours': None if report is None else report.actual_hours,
            # ⚠ The reason a row cannot be recorded, so the screen says WHY rather than hiding it.
            'blocked': None if hours is not None else 'no_actual_reported',
            # Prefilled for the screen's "record these hours" action, so the tag that makes the
            # request countable as billed is written by the code, not typed by a human.
            'module': f'{tag} {r.title}'[:200],
            # WHEN WE WORKED — the month these hours belong to, and how that was decided.
            'worked_on': worked_on,
            'worked_month': worked_on.strftime('%Y-%m'),
            'worked_basis': worked_basis,
        })
    return out


def closing_report(req):
    """The latest approved, un-superseded analysis that states what the work ACTUALLY took.

    ⚠ **THIS IS THE DOCUMENT THE ORGANISATION WAS SENT**, so it is the only honest source for a
    bill. Returns the analysis, or None when no closing figure has been recorded yet — and None
    must REFUSE an invoice, never fall back to the quote. Falling back is precisely the defect:
    on 2026-10-29 the owner audited all sixteen billed requests and found five billed on their
    PLAN while the closing report published a different number to the customer.

    "Latest" is by `(approved_at, id)`, the same ordering `_hours_bearing_analysis` uses, so the
    two cannot disagree about which report is the final one.
    """
    rows = [a for a in req.analyses.all()
            if a.approved_at and not a.superseded_at and a.charged_hours is not None]
    if not rows:
        return None
    return max(rows, key=lambda a: (a.approved_at, a.id))


def billable_hours(req):
    """What this request puts on an invoice: ``Decimal`` hours, or None when nothing is reported.

    ⚠ **NEVER `quote_hours`.** The quote is the plan and the plan is not what happened. Request 10
    was quoted 15.0, re-scoped downward and spent 11.5 — and billed 15.0. Request 14's closing
    report said *"none of it is charged"* and it was billed 2.0.

    ⚠ **0.0 IS A REAL ANSWER AND IS NOT None.** It means the work was done and deliberately not
    charged, which a caller must be able to tell apart from "nobody has said yet".
    """
    report = closing_report(req)
    return None if report is None else report.charged_hours


#: The most hours one request may claim. A sanity ceiling, the same one `org_requests._MAX_HOURS`
#: uses on a quote — held separately only because importing it would make this leaf depend on the
#: module that imports it.
_MAX_REPORTED_HOURS = 100000


def _clean_reported_hours(value, code):
    """Hours as a Decimal to one place, or raise. ⚠ **0.0 IS VALID HERE** and is the whole point.

    `org_requests._clean_hours` refuses zero, correctly: a QUOTE of nothing is meaningless. A
    REPORT of nothing is not — request 14's closing report said *"none of it is charged"*, and 0.0
    is exactly how that is written down. Reusing the quote cleaner would have refused the very
    figure this sprint exists to record, so this is a separate function on purpose.
    """
    from decimal import Decimal, InvalidOperation

    from .org_requests import OrgRequestError

    try:
        hours = Decimal(str(value)).quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError, TypeError):
        raise OrgRequestError(code)
    if hours < 0 or hours > _MAX_REPORTED_HOURS:
        raise OrgRequestError(code)
    return hours


def record_hours(analysis, admin, *, actual_hours, charged_hours=None, charge_note=''):
    """Write down what the work ACTUALLY took and what we will charge for it (super only).

    ⚠ **THIS IS A TRANSCRIPTION, NOT A DECISION.** The figures already exist — they were published
    to the organisation in the closing report, in prose. The owner is copying them into columns so
    the invoice can read them. **Nothing here parses the prose**, and nothing should: on 2026-10-29
    five of sixteen billed requests were wrong precisely because a machine was left to infer the
    number, and a guess that lands on an invoice is worse than a blank that refuses one.

    ⚠ **THE ANALYSIS MUST BE APPROVED.** An unapproved draft was never sent, so its figures were
    never communicated, so they are not the authority (owner, 2026-10-29: *"What matters is, what
    was communicated back to the requester."*). A superseded one is refused for the same reason.

    `charged_hours` defaults to `actual_hours`, which is the ordinary case. They may differ in
    EITHER direction and both are real:
      * charged < actual — we absorbed the overrun (request 14: five hours spent, nothing charged);
      * charged > actual — the organisation accepted the extra (request 38).
    ⚠ **A DIFFERENCE REQUIRES `charge_note`.** An unexplained write-off is money moved with no
    reason on the record, which is the same defect `OrgBuildHours.basis` exists to prevent.

    ⚠ **EDITING AFTER THE MONTH IS BILLED IS ALLOWED, AND CHANGES NO INVOICE.** `InvoiceLine` rows
    are frozen snapshots, so a figure corrected today cannot rewrite a document already sent — that
    is what `OrgBillingCorrection` is for. This has to be allowed, because the five figures the
    owner audited belong to requests that are ALREADY billed; refusing the edit would mean the
    record could never be made right at all.
    """
    from . import org_requests
    from .org_requests import OrgRequestError

    if not org_requests._is_super(admin):
        raise OrgRequestError('forbidden')
    if not analysis.approved_at:
        raise OrgRequestError('analysis_not_approved')
    if analysis.superseded_at:
        raise OrgRequestError('analysis_superseded')

    actual = _clean_reported_hours(actual_hours, 'bad_actual_hours')
    charged = (actual if charged_hours in (None, '')
               else _clean_reported_hours(charged_hours, 'bad_charged_hours'))
    note = (charge_note or '').strip()
    if charged != actual and not note:
        raise OrgRequestError('charge_note_required')
    if len(note) > org_requests.COMMENT_MAX_CHARS:
        raise OrgRequestError('charge_note_too_long')

    analysis.actual_hours = actual
    analysis.charged_hours = charged
    # Blank means "no note", stored as NULL rather than '' so the column reads the same way the
    # other two do: absent, not empty.
    analysis.charge_note = note or None
    # `updated_at` is `auto_now`, so NAMING it is what makes it move — it is not assigned above.
    analysis.save(update_fields=['actual_hours', 'charged_hours', 'charge_note', 'updated_at'])
    return analysis


def worked_date(request):
    """The day the work happened, and which field said so.

    Returns ``(date, 'scheduled'|'last touched')``.

    ⚠ NOT `created_at`. That is the day somebody ASKED, which on production sits in a different
    month from the work for a third of the quoted requests. `scheduled_for` is the day the work
    was slotted in and is the right answer where it exists; `updated_at` is the fallback and is
    weaker, because any later edit to the request moves it. The caller reports which was used
    rather than presenting both as equally sound.
    """
    from django.utils import timezone

    if request.scheduled_for:
        return request.scheduled_for, 'scheduled'
    return timezone.localtime(request.updated_at).date(), 'last touched'


def consent_gaps(organisation, period_month):
    """Billable FEATURE hours in this month whose request was never quoted, or never accepted.

    ⚠ **THE OWNER'S RULE, 2026-10-29:** *"Make sure every feature has a quote and acceptance from
    BrightPath (including me signed in as BrightPath org admin)."* A feature is priced work, so
    billing one the organisation never agreed to is charging for something nobody ordered. This is
    the check that makes that impossible rather than unlikely; `invoicing.readiness` raises it as
    an ABSOLUTE refusal, not a warning somebody can click past, because there is a remedy — quote
    it and have it accepted — and "bill it anyway" is not one.

    ⚠ **WHO pressed accept does not matter, and cannot be known anyway.** The owner holds a
    BrightPath org_admin account and `org_requests.approve` admits that role as well as a super,
    so an acceptance made while signed in as BrightPath is a real acceptance. It is also the only
    answer available: `approve()` records `approved_at` but throws away the `by_role` it is handed,
    so nothing on the row says which account pressed it (TD-418).

    ⚠ **BUGS ARE NOT CHECKED.** A bug is free, so there is nothing to consent to — and demanding a
    quote for work nobody is charged for would block a month over paperwork for RM0.00.

    ⚠ **HOURS WITH NO REQUEST BEHIND THEM ARE NOT CHECKED EITHER.** A super typed those straight
    onto the build-hours screen; there is no request to carry a quote, and refusing them would make
    the screen's own feature unusable. They are deliberate and they stay billable — the same
    judgement `billable_kind` makes, and the same place it would be wrong to guess.

    Returns a list of ``{'request_id', 'title', 'hours', 'missing'}``, `missing` naming what is
    absent ('a quote', 'an acceptance', or both).
    """
    from .models import OrgBuildHours, OrgRequest

    wanted = {}
    for row in OrgBuildHours.objects.filter(organisation=organisation,
                                            period_month=period_month):
        request_id = request_id_from_module(row.module)
        if request_id is None or billable_kind(row.module) == 'bug':
            continue
        wanted[request_id] = wanted.get(request_id, 0) + 1

    out = []
    for req in OrgRequest.objects.filter(pk__in=sorted(wanted)).order_by('id'):
        missing = []
        if req.quoted_at is None or req.quote_hours is None:
            missing.append('a quote')
        if req.approved_at is None:
            missing.append('an acceptance')
        if missing:
            out.append({'request_id': req.id, 'title': req.title,
                        'hours': req.quote_hours, 'missing': ' and '.join(missing)})
    # A tag naming a request that does not exist cannot be checked, and `billable_kind` already
    # treats it as billable. Say so here rather than letting it pass silently.
    for request_id in sorted(set(wanted) - set(
            OrgRequest.objects.filter(pk__in=sorted(wanted)).values_list('pk', flat=True))):
        out.append({'request_id': request_id, 'title': '(no such request)',
                    'hours': None, 'missing': 'a quote and an acceptance'})
    return out


def bug_reports_fixed(organisation, period_month):
    """The bug reports FIXED in this month: how many, and the engineer's hours where known.

    Returns ``{'count': int, 'hours': Decimal|None}``. Free work either way — this is what the
    organisation GOT, never what it pays.

    ⚠ **THE HOURS ARE THE ENGINEER'S, NOT A QUOTE.** The owner compared the first invoice against
    the request list on 2026-10-29 and found most finished requests missing. The first diagnosis
    here — "there are no hours for free work" — was WRONG, and the owner disproved it with request
    7's analysis showing 5.0 hours. A bug is never *quoted*, so `quote_hours` is null and no
    `OrgBuildHours` row exists; but the engineer's reading of the code carries
    `estimated_hours`, and that is a real measurement of real work.

    ⚠ **THE LATEST ANALYSIS IS OFTEN THE WRONG ONE.** A finished request carries the ESTIMATE and
    then, since October 2026, a COMPLETION REPORT written after the work — and a completion report
    carries no hours, because it reports rather than estimates. `org_requests.approved_analysis`
    takes the latest, which for every October bug is that report, which is why the first version of
    this function reported October as "ten bugs, no hours" when the estimates were sitting one row
    below. This takes the most recent analysis that actually CARRIES a figure. It still reads the
    same candidates (approved, not superseded, with a cited file) so it cannot drift from the
    screen about which analyses count — only about which of them answers "how long?".

    ⚠ **That also makes it right AFTER the hours rule lands.** Once a completion report records the
    ACTUAL hours against the plan, the newest figure is the actual one, and this picks it up with
    no change.

    ⚠ **`hours` is None when nothing is known, NEVER 0.0.** Two October bugs (36 and 43) still
    carry no estimate anywhere. Printing "0.0 hours" for work that was done would be a confident
    lie; a blank says "not measured". The caller decides how to say that.
    """
    from decimal import Decimal as _D

    from . import org_requests
    from .models import OrgRequest

    qs = OrgRequest.objects.filter(status='done')
    if organisation is not None:
        qs = qs.filter(organisation=organisation)

    count = 0
    hours = _D('0.0')
    measured = 0
    for req in qs.prefetch_related('analyses'):
        if (req.triaged_kind or req.kind or 'feature').strip() != 'bug':
            continue
        worked_on, _basis = worked_date(req)
        if worked_on.strftime('%Y-%m') != period_month:
            continue
        count += 1
        planned = _hours_bearing_analysis(req)
        if planned is not None:
            hours += planned
            measured += 1
    return {'count': count, 'hours': hours if measured else None}


def _hours_bearing_analysis(req):
    """The hours on the most recent analysis that HAS an hours figure, or None.

    Same candidate set as `org_requests.approved_analysis` — approved, not superseded, carrying at
    least one cited file — so the two cannot disagree about which analyses are real. It differs in
    one way only: it skips the ones that answer no question about time, which is every completion
    report.
    """
    rows = [a for a in req.analyses.all()
            if a.approved_at and not a.superseded_at and a.cited_files
            and a.estimated_hours is not None]
    if not rows:
        return None
    return max(rows, key=lambda a: (a.approved_at, a.id)).estimated_hours
