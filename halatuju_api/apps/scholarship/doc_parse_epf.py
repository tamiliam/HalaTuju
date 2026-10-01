"""The KWSP EPF "Penyata Ahli" parser, moved out of `doc_parse.py` (TD-317).

Moved VERBATIM (the P3 section: `_CARUMAN_RE`, `_caruman_amounts`, `_last_caruman`,
`_epf_address` and `_parse_epf`) so the split contribution totals could be built without
growing `doc_parse.py` past its size allowance. `doc_parse` imports every name back at the line
the section used to occupy and REGISTERS `_parse_epf` there (`register('epf')(_parse_epf)`), so
`doc_parse._parse_epf` & co. resolve and dispatch exactly as before.

This module imports only the leaf `doc_parse_text`, never `doc_parse`, so either import order
works (review F3). `test_doc_parse.py::TestEpfParser` pins both: the registered parser is this
one, and importing this module first in a fresh interpreter succeeds.
"""
from __future__ import annotations

import re
from typing import Optional

from .doc_parse_text import _first_rm_figure, _lines, find_value, first_nric, has


# ── P3: KWSP EPF statement ────────────────────────────────────────────────────
# The KWSP "Penyata Ahli" — fixed labels: name after SULIT DAN PERSENDIRIAN, PENYATA AHLI
# TAHUN <year>, No. Kad Pengenalan, No. Majikan, JUMLAH SIMPANAN: RM<x>, and the CARUMAN
# SEMASA monthly rows (latest month's total = monthly_contribution). A mis-slotted Borang
# EC / payslip carries NONE of these → None → Gemini (free mis-slot detection).

_CARUMAN_RE = re.compile(
    r'^(?:jan|feb|mac|apr|mei|jun|jul|ogos|ogo|sep|okt|nov|dis)-\d{2}\b.*?([\d,]+\.\d{2})\s*$',
    re.IGNORECASE)


def _caruman_amounts(text: str) -> list:
    """Every monthly CONTRIBUTION amount (float) from the CARUMAN SEMASA rows, in order.

    Review F2: read through `_caruman_rows`, so the one-cell-per-line layout real OCR prints is
    read too. Before it, every real statement in the snapshot corpus read 'unknown' here."""
    return [total for _employer, _member, total in _caruman_rows(text)]


def _money_cell(s: str) -> Optional[float]:
    return float(s.replace(',', '')) if _MONEY_CELL_RE.match(s) else None


#: The one-cell-per-line layout (review F2): every cell of the CARUMAN SEMASA table on its own
#: line — the month labels first (`Jan-26` / `Caruman IWS` …), then per row a date and three
#: figures (Majikan, Ahli, Jumlah), then the table's grand total. All 13 real snapshots print it so.
_MONTH_CELL_RE = re.compile(r'^(?:jan|feb|mac|apr|mei|jun|jul|ogos|ogo|ogs|sep|okt|nov|dis)-\d{2}$',
                            re.IGNORECASE)
_DATE_CELL_RE = re.compile(r'^\d{2}/\d{2}/\d{4}$')
_MONEY_CELL_RE = re.compile(r'^[\d,]+\.\d{2}$')
_SECTION_END_RE = re.compile(r'^(?:PENGELUARAN|PELARASAN)', re.IGNORECASE)


def _caruman_rows(text: str) -> list:
    """The CARUMAN SEMASA rows as ``(employer, member, total)`` floats — employer/member None
    where the row prints only its total. The inline layout (one row per line) when present, else
    the one-cell-per-line layout. ``[]`` when the table cannot be read WHOLE.

    ⚠ ALL OR NOTHING for the cell layout: every date must be followed by three figures, the month
    labels must number exactly the rows, and a grand total (if printed) must equal the rows' sum
    to the sen. Anything else is a table we did not read, and `[]` keeps it 'unknown' as before."""
    lines = _lines(text)
    inline = []
    for ln in lines:
        m = _CARUMAN_RE.match(ln)
        if m:
            s = _SPLIT_RE.search(ln)
            er, ee = ((float(g.replace(',', '')) for g in s.groups()[:2]) if s else (None, None))
            inline.append((er, ee, float(m.group(1).replace(',', ''))))
    if inline:
        return inline
    start = next((k for k, ln in enumerate(lines) if re.search(r'caruman\s+semasa', ln, re.I)), -1)
    if start < 0:
        return []
    end = next((k for k in range(start + 1, len(lines)) if _SECTION_END_RE.match(lines[k])),
               len(lines))
    cells = [ln for ln in lines[start + 1:end] if ln]
    rows, loose, months, k = [], [], 0, 0
    while k < len(cells):
        if _MONTH_CELL_RE.match(cells[k]):
            months += 1
        elif _DATE_CELL_RE.match(cells[k]):
            figs = [_money_cell(c) for c in cells[k + 1:k + 4]]
            if len(figs) < 3 or None in figs:
                return []
            rows.append(tuple(figs))
            k += 4
            continue
        elif _money_cell(cells[k]) is not None:
            loose.append(_money_cell(cells[k]))
        k += 1
    if not rows or months != len(rows) or len(loose) > 1:
        return []
    if loose and abs(loose[0] - sum(t for _e, _m, t in rows)) > 0.005:
        return []
    return rows


