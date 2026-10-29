"""The METER side of billing — who was busy, and whether the ledger agrees (2026-10-29).

Split out of `platform_cost.py` (moves only, when that file passed the 600-line standard), with
one new guard that belongs here rather than there.

The two halves of a metered charge live in different tables and are written by different hands:

    UsageEvent   — one row per billable provider call, written UNCONDITIONALLY from the app
    PlatformCost — one row per supplier invoice line, written by a SYNC somebody has to run

That asymmetry is the whole reason `metered_activity_without_cost` exists. The meter cannot
fail quietly; the ledger can, and did.
"""
from decimal import Decimal


def _year_month(period_month):
    """``'2026-10'`` -> ``(2026, 10)``, and None for anything unreadable.

    ⚠ **IT USED TO RETURN `(0, 0)` AND THAT CRASHED.** Both functions below carried
    `year = mon = 0` on a bad month, on the reasoning that year zero matches no row. It does not
    match no row — it reaches Django's `__year` lookup, which builds `datetime(0, 1, 1)` to bound
    the query and raises `ValueError: year 0 is out of range`. Found on 2026-10-29 by a test
    asserting the old claim. None is returned instead, and every caller answers "nothing" for a
    month it cannot read, which is what the comment always said would happen.
    """
    try:
        year, mon = (int(x) for x in str(period_month).split('-'))
    except (ValueError, AttributeError):
        return None
    return year, mon


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

    when = _year_month(period_month)
    counts = {} if when is None else {
        r['organisation_id']: r['n']
        for r in (UsageEvent.objects
                  .filter(created_at__year=when[0], created_at__month=when[1],
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


def metered_rows(period_month):
    """The month's ledger rows that fall in the METERED bucket, as ``(rows, myr, awaiting_fx)``.

    `myr` sums only the rows whose ringgit value is known. `awaiting_fx` counts the rest, and is
    the reason this returns three things instead of one: a metered total of zero because the FX
    rate has not arrived yet is a DIFFERENT fault from one because nothing was ever synced, and
    `invoicing.readiness` already has a problem code for the first (`fx_missing`). Reporting both
    for the same month would make one fault read as two.
    """
    from . import platform_cost
    from .models import PlatformCost

    rows, myr, awaiting_fx = 0, Decimal('0.00'), 0
    for r in PlatformCost.objects.filter(period_month=period_month):
        if platform_cost.cost_bucket(r.service, r.sku, r.attributable) != 'metered':
            continue
        rows += 1
        if r.amount_myr is None:
            awaiting_fx += 1
        else:
            myr += r.amount_myr
    return rows, myr, awaiting_fx


def metered_activity_without_cost(organisation, period_month):
    """The meter recorded this tenant's calls, but the month's metered cost reads zero.

    Returns None when there is nothing wrong, or a dict of the figures to print.

    ⚠ **THIS IS THE OCTOBER 2026 FAULT, WRITTEN DOWN AS A GUARD.** October's metered cost read
    RM0.00 on a month in which BrightPath ran OCR and Gemini all month. The cause was mundane and
    invisible: `sync_gcp_costs` had never been run for October, so the ledger simply had no
    metered rows. Nothing in `readiness` objected, because every check it had asked "is the
    ledger internally consistent?" and the ledger was perfectly consistent — and empty.

    ⚠ **The diagnosis I reached first was WRONG and must not be rebuilt.** I concluded that
    prepaid Gemini credit was hiding the cost from the BigQuery export. It was not: the owner's
    own GCP console and AI Studio both read RM34.95 for October, and the export covers prepay and
    postpay alike. The fault was a sync that had not run. Do not add prepay logic here.

    Every `UsageEvent` row is "one row per billable provider call" (see the model docstring), so
    events mean money was spent somewhere — at Google, at Brevo or at Twilio. Events without
    money is therefore a ledger that is not finished, not a free month.

    It stays OVERRIDABLE, though, for the one case where events really do cost nothing: a month
    that fell inside a provider's free tier. A super may then issue it with a written reason. The
    monthly job overrides nothing, which is the protection that actually matters — an unattended
    run is how an under-billed month would otherwise reach a customer.
    """
    from .models import UsageEvent

    when = _year_month(period_month)
    if when is None:
        return None
    events = (UsageEvent.objects
              .filter(created_at__year=when[0], created_at__month=when[1],
                      organisation=organisation)
              .count())
    if not events:
        return None

    rows, myr, awaiting_fx = metered_rows(period_month)
    if awaiting_fx:
        # `fx_missing` owns this month. Saying it twice, in two vocabularies, would send somebody
        # looking for a second fault that does not exist.
        return None
    if myr > 0:
        return None
    return {'events': events, 'metered_rows': rows, 'metered_myr': myr}


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

    from . import platform_cost
    from .models import UsageEvent

    totals = platform_cost.month_totals(period_month)
    when = _year_month(period_month)
    rows = UsageEvent.objects.none() if when is None else UsageEvent.objects.filter(
        created_at__year=when[0], created_at__month=when[1])

    events = rows.values('service').annotate(n=Count('id')).order_by('-n')
    counts = {e['service']: e['n'] for e in events}
    total_events = sum(counts.values())
    org_null = rows.filter(organisation__isnull=True).count()

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
