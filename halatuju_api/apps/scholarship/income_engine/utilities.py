"""Utility bills: the billing month, the age of a bill, the holder reconciliation, the
per-capita reading and the hardship signal.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import datetime
import re

from ..document_snapshot import latest_doc, live_docs
from ..vision import canonical_name_tokens, relationship_name_match as name_match
from .identity_checks import _roster_candidates
from .salary_figures import _arrears_amount, _doc_fields, _parse_rm


# ── Utility bills as a SOFT B40 proxy + hardship signal (imperfect; officer context) ─
# Utility spend is a WEAK, noisy wealth proxy (especially once STR already verifies B40),
# so the bands are deliberately generous: a normal household reads 'reasonable', and only
# a genuinely high per-capita is worth an officer's eye. No amber 'borderline' band — it
# only produced spurious "explain your utility spend" concerns on ordinary families.
_UTILITY_B40_CEILING = 40   # < RM40/capita/month combined → comfortably consistent with B40
_UTILITY_HIGH_FLOOR = 60    # > RM60/capita/month → only then worth an officer's eye (M40/T20)


# Reading a utility bill: a month-name → number map (Malay + English, common OCR forms)
# and a tolerant period parser, so "Mei 2026" / "05/2026" / "2026-05" all resolve.
_UTILITY_MONTHS = {
    'jan': 1, 'feb': 2, 'mac': 3, 'mar': 3, 'apr': 4, 'apl': 4, 'mei': 5, 'may': 5,
    'jun': 6, 'jul': 7, 'ogo': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10,
    'nov': 11, 'dis': 12, 'dec': 12,
}
_UTILITY_CURRENT_MONTHS = 3   # a bill within ~3 months of the review date counts as 'current' — the
                              # ASK standard + the officer's 'Current' chip.
_UTILITY_ACCEPT_MONTHS = 6    # owner 2026-07-09/-10: we ASK for a bill within 3 months, but a DATED
                              # bill within ~6 months is ACCEPTED without re-looping (the officer
                              # eyeballs the date). A student who can only produce a slightly older
                              # bill is never trapped re-uploading; older than 6 still re-asks. This
                              # is ALSO the officer chip's amber→red line (owner 2026-07-10): the
                              # recency chip is a THREE-tier traffic light — ≤3mo green 'current',
                              # 3–6mo amber 'ageing', >6mo red 'stale' (``_utility_currency``).


def _parse_billing_month(period):
    """``(year, month)`` from a free-form billing period ('Mei 2026', '05/2026',
    '2026-05', 'April 2026'), or None when nothing parseable is found."""
    if not period:
        return None
    t = str(period).lower()
    ym = re.search(r'(20\d{2})', t)
    year = int(ym.group(1)) if ym else None
    month = None
    for name, num in _UTILITY_MONTHS.items():
        if name in t:
            month = num
            break
    if month is None:                                  # numeric month
        m = re.search(r'\b(\d{1,2})[/\-.](20\d{2})\b', t)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r'\b(20\d{2})[/\-.](\d{1,2})\b', t)
            if m:
                year, month = int(m.group(1)), int(m.group(2))
    if not year or not month or not (1 <= month <= 12):
        return None
    return year, month


def _bill_as_of(fields):
    """The point-in-time a utility bill speaks to, as ``(year, month)``, preferring the TARIKH BIL
    (``bill_date`` — a single unambiguous issue date, owner 2026-07-09) over the TEMPOH BIL
    ``billing_period`` range (whose start/end is ambiguous and often degrades to month-only or blank
    on a photo). ``None`` when neither yields a readable date (the 'undated' case)."""
    if not isinstance(fields, dict):
        return None
    for key in ('bill_date', 'billing_period'):
        ym = _parse_billing_month(fields.get(key))
        if ym:
            return ym
    return None


def _bill_age_months(fields, today):
    """How many months old the bill is (from ``_bill_as_of``), or ``None`` when undated. A
    future-dated bill (data entry) clamps to 0."""
    ym = _bill_as_of(fields)
    if not ym:
        return None
    return max(0, (today.year - ym[0]) * 12 + (today.month - ym[1]))


_MONTH_ABBR = ('', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def _bill_month_label(fields):
    """The bill's point-in-time as a STANDARDISED 'MMM YYYY' (e.g. 'May 2026'), from the same
    ``_bill_as_of`` the currency chip uses — so however the raw Tarikh Bil / Tempoh Bil is printed
    (a dd.mm.yyyy range, a full/Malay month name, an ISO date), the officer sees ONE consistent
    format. '' when undated (the caller falls back to the raw string)."""
    ym = _bill_as_of(fields)
    return f'{_MONTH_ABBR[ym[1]]} {ym[0]}' if ym else ''


def _utility_currency(fields, today):
    """Is the bill recent? A THREE-tier traffic light (owner 2026-07-10):
    'current' (≤3 months of *today* — green) | 'ageing' (3–6 months — amber, accepted but ageing) |
    'stale' (older than the ~6-month accept window — red) | 'unknown' (no readable date — grey).
    Dated from TARIKH BIL when present, else the TEMPOH BIL period (``_bill_as_of``), against the
    review date — the question is whether this is a LIVE household paying bills now. The 3-month line
    is still the ASK standard; the 6-month line is still the RE-ASK threshold (``_bill_needs_upload``,
    which re-asks only on 'stale'). NOTE: takes the whole ``fields`` dict (not just the period string)
    so it can prefer the bill date."""
    age = _bill_age_months(fields, today)
    if age is None:
        return 'unknown'
    if age <= _UTILITY_CURRENT_MONTHS:
        return 'current'
    if age <= _UTILITY_ACCEPT_MONTHS:
        return 'ageing'
    return 'stale'


def utility_reasonable(application):
    """Combined household utility consumption as a soft B40 proxy, shown identically on
    every bill row. Water alone is a weak signal (cheap, flat across households) — so a
    verdict is only given when BOTH bills are present; one bill → 'partial' (can't judge).
    Returns ``{status, detail, per_capita}``:
      - status: 'reasonable' (≤ RM60/head — the normal case) | 'high' (> RM60/head, an
                officer/interview signal only, NEVER a student query) | 'partial' (only one
                bill) | 'unknown' (no amount / no household size). No amber 'borderline'.
      - detail: 'both' | 'water_only' | 'electricity_only' | '' — which bills informed it."""
    amounts = {}
    for dt in ('water_bill', 'electricity_bill'):
        d = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(d).get('amount')) if d else None
        if amt is not None:
            amounts[dt] = amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not amounts or not size:
        return {'status': 'unknown', 'detail': '', 'per_capita': None}
    if len(amounts) < 2:                               # one bill alone can't judge consumption
        detail = 'water_only' if 'water_bill' in amounts else 'electricity_only'
        return {'status': 'partial', 'detail': detail, 'per_capita': None}
    pc = sum(amounts.values()) / size
    # Two outcomes only — no amber middle. A normal household is 'reasonable'; only a
    # genuinely high per-capita (> RM60/head) flags, and that is an officer/interview
    # signal (possible undeclared income), never something the student is queried about.
    status = 'high' if pc > _UTILITY_HIGH_FLOOR else 'reasonable'
    return {'status': status, 'detail': 'both', 'per_capita': round(pc, 2)}


def _utility_name_unrelated(application, bill_name):
    """True when the account-holder name matches NEITHER the student, NOR a declared parent /
    roster member (father / mother / named guardian / sibling), NOR any uploaded parent/earner
    IC — a soft 'bill is in someone else's name' note. Bills are routinely in a parent's name
    (fine — that matches the roster / IC); the note fires only when it's a genuine stranger.
    Never asserted on a blank read or with no reference name to compare against.

    Owner 2026-07-08: the DECLARED father/mother names (from 'My family') are now checked FIRST,
    so a bill in the father's name no longer triggers a 'whose bill?' query just because no parent
    IC happens to be on file (the SIVAKUMAR A/L KALIAPPAN over-ask)."""
    bill = (bill_name or '').strip()
    if not bill:
        return False
    candidates = []
    student = getattr(getattr(application, 'profile', None), 'name', '') or ''
    if student.strip():
        candidates.append(student)
    for _member, nm in _roster_candidates(application):   # declared father/mother/guardian/siblings
        if nm.strip():
            candidates.append(nm)
    for ic in live_docs(application, 'parent_ic'):
        nm = (getattr(ic, 'vision_name', '') or '').strip()
        if nm:
            candidates.append(nm)
    if not candidates:
        return False
    return all(name_match(bill, c) == 'mismatch' for c in candidates)


def _utility_holder_names(application):
    """Every non-blank account-holder name read off the household's water + electricity
    bills (latest first)."""
    names = []
    for dt in ('water_bill', 'electricity_bill'):
        for doc in live_docs(application, dt):
            nm = (_doc_fields(doc).get('name', '') or '').strip()
            if nm:
                names.append(nm)
    return names


def _same_utility_holder(a, b):
    """Two utility-bill holder names are the SAME person under an OCR cut/wrinkle: they
    share every name token but one EXACTLY, and the odd token is one CONTAINED in the other
    (a dropped letter — 'HANA' ⊂ 'THANA'). Deliberately strict — a pure substitution
    (Siva vs Sira) or a genuinely different name never merges, so reconciliation only ever
    swaps in a cleaner read of the SAME holder, never conflates two people. Token order is
    not significant (the canonical tokens are an unordered set)."""
    sa, sb = set(canonical_name_tokens(a)), set(canonical_name_tokens(b))
    if not sa or not sb or len(sa) != len(sb) or len(sa) < 2:
        return False
    only_a, only_b = sa - sb, sb - sa
    if not only_a:                       # identical token sets
        return True
    if len(only_a) == 1 and len(only_b) == 1:
        x, y = only_a.pop(), only_b.pop()
        return (x in y or y in x) and abs(len(x) - len(y)) <= 2
    return False


def _reconciled_holder_name(application, raw_name):
    """The cleanest read of THIS account holder across the household's utility bills.
    A wrinkled / cut bill can drop a letter — 'HANA BALAN A/L NARAYANAN' for the clean
    'THANA BALAN A/L NARAYANAN' — so when another bill carries the SAME person's name,
    prefer the LONGEST, most complete read. Deterministic + auditable; no AI guess.
    Returns ``raw_name`` unchanged when nothing reconciles."""
    raw = (raw_name or '').strip()
    if not raw:
        return raw
    best = raw
    for nm in _utility_holder_names(application):
        if nm != best and _same_utility_holder(nm, raw) and len(nm) > len(best):
            best = nm
    return best


def utility_check(doc, today=None):
    """For a water / electricity bill: the account-holder name (a data point — bills are in
    a parent's name), the home address (matched via the upload-time ``vision_address_match``),
    the monthly charge + any arrears, plus three soft facts — whether the bill is CURRENT
    (≤3 months old), whether household consumption is REASONABLE (combined per-capita, both
    bills), and whether ARREARS exceed the current charge (a hardship signal). All soft,
    never a gate. Returns the fact dict or None for a non-utility doc."""
    if getattr(doc, 'doc_type', '') not in ('water_bill', 'electricity_bill'):
        return None
    if today is None:
        today = datetime.date.today()
    app = doc.application
    f = _doc_fields(doc)
    # Reconcile OCR variants of the holder across the household's bills — a wrinkled bill
    # that dropped a letter is reported under its clean form, so the row + the flag quote
    # the full name (e.g. 'HANA BALAN' read from a creased bill → 'THANA BALAN').
    name = _reconciled_holder_name(app, (f.get('name', '') or '').strip())
    monthly = _parse_rm(f.get('amount'))
    arrears = _arrears_amount(f.get('unpaid_balance'))
    reasonable = utility_reasonable(app)
    return {
        'name': name,
        'address': (f.get('address', '') or '').strip(),
        'monthly_bill': (f.get('amount', '') or '').strip(),
        'unpaid_balance': (f.get('unpaid_balance', '') or '').strip(),
        'address_status': getattr(doc, 'vision_address_match', '') or '',
        'current_status': _utility_currency(f, today),
        # Standardised 'MMM YYYY' period for the cockpit values line (same date as current_status).
        'bill_month': _bill_month_label(f),
        'reasonable_status': reasonable['status'],
        'reasonable_detail': reasonable['detail'],
        # 'arrears' (shown green) only when arrears exceed the current charge; else hidden.
        'outstanding_status': 'arrears' if (arrears and monthly and arrears > monthly) else '',
        'name_note': 'unrelated' if _utility_name_unrelated(app, name) else '',
    }


def utility_holder_unknown(application):
    """#8: the account-holder name on a water/electricity bill matches NEITHER the student
    nor any uploaded parent IC — a 'whose bill is this?' query. Returns the holder name of
    the first such bill, or None. Bills routinely sit in a parent's name (fine — that
    matches the IC); this fires only when the holder is a stranger to the documents."""
    for dt in ('water_bill', 'electricity_bill'):
        for doc in live_docs(application, dt):
            facts = utility_check(doc)
            if facts and facts.get('name_note') == 'unrelated' and facts.get('name'):
                return facts['name']
    return None


def utility_address_mismatch(application):
    """#8: a water/electricity bill's supply address is a HARD mismatch against the
    student's stated address. Returns True only on ``vision_address_match == 'mismatch'`` —
    a 'partial' (a missing postcode or a shortened/abbreviated street) deliberately stays
    silent, so only a genuinely different address raises the query. Soft, never a gate."""
    for dt in ('water_bill', 'electricity_bill'):
        for doc in live_docs(application, dt):
            if (getattr(doc, 'vision_address_match', '') or '') == 'mismatch':
                return True
    return False


def _latest_doc(application, doc_type):
    # TD-282: one shared read when the officer's detail GET has a snapshot open; otherwise
    # exactly the query this used to build for itself.
    return latest_doc(application, doc_type)


def utility_per_capita(application):
    """Combined water + electricity MONTHLY bill ÷ household size, with a soft B40 proxy.
    Returns ``{per_capita, signal}`` ('b40' | 'neutral' | 'high') or None when no bill
    amount / household size. IMPERFECT — officer context, never a verdict gate."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not any_read or not size:
        return None
    pc = total / size
    signal = 'b40' if pc < _UTILITY_B40_CEILING else ('high' if pc > _UTILITY_HIGH_FLOOR else 'neutral')
    return {'per_capita': round(pc, 2), 'signal': signal}


def utility_monthly_total(application):
    """Combined water + electricity MONTHLY charge (RM), or None when neither bill
    amount could be read. Used for the 'utility spend high vs declared income' flag."""
    total, any_read = 0.0, False
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _parse_rm(_doc_fields(doc).get('amount')) if doc else None
        if amt is not None:
            total += amt
            any_read = True
    return round(total, 2) if any_read else None


def utility_hardship(application):
    """True when the utility bills carry meaningful arrears (unpaid balance) — a soft
    hardship signal that SUPPORTS need. Sums arrears across water + electricity."""
    total = 0.0
    for dt in ('water_bill', 'electricity_bill'):
        doc = _latest_doc(application, dt)
        amt = _arrears_amount(_doc_fields(doc).get('unpaid_balance')) if doc else None
        if amt:
            total += amt
    return total > 100
