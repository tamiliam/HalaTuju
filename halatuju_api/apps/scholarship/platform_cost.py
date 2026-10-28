"""Platform cost ledger — classification + reconciliation (2026-07-26).

The COST side of billing. ``usage.py`` answers "what did this organisation consume?";
this module answers "what did the platform cost, and how much of it can honestly be
attributed to tenant activity at all?"

The finding that shaped it (June 2026, measured from the BigQuery billing export):

    tenant-driven   RM19.91   23%   Vision, Gemini, request-serving CPU/memory, egress
    platform-driven RM63.49   72%   Cloud Run JOBS, Artifact Registry, Scheduler, Build
    tax              RM5.04    5%   pro-rata over both

So roughly three-quarters of the "metered" GCP bill does not move with tenant activity at
all — it moves with our cron schedule and our deploy pace. That is a **platform fee**, not a
metered charge, and pretending otherwise would produce a number that looks precise and is
arbitrary. Hence ``attributable``: this module's one real judgement.

Everything here is pure except ``reconcile``, which reads the ledger. No writes — the two
management commands own those, so there is exactly one place each kind of row is created.
"""
from decimal import Decimal

# Requests and the hours recorded against them live in `request_hours.py` (moves only, 2026-10-29:
# this file reached 760 lines against a 701-line allowance). Re-exported so every existing
# `platform_cost.<name>` caller keeps working, including `mock.patch.object(platform_cost, ...)`.
#
# ⚠ BOUND AS NAMES, not `from .request_hours import ...`. A plain re-export import reads as an
# unused import to the linter and needs an F401 suppression to silence it — and the count of those
# suppressions is itself a budget that may not rise (`TestNoNewBlindSpots`). Binding through the
# module USES the import, so there is nothing to suppress. Rebinding also keeps the names
# patchable: `development_charge` looks `billable_kind` up as a global at call time.
# (That guard counts the marker as a literal string, so it counts one written in prose too — this
# comment deliberately describes the marker instead of spelling it.)
from . import request_hours

billable_kind = request_hours.billable_kind
consent_gaps = request_hours.consent_gaps                       # the quote + acceptance check
request_id_from_module = request_hours.request_id_from_module
request_module_tag = request_hours.request_module_tag
unbilled_request_hours = request_hours.unbilled_request_hours
worked_date = request_hours.worked_date

# ── The attribution rule ──────────────────────────────────────────────────────
# A SKU is attributable when its volume moves with what tenants DO. Matched on the SKU
# description because that is the grain the invoice is actually billed at — matching on the
# service name would sweep Cloud Run's request-serving (tenant) together with its Jobs
# (our crons), which is exactly the conflation that hid the biggest line for a month.
#
# Substring match, lowercased. Order does not matter; any hit attributes the line.
ATTRIBUTABLE_SKU_MARKERS = (
    'document text detection',   # Cloud Vision — one call per applicant document
    'generate content',          # Gemini — per applicant report / extraction
    # ⚠ THE SAME SKU, SPELT WITH AN UNDERSCORE, AND IT WAS BEING MISSED. Google bills it as
    # 'Generate_content text output token count for …', which the spaced marker above does not
    # match — so every Gemini line fell through to `platform`, the most tenant-driven cost on the
    # invoice counted as our own. Found on 2026-09-11 when the July and August pulls were read
    # line by line for the first time. It is RM0.03 today and it is the line that grows.
    'generate_content',
    'gemini api',                # the service name, so a future Gemini SKU cannot slip past too
    'services cpu',              # Cloud Run request-serving (NOT 'Jobs CPU')
    'services memory',           # ditto
    'data transfer',             # egress — serving responses to real users
    'standard storage',          # Cloud Storage — the documents tenants uploaded
    # ── Twilio (2026-09-11, once its invoices reached the ledger) ────────────
    'programmable messaging',    # WhatsApp + SMS TO APPLICANTS — one send per real person
    'account security',          # Authy / Verify — one code per real person signing in
)

