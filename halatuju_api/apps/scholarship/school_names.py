"""STPM school-name casing, moved out of `offer_pathway.py` (TD-145, 2026-10-04).

Moved VERBATIM (`_SCHOOL_POSTCODE`, `_SCHOOL_ACRONYM_EXPAND`, `clean_school_name`) to make room
for TD-145's institution check without growing `offer_pathway.py` past its size allowance.
`offer_pathway` imports the names back where the section was, so `op.clean_school_name` resolves
exactly as before. A leaf: imports nothing from this app but the generated `same_name_schools` set.

`school_name_core` (2026-10-31) is the ONE place a stored school name loses the ", TOWN" our lists add
to same-name schools before it is compared with a document: the offer-letter institution check
(`pathway_engine._field_status`) and the school-leaving certificate's school chip
(`academic_engine._school_match`), on both sides.
"""
import re

from .same_name_schools import SAME_NAME_SCHOOL_STATES, SAME_NAME_SCHOOLS


_SCHOOL_POSTCODE = re.compile(r'\b\d{5}\b')
_SCHOOL_ACRONYM_EXPAND = {
    'SMK': 'Sekolah Menengah Kebangsaan',
    'SMJK': 'Sekolah Menengah Jenis Kebangsaan',
    'SMKA': 'Sekolah Menengah Kebangsaan Agama',
    'KTE': 'Kolej Tingkatan Enam',
    'SM': 'Sekolah Menengah',
}


def _same_name_keys(s: str) -> set:
    """Upper-case, single-spaced — and, when it opens with a spelt-out school type, each way of
    folding that back to a short form ("Sekolah Menengah Kebangsaan Convent, Taiping" → "SMK
    CONVENT, TAIPING"; "…Kebangsaan Agama X" → both "SMKA X" and "SMK AGAMA X"). So a name re-cased by
    `clean_school_name` is still recognised."""
    key = ' '.join((s or '').upper().split())
    return {key} | {short + key[len(full):] for short, full in _SCHOOL_ACRONYM_EXPAND.items()
                    if key.startswith(full.upper() + ' ')}


def school_name_core(name: str) -> str:
    """The school NAME without the ", <TOWN>" our lists add to a name several schools share (owner,
    2026-10-31: *"The model need to match the school names only and not the town as well for this
    set of schools."*). "SMK CONVENT, TAIPING" → "SMK CONVENT".

    Cut ONLY when the whole string is one of OUR disambiguated names (`same_name_schools`, generated
    from the lists by `scripts/school_town_names.py`), so a real name holding a comma ("SMK PETAGAS,
    PENAMPANG") or anything a student typed is returned unchanged. For COMPARISON only — every screen
    still shows the full name with its town. Pure; never raises."""
    s = (name or '').strip()
    if ',' not in s or not (_same_name_keys(s) & SAME_NAME_SCHOOLS):
        return s
    return s[:s.rindex(',')].rstrip()


def _plain(s: str) -> str:
    """Upper-case, apostrophes dropped, every other mark a space, single-spaced: "St." is "ST"."""
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', (s or '').upper().replace("'", '')).split())


def _state_forms(state: str) -> set:
    """Our state as a letter may print it: "WP Kuala Lumpur" also reads "Kuala Lumpur"."""
    st = _plain(state)
    bare = re.sub(r'^(WP|W P|WILAYAH PERSEKUTUAN) ', '', st)
    return {f for f in (st, bare, f'WILAYAH PERSEKUTUAN {bare}' if bare != st else '') if f}


def keep_our_town(stored: str, letter: str) -> str:
    """What to save when an offer letter names the pre-U school (review fixes, 2026-10-31): the STORED
    "NAME, TOWN" — one of our same-name schools — only when the letter names EXACTLY that school;
    else the letter's own name, which is what was saved before.

    STRICT (review 2). Both sides are compared case-, punctuation- and spacing-blind ("ST." is "ST"),
    a spelt-out leading school type folds to its short form ("Sekolah Menengah Kebangsaan" is "SMK",
    which `clean_school_name` produces), 5-digit postcodes are dropped, and then the letter must be:
    our name; or our name and OUR town; either one followed only by our state. Nothing else — no
    other digit dropped, no word reordered, no type word ignored — so "SMK SULTAN ISMAIL 2", "SMK
    MUNSHI ABDULLAH" and a school named after its OWN town ("SMK Kepala Batas, Kepala Batas" against
    "SMK KEPALA BATAS, ALOR SETAR") all replace. Pure; never raises."""
    stored = (stored or '').strip()
    core = school_name_core(stored)
    if not letter or core == stored:
        return letter
    name, town = _plain(core), _plain(stored[len(core):])
    state = next((SAME_NAME_SCHOOL_STATES[k] for k in _same_name_keys(stored) if k in SAME_NAME_SCHOOL_STATES), '')
    said = ' '.join(re.sub(r'\b\d{5}\b', ' ', _plain(letter)).split())
    for st in sorted(_state_forms(state), key=len, reverse=True):
        if said.endswith(' ' + st):
            said = said[:-len(st) - 1]
            break
    wanted = _same_name_keys(name) | _same_name_keys(f'{name} {town}')
    return stored if _same_name_keys(said) & wanted else letter


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
