"""TNB full bill, PHOTO layout (OCR-first S6, 2026-11-19): rules first, AI fallback.

The full TNB bill ("Bil Elektrik Anda") read from a PHOTO comes out of OCR column by column: the
labels "Tunggakan", "Caj Semasa", "Penggenapan", "Jumlah Bil" each on their own line, with "RM"
and the figure on the following lines, and no "ALAMAT POS" label. `doc_parse._parse_electricity`
format A reads only the PDF text layer (ALAMAT POS + "Caj Semasa (RM) <figure>"), so every photo
went to Gemini. This reader takes the photo layout, but ONLY when the page proves itself:

  * a TNB bill (TNB marker, the full-bill labels) and never Sabah / Sarawak (SESB / SEB stay AI);
  * the summary box reconciles TO THE SEN: Tunggakan + Caj Semasa + Penggenapan = Jumlah Bil,
    each figure inside its OWN label's zone (exactly one figure per zone);
  * the itemised "Caj Semasa" further down prints the SAME figure (so a swapped arrears / charge
    pair cannot pass);
  * the holder is a parentage-connector name line right after the invoice number, the address
    block below it ends on its postcode line or a peninsular state, with no stray number in it;
  * the Tarikh Bil is a clean "dd <month> 20yy" date that falls 0-31 days after the Tempoh Bil
    ends (review round 1: no period, no lock — `income_engine.utilities` dates a bill by it), and
    the Tempoh Bil itself starts before it ends and spans 20-62 days (review round 2);
  * the current charge is not negative, and no bill label sits inside the address block.
Anything else → None, and the bill goes to Gemini exactly as before.

A LANE SWITCH (``OCR_FIRST_TNB_PHOTO_ENABLED``, off by default): Gate 1 of the OCR-first roadmap
needs 20 held-out bills locked with zero wrong fields against a hand-checked truth set, and the
cached corpus has no truth set for bills. Until the owner turns it on, `doc_parse` never calls
this reader. A leaf: it imports only `doc_parse_text` at module level.
"""
from __future__ import annotations

import datetime
import os
import re
from typing import Optional

from .doc_parse_text import _lines, has

#: The settings switch for this lane (env ``OCR_FIRST_TNB_PHOTO_ENABLED=1``).
PHOTO_SWITCH = 'OCR_FIRST_TNB_PHOTO_ENABLED'

_TNB_RE = (r'tenaga\s*nasional', r'\bTNB\b', r'careline', r'my\s*tnb', r'bil\s+elektrik')
_NOT_TNB_RE = (r'\bsabah\b', r'\bsarawak\b', r'\bSESB\b', r'\bSESCO\b', r'\bSEB\b')
_GRAMMAR = (r'tarikh\s+bil', r'tunggakan', r'caj\s+semasa', r'penggenapan', r'jumlah\s+bil')
_MONEY_RE = re.compile(r'^(?:RM\s*)?(-?[\d,]*\d\.\d{2})$', re.IGNORECASE)
_NAME_BEFORE_RE = re.compile(r'^(?::\s*)?(?:\d{9,}|RM\s*[\d,]+\.\d{2}|:)$', re.IGNORECASE)
_POSTCODE_RE = re.compile(r'^\d{5}\s+[A-Z]')
_STATES = ('JOHOR', 'KEDAH', 'KELANTAN', 'MELAKA', 'NEGERI SEMBILAN', 'PAHANG', 'PERAK', 'PERLIS',
           'PULAU PINANG', 'SELANGOR', 'TERENGGANU', 'WP KUALA LUMPUR', 'W.P. KUALA LUMPUR',
           'KUALA LUMPUR', 'WILAYAH PERSEKUTUAN', 'PUTRAJAYA', 'WP PUTRAJAYA')
_MONTHS = (r'jan(?:uari)?|feb(?:ruari)?|mac|apr(?:il)?|mei|jun|jul(?:ai)?|ogos|sep(?:tember)?'
           r'|okt(?:ober)?|nov(?:ember)?|dis(?:ember)?')