# Explicitly NOT attributable, listed so the reasoning survives review rather than living in
# the negative space of the tuple above. These are real costs; they are simply OURS.
PLATFORM_SKU_MARKERS = (
    'jobs cpu',                  # scheduled crons — fires on a clock, not on tenant activity
    'jobs memory',
    'artifact registry',         # CI images — a function of OUR deploy pace
    'cloud scheduler',           # the cron schedule itself
    'cloud build',               # CI
    # ── The other three providers (2026-09-11) ──────────────────────────────
    # Each is a STANDING charge: it is the same whether one applicant uses the platform or a
    # thousand do, which is the definition this module works to. Listed rather than left to the
    # conservative default so the reasoning survives review.
    'phone numbers',             # Twilio — one number, rented monthly, used or not
    'business starter',          # Google Workspace — our own mailboxes
    'google workspace',
    'pro plan',                  # Supabase — the database base fee, flat
)


# ── The third bucket: what it costs us to DELIVER HOURS ──────────────────────
# Owner, 2026-09-11: *"My biggest cost is Claude, which needs to be included via the request
# hours."* That sentence decides where this cost belongs, and it is neither of the other two.
#
# ⚠ IT MUST NOT SIT IN THE PLATFORM BUCKET. Platform cost is marked up and charged as the
# infrastructure line; development hours are marked up and charged as the development line. Claude
# is an input to the SECOND. Leaving it in `platform` would recover the same ringgit twice — once
# through the infrastructure fee and again through the hourly rate — which is the single most
# expensive kind of quiet mistake an invoice can carry.
#
# What it buys instead: the development line can show what the hours COST beside what they are
# CHARGED, so "is RM50/hour enough?" becomes a figure on a screen rather than a feeling.
DEVELOPMENT_SKU_MARKERS = (
    'anthropic',
    'claude',
)


# ── The services that run the whole platform, as a tenant should see them (2026-09-15) ───────
# Owner, 2026-09-15, reading the organisation's Usage & Billing page: *"We have not mentioned anything
# about Google Workspace, which covers emails, drive, google meet"* and *"No mention of Cloudflare or
# Github, which are at present free platform level services."* The page named three free services in
# a footnote and nothing that is paid but shared — so the biggest standing costs were invisible.
#
# Names and plans only: WHAT each costs is a commercial disclosure that stays on the super-only costs
# screen. Every ledger source is either listed here or excluded below WITH A REASON, and a test fails
# if a new source is added without that decision.
PLATFORM_SERVICES = (
    {'key': 'gcp', 'plan': 'paid'},         # hosting the site and app, AI, document reading
    {'key': 'supabase', 'plan': 'paid'},    # database, file storage, data transfer (egress)
    {'key': 'workspace', 'plan': 'paid'},   # email mailboxes, Google Drive, Google Meet
    {'key': 'twilio', 'plan': 'paid'},      # the WhatsApp number
    {'key': 'brevo', 'plan': 'free'},       # sending email
    {'key': 'cloudflare', 'plan': 'free'},  # Turnstile bot checks on sign-in and the contact form
    {'key': 'github', 'plan': 'free'},      # code and automatic deployments
)
NOT_A_PLATFORM_SERVICE = {
    'anthropic': 'a cost of delivering development hours, recovered through the hourly rate; not '
                 'a service the organisation uses',
    'openai': 'a fallback AI provider that has never run on production; list it the day it does',
    'other': 'a bucket for one-off lines, not a service',
}


def is_development_cost(service: str, sku: str) -> bool:
    """True when this line is an input to billable development hours, not to running the site."""
    hay = f'{service or ""} {sku or ""}'.lower()
    return any(m in hay for m in DEVELOPMENT_SKU_MARKERS)


def cost_bucket(service: str, sku: str, attributable=None) -> str:
    """Which of the four buckets a ledger line belongs in.

    ``'tax'`` | ``'development'`` | ``'metered'`` | ``'platform'``. One place, so the sync, the
    month totals and the charge cannot disagree about a line.

    `attributable` is the flag already stored on the row; pass it to respect what was recorded
    at sync time, or leave it None to re-derive from the SKU.
    """
    if is_tax(service, sku):
        return 'tax'
    if is_development_cost(service, sku):
        return 'development'
    attr = classify_sku(service, sku) if attributable is None else attributable
    return 'metered' if attr else 'platform'


