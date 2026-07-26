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