def _last_caruman(text: str) -> str:
    """The LAST (most recent) monthly contribution row → ``RM<n>``. '' if none parsed."""
    amts = _caruman_amounts(text)
    return f'RM{amts[-1]:.2f}' if amts else ''


def _epf_address(text: str) -> str:
    """Best-effort member address: the line carrying a 5-digit postcode + the line above it
    (the Penyata Ahli prints the correspondence address as a short block). '' if none. Soft —
    the address matcher + officer eyeball decide; never a gate."""
    lines = [ln for ln in _lines(text) if ln]
    for i, ln in enumerate(lines):
        if re.search(r'\b\d{5}\b', ln):
            prev = lines[i - 1] if i > 0 else ''
            return ' '.join(p for p in (prev, ln) if p).strip()
    return ''


#: A CARUMAN SEMASA row ENDS with three figures: Caruman Majikan, Caruman Ahli, Jumlah (TD-317).
_SPLIT_RE = re.compile(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')


def _caruman_split(text: str) -> Optional[tuple]:
    """``('RM<Σ Caruman Majikan>', 'RM<Σ Caruman Ahli>')`` over the CONTRIBUTING rows (total > 0)
    — the two totals `income_engine.salary_figures._epf_monthly_salary` reverses the statutory
    rates from — or None.

    ⚠ ALL OR NOTHING. Every contributing row must carry both shares AND they must add up to its
    total, to the sen. `_epf_monthly_salary` divides each sum by `months_counted`, which counts
    every contributing row, so a sum over fewer rows would UNDER-state the salary; a row whose
    shares do not add up is a mis-read column. Either way: None, and the statement keeps the
    legacy ÷0.24 estimate it had before TD-317."""
    er = ee = 0.0
    seen = 0
    for employer, member, total in _caruman_rows(text):   # both layouts (review F2)
        if total <= 0:
            continue
        if employer is None or member is None:
            return None
        if abs(employer + member - total) > 0.005:
            return None
        er, ee, seen = er + employer, ee + member, seen + 1
    return (f'RM{er:.2f}', f'RM{ee:.2f}') if seen else None


def _parse_epf(text: str) -> Optional[dict]:
    if not has(text, r'penyata\s+ahli') or not has(text, r'ahli\s+kwsp', r'jumlah\s+simpanan', r'\bKWSP\b'):
        return None                          # not a KWSP Penyata Ahli (e.g. a Borang EC) → Gemini
    lines = _lines(text)
    si = next((k for k, ln in enumerate(lines)
               if re.search(r'sulit\s+dan\s+persendirian', ln, re.IGNORECASE)), -1)
    name = next((ln for ln in lines[si + 1:] if ln), '') if si >= 0 else ''
    nric = first_nric(find_value(text, r'no\.?\s*kad\s+pengenalan')) or first_nric(text)
    # The KWSP employer number is a digit code — extract the digit-run so a label/value
    # adjacency broken by image OCR yields '' rather than junk ("RINGKASAN", ":").
    em = re.search(r'\d{6,}', find_value(text, r'no\.?\s*majikan'))
    employer = em.group(0) if em else ''
    balance = _first_rm_figure(find_value(text, r'jumlah\s+simpanan'))
    ym = re.search(r'penyata\s+ahli\s+tahun\s+(20\d{2})', text, re.IGNORECASE)
    year = ym.group(1) if ym else ''
    statement_date = find_value(text, r'tarikh\s+penyata') or year
    if not (name or nric or balance):
        return None
    # The CONTRIBUTION signal: average the months shown (steadier than one row), and
    # distinguish a GENUINE zero ("Tiada Transaksi" / no current contributions — a real
    # 'no formal salary' signal) from an UNREADABLE table (couldn't parse → 'unknown').
    amts = _caruman_amounts(text)
    positives = [a for a in amts if a > 0]
    if positives:
        contribution_status, avg = 'has', round(sum(positives) / len(positives), 2)
        avg_contribution, months = f'RM{avg:.2f}', str(len(positives))
    elif has(text, r'tiada\s+transaksi') or amts:    # rows present but all zero, or explicit none
        contribution_status, avg_contribution, months = 'zero', 'RM0.00', str(len(amts))
    else:
        contribution_status, avg_contribution, months = 'unknown', '', ''
    out = {'name': name, 'nric': nric, 'employer': employer, 'latest_balance': balance,
           'last_contribution': '', 'monthly_contribution': _last_caruman(text),
           'avg_monthly_contribution': avg_contribution, 'months_counted': months,
           'contribution_status': contribution_status, 'statement_date': statement_date,
           'address': _epf_address(text), 'year': year}
    # TD-317: the split totals the Gemini read carries, so the exact `max()` salary formula
    # applies here too. Absent (not blank) when the rows do not split cleanly — see the helper.
    split = _caruman_split(text) if positives else None
    if split:
        out['employer_contribution_total'], out['employee_contribution_total'] = split
    return out
