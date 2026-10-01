"""The OCR-text helpers the label parsers share, moved out of `doc_parse.py` (review F3).

Moved VERBATIM: `_lines`, `find_value`, `has`, `_NRIC_RE`, `first_nric` and `_first_rm_figure`.
A LEAF: it imports nothing from this app, so `doc_parse` and `doc_parse_epf` can both import it
in either order (before the move `doc_parse_epf` imported them from `doc_parse`, which imports
`doc_parse_epf` back, so importing `doc_parse_epf` first raised a circular ImportError).
`doc_parse` re-exports every name, so `doc_parse.find_value` & co. resolve as before.
"""
from __future__ import annotations

import re


# ── text + label helpers ──────────────────────────────────────────────────────


def _lines(text: str) -> list:
    """OCR text → trimmed lines (newline-normalised)."""
    norm = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    return [ln.strip() for ln in norm.split('\n')]


def find_value(text: str, label: str) -> str:
    """The value printed after ``label`` (a regex, case-insensitive). Tries the remainder
    of the label's own line (after an optional ``: = -`` separator); if that's blank, the
    next non-empty line. ``''`` when the label isn't present.

    Label-anchored, not position-anchored, so it survives a label sitting on its own line
    (mobile screenshots) or inline with its value (desktop/PDF)."""
    pat = re.compile(label, re.IGNORECASE)
    lines = _lines(text)
    for i, ln in enumerate(lines):
        m = pat.search(ln)
        if not m:
            continue
        rest = ln[m.end():].lstrip(' \t:=-').strip()
        if rest:
            return rest
        for nxt in lines[i + 1:]:
            if nxt:
                return nxt
        return ''
    return ''


def has(text: str, *patterns: str) -> bool:
    """True iff any regex pattern is present (case-insensitive). Used for surface markers."""
    blob = text or ''
    return any(re.search(p, blob, re.IGNORECASE) for p in patterns)


_NRIC_RE = re.compile(r'\b(\d{6})[-\s]?(\d{2})[-\s]?(\d{4})\b')


def first_nric(text: str) -> str:
    """The first Malaysian NRIC in the text, normalised to ``######-##-####``. '' if none."""
    m = _NRIC_RE.search(text or '')
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''


def _first_rm_figure(v: str) -> str:
    """First currency figure in ``v`` → ``RM<n>`` (commas stripped). '' if none.

    ⚠ Named for what it does since code health H7. It used to be called `_money`, which it shared
    with seven other functions in this app that PARSED or FORMATTED money; this one does neither.
    It reads OCR text and returns a display string, it refuses nothing, and it has no opinion
    about zero, negatives or decimal places — see `money.py` for the functions that do.

    ⚠ TWO THINGS IT USED TO GET WRONG, fixed on the owner's order 2026-09-19 (TD-261):

    * **The minus sign was dropped**, so a CREDIT ('-40.00' — the household is ahead on the
      account) was stored as a charge of RM40.00. The sign is kept now, and kept AFTER the ``RM``
      (``RM-40.00``): that is the shape both readers of the stored string already handle —
      ``income_engine._arrears_amount`` spots a credit by matching ``-\\s*\\d``, which
      ``-RM40.00`` would NOT satisfy, and the cockpit's ``_arrearsAmount`` reads either. Only the
      LEADING minus is a sign; no fixture or corpus here shows a Malaysian bill printing a credit
      as ``40.00-``, ``40.00 CR`` or ``(40.00)``, and an unseen shape cannot be tested.
    * **One decimal place was dropped** ('1234.5' → 'RM1234'): the pattern admitted two decimals
      or none, and ``[\\d,]+`` then matched the integer part alone. One OR two now, reported as
      the document prints it ('RM1234.5') rather than padded — this extracts, it does not format.
    """
    m = re.search(r'(-?[\d,]+(?:\.\d{1,2})?)', v or '')
    return f'RM{m.group(1).replace(",", "")}' if m else ''