def classify_sku(service: str, sku: str) -> bool:
    """True if this invoice line moves with TENANT activity.

    Deliberately conservative: anything unrecognised is **platform** (False), so a new SKU
    lands in the fee rather than silently inflating a tenant's metered charge. An unbilled
    tenant is a pricing conversation; an over-billed one is a refund and an apology.
    """
    hay = f'{service or ""} {sku or ""}'.lower()
    if any(m in hay for m in PLATFORM_SKU_MARKERS):
        return False
    return any(m in hay for m in ATTRIBUTABLE_SKU_MARKERS)


def is_tax(service: str, sku: str) -> bool:
    """Tax is pro-rata over everything and belongs to neither side on its own."""
    return 'tax' in f'{service or ""} {sku or ""}'.lower()


# ── Reconciliation ────────────────────────────────────────────────────────────

def month_totals(period_month):
    """Ledger totals for one month, split the way the pricing decision needs them.

    Returns a plain dict (no model objects) so a caller — a command today, an endpoint
    later — cannot accidentally surface a cost row to an org-facing surface.
    """
    from .models import PlatformCost

    rows = PlatformCost.objects.filter(period_month=period_month)
    total = attributable = platform = tax = development = Decimal('0.00')
    by_source = {}
    entered_sources = set()
    # ⚠ TRACKED SEPARATELY FROM `entered_sources`, and the difference is the whole point of the
    # provenance column. An EXTRACTED figure is reproducible — the provider's PDF parsed by a
    # parser that refuses unless it reconciles to the printed total. An ENTERED one is a person's
    # reading, checkable by nobody. Collapsing them would put a warning on a sound figure and,
    # far worse, make a hand-typed figure look sound.
    extracted_sources = set()
    # Rows whose ringgit cost is not yet known — a held invoice awaiting its FX rate. They are
    # COUNTED and reported, never dropped: a total that quietly omits a RM100 line is worse
    # than one that says "incomplete", because only the second prompts anyone to go and look.
    unconverted = []

    for r in rows:
        if r.provenance == 'entered':
            entered_sources.add(r.source)
        elif r.provenance == 'extracted':
            extracted_sources.add(r.source)
        if r.amount_myr is None:
            unconverted.append({
                'source': r.source,
                'invoice_ref': r.invoice_ref,
                'currency': r.currency,
                'amount_original': r.amount_original,
            })
            continue
        total += r.amount_myr
        by_source[r.source] = by_source.get(r.source, Decimal('0.00')) + r.amount_myr
        bucket = cost_bucket(r.service, r.sku, r.attributable)
        if bucket == 'tax':
            tax += r.amount_myr
        elif bucket == 'development':
            development += r.amount_myr
        elif bucket == 'metered':
            attributable += r.amount_myr
        else:
            platform += r.amount_myr

    return {
        'month': period_month,
        'lines': rows.count(),
        'total_myr': total,
        'attributable_myr': attributable,
        'platform_myr': platform,
        # ⚠ What it costs us to DELIVER HOURS (Claude), held apart from `platform_myr` so it is
        # never marked up as infrastructure. It is recovered through the hourly rate instead —
        # charging it in both places would take the same ringgit twice.
        'development_myr': development,
        'tax_myr': tax,
        'by_source': by_source,
        # Which sources in this month rest on a human reading a PDF. Surfaced, never hidden:
        # a total that mixes measured and entered figures without saying so is not an audit.
        'entered_sources': sorted(entered_sources),
        # Sources read from the provider's own invoice by a parser that reconciles to the
        # printed total. Reported so the reader knows WHERE each figure came from, but it is a
        # note, not a warning — unlike `entered_sources`, which is one.
        'extracted_sources': sorted(extracted_sources),
        # Truthfulness flags. `is_complete` False means the total below is a FLOOR, not a total.
        'unconverted': unconverted,
        'is_complete': not unconverted,
        # Providers whose billing period does not line up with the calendar month, so a
        # cross-provider comparison in this month is comparing unlike windows.
        'period_caveats': sorted({r.period_note for r in rows if r.period_note}),
    }


# ── Rates + charges (owner design 2026-07-27) ─────────────────────────────────
# Hours are recorded ORG-side; the conversion rate and per-category margins are PLATFORM-side
# editable values. Everything below reads those rates — nothing here carries a hard-coded price.

class RateMissing(Exception):
    """No rate in force for a (category, kind) on the date asked for.

    Raised, never swallowed. A missing rate must stop a charge being computed: an unbilled
    month is a visible problem somebody fixes, whereas a month billed at a defaulted rate is
    an invoice you have to withdraw and explain.
    """


