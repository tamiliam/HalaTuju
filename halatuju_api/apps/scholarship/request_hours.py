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
    for r in qs.select_related('organisation').order_by('id'):
        tag = request_module_tag(r.id)
        if any(tag in m for m in recorded):
            continue
        worked_on, worked_basis = worked_date(r)
        out.append({
            'request_id': r.id,
            'organisation_id': r.organisation_id,
            'organisation': r.organisation.name,
            'title': r.title,
            'hours': r.quote_hours,
            # Prefilled for the screen's "record these hours" action, so the tag that makes the
            # request countable as billed is written by the code, not typed by a human.
            'module': f'{tag} {r.title}'[:200],
            # WHEN WE WORKED — the month these hours belong to, and how that was decided.
            'worked_on': worked_on,
            'worked_month': worked_on.strftime('%Y-%m'),
            'worked_basis': worked_basis,
        })
    return out


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
