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
)

# Explicitly NOT attributable, listed so the reasoning survives review rather than living in
# the negative space of the tuple above. These are real costs; they are simply OURS.
PLATFORM_SKU_MARKERS = (
    'jobs cpu',                  # scheduled crons — fires on a clock, not on tenant activity
    'jobs memory',
    'artifact registry',         # CI images — a function of OUR deploy pace
    'cloud scheduler',           # the cron schedule itself
    'cloud build',               # CI
)


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
    total = attributable = platform = tax = Decimal('0.00')
    by_source = {}
    entered_sources = set()
    # Rows whose ringgit cost is not yet known — a held invoice awaiting its FX rate. They are
    # COUNTED and reported, never dropped: a total that quietly omits a RM100 line is worse
    # than one that says "incomplete", because only the second prompts anyone to go and look.
    unconverted = []

    for r in rows:
        if r.provenance == 'entered':
            entered_sources.add(r.source)
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
        if is_tax(r.service, r.sku):
            tax += r.amount_myr
        elif r.attributable:
            attributable += r.amount_myr
        else:
            platform += r.amount_myr

    return {
        'month': period_month,
        'lines': rows.count(),
        'total_myr': total,
        'attributable_myr': attributable,
        'platform_myr': platform,
        'tax_myr': tax,
        'by_source': by_source,
        # Which sources in this month rest on a human reading a PDF. Surfaced, never hidden:
        # a total that mixes measured and entered figures without saying so is not an audit.
        'entered_sources': sorted(entered_sources),
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
    """
    from .models import OrgBuildHours

    rows = OrgBuildHours.objects.filter(
        organisation=organisation, period_month=period_month)
    hours = sum((r.hours for r in rows), Decimal('0.0'))
    if not rows:
        return {'month': period_month, 'hours': Decimal('0.0'), 'lines': [],
                'rate_myr': None, 'margin_pct': None,
                'subtotal_myr': Decimal('0.00'), 'charge_myr': Decimal('0.00')}

    from .models import BillingRate
    on = _month_start(period_month)
    # Deliberately NOT wrapped in try/except — a missing rate propagates to the caller.
    rate = rate_in_force(BillingRate.CATEGORY_DEVELOPMENT, BillingRate.KIND_HOURLY_RATE, on)
    margin = rate_in_force(BillingRate.CATEGORY_DEVELOPMENT, BillingRate.KIND_MARGIN_PCT, on)

    subtotal = (hours * rate).quantize(Decimal('0.01'))
    charge = (subtotal * (Decimal('1') + margin / Decimal('100'))).quantize(Decimal('0.01'))
    return {
        'month': period_month,
        'hours': hours,
        'lines': [{'module': r.module, 'hours': r.hours, 'basis': r.basis} for r in rows],
        'rate_myr': rate,
        'margin_pct': margin,
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


# ── The bill (2026-09-11) ─────────────────────────────────────────────────────

def request_module_tag(request_id) -> str:
    """The marker that ties an `OrgBuildHours` line back to the request it came from.

    A convention, not a foreign key, because `OrgBuildHours` deliberately predates this and
    holds hours that never came from a request at all. The tag is what makes a request
    countable as billed without narrowing the model to requests only.
    """
    return f'[REQ-{request_id}]'


def unbilled_request_hours(organisation=None):
    """Finished request work that carries quoted hours and has NEVER been billed.

    The gap the owner found: *"You also need to include the work we do fulfilling requests,
    which are billed."* Requests carry `quote_hours`; `OrgBuildHours` carries what is billed;
    on production the first held 27.5 hours and the second held nothing at all. Nothing joined
    them, so finished work simply never reached an invoice.

    ⚠ **This does NOT bill anything, and that is deliberate.** A request has no completion date
    — only `updated_at`, which any later edit moves — so there is no honest way to decide which
    MONTH a finished request belongs to. Inventing one would put work in the wrong month and
    then discount or charge it by that wrong month's terms. So this REPORTS the outstanding
    work and the owner records it against a month through `OrgBuildHours`, where `basis` makes
    the choice explicit and reviewable.

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
        out.append({
            'request_id': r.id,
            'organisation_id': r.organisation_id,
            'organisation': r.organisation.name,
            'title': r.title,
            'hours': r.quote_hours,
            # Prefilled for the screen's "record these hours" action, so the tag that makes the
            # request countable as billed is written by the code, not typed by a human.
            'module': f'{tag} {r.title}'[:200],
        })
    return out


def adjustment_for(organisation, period_month):
    """The discount agreed for this organisation and this month, or None."""
    from .models import OrgBillingAdjustment

    return (OrgBillingAdjustment.objects
            .filter(organisation=organisation, period_month=period_month)
            .first())


def charge_for(organisation, period_month):
    """What this organisation is charged for a month — and what could NOT be worked out.

    Returns every line with its own status, never a single number. Three categories exist and
    only one of them can honestly be billed today:

      * **development** — hours x rate x margin. Real. Computed here.
      * **metered** — refused: there is no unit-price table (Sprint 13a, "NO prices in v1"), so
        a per-event charge would have to invent prices, and an invented price on an invoice is
        an invoice you withdraw.
      * **infrastructure** — refused: the platform cost is a PLATFORM total. Splitting it across
        tenants needs an allocation rule nobody has agreed. June measured 72% of the GCP bill as
        our own crons and deploys, so "share it out per tenant" is not a neutral default; it is
        a pricing decision, and it is the owner's to make.

    Each refusal is REPORTED in `blocked`, never rendered as RM0.00. A line the reader can see
    is missing gets fixed; a zero gets believed.

    The discount is applied LAST and shown as its own line, so the month reads
    subtotal -> discount -> charged. That is the owner's July requirement: shown in full,
    charged nothing.
    """
    blocked = []
    lines = []
    subtotal = Decimal('0.00')

    try:
        dev = development_charge(organisation, period_month)
    except RateMissing as exc:
        dev = None
        blocked.append({'category': 'development', 'reason': str(exc)})
    if dev is not None and dev['hours']:
        lines.append({
            'category': 'development',
            'hours': dev['hours'],
            'rate_myr': dev['rate_myr'],
            'margin_pct': dev['margin_pct'],
            'amount_myr': dev['charge_myr'],
            'detail': dev['lines'],
        })
        subtotal += dev['charge_myr']

    blocked.append({
        'category': 'metered',
        'reason': 'No unit prices are set, so metered usage cannot be priced. The meter counts '
                  'events; it does not yet know what an event costs.'})
    blocked.append({
        'category': 'infrastructure',
        'reason': 'Platform cost is recorded for the whole platform. No rule has been agreed '
                  'for sharing it between tenants, so it is not charged to any of them.'})

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
