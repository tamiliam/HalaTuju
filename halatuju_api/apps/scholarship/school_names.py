"""STPM school-name casing, moved out of `offer_pathway.py` (TD-145, 2026-10-04).

Moved VERBATIM (`_SCHOOL_POSTCODE`, `_SCHOOL_ACRONYM_EXPAND`, `clean_school_name`) to make room
for TD-145's institution check without growing `offer_pathway.py` past its size allowance.
`offer_pathway` imports the names back where the section was, so `op.clean_school_name` resolves
exactly as before. A leaf: imports nothing from this app.
"""
import re


_SCHOOL_POSTCODE = re.compile(r'\b\d{5}\b')
_SCHOOL_ACRONYM_EXPAND = {
    'SMK': 'Sekolah Menengah Kebangsaan',
    'SMJK': 'Sekolah Menengah Jenis Kebangsaan',
    'SMKA': 'Sekolah Menengah Kebangsaan Agama',
    'KTE': 'Kolej Tingkatan Enam',
    'SM': 'Sekolah Menengah',
}


def clean_school_name(*candidates: str) -> str:
    """Casing-only standardisation of a recorded STPM school name — NO catalogue lookup, so the
    school IDENTITY never changes (avoids the SMK↔SMJK / "Tun Hussein Onn" vs "Bandar Tun Hussein
    Onn 2" mis-match that catalogue-matching a 250-school bidang would cause). Of the given
    recorded values it picks the address-free (no postcode) and fullest one, expands a leading
    acronym (SMK/SMJK/SMKA/KTE/SM) to its full form for a consistent style, and Title-cases it."""
    cands = [c.strip() for c in candidates if c and c.strip()]
    if not cands:
        return ''
    addr_free = [c for c in cands if not _SCHOOL_POSTCODE.search(c)] or cands
    best = max(addr_free, key=len)
    toks = best.split()
    if toks and toks[0].upper() in _SCHOOL_ACRONYM_EXPAND:
        best = _SCHOOL_ACRONYM_EXPAND[toks[0].upper()] + ' ' + ' '.join(toks[1:])
    return best.title()