def _month_start(period_month):
    from datetime import date
    year, mon = (int(x) for x in str(period_month).split('-'))
    return date(year, mon, 1)


def month_end(period_month):
    """Last day of 'YYYY-MM' as a date. One home, because two date rules give two answers.

    Used by the GCP sync's month bounds and by the FX lookup, which takes the rate at the END of
    the billing month (owner ruling, 2026-09-11).
    """
    from datetime import date, timedelta
    year, mon = (int(x) for x in str(period_month).split('-'))
    year, mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    return date(year, mon, 1) - timedelta(days=1)


def rate_in_force(category, kind, on_date):
    """The value that applied ON that date — not the current one.

    This is what stops a rate change in September silently re-pricing August. Returns the
    latest row whose ``effective_from`` is on or before ``on_date``.
    """
    from .models import BillingRate

    row = (BillingRate.objects
           .filter(category=category, kind=kind, effective_from__lte=on_date)
           .order_by('-effective_from')
           .first())
    if row is None:
        raise RateMissing(
            f'No {kind} in force for {category} on {on_date}. Set one on the platform '
            f'billing-rates screen before billing this month — it will not be guessed.')
    return row.value


def development_charge(organisation, period_month):
    """What this organisation is charged for build hours in a month.

    hours x hourly_rate x (1 + development margin), each factor read from the rate table as at
    the FIRST of the billed month. Returns a dict, never a bare number, because a charge on an
    invoice needs to show its own working — the tenant is entitled to see how it was reached.

    ⚠ **BUG HOURS ARE WORKED AND COUNTED, AND CHARGED AT ZERO.** The owner's own note on the 15%
    development margin, written 2026-09-11, says why: *"The margin should help cover bug fixing
    which is not billed separately."* So a bug is already paid for inside the hourly rate, and
    billing it again as a feature would charge for the same work twice. `billable_kind` makes the
    call per row; bug rows keep their hours (they are real time, and `hours`/`subtotal_myr` still
    include them) and take `amount_myr` 0.00.

    ⚠ **`subtotal_myr` IS THE COST OF ALL THE TIME, INCLUDING THE FREE PART.** It is the figure the
    owner's screen puts beside the charge to answer *"is RM50/hour enough?"*, and dropping the
    unbilled hours out of it would make the margin look better than it is. A month that was all
    bug-fixing should read as costly and recover nothing — because that is what happened.
    """
    from .models import OrgBuildHours

    rows = OrgBuildHours.objects.filter(
        organisation=organisation, period_month=period_month)
    hours = sum((r.hours for r in rows), Decimal('0.0'))
    if not rows:
        return {'month': period_month, 'hours': Decimal('0.0'), 'lines': [],
                'rate_myr': None, 'margin_pct': None, 'feature_hours': Decimal('0.0'),
                'bug_hours': Decimal('0.0'), 'billed_rate_myr': None,
                'subtotal_myr': Decimal('0.00'), 'charge_myr': Decimal('0.00')}

    from .models import BillingRate
    on = _month_start(period_month)
    # Deliberately NOT wrapped in try/except — a missing rate propagates to the caller.
    rate = rate_in_force(BillingRate.CATEGORY_DEVELOPMENT, BillingRate.KIND_HOURLY_RATE, on)
    margin = rate_in_force(BillingRate.CATEGORY_DEVELOPMENT, BillingRate.KIND_MARGIN_PCT, on)

    subtotal = (hours * rate).quantize(Decimal('0.01'))
    # ⚠ THE CHARGE IS THE SUM OF THE MODULE LINES AT THE BILLED RATE (2026-09-14), not
    # `subtotal x (1 + margin)` rounded once. An invoice prints each module as hours x rate =
    # amount, and a tenant checks that arithmetic with a calculator. Rounding the total once and
    # the lines separately could leave the lines a cent short of the total, on a document that is
    # supposed to add up. Identical to the old figure whenever the billed rate is whole cents —
    # which RM50 +15% = RM57.50 is.
    billed_rate = (rate * (Decimal('1') + margin / Decimal('100'))).quantize(Decimal('0.01'))
    lines = []
    for r in rows:
        kind = billable_kind(r.module)
        free = kind == 'bug'
        lines.append({
            'module': r.module,
            'request_id': request_id_from_module(r.module),
            'kind': kind,
            'hours': r.hours,
            'basis': r.basis,
            # A bug's rate is printed as RM0.00 rather than left blank: the owner asked for the
            # hours AND the rate to show, so the arrangement reads off the paper instead of
            # needing to be explained.
            'unit_amount_myr': Decimal('0.00') if free else billed_rate,
            'amount_myr': (Decimal('0.00') if free
                           else (r.hours * billed_rate).quantize(Decimal('0.01'))),
        })
    charge = sum((ln['amount_myr'] for ln in lines), Decimal('0.00'))
    feature_hours = sum((ln['hours'] for ln in lines if ln['kind'] != 'bug'), Decimal('0.0'))
    bug_hours = sum((ln['hours'] for ln in lines if ln['kind'] == 'bug'), Decimal('0.0'))
    return {
        'month': period_month,
        'hours': hours,
        'feature_hours': feature_hours,
        'bug_hours': bug_hours,
        'lines': lines,
        'rate_myr': rate,
        'margin_pct': margin,
        'billed_rate_myr': billed_rate,
        'subtotal_myr': subtotal,
        'charge_myr': charge,
    }


