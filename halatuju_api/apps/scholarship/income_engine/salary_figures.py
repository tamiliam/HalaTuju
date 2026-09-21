"""Reading a figure off a payslip or an EPF statement: the monthly amount, arrears, the
employer-less EPF case and the salary an EPF contribution implies.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import re



# ── Per-capita income from the documents (Check-1 I4, salary route) ──────────
_AMOUNT_RE = re.compile(r'(\d[\d,]*\.?\d*)')
# EPF total monthly contribution ≈ 11% (employee) + 13% (employer) = 24% of salary, so a
# salary estimate when there's no payslip: monthly_salary ≈ contribution / 0.24.
_EPF_CONTRIB_RATE = 0.24

# #9 payslip-vs-EPF tolerance. The payslip gross and the EPF-implied salary rarely match
# to the ringgit — overtime, late employer payments, and variable operator-grade pay all
# move them apart — so the flag stays QUIET unless they diverge a lot. Flag only when the
# ratio (slip ÷ epf_implied) falls outside this band (the bounds are reciprocals, so it is
# symmetric: more than ~1.67× apart in either direction).
_SLIP_EPF_LO = 0.6
_SLIP_EPF_HI = 1.67

# A backstop on a garbled salary read: net (take-home) can never exceed gross (net =
# gross − deductions). A small tolerance absorbs rounding/OCR noise; beyond it the read
# is inconsistent and must not be trusted for the income figure.
_NET_OVER_GROSS_TOL = 1.02


def _salary_monthly_amount(f):
    """A salary slip's representative MONTHLY pay — gross preferred, else net — but ONLY when the
    read is internally consistent. A garbled OCR of a hand-written voucher can mis-read the ruled
    ringgit|sen columns or grab the wrong cells; the tell is **net > gross**, impossible on a real
    payslip. When that happens the amount is unreliable → return None, so income falls to 'verify at
    interview' rather than asserting a false (often 100x-inflated) figure. (#66.)

    Prefers the ANNUALISED figure when the slip carries a YEAR-TO-DATE gross (``gross_income_ytd``):
    a single payslip month under-states a job with variable overtime (#13: basic RM3,800/mo but YTD
    ÷ 12 ≈ RM7,064/mo). YTD ÷ 12 is the representative monthly (the YTD period is ambiguous — a
    flagged interview item — so the headroom band routes a near-line annualised figure to 'unsure').
    Never lets a mis-read YTD DEFLATE the figure below the single month — which also means a YTD
    with NO readable monthly figure is unusable (the deflate guard can't run)."""
    gross = _parse_rm(f.get('gross_income'))
    net = _parse_rm(f.get('net_income'))
    if gross and net and net > gross * _NET_OVER_GROSS_TOL:
        return None
    month = gross or net
    ytd = _parse_rm(f.get('gross_income_ytd'))
    # YTD is trustworthy only ALONGSIDE a readable monthly figure (the >= deflate guard).
    # Alone, its period is unknowable: an early-year slip's YTD ÷ 12 understates income up
    # to 12× (January: RM3,800 actual → RM317 "monthly" → a false B40 green). Unreadable
    # monthly cells → None → 'verify at interview', same as the garbled-read rule above.
    if ytd and month is not None:
        annualised = round(ytd / 12.0, 2)
        if annualised >= month:
            return annualised
    return month


def _parse_rm(s):
    """Parse an RM figure ('RM 9,900.04' / '2400.00' / 'RM2,400') → float, or None."""
    if not s:
        return None
    m = _AMOUNT_RE.search(str(s).replace(' ', ''))
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def _arrears_amount(raw):
    """Parse a utility bill's arrears (unpaid balance), treating a CREDIT as zero owed.
    A negative balance ('-1.29', 'RM -1.29') or a 'CR'/'kredit' marker means the household
    is AHEAD on the account, not behind — so it must not read as arrears (``_parse_rm``
    strips the minus sign and would otherwise record a credit as a positive amount owed).
    Returns the arrears (float), 0.0 for a credit, or None when nothing parseable."""
    s = str(raw or '').strip()
    if not s:
        return None
    if re.search(r'-\s*\d', s) or re.search(r'\b(cr|kredit|credit)\b', s, re.IGNORECASE):
        return 0.0
    return _parse_rm(s)


def _doc_fields(doc):
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields', {})
    return f if isinstance(f, dict) else {}


def epf_no_employer(f):
    """"No. Majikan 000000000" — no employer on the statement date. The statement proving, on its
    own face, that the member was not employed (owner, #126).

    Reads BOTH keys. The schema carries `employer_number` (the No. Majikan) and `employer` (the
    company name), and the reader routinely files the all-zeros NUMBER under `employer` — so the
    two call sites that keyed on `employer_number` alone silently DROPPED the very proof they had
    extracted. Either field carrying the zeros is the same fact.

    One definition, used by both consumers (implied salary → 0, and the unemployment
    corroboration) — they had the same check, hand-written twice, and the same bug twice.
    """
    return any(re.sub(r'\D', '', str(f.get(k) or '')) == '000000000'
               for k in ('employer_number', 'employer'))


def _epf_monthly_salary(f):
    """Estimate MONTHLY salary from an EPF statement (TD-123 contract). Returns a float
    (0.0 = unemployed), or None when nothing usable.

    - **Unemployed** iff ``No. Majikan == 000000000`` (the only employment check) → 0.0.
    - Otherwise reverse the statutory rates (hardcode employee **11%**, employer **13%**) from
      the contribution TOTALS over the statement + the month count ``n``:
      ``monthly_salary = max(Σ Caruman Majikan /(n·0.13),  Σ Caruman Ahli /(n·0.11))``.
      ``max()`` self-corrects across salary tiers without detecting them: above RM5,000 the
      employer share drops to 12% so the employer-via-13% term under-states, while the
      employee-via-11% term stays exact — ``max()`` selects it.
    - **Legacy fallback** (records extracted before the split totals existed): the old combined
      ``avg_monthly_contribution`` / ``monthly_contribution`` ÷ 0.24."""
    if epf_no_employer(f):
        return 0.0
    try:
        n = int(re.sub(r'\D', '', str(f.get('months_counted') or '')) or 0) or 1
    except ValueError:
        n = 1
    cands = []
    er = _parse_rm(f.get('employer_contribution_total'))
    ee = _parse_rm(f.get('employee_contribution_total'))
    if er:
        cands.append(er / (n * 0.13))
    if ee:
        cands.append(ee / (n * 0.11))
    if cands:
        return round(max(cands), 2)
    contrib = _parse_rm(f.get('avg_monthly_contribution')) or _parse_rm(f.get('monthly_contribution'))
    return round(contrib / _EPF_CONTRIB_RATE, 2) if contrib else None
