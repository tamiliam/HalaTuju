"""THE ONE JUNK-NAME GUARD (TD-742 linkage Phase 1, owner ruling 25 Nov 2026).

A person's name read off a document is sometimes not a name at all: a bare ':' left where the
reader grabbed the separator, a label word ("NAMA", "PENERIMA") taken for its value, two stray
letters, or a name with the holder's IC number glued on. Compared with a real name, any of these
looks like a different person, and the fault then shows on a document that is correct (case 177:
the STR recipient read ':' and the correct parent IC showed "Wrong card").

`clean_person_name` says what of a read is a usable name, and '' when nothing is. It has two
callers and no other home:

* the readers, for NEW reads only (`doc_parse._parse_str`, `doc_parse_epf._parse_epf`): a
  failing candidate is skipped, so the AI read is used instead;
* the case-page DISPLAY (`link_display`), at comparison time, so a bad read already stored shows
  grey "not read" without any re-read. The decision code does not call it (Phase 1 is display
  only; Phase 2 moves decisions to the bands, a later sprint).

Rules (each is a reason the value is "not read"):

* fewer than ``MIN_LETTERS`` letters (request #66 precedent: the school-leaving reader's 4-letter
  floor);
* every word a known label word (``LABEL_WORDS``);
* an IC number inside the value is split off and the rest judged on its own.

Pure: no Django, no I/O, so the readers can import it at module level.
"""
from __future__ import annotations

import re

#: A whole name shorter than this many letters is not a name (request #66 precedent).
MIN_LETTERS = 4

#: Words that are printed LABELS on the documents we read, never a person's whole name. A value
#: made only of these is a label the reader took for its value.
LABEL_WORDS = frozenset({
    'NAMA', 'NAME', 'PENUH', 'FULL', 'PENERIMA', 'RECIPIENT', 'PEMOHON', 'PERMOHONAN',
    'KAD', 'PENGENALAN', 'NO', 'IC', 'MYKAD', 'NRIC', 'BARU', 'LAMA',
    'STATUS', 'SEMASA', 'FASA', 'BAYARAN', 'TARIKH', 'ALAMAT', 'ADDRESS',
    'AHLI', 'PENYATA', 'SULIT', 'DAN', 'PERSENDIRIAN', 'KWSP', 'EPF', 'STR', 'SARA',
    'JUMLAH', 'BIL', 'MAKLUMAT',
})

#: An IC number as printed (12 digits, dashes or spaces optional).
_NRIC_RE = re.compile(r'\d{6}\s*-?\s*\d{2}\s*-?\s*\d{4}')
_LEAD_JUNK = re.compile(r'^[\W\d_]+')
_TRAIL_JUNK = re.compile(r'[\s:;,|()\-]+$')
_LATIN_WORD = re.compile(r'[A-Za-z]+')


def clean_person_name(raw) -> str:
    """The usable name in ``raw``, or '' when it is not a name (see the module rules).
    A real name comes back with any glued-on IC number removed, leading punctuation dropped and
    spaces collapsed; nothing else about it changes."""
    s = _NRIC_RE.sub(' ', str(raw or ''))
    s = _TRAIL_JUNK.sub('', _LEAD_JUNK.sub('', ' '.join(s.split())))
    if sum(ch.isalpha() for ch in s) < MIN_LETTERS:
        return ''
    words = _LATIN_WORD.findall(s.upper())
    if words and all(w in LABEL_WORDS for w in words):
        return ''
    return s


def pick_name(*candidates) -> tuple[str, bool]:
    """The first candidate that is a usable name, and whether every candidate found (non-blank)
    was junk. ``('', False)`` when none was found at all; ``('', True)`` when only junk was."""
    name = next((c for c in map(clean_person_name, candidates) if c), '')
    return name, not name and any(str(c or '').strip() for c in candidates)


def name_not_read(raw) -> bool:
    """True when the document's own name is blank or junk (`clean_person_name` gives '')."""
    return not clean_person_name(raw)