_BILL_DATE_RE = re.compile(r'^(0?[1-9]|[12]\d|3[01])\s+(' + _MONTHS + r')\s+(20[2-3]\d)$', re.IGNORECASE)
_PERIOD_RE = re.compile(r'(\d{2}\.\d{2}\.20\d{2})\s*-?\s*(\d{2}\.\d{2}\.20\d{2})')
#: Month number by the first three letters of the Malay name (``_MONTHS``).
_MONTH_NO = {m: k for k, m in enumerate(('jan', 'feb', 'mac', 'apr', 'mei', 'jun', 'jul', 'ogo',
                                          'sep', 'okt', 'nov', 'dis'), start=1)}
#: A bill label printed on its own line (review round 1): never part of an address.
_LABEL_LINE_RE = re.compile(r'^(?:no\.?\s*(?:akaun|invois|kontrak)|tarikh\b|tempoh\b|jumlah\b|tunggakan'
                            r'|caj\b|penggenapan|bil\s+elektrik|sila\b|tarif\b|amaun\b)', re.IGNORECASE)
#: Bill words that never sit in an address, ANYWHERE on the line (review round 2, L1: "Jenis
#: Premis Kediaman", "Kod Tarif A" were taken as address lines).
_LABEL_WORD_RE = re.compile(r'\b(?:premis|tarif|meter|kod|jenis|kediaman|akaun|invois)\b', re.IGNORECASE)