def apply_margin(amount_myr, category, period_month):
    """Add the category's in-force margin to a cost. Used for infrastructure + metered lines.

    Kept separate from `development_charge` because those two categories start from a COST we
    paid, whereas development starts from hours we spent — different inputs, same margin
    mechanism, and conflating them would hide which is which on the invoice.
    """
    from .models import BillingRate

    margin = rate_in_force(category, BillingRate.KIND_MARGIN_PCT, _month_start(period_month))
    return ((amount_myr or Decimal('0.00'))
            * (Decimal('1') + margin / Decimal('100'))).quantize(Decimal('0.01'))


# ── The bill (2026-09-11) ─────────────────────────────

# `request_module_tag`, `request_id_from_module`, `billable_kind`, `unbilled_request_hours` and
# `worked_date` moved to `request_hours.py` on 2026-10-29 and are re-exported at the top of this
# file, so `platform_cost.<name>` still reaches them.


def adjustment_for(organisation, period_month):
    """The discount agreed for this organisation and this month, or None."""
    from .models import OrgBillingAdjustment

    return (OrgBillingAdjustment.objects
            .filter(organisation=organisation, period_month=period_month)
            .first())


def tenant_shares(period_month):
    """Each tenant's share of the month's platform cost, and the rule that decided it.

    Owner ruling, 2026-09-11: *"For everything apply the markup/margin as determined by the rate
    that is set."* Applying a margin to a platform-wide cost means first deciding whose cost it
    is, so the split has to be stated rather than assumed.

    Two rules, because the two cost buckets genuinely differ:

      * **metered** — split by each tenant's share of METERED EVENTS that month. Measured, not
        invented: it is the same `UsageEvent` table the usage screen already counts. That is what
        "metered" means, and a tenant that ran nothing pays nothing.
      * **infrastructure** — split EQUALLY. It is a standing cost: the database, the mailboxes,
        the phone number and the cron schedule are the same size whether a tenant is busy or
        idle, so usage-weighting it would charge the active tenant for the idle one's readiness.

    ⚠ **There is ONE tenant today, so both rules return 100% and neither has ever been exercised
    in anger.** They are written down here, and returned in the payload, precisely so that the
    day a second tenant arrives the split is a decision somebody reviews rather than a default
    nobody noticed. Events with no organisation — platform-base work — are excluded from the
    weighting; they belong to nobody and must not dilute anyone's share.

    Returns ``{org_id: {'metered': Decimal, 'infrastructure': Decimal, 'rule': str}}``.
    """
    from django.db.models import Count

    from apps.courses.models import PartnerOrganisation

    from .models import UsageEvent

    # `.tenants()`, never a bare `is_active` filter: this table is dual-role and holds referral
    # partners alongside tenants. Ten rows on production, one tenant.
    tenants = list(PartnerOrganisation.objects.tenants().order_by('id'))
    if not tenants:
        return {}
    equal = Decimal('1') / Decimal(len(tenants))

    try:
        year, mon = (int(x) for x in str(period_month).split('-'))
    except (ValueError, AttributeError):
        year = mon = 0
    counts = {
        r['organisation_id']: r['n']
        for r in (UsageEvent.objects
                  .filter(created_at__year=year, created_at__month=mon,
                          organisation__isnull=False)
                  .values('organisation_id')
                  .annotate(n=Count('id')))
    }
    total_events = sum(counts.values())

    out = {}
    for org in tenants:
        if total_events:
            metered = Decimal(counts.get(org.id, 0)) / Decimal(total_events)
            rule = 'metered by share of usage events; infrastructure split equally'
        else:
            metered = equal
            rule = ('no metered events this month, so both split equally')
        out[org.id] = {'metered': metered, 'infrastructure': equal, 'rule': rule}
    return out


