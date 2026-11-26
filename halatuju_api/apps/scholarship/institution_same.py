"""Do two offer-letter institution lines name the same institution? (fix: false "Course switched").

``offer_pathway_switch`` used to compare the old and new offer with the bare token matcher, so one
university written two ways ("UNIVERSITI PENDIDIKAN SULTAN IDRIS" and "UPSI") shared no token and read
as a switch. ``institutions_differ`` is the switch test: True only when the two lines name genuinely
DIFFERENT institutions.

Order: (1) the old token compare, a shared distinctive word means the same place; (2) both lines resolved
to a public university (full name, English name or acronym, whole words, from the one list of the 20 UA
names in ``genuineness.offer_signatures`` plus their acronyms), else to ONE catalogue institution through
``offer_course_match.CampusReader``. Two lines on the same university are the same unless BOTH name a
campus and the campuses share no word (one side naming no campus is not a switch). A line neither
route can place falls back to the token result. Pure read.
"""
from __future__ import annotations

import re

from .pathway_match import _field_status, distinctive_tokens
from .school_names import school_name_core

# Acronyms and English names of the 20 public universities, keyed by the Malay name in
# ``offer_signatures._UA_NAMES`` (the single list of names; a test pins that no name is left out).
_UA_ALIASES = {
    'UNIVERSITI MALAYA': ('UM', 'UNIVERSITY OF MALAYA'),
    'UNIVERSITI SAINS MALAYSIA': ('USM', 'UNIVERSITY SAINS MALAYSIA'),
    'UNIVERSITI KEBANGSAAN MALAYSIA': ('UKM', 'NATIONAL UNIVERSITY OF MALAYSIA'),
    'UNIVERSITI PUTRA MALAYSIA': ('UPM', 'UNIVERSITY PUTRA MALAYSIA'),
    'UNIVERSITI TEKNOLOGI MALAYSIA': ('UTM', 'UNIVERSITY OF TECHNOLOGY MALAYSIA'),
    'UNIVERSITI TEKNOLOGI MARA': ('UITM', 'MARA UNIVERSITY OF TECHNOLOGY', 'UNIVERSITY OF TECHNOLOGY MARA'),
    'UNIVERSITI ISLAM ANTARABANGSA MALAYSIA': ('UIAM', 'IIUM', 'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'),
    'UNIVERSITI UTARA MALAYSIA': ('UUM', 'NORTHERN UNIVERSITY OF MALAYSIA'),
    'UNIVERSITI MALAYSIA SARAWAK': ('UNIMAS', 'UNIVERSITY MALAYSIA SARAWAK'),
    'UNIVERSITI MALAYSIA SABAH': ('UMS', 'UNIVERSITY MALAYSIA SABAH'),
    'UNIVERSITI PENDIDIKAN SULTAN IDRIS': ('UPSI', 'SULTAN IDRIS EDUCATION UNIVERSITY'),
    'UNIVERSITI SAINS ISLAM MALAYSIA': ('USIM', 'ISLAMIC SCIENCE UNIVERSITY OF MALAYSIA'),
    'UNIVERSITI TEKNIKAL MALAYSIA MELAKA': ('UTEM', 'TECHNICAL UNIVERSITY OF MALAYSIA MALACCA',
                                            'UNIVERSITI TEKNIKAL MALAYSIA MALACCA'),
    'UNIVERSITI MALAYSIA PAHANG': ('UMP', 'UNIVERSITI MALAYSIA PAHANG AL SULTAN ABDULLAH', 'UMPSA',
                                   'UNIVERSITY MALAYSIA PAHANG'),
    'UNIVERSITI MALAYSIA PERLIS': ('UNIMAP', 'UNIVERSITY MALAYSIA PERLIS'),
    'UNIVERSITI TUN HUSSEIN ONN MALAYSIA': ('UTHM', 'TUN HUSSEIN ONN UNIVERSITY OF MALAYSIA'),
    'UNIVERSITI MALAYSIA TERENGGANU': ('UMT', 'UNIVERSITY MALAYSIA TERENGGANU'),
    'UNIVERSITI MALAYSIA KELANTAN': ('UMK', 'UNIVERSITY MALAYSIA KELANTAN'),
    'UNIVERSITI PERTAHANAN NASIONAL MALAYSIA': ('UPNM', 'NATIONAL DEFENCE UNIVERSITY OF MALAYSIA'),
    'UNIVERSITI SULTAN ZAINAL ABIDIN': ('UNISZA', 'SULTAN ZAINAL ABIDIN UNIVERSITY'),
}


def _words(text: str) -> str:
    """Upper-case, apostrophes dropped, other punctuation to spaces, padded for whole-word search."""
    t = re.sub(r"['’]", '', (text or '').upper())
    return ' ' + ' '.join(re.findall(r'[A-Z0-9]+', t)) + ' '


def _ua_hits(text: str):
    """{canonical name: the phrases of it found as whole words in ``text``}. A name found only inside a
    longer name's span (UM inside nothing; 'UNIVERSITI MALAYSIA PAHANG' inside its Al-Sultan Abdullah
    form) is kept by the longer phrase only."""
    w = _words(text)
    hits = {}
    for canon, aliases in _UA_ALIASES.items():
        found = [p for p in (canon, *aliases) if f' {_words(p).strip()} ' in w]
        if found:
            hits[canon] = found
    return hits


def _ua_key(text: str):
    """(key, phrases) when ``text`` names exactly ONE public university, else ('', ())."""
    hits = _ua_hits(text)
    if len(hits) != 1:
        return '', ()
    ((canon, found),) = hits.items()
    return canon, tuple(found)


def _catalogue_key(text: str, index):
    """The ONE catalogue institution ``CampusReader`` says ``text`` names, else ''."""
    from .offer_course_match import CampusReader
    named = CampusReader(text, index).named
    ids = {iid for iid, _n in named}
    return f'cat:{next(iter(ids))}' if len(ids) == 1 else ''


def _campus_words(text: str, phrases) -> set:
    """What a line names beyond the university itself: its distinctive words minus the university's
    own name / acronym words and any bracketed acronym. Empty = the line names no campus."""
    own = set()
    for p in phrases:
        own |= distinctive_tokens(p)
    own |= {p.lower() for p in phrases}
    return distinctive_tokens(school_name_core(text)) - own


def institutions_differ(a: str, b: str) -> bool:
    """True only when the two offer-letter institution lines name genuinely different institutions."""
    if not (a or '').strip() or not (b or '').strip():
        return False                                     # nothing to compare
    ka, pa = _ua_key(a)
    kb, pb = _ua_key(b)
    # A university named on either side is decided by identity, not by a shared place word (a Sabah
    # school and UMS share only "sabah"); otherwise a shared distinctive word means the same place.
    if not (ka or kb) and _field_status(a, b) != 'clash':
        return False
    if ka and kb:
        if ka != kb:
            return True                                  # two different public universities
        ca, cb = _campus_words(a, pa), _campus_words(b, pb)
        return bool(ca and cb and not (ca & cb))         # different campuses of one university
    if ka or kb:
        return True                                      # a university against something else
    try:
        from .offer_course_match import catalogue_index
        index = catalogue_index()
        ca, cb = _catalogue_key(a, index), _catalogue_key(b, index)
    except Exception:                                    # the catalogue is an aid, never a gate
        return True
    return not (ca and cb and ca == cb)
