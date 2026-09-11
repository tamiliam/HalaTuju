"""Foreign-exchange rates for the cost ledger (2026-09-11).

Two of the four providers invoice in US dollars — Supabase ($25/month) and Twilio — so every
ringgit total depends on a rate, and a rate typed from memory is exactly the "estimate dressed as
a fact" the ledger exists to prevent.

**Owner ruling, 2026-09-11:** *"As to the currency exchange, just use the exchange at the end of
the billing month."* That supersedes the earlier preference for the rate the card was actually
charged at. The card rate is truer to the cent, but it is buried in a bank statement nobody can
reach from a management command, and the owner's overriding requirement is that **nothing here is
manual**. A published closing rate is reproducible, dated, and citable — which is the property
that actually matters for an audit, and the card rate is not reproducible at all.

**Source: the European Central Bank**, via frankfurter.dev, which republishes the ECB reference
rates. Free, no key, no account. ECB publishes on TARGET business days only, so a month ending at
a weekend has no rate of its own; the API returns the most recent publication on or before the
date asked for, and the DATE IT ACTUALLY USED comes back in the response. That returned date is
recorded on the row, never the date we asked for — otherwise a Sunday rate looks like a Sunday
publication that never existed.

⚠ **A failed lookup raises.** It never falls back to a previous month, a cached value or a
guess. An unconverted invoice is already a first-class state in this ledger (`amount_myr` is
nullable, and `month_totals` reports the month as a FLOOR) — that honest gap is strictly better
than a plausible number nobody can source.
"""
from decimal import Decimal, InvalidOperation

ECB_ENDPOINT = 'https://api.frankfurter.dev/v1/{date}'
TIMEOUT_SECONDS = 20
USER_AGENT = 'halatuju-billing/1.0 (+https://halatuju.xyz)'


class RateUnavailable(Exception):
    """No published rate could be fetched for that currency and date.

    Raised, never swallowed — see the module note. The caller leaves `amount_myr` null and the
    month reports itself incomplete, which is a visible problem somebody fixes.
    """


def closing_rate(currency, on_date):
    """Units of MYR per one unit of `currency`, as published on or before `on_date`.

    Returns ``(Decimal rate, date actually_published)``. The second value is the point: it is
    what gets written to the ledger row, so a reader can look the figure up again.

    MYR to MYR is 1 and makes no network call — a provider that already invoices in ringgit must
    not be able to fail on an exchange-rate outage.
    """
    import json
    import urllib.error
    import urllib.request
    from datetime import date as _date

    code = (currency or '').upper().strip()
    if code in ('', 'MYR'):
        return Decimal('1'), (on_date if isinstance(on_date, _date) else None)

    url = ECB_ENDPOINT.format(date=on_date.isoformat())
    url = f'{url}?base={code}&symbols=MYR'
    # ⚠ A User-Agent is REQUIRED. The host answers urllib's default `Python-urllib/3.x` with a
    # flat 403, which arrives here looking exactly like an outage. Naming ourselves is also
    # simply good manners towards a free service we depend on.
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise RateUnavailable(
            f'Could not fetch a {code}->MYR rate for {on_date} from the ECB: {exc}. '
            f'The invoice is recorded with no ringgit amount, and the month will report '
            f'itself incomplete until a rate is available.') from exc

    try:
        rate = Decimal(str(payload['rates']['MYR']))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise RateUnavailable(
            f'The ECB response for {code} on {on_date} carried no MYR rate: {payload!r}') from exc

    # The date the ECB ACTUALLY published on, which for a weekend or holiday is earlier than the
    # date asked for. Recorded as-is so the figure can be looked up again.
    used = payload.get('date') or on_date.isoformat()
    try:
        used_date = _date.fromisoformat(used)
    except (TypeError, ValueError):
        used_date = on_date
    return rate, used_date


def to_myr(amount, currency, on_date):
    """Convert an invoiced amount to ringgit at the closing rate.

    Returns ``(Decimal myr, Decimal rate, date published)``. Quantised to the cent at the very
    end — money rounds once, and only after the multiplication.
    """
    rate, used = closing_rate(currency, on_date)
    myr = (Decimal(str(amount)) * rate).quantize(Decimal('0.01'))
    return myr, rate, used