def charge_for(organisation, period_month):
    """What this organisation is charged for a month — and what could NOT be worked out.

    Returns every line with its own status, never a single number. Three categories, and each is
    a real cost we paid or real time we spent, marked up by the margin in force for it:

      * **infrastructure** — the platform-driven slice of the month's bill (crons, CI, the
        database, the mailboxes, the phone number), this tenant's share, plus the infrastructure
        margin.
      * **metered** — the tenant-driven slice (OCR, AI, egress, messages), this tenant's share,
        plus the metered margin.
      * **development** — hours x hourly rate x the development margin.

    Owner ruling, 2026-09-11: *"For everything apply the markup/margin as determined by the rate
    that is set."* So a category is charged whenever its margin exists, and the two cost lines are
    grounded in the LEDGER — real invoices — rather than in a unit-price table nobody has written.
    That is what replaced the earlier refusal to price them at all.

    ⚠ **Tax is shared pro-rata between the two cost lines**, in proportion to their size, so the
    charged total still starts from exactly what the providers charged us. Tax belongs to neither
    bucket on its own, and dropping it would quietly bill below cost.

    ⚠ **A missing margin still REFUSES.** `rate_in_force` raises, the category lands in `blocked`
    with its reason, and nothing is rendered as RM0.00. A line the reader can see is missing gets
    fixed; a zero gets believed. That is unchanged and is the point of the rate table.

    The discount is applied LAST and shown as its own line, so the month reads
    subtotal -> discount -> charged. That is the owner's July requirement: shown in full,
    charged nothing.
    """
    from .models import BillingRate

    blocked = []
    lines = []
    subtotal = Decimal('0.00')

    # ── The two lines that come from the invoices we actually paid ───────────
    totals = month_totals(period_month)
    shares = tenant_shares(period_month)
    share = shares.get(getattr(organisation, 'id', None),
                       {'metered': Decimal('0'), 'infrastructure': Decimal('0'), 'rule': ''})

    # Tax pro-rata over the three cost buckets. Guarded against a month that is all tax — then
    # there is nothing to apportion it over and it stays out rather than being invented into one.
    cost_base = (totals['attributable_myr'] + totals['platform_myr']
                 + totals['development_myr'])
    tax = totals['tax_myr']
    if cost_base > 0:
        def _with_tax(part):
            return part + (tax * part / cost_base)
    else:
        def _with_tax(part):
            return part
    metered_cost = _with_tax(totals['attributable_myr'])
    infra_cost = _with_tax(totals['platform_myr'])
    # ⚠ NOT marked up here. It is what the hours COST us, carried onto the development line so
    # the rate can be judged against it. Marking it up as infrastructure would recover Claude
    # twice — once in the fee and again in the hourly rate.
    dev_cost = _with_tax(totals['development_myr']).quantize(Decimal('0.01'))

    for category, cost, weight in (
        (BillingRate.CATEGORY_INFRASTRUCTURE, infra_cost, share['infrastructure']),
        (BillingRate.CATEGORY_METERED, metered_cost, share['metered']),
    ):
        ours = (cost * weight).quantize(Decimal('0.01'))
        try:
            amount = apply_margin(ours, category, period_month)
        except RateMissing as exc:
            blocked.append({'category': category, 'reason': str(exc)})
            continue
        margin = rate_in_force(category, BillingRate.KIND_MARGIN_PCT,
                               _month_start(period_month))
        lines.append({
            'category': category,
            'hours': None,
            'rate_myr': None,
            'margin_pct': margin,
            # What WE paid for this slice, before the margin. Shown beside the charge so the
            # markup is visible rather than baked into one unexplained figure.
            'cost_myr': ours,
            'share_pct': (weight * 100).quantize(Decimal('0.01')),
            'share_rule': share['rule'],
            'amount_myr': amount,
            'detail': [],
        })
        subtotal += amount

    # ── The line that comes from the hours we spent ──────────────────────────
    try:
        dev = development_charge(organisation, period_month)
    except RateMissing as exc:
        dev = None
        blocked.append({'category': 'development', 'reason': str(exc)})
    if dev is not None and dev['hours']:
        lines.append({
            'category': 'development',
            'hours': dev['hours'],
            # The split the invoice groups on. `hours` stays the TOTAL worked, so a screen that
            # shows it keeps telling the truth about how much time the month took.
            'feature_hours': dev['feature_hours'],
            'bug_hours': dev['bug_hours'],
            'rate_myr': dev['rate_myr'],
            'margin_pct': dev['margin_pct'],
            'cost_myr': dev['subtotal_myr'],
            'share_pct': None,
            'share_rule': '',
            # ⚠ WHAT THE TOOLS COST US THIS MONTH, beside what the hours are charged at. This is
            # the only place the two meet, and it is the whole reason Claude is a development
            # cost rather than a platform one: it turns "is RM50/hour enough?" into a figure on
            # a screen. It is NOT added to the charge — it is already recovered by the rate.
            'tool_cost_myr': dev_cost,
            'billed_rate_myr': dev['billed_rate_myr'],
            'amount_myr': dev['charge_myr'],
            'detail': dev['lines'],
        })
        subtotal += dev['charge_myr']
    elif dev_cost > 0:
        # Tools cost money in a month with no billable hours. Silence would read as "nothing was
        # spent"; this says a real cost was carried and recovered by nothing.
        blocked.append({
            'category': 'development',
            'reason': f'Tools for development cost RM{dev_cost} this month, and no billable '
                      f'hours were recorded against it — so nothing recovers that cost.'})

    adj = adjustment_for(organisation, period_month)
    discount_pct = adj.discount_pct if adj else Decimal('0.00')
    discount = (subtotal * discount_pct / Decimal('100')).quantize(Decimal('0.01'))

    return {
        'month': period_month,
        'organisation_id': organisation.id if organisation else None,
        'lines': lines,
        'subtotal_myr': subtotal,
        'discount_pct': discount_pct,
        'discount_myr': discount,
        'discount_reason': adj.reason if adj else '',
        'discount_set_by': adj.set_by_email if adj else '',
        'charged_myr': (subtotal - discount).quantize(Decimal('0.01')),
        # Why a category is absent. Rendered on the screen — a silent omission is the thing
        # this whole module exists to stop.
        'blocked': blocked,
    }


