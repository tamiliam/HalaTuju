"""The STPM subject names a results document prints, and the ONE matcher every reader uses.

Moved out of `higher_results.py` (2026-11-07, which re-exports the names) when the matcher became
typo-tolerant: an AI read prints "PENGJIAN AM" for PENGAJIAN AM (apps 173, 196, 278, 279, 341, 418)
and "PENGJIAN PERNIAGAAN" for PENGAJIAN PERNIAGAAN (173, 196). The certificate prints the right name;
the read dropped a letter. Before, such a row was silently IGNORED — so 196's real Pengajian Am
mismatch (entered B+, certificate B) never showed, and 278's list of "subjects not entered" had no PA.

THE RULE (`stpm_key`). A printed name (its leading paper code dropped, squashed to letters and digits):
1. matches a known name EXACTLY → that subject (unchanged);
2. else, only for a name with NO digit in it (343's "PENGAJIAN AM 1 … 4" is a per-paper layout,
   not a typo — TD-581), within a small edit distance of the known names — 1 edit for a name of 5 to
   11 characters, 2 for 12 or more, none under 5 ("ICT") — of exactly ONE subject → that subject;
3. else (no subject near, or two near — "MATEMATIK" sits one edit from both T and M) → unrecognised.
A near match never lands on a subject the SAME document already printed exactly (`stpm_keyed_rows`):
two rows for one subject is not a typo we can resolve, so the near one stays unrecognised.

Why those distances: the closest pair of DIFFERENT subjects' names is Matematik T / M (1 edit, which
rule 3 makes ambiguous); every other pair is at least 3 apart (fizik / kimia, sejarah / syariah), so
one edit can never be nearer two subjects than one. A long name (12+ letters, e.g. "PENGAJIAN
PERNIAGAAN") tolerates a second slip while staying under that gap. Under 5 there is no room at all.
"""
from __future__ import annotations

import re

#: STPM subject keys (`stpm_grades`, the web's `STPM_SUBJECTS`) → the names a slip prints for
#: them, Malay and English. A printed subject no rule here recognises is named by the Academic card
#: on an STPM read (`higher_results.student_higher_check`'s ``unrecognised``) — never dropped.
_STPM_NAMES = {
    'PA': ('pengajian am', 'general studies'), 'MATH_T': ('matematik t', 'mathematics t'),
    'MATH_M': ('matematik m', 'mathematics m'), 'PHYSICS': ('fizik', 'physics'),
    'CHEMISTRY': ('kimia', 'chemistry'), 'BIOLOGY': ('biologi', 'biology'),
    'FURTHER_MATH': ('matematik lanjutan t', 'further mathematics t', 'further mathematics'),
    'ECONOMICS': ('ekonomi', 'economics'), 'ACCOUNTING': ('perakaunan', 'accounting'),
    'BUSINESS': ('pengajian perniagaan', 'business studies'), 'GEOGRAFI': ('geografi', 'geography'),
    'SEJARAH': ('sejarah', 'history'),
    'KESUSASTERAAN_MELAYU': ('kesusasteraan melayu', 'kesusasteraan melayu komunikatif',
                             'communicative malay literature'),
    'BAHASA_MELAYU': ('bahasa melayu',), 'BAHASA_CINA': ('bahasa cina', 'chinese language'),
    'BAHASA_TAMIL': ('bahasa tamil', 'tamil language'), 'SENI_VISUAL': ('seni visual', 'visual arts'),
    'SYARIAH': ('syariah', 'syariah islamiah', 'pengajian syariah'),
    'USULUDDIN': ('usuluddin', 'pengajian usuluddin'),
    'ICT': ('sains komputer', 'ict', 'information and communications technology', 'computing'),
    # STPM CGPA sprint C1 (2026-10-28): the rest of the MPM list (`courses/stpm_subjects.py`).
    'BAHASA_ARAB': ('bahasa arab', 'arabic language'),
    'LITERATURE_IN_ENGLISH': ('literature in english', 'kesusasteraan inggeris'),
    'TAHFIZ_AL_QURAN': ('tahfiz al-quran', 'tahfiz al quran'),
    'SAINS_SUKAN': ('sains sukan', 'sports science'),
}


def _squash(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


_STPM_BY_NAME = {_squash(n): key for key, names in _STPM_NAMES.items() for n in names}


def _room(squashed: str) -> int:
    """The edits a printed name of this length may carry (the module docstring says why)."""
    return 0 if len(squashed) < 5 else 1 if len(squashed) < 12 else 2


def _within(a: str, b: str, room: int) -> bool:
    """Levenshtein distance of `a` and `b` at most `room` (a banded row walk; the names are short)."""
    if abs(len(a) - len(b)) > room:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > room:
            return False
        prev = cur
    return prev[-1] <= room


def _printed(name) -> str:
    return _squash(re.sub(r'^\d+\s*', '', (name or '').strip()))   # "950 MATEMATIK (T)"


def stpm_key(name, taken=frozenset(), near_ok=True):
    """The subject key for ONE printed name, or None (unrecognised). `taken`: the keys this same
    document printed exactly — a near match never lands on one of them. `near_ok` False: exact only."""
    sq = _printed(name)
    if sq in _STPM_BY_NAME:
        return _STPM_BY_NAME[sq]
    room = _room(sq) if near_ok else 0
    if not room or any(c.isdigit() for c in sq):
        return None
    near = {key for known, key in _STPM_BY_NAME.items() if _within(sq, known, room)}
    return next(iter(near)) if len(near) == 1 and not near & set(taken) else None


def stpm_keyed_rows(fields):
    """(printed name, subject key or None, the document's grade) for each subject row of a read,
    in order — exact names first claim their subjects, then each near one is matched (`stpm_key`).
    Near matches only on a page read as STPM (`results_kind_detected`): a Matriculation or Diploma
    transcript filed as STPM (apps 306 / 340, TD-582) is never "corrected" into STPM subjects."""
    rows = [r for r in (fields.get('results') or []) if isinstance(r, dict)]
    exact = {_STPM_BY_NAME.get(_printed(r.get('subject'))) for r in rows} - {None}
    near_ok = fields.get('results_kind_detected') == 'stpm'
    for row in rows:
        name = (row.get('subject') or '').strip()
        yield name, stpm_key(name, exact, near_ok), re.sub(r'\s+', '', (row.get('grade') or '')).upper()