def _switch_text_on(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in ('1', 'true', 'yes')


def lane_on(name: str = PHOTO_SWITCH) -> bool:
    """Is the OCR-first lane ``name`` switched on? A Django setting of that name when one exists
    (tests override it), else the env var of that name. ON only for a real ``True`` or the text
    '1' / 'true' / 'yes' (review round 1: the text '0' / 'False' is OFF). Not added to
    settings/base.py: that file sits at its code-standards size ceiling. Review round 2 (L4): when
    Django settings are not configured (a hand-run script), the env var still decides."""
    value = None
    try:
        from django.conf import settings
        if settings.configured:
            value = getattr(settings, name, None)
    except Exception:
        value = None
    if value is None:
        value = os.environ.get(name, '')
    return value is True or _switch_text_on(value)


def _label_at(lines: list, pattern: str, start: int = 0) -> int:
    """Index of the first line at/after ``start`` that IS the label (the whole line), else -1."""
    rx = re.compile(r'^' + pattern + r'\.?$', re.IGNORECASE)
    return next((k for k in range(start, len(lines)) if rx.match(lines[k])), -1)


def _zone_figure(lines: list, lo: int, hi: int) -> Optional[str]:
    """The ONE money figure in ``lines[lo:hi]`` (commas stripped), or None for zero or several."""
    figs = [m.group(1).replace(',', '') for m in (_MONEY_RE.match(ln) for ln in lines[lo:hi]) if m]
    return figs[0] if len(figs) == 1 else None


def _summary(lines: list) -> Optional[tuple]:
    """``(arrears, charge, end_index)`` from the summary box when it reconciles, else None."""
    t = _label_at(lines, r'tunggakan')
    c = _label_at(lines, r'caj\s+semasa', t + 1) if t >= 0 else -1
    p = _label_at(lines, r'penggenapan', c + 1) if c >= 0 else -1
    j = _label_at(lines, r'jumlah\s+bil', p + 1) if p >= 0 else -1
    if j < 0:
        return None
    nxt = next((k for k in range(j + 1, min(j + 5, len(lines))) if not _MONEY_RE.match(lines[k])
                and lines[k].upper() != 'RM'), min(j + 5, len(lines)))
    parts = [_zone_figure(lines, t + 1, c), _zone_figure(lines, c + 1, p),
             _zone_figure(lines, p + 1, j), _zone_figure(lines, j + 1, nxt)]
    if None in parts:
        return None
    arrears, charge, rounding, total = (float(x) for x in parts)
    if abs(rounding) > 0.05 or abs(arrears + charge + rounding - total) > 0.005:
        return None
    return parts[0], parts[1], nxt


def _itemised_charge_agrees(lines: list, start: int, charge: str) -> bool:
    """The itemised "Caj Semasa" below the summary prints the same figure."""
    k = _label_at(lines, r'caj\s+semasa', start)
    return k >= 0 and _zone_figure(lines, k + 1, min(k + 3, len(lines))) == charge


def _holder(lines: list) -> Optional[tuple]:
    """``(name, address)`` from the block between the invoice number and Jumlah Perlu Dibayar."""
    from .doc_parse import _NAME_LINE           # lazy: doc_parse imports this module
    inv = next((k for k, ln in enumerate(lines) if re.match(r'^no\.?\s*invois\b', ln, re.I)), -1)
    end = next((k for k, ln in enumerate(lines) if re.match(r'^jumlah\s+perlu\s+dibayar', ln, re.I)), -1)
    if inv < 0 or end <= inv:
        return None
    block = [ln for ln in lines[inv + 1:end] if ln]
    names = [k for k, ln in enumerate(block) if 6 <= len(ln) <= 60 and _NAME_LINE.match(ln)]
    if len(names) != 1 or names[0] == 0 or not _NAME_BEFORE_RE.match(block[names[0] - 1]):
        return None
    address = block[names[0] + 1:]
    if not 2 <= len(address) <= 6 or any(re.search(r'\d{8,}|^:', ln) or _LABEL_LINE_RE.match(ln)
                                         or _LABEL_WORD_RE.search(ln) for ln in address):
        return None
    post = [k for k, ln in enumerate(address) if _POSTCODE_RE.match(ln)]
    if len(post) != 1 or post[0] < len(address) - 2:
        return None
    if post[0] == len(address) - 2 and not address[-1].upper().startswith(_STATES):
        return None
    return block[names[0]], ', '.join(ln.rstrip(',') for ln in address)


def _bill_date(lines: list, period: str) -> str:
    """The Tarikh Bil, only when it is a real date 0-31 days after the billing period ENDS
    (review round 1: a misread year or month would flip a bill current / stale). '' otherwise,
    and '' when there is no period to check it against."""
    k = _label_at(lines, r'tarikh\s+bil')
    nxt = next((ln for ln in lines[k + 1:k + 3] if ln), '') if k >= 0 else ''
    m = _BILL_DATE_RE.match(nxt)
    if not m or not period:
        return ''
    try:
        issued = datetime.date(int(m.group(3)), _MONTH_NO[m.group(2)[:3].lower()], int(m.group(1)))
        ends = datetime.datetime.strptime(period.split()[1], '%d.%m.%Y').date()
    except (ValueError, KeyError, IndexError):
        return ''
    return nxt if 0 <= (issued - ends).days <= 31 else ''


#: A TNB billing period runs about a month (review round 2: 20-62 days, start before end).
_PERIOD_DAYS = (20, 62)


def _billing_period(lines: list) -> str:
    """The Tempoh Bil as ``'<start> <end>'``, only when both are real dates, the start comes first
    and the span is `_PERIOD_DAYS` (review round 2, M3: `freshness._income_doc_recency` picks among
    duplicate bills by the START month, so a misread start must not lock). '' otherwise."""
    k = next((i for i, ln in enumerate(lines) if re.search(r'tempoh\s+bil', ln, re.I)), -1)
    for ln in lines[k:k + 5] if k >= 0 else []:
        m = _PERIOD_RE.search(ln)
        if m:
            try:
                start, end = (datetime.datetime.strptime(g, '%d.%m.%Y').date() for g in m.groups())
            except ValueError:
                return ''
            span = (end - start).days
            return f'{m.group(1)} {m.group(2)}' if _PERIOD_DAYS[0] <= span <= _PERIOD_DAYS[1] else ''
    return ''


def parse_tnb_photo(text: str) -> Optional[dict]:
    """The photo-layout TNB full bill (the module docstring's rules), or None → Gemini."""
    if not has(text, *_TNB_RE) or has(text, *_NOT_TNB_RE) or not all(has(text, p) for p in _GRAMMAR):
        return None
    lines = [ln for ln in _lines(text) if ln]
    summary = _summary(lines)
    if summary is None or summary[1].startswith('-'):    # review round 1: never a negative charge
        return None
    if not _itemised_charge_agrees(lines, summary[2], summary[1]):
        return None
    period = _billing_period(lines)
    holder, bill_date = _holder(lines), _bill_date(lines, period)
    if holder is None or not bill_date:
        return None
    return {'name': holder[0], 'address': holder[1], 'amount': f'RM{summary[1]}',
            'unpaid_balance': f'RM{summary[0]}', 'billing_period': period, 'bill_date': bill_date}
