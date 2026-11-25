"""TD-718 repair 3 (2026-11-25): the MySTR status read must not mistake "Status Pedalaman" for a rejection.

Every Semakan Status page carries a "Status Pedalaman" field whose value is "Ya" or "Tidak". When OCR
puts that "Tidak" and the status "Lulus" on ONE line, "Tidak Lulus" reads as a rejection of an approved
page (red). In production about two thirds of the stored STR copies are approved and none carries any
rejected wording, so a false red on an approved page is the bigger risk. Three rules, all used by
``doc_parse._parse_str``:

  * ``one_line_per_break`` (B1) — every line break Python knows (``\\r``, ``\\u2028``, ``\\u2029``,
    ``\\v``, ``\\f``, ``\\x85`` …) becomes ``\\n``, so the reader's lines (``doc_parse_text._lines``
    splits only ``\\n`` and ``\\r``) and its one-line tokens (a real space, TAB or NBSP only) agree, and
    a "Tidak" and a "Lulus" on two lines can never be stored as one "Tidak Lulus" value.
  * ``status_value`` (B2) — the label-anchored status value; when the status label shares its line with
    a "Status Pedalaman" label just before it (a grid: both labels on one row, both values on the next),
    the value's first word is Pedalaman's "Ya" / "Tidak" and is dropped. "Tidak Lulus" → "Lulus";
    "Tidak Tidak Lulus" → "Tidak Lulus".
  * ``ambiguous_tidak_lulus`` (B3) — a body-scan "Tidak Lulus" / "Tidak Diluluskan" on a page that has a
    "Status Pedalaman" label cannot be told from Pedalaman's "Tidak" beside a "Lulus". The caller then
    stores no status: the ladder reads ``unreadable`` (amber, passes the gate, an officer looks). Never
    red, never green on an ambiguous read. Without that label the phrase still reads rejected.

A label-anchored "Tidak Lulus" whose label line holds only the status label stays a rejection (B4),
except (B5, repair round 5): when the nearest non-empty line above the status label line is a BARE
"Status Pedalaman" label (no value of its own; an info icon allowed), the two labels are stacked and the
two values may have merged on one line, so a value of exactly "Tidak Lulus" / "Tidak Diluluskan" is
ambiguous and ``status_value`` returns '' (the B3 handling: no status, amber). The value may sit on the
line after the status label or on the status label's own line: with no Pedalaman value above, the
"Tidak" may be Pedalaman's in both. "Ya Lulus", "Tidak Tidak Lulus" and "Ya Tidak Lulus" are not exactly
the phrase and read as before. Pure; never raises.
"""
from __future__ import annotations

import re

from .doc_parse_text import _lines, find_value

_ICON = r'(?:\(\s*i\s*\)|ⓘ|\bi\b)'
#: The "Status Pedalaman" label at the END of the text before the status label on its line.
_PEDALAMAN_BEFORE = re.compile(r'status\s+pedalaman[\s:]*(?:' + _ICON + r'[\s:]*)?$', re.IGNORECASE)
#: Pedalaman's own value at the start of a grid value line: "Ya" / "Tidak", optionally "(Sabah)".
_PEDALAMAN_WORD = re.compile(r'^(?:ya|tidak)\b(?:[ \t\xa0]*\([^)]*\))?[ \t\xa0]*', re.IGNORECASE)
_TIDAK_LULUS = re.compile(r'tidak[ \t\xa0]+(?:lulus|diluluskan)', re.IGNORECASE)
_HAS_PEDALAMAN = re.compile(r'status\s+pedalaman', re.IGNORECASE)
#: A line holding ONLY the "Status Pedalaman" label (B5): no value; an info icon / colon allowed.
_BARE_PEDALAMAN = re.compile(r'status[ \t\xa0]+pedalaman[ \t\xa0:]*(?:' + _ICON + r'[ \t\xa0:]*)?',
                             re.IGNORECASE)


def one_line_per_break(text: str) -> str:
    """``text`` with every kind of line break as ``\\n`` (B1)."""
    return '\n'.join((text or '').splitlines())


def status_value(text: str, label: str) -> str:
    """``find_value(text, label)``, less a leading Pedalaman "Ya" / "Tidak" when the label's line holds
    the "Status Pedalaman" label just before it (B2); '' for an exact "Tidak (Di)Lulus(kan)" under a
    bare "Status Pedalaman" label line (B5). The line is the one ``find_value`` reads."""
    value = find_value(text, label)
    try:
        pat = re.compile(label, re.IGNORECASE)
        lines = _lines(text)
        for i, ln in enumerate(lines):
            m = pat.search(ln)
            if m:
                if _PEDALAMAN_BEFORE.search(ln[:m.start()]):
                    return _PEDALAMAN_WORD.sub('', value, count=1)
                above = next((p for p in reversed(lines[:i]) if p), '')
                if _TIDAK_LULUS.fullmatch(value.strip()) and _BARE_PEDALAMAN.fullmatch(above):
                    return ''                                                   # B5: ambiguous
                return value
    except Exception:
        return value
    return value


def ambiguous_tidak_lulus(token: str, text: str) -> bool:
    """True when the body-scan ``token`` is "Tidak Lulus" / "Tidak Diluluskan" and the page carries a
    "Status Pedalaman" label: the "Tidak" may be Pedalaman's (B3)."""
    return bool(_TIDAK_LULUS.fullmatch(token or '')) and bool(_HAS_PEDALAMAN.search(text or ''))
