"""The offer letter's IC number, guarded (offer exact-read S4 review, 2026-11-02, H2 + M1 + M4).

Why it needs a guard: the offer IC drives the Name·IC check (`pathway_engine._ic_status`). A WRONG
number reads `mismatch` — a wrong-person red that blocks submission (`doc_red_keys.person_red`). A
BLANK is not harmless either: it reads `unreadable`, which the cockpit chip shows red
(`verdict_ladder._OFFER_CHIP_RED`) and the ladder counts — but it never blocks as a wrong person. So
the order of preference is: the right number > a blank > a wrong number.

The rules (`guard_nric`), given what the reader returned, where it says it read it, the student's own
profile IC (when the read runs for an application) and the page-1 text (a PDF's text layer, else the
Vision OCR of page 1):

  1. **Only the offer pages count** (owner, 2026-11-01). The identity fields are read from PAGE 1
     alone (`offer_reader`), so a filled reply / acceptance form later in the file is never read.
  2. **A labelled IC** ("No. Kad Pengenalan" / "No. K/P" …, source ``label``) is kept when it equals
     the profile IC or is ONE digit off it (`vision.nric_close` — the same tolerance `_ic_status`
     applies, so an OCR slip still reads `match`), or when it is a well-formed IC (`plausible_ic`):
     12 digits, a real YYMMDD date, a real place-of-birth code and a birth year 14-70 years ago. A
     well-formed IC of someone else is kept on purpose: that IS a wrong-person letter.
  3. **An IC from the reference line** (UPM "[IC]/UP…", source ``reference_line``), from anywhere
     else (``other``), or with NO stated source (S4 re-review M1: a missing or unknown source is
     ``other``, never ``label``) is CORROBORATE-ONLY: kept only when it EXACTLY equals the profile IC
     (owner rule; re-review L2 — not one digit off), so it can produce `match` and never `mismatch`;
     otherwise blanked.
  4. **Cross-check (M4).** When the page-1 text carries IC-shaped runs and the read number is none of
     them (nor one digit off one), it is blanked: the model read a number the page does not print.
  5. **Backstop (H2).** A blank IC is filled ONLY from a well-formed 12-digit run on PAGE 1's TEXT
     LAYER that equals the profile IC (source ``text_layer``) — never from a photo's OCR, never a guess,
     and ONLY when the model returned no usable number (no IC, or a malformed one). An IC the model DID
     read and the guard blanked — another person's, uncorroborated, or one the page does not print — is
     never replaced by the profile's (S4 re-review M2: that would turn a wrong-person read into `match`).

Each outcome is recorded in ``nric_check`` (never the number).
"""
from __future__ import annotations

import datetime
import re

#: Malaysian MyKad place-of-birth codes (digits 7-8): the states 01-16 and 21-59, and the foreign
#: codes 60-68, 71-72, 74-79, 82-93, 98-99 (the National Registration Department's table).
_PLACE_CODES = frozenset([*range(1, 17), *range(21, 60), *range(60, 69), 71, 72, *range(74, 80),
                          *range(82, 94), 98, 99])
_IC_RUN = re.compile(r'(?<!\d)(\d{6})[\s-]?(\d{2})[\s-]?(\d{4})(?!\d)')
#: Text this short holds too little to cross-check against.
_MIN_CROSS_TEXT = 200
SOURCES = ('label', 'reference_line', 'other', 'none')


def digits(value) -> str:
    return re.sub(r'\D', '', str(value or ''))


def plausible_ic(value, today=None) -> bool:
    """12 digits, a real YYMMDD birth date, a real place code, and a birth year 14-70 years ago."""
    d = digits(value)
    if len(d) != 12:
        return False
    yy, mm, dd, place = int(d[:2]), int(d[2:4]), int(d[4:6]), int(d[6:8])
    today = today or datetime.date.today()
    year = 2000 + yy if 2000 + yy <= today.year else 1900 + yy
    try:
        datetime.date(year, mm, dd)
    except ValueError:
        return False
    return place in _PLACE_CODES and 14 <= today.year - year <= 70


def _close(a, b) -> bool:
    from .vision import nric_close, nric_match
    return bool(a) and bool(b) and (nric_match(a, b) or nric_close(a, b))


def _exact(a, b) -> bool:
    return bool(digits(a)) and digits(a) == digits(b)


def ic_runs(text) -> list:
    """Every IC-shaped 12-digit run in ``text`` (dashes / spaces between the groups allowed)."""
    return [''.join(m.groups()) for m in _IC_RUN.finditer(text or '')]


def guard_nric(fields: dict, *, profile_nric: str = '', page1_text: str = '',
               page1_is_text_layer: bool = False, today=None) -> str:
    """Apply the rules above to ``fields`` IN PLACE (``candidate_nric``, ``candidate_nric_source``)
    and return the outcome recorded in ``nric_check``."""
    value = str(fields.get('candidate_nric') or '').strip()
    source = str(fields.get('candidate_nric_source') or '').strip().lower() or ('other' if value else 'none')
    source = source if source in SOURCES and (source != 'none' or not value) else 'other'
    outcome = 'blank'
    if value:
        mine = _close(value, profile_nric)
        if source != 'label':      # corroborate-only: the profile IC EXACTLY (owner rule, re-review L2)
            outcome = 'kept_corroborated' if _exact(value, profile_nric) else 'blanked_uncorroborated'
        elif mine:
            outcome = 'kept_profile'
        elif plausible_ic(value, today):
            outcome = 'kept_well_formed'
        else:
            outcome = 'blanked_malformed'
        runs = ic_runs(page1_text) if len(page1_text or '') >= _MIN_CROSS_TEXT else []
        if outcome.startswith('kept') and runs and not any(_close(value, r) for r in runs):
            outcome = 'blanked_not_on_page'
    if outcome.startswith('blanked') or outcome == 'blank':
        fields['candidate_nric'], fields['candidate_nric_source'] = '', 'none'
        want = digits(profile_nric)
        refill = outcome in ('blank', 'blanked_malformed')          # never over a read the guard refused
        if refill and page1_is_text_layer and want and plausible_ic(want, today) and want in ic_runs(page1_text):
            fields['candidate_nric'], fields['candidate_nric_source'] = want, 'text_layer'
            outcome += '+backstop'
    else:
        fields['candidate_nric_source'] = source
    return outcome
