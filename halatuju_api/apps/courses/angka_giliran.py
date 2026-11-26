"""The Angka Giliran (exam index number) — its two shapes and the ONE normaliser (pre-U sprint, 2026-11-26).

An SPM index reads ``AB123C456``; an STPM index reads ``AB1234/5678`` (the slip's own shape,
`apps.scholarship.stpm_parse._INDEX_RE`). The web (`src/lib/angkaGiliran.ts`) normalises the same
way — upper case, every space removed — and the model column holds 11 characters for the STPM one.
"""
import re

#: SPM: two letters, three digits, a letter, three digits.
SPM_RE = re.compile(r'^[A-Z]{2}\d{3}[A-Z]\d{3}$')
#: STPM: two letters, four digits, a slash, four digits.
STPM_RE = re.compile(r'^[A-Z]{2}\d{4}/\d{4}$')
MAX_LENGTH = 11


def normalise(value):
    """Upper case, every whitespace character removed. '' for None."""
    return re.sub(r'\s+', '', str(value or '')).upper()


def is_valid(value):
    """True for a blank value (the field is optional) or either shape, after `normalise`."""
    v = normalise(value)
    return v == '' or bool(SPM_RE.match(v) or STPM_RE.match(v))
