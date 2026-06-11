"""Deterministic label-anchored field capture for standardised-issuer documents.

Malaysian fixed-format documents — MySTR/STR, TNB electricity, KWSP EPF, JPN birth
certificate, government offer letters — print their fields at FIXED LABELS. This module
reads those fields off the OCR text / PDF text-layer DETERMINISTICALLY, returning the SAME
field keys as ``vision._FIELD_SCHEMAS[doc_type]``, OR ``None`` when the text doesn't match
the expected layout — so ``vision.run_field_extraction_for_document`` falls back to Gemini.

Deterministic-first, Gemini-fallback: the auditable + free path for the standardised tail;
Gemini stays the fallback for the unstandardised one (university offers, odd utilities,
mis-slotted uploads). This mirrors the results-slip pattern (``_extract_slip_deterministic``).

Contract for every parser:
  * pure ``(text: str) -> dict | None``; NEVER raises (the dispatcher also guards).
  * be CONSERVATIVE — return ``None`` unless the text clearly IS this document and the key
    fields are present, so an unrecognised layout degrades to exactly today's Gemini read.
  * MUST be validated against REAL documents before its path is trusted in prod, not just
    the synthetic fixtures in tests (lessons.md S15 / L86 — that miss cost 3 deploys once).
"""
from __future__ import annotations

import re
from typing import Callable, Optional

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


# Tolerate an intervening ``)``/space — Malaysian bills print the amount as a column under
# an ``(RM)`` header (TNB: "Jumlah Bil Anda (RM) 76.65") as well as inline ("RM700").
_RM_RE = re.compile(r'RM\s*\)?\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE)


def first_amount(text: str) -> str:
    """The first ``RM…`` amount in the text (digits + optional decimals), normalised to
    ``RM<n>``. '' if none."""
    m = _RM_RE.search(text or '')
    return f'RM{m.group(1).replace(",", "")}' if m else ''


# ── registry + dispatcher ─────────────────────────────────────────────────────

_PARSERS: dict = {}


def register(doc_type: str) -> Callable:
    """Register a deterministic parser for ``doc_type``. Parsers are added one per phase
    (STR → TNB elec → KWSP EPF → JPN BC → govt offer → water)."""
    def deco(fn):
        _PARSERS[doc_type] = fn
        return fn
    return deco


def parse_by_labels(doc_type: str, text: str) -> Optional[dict]:
    """Deterministic field capture for ``doc_type`` from ``text``; ``None`` → the caller
    uses Gemini. Never raises — any parser trouble degrades to the Gemini fallback."""
    fn = _PARSERS.get(doc_type)
    if fn is None or not (text or '').strip():
        return None
    try:
        result = fn(text)
    except Exception:
        return None
    # A parser must return the full field dict or None — never a partial/garbage value.
    return result if isinstance(result, dict) and result else None
