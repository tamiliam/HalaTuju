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
_STRICT_START_RE = re.compile(r'caruman\s+semasa', re.IGNORECASE)
#: A line that OPENS with a month label (an inline row, read or not).
_MONTH_START_RE = re.compile(r'^(?:jan|feb|mac|apr|mei|jun|jul|ogos|ogo|ogs|sep|okt|nov|dis)-\d{2}\b',
                             re.IGNORECASE)
#: The inline layout's grand total: a bare figure, or "JUMLAH (RM) <figure>".
_TOTAL_LINE_RE = re.compile(r'^(?:jumlah\b.*?)?([\d,]+\.\d{2})$', re.IGNORECASE)


def _caruman_rows(text: str) -> list:
    """The CARUMAN SEMASA rows (`_strict_rows`); when those are ``[]`` and the S6 lane switch is
    on, the reconciled token read (`_relaxed_rows`). ``[]`` when neither reads the table whole."""
    return _strict_rows(text) or (_relaxed_rows(text) if _relaxed_on() else [])


def _section(lines: list, start_re) -> Optional[tuple]:
    """``(body lines, closed)`` of the CARUMAN SEMASA section: the lines after its header, up to
    its end marker (PENGELUARAN / PELARASAN) when one follows (``closed``), else to the end of the
    text. None when no header is found."""
    start = next((k for k, ln in enumerate(lines) if start_re.search(ln)), -1)
    if start < 0:
        return None
    end = next((k for k in range(start + 1, len(lines)) if _SECTION_END_RE.match(lines[k])), -1)
    return (lines[start + 1:end] if end >= 0 else lines[start + 1:]), end >= 0


def _whole(rows: list, loose: list, closed: bool) -> bool:
    """Review round 2 (M1/M2): the rows are the WHOLE table only when at most one figure is left
    over and it is the grand total (equal to the rows' sum to the sen), or, with no grand total,
    the section's end marker was read. Neither: nothing proves the page was not cut mid-table."""
    if not rows or len(loose) > 1:
        return False
    if loose:
        return abs(loose[0] - sum(t for _e, _m, t in rows)) <= 0.005
    return closed


def _strict_rows(text: str) -> list:
    """The CARUMAN SEMASA rows as ``(employer, member, total)`` floats, read inside the section
    only. The inline layout (one row per line) when present, else the one-cell-per-line layout.
    ``[]`` when the table cannot be read WHOLE.

    ⚠ ALL OR NOTHING, both layouts (review round 2): every row carries its three figures and the
    two shares make the total to the sen; the month labels number exactly the rows; and `_whole`
    (a reconciling grand total, or the section's end marker). Anything else is a table we did not
    read, and `[]` keeps it 'unknown' (the AI read decides)."""
    sec = _section(_lines(text), _STRICT_START_RE)
    if sec is None:
        return []
    cells = [ln for ln in sec[0] if ln]
    if any(_CARUMAN_RE.match(ln) for ln in cells):
        return _inline_rows(cells, sec[1])
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
    if months != len(rows) or any(abs(er + ee - t) > 0.005 for er, ee, t in rows):
        return []
    return rows if _whole(rows, loose, sec[1]) else []


def _inline_rows(body: list, closed: bool) -> list:
    """The inline layout: one row per line (``Jan-26 Caruman 16/01/2026 221.00 187.00 408.00``).
    Review round 2 (M1): EVERY line that opens with a month label must end in its three figures
    with the shares making the total — a label whose figures OCR moved to a later line, or a
    total-only row, refuses the table (its last figure could be a share, not the total)."""
    rows, loose = [], []
    for ln in body:
        if _MONTH_START_RE.match(ln):
            s = _SPLIT_RE.search(ln)
            if not s:
                return []
            er, ee, t = (float(g.replace(',', '')) for g in s.groups())
            if abs(er + ee - t) > 0.005:
                return []
            rows.append((er, ee, t))
        else:
            m = _TOTAL_LINE_RE.match(ln)
            if m:
                loose.append(float(m.group(1).replace(',', '')))
    return rows if _whole(rows, loose, closed) else []


def _shares_doubtful(rows: list) -> bool:
    """A contributing row whose employer share is SMALLER than its member share. Review round 2
    (H1): NOT proof of swapped columns (a member may elect a higher rate, or contribute with no
    employer), so the row stays for status / months / total; only the employer/member split is
    dropped, so no salary is backed out of a doubtful split."""
    return any(t > 0 and er is not None and ee is not None and er < ee for er, ee, t in rows)


# ── OCR-first S6 (2026-11-19): the RELAXED cell read, behind its lane switch ──────────────────
#: The reader's version, stored as ``parser_version`` beside a rules read.
EPF_PARSER_VERSION = '1.1.0'
#: The settings switch (env ``OCR_FIRST_EPF_RELAXED_ENABLED=1``); off until Gate 1 passes.
RELAXED_SWITCH = 'OCR_FIRST_EPF_RELAXED_ENABLED'
_SECTION_START_RE = re.compile(r'caruman\s*semasa', re.IGNORECASE)
_MONTH_TOKEN_RE = re.compile(r'^(?:jan|feb|mac|apr|mei|jun|jul|ogos|ogo|ogs|sep|okt|nov|dis)-\d{2}$',
                             re.IGNORECASE)