def reconcile(period_month):
    """Compare what the METER recorded against the attributable slice of the real invoice.

    This is the point of the whole ledger. The meter counts events; the invoice counts money.
    If the two drift apart, either the meter is missing a seam or its unit prices are wrong —
    and you want to learn that from a monthly reconciliation, not from a customer.

    v1 reports the two figures side by side and the event counts behind them. It deliberately
    does NOT compute an implied unit price: there is no price table yet (Sprint 13a decision,
    "NO prices in v1"), and inventing one here would quietly become the thing people cite.
    """
    from django.db.models import Count

    from .models import UsageEvent

    totals = month_totals(period_month)
    try:
        year, mon = (int(x) for x in str(period_month).split('-'))
    except (ValueError, AttributeError):
        year = mon = 0

    events = (UsageEvent.objects
              .filter(created_at__year=year, created_at__month=mon)
              .values('service')
              .annotate(n=Count('id'))
              .order_by('-n'))
    counts = {e['service']: e['n'] for e in events}
    total_events = sum(counts.values())
    org_null = (UsageEvent.objects
                .filter(created_at__year=year, created_at__month=mon,
                        organisation__isnull=True)
                .count())

    return {
        **totals,
        'metered_events': total_events,
        'metered_by_service': counts,
        # Unattributed events are the meter's own blind spot. Platform-base work legitimately
        # has no tenant, so this is a figure to READ, not a failure — but a rising share means
        # a tenant is being under-charged, which is why it sits on the reconciliation.
        'metered_org_null': org_null,
        'metered_org_null_pct': (round(org_null * 100.0 / total_events, 1)
                                 if total_events else 0.0),
    }