#: The section header's footnote line "… bagi tahun 2026 sahaja." — its year is not a figure.
_YEAR_LINE_RE = re.compile(r'\btahun\s+20\d{2}\b', re.IGNORECASE)


def _relaxed_on() -> bool:
    from .doc_parse_tnb import lane_on            # the shared switch reader (a leaf)
    return lane_on(RELAXED_SWITCH)


def _relaxed_rows(text: str) -> list:
    """The CARUMAN SEMASA cells read as TOKENS, so a row whose figures OCR split over lines or
    joined onto one line (the date and its figures together, two month labels on one line) still
    reads. ``[]`` (refuse) unless EVERY part reconciles:

      * each date is followed by exactly three figures before the next date, and Majikan + Ahli =
        Jumlah to the sen (the strict read never checks this inside a row);
      * the month labels number exactly the rows, and the dates run oldest to newest (so the last
        row IS the latest month);
      * at most one figure is left over, and it equals the rows' sum to the sen (the grand total).
    Review round 1 also refuses a table with no positive total (0 + 0 = 0 proves nothing; 'zero'
    still comes from the strict read or a "Tiada Transaksi" inside the section). Review round 2:
    any unreadable token holding a digit ANYWHERE in the section refuses (L2: "4O8.00" before the
    first date was skipped), except on the header's "tahun 20yy" line; `_whole` must hold (M2: a
    reconciling grand total or the section's end marker); and an employer share smaller than the
    member share no longer refuses the row (H1) — `_caruman_split` drops only the split.
    """
    sec = _section(_lines(text), _SECTION_START_RE)
    if sec is None:
        return []
    tokens = [tok for ln in sec[0] for tok in _YEAR_LINE_RE.sub(' ', ln).split()]
    rows, dates, loose, months, pending = [], [], [], 0, None
    for tok in tokens:
        if _MONTH_TOKEN_RE.match(tok):
            months += 1
        elif _DATE_CELL_RE.match(tok):
            if pending is not None:
                return []                             # a date with fewer than three figures
            pending, figs = tok, []
        elif _MONEY_CELL_RE.match(tok):
            if pending is None:
                loose.append(_money_cell(tok))
                continue
            figs.append(_money_cell(tok))
            if len(figs) == 3:
                if abs(figs[0] + figs[1] - figs[2]) > 0.005:
                    return []                         # the shares do not make the total
                rows.append(tuple(figs))
                dates.append(pending)
                pending = None
        elif re.search(r'\d', tok):
            return []                                 # an unreadable figure: never skip it
    if pending is not None or months != len(rows) or not _whole(rows, loose, sec[1]):
        return []
    if not any(t > 0 for _e, _m, t in rows):
        return []
    order = [(d[6:], d[3:5], d[:2]) for d in dates]
    return rows if order == sorted(order) else []


def epf_lane(text: str) -> str:
    """The rules lane of an EPF read: ``kwsp_penyata_relaxed`` when only the relaxed cell read
    gives the table, else ``kwsp_penyata``."""
    return 'kwsp_penyata_relaxed' if (_relaxed_on() and not _strict_rows(text)
                                      and _relaxed_rows(text)) else 'kwsp_penyata'


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
    rows = _caruman_rows(text)                             # both layouts (review F2)
    if _shares_doubtful(rows):
        return None                                        # review round 2 (H1): split only
    for employer, member, total in rows:
        if total <= 0:
            continue
        if employer is None or member is None:
            return None
        if abs(employer + member - total) > 0.005:
            return None
        er, ee, seen = er + employer, ee + member, seen + 1
    return (f'RM{er:.2f}', f'RM{ee:.2f}') if seen else None


def _tiada_in_section(text: str) -> bool:
    """A GENUINE "no contributions": "Tiada Transaksi" printed INSIDE the CARUMAN SEMASA section —
    after its header, before its end marker (PENGELUARAN / PELARASAN), with no date or figure in
    the section. Review round 2 (H1): real statements print "Tiada Transaksi" under an empty
    PENGELUARAN / PELARASAN too, so one found anywhere else, or a section with no end marker
    read, proves nothing about contributions → 'unknown' (the AI read decides)."""
    sec = _section(_lines(text), _SECTION_START_RE)
    if sec is None or not sec[1]:
        return False
    body = '\n'.join(sec[0])
    return (bool(re.search(r'tiada\s+transaksi', body, re.IGNORECASE))
            and not re.search(r'\d{2}/\d{2}/\d{4}|\d\.\d{2}\b', body))


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
    elif amts or _tiada_in_section(text):    # rows read whole but all zero, or explicit none
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
