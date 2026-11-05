"""A results document whose name is ONE LOOK-ALIKE LETTER off the student's: a likely misread, not
another person (org request #56, 2026-11-05; owner ruling 2026-11-05: look-alike letters only).

A BrightPath matriculation transcript came back from the AI fallback reader with one letter of
the given name read as "Q" for "O". The stored verdict (`vision.doc_student_verdict`, the strict
`name_match`) said 'name_mismatch', and the Documents step blocked the student.

The rule, deliberately narrow (owner-approved plan + the 2026-11-05 review):

* The two names are compared PART BY PART, IN PRINTED ORDER (`vision._canonical_name_seq`, so
  "A/P", "BIN" and other parentage words drop out the same way they do for the strict match).
* They must have the SAME number of parts, and every part but ONE must be identical.
* The one differing part must be the same length in both, at least ``MIN_PART_LETTERS`` long,
  and differ by exactly ONE SUBSTITUTED letter, AND the two letters must be a known print-OCR
  confusion (``LOOK_ALIKE_PAIRS``: O for Q, yes; A for I, never). A results slip carries no IC, so
  nothing else proves identity: any-letter tolerance let a sibling's slip through (AINI / AINA,
  MING / LING, RAJA / RAMA).
* A digit read inside a name ("R0HANA") is the same misread: the strict tokeniser splits the part
  there, so the ONE digit in the read name is put back as each letter it is a look-alike of.
* Compared against the STUDENT'S OWN name only (never a guardian's).
* Only on a document scored GENUINE or not scored at all (`doc_misread`): a suspect or fake slip
  keeps the red mismatch, so a doubtful document cannot also borrow the name tolerance. An
  'unchecked' (not-final) page counts as neither: it gets no tolerance.

Anything else stays 'mismatch' and blocks exactly as before. The caller (`academic_engine.
_slip_name_status`) turns a likely misread into 'partial': never a block, an amber chip, and a
reviewer note asking them to check it is the student's slip. Read-time only: no stored field changes.
"""
import re

MIN_PART_LETTERS = 4   # parts of 1-3 letters (LIM, ALI, NG) get no tolerance: one letter is too much of them

#: The ONLY substitutions read as a misread: uppercase Latin glyphs a print OCR / AI reader really
#: confuses (owner ruling 2026-11-05). Unordered pairs, lowercase (the compare is lowercase). Never a
#: vowel for a vowel (AINI / AINA), never M/N (MING / NING), H/N, R/P or I/J — decisions.md #56 lists
#: every rejected pair and why. Digit pairs apply to a digit read inside a name part.
LOOK_ALIKE_PAIRS = frozenset(frozenset(p) for p in (
    ('o', 'q'), ('o', 'd'), ('o', '0'), ('q', '0'), ('d', '0'),   # the round letters and zero
    ('i', 'l'), ('i', '1'), ('l', '1'),                           # the upright strokes and one
    ('s', '5'), ('b', '8'), ('z', '2'), ('g', '6'),               # letter / digit shapes
    ('u', 'v'), ('c', 'g'), ('e', 'f'),                           # a lost or faint stroke
))


def _look_alike(a: str, b: str) -> bool:
    return frozenset((a, b)) in LOOK_ALIKE_PAIRS


def _one_substitution(a: str, b: str) -> bool:
    """Same length, at least MIN_PART_LETTERS, exactly one position differs, by a look-alike pair."""
    if len(a) != len(b) or len(a) < MIN_PART_LETTERS:
        return False
    diffs = [(x, y) for x, y in zip(a, b) if x != y]
    return len(diffs) == 1 and _look_alike(*diffs[0])


def _digit_misread(read_name: str, own: list) -> bool:
    """The read name holds exactly ONE digit, inside a part of at least MIN_PART_LETTERS characters,
    and putting back a letter it is a look-alike of makes the name identical to the student's."""
    from .vision import _canonical_name_seq
    digits = list(re.finditer(r'\d', read_name))
    if len(digits) != 1:
        return False
    pos, digit = digits[0].start(), digits[0].group()
    part = next(m for m in re.finditer(r'[A-Za-z0-9]+', read_name) if m.start() <= pos < m.end())
    if len(part.group()) < MIN_PART_LETTERS or not re.search(r'[A-Za-z]', part.group()):
        return False
    for pair in LOOK_ALIKE_PAIRS:
        if digit in pair:
            (letter,) = pair - {digit}
            if not letter.isdigit() and _canonical_name_seq(
                    read_name[:pos] + letter + read_name[pos + 1:]) == own:
                return True
    return False


def one_letter_misread(read_name: str, own_name: str) -> bool:
    """True iff `read_name` is `own_name` with exactly one LOOK-ALIKE letter substituted in exactly
    one part of at least MIN_PART_LETTERS letters, every other part identical and in the same order."""
    from .vision import _canonical_name_seq, _strip_name_label
    stripped = _strip_name_label(read_name or '')
    own = _canonical_name_seq(own_name or '')
    if not own:
        return False
    if re.search(r'\d', stripped):
        return _digit_misread(stripped, own)
    read = _canonical_name_seq(stripped)
    if not read or len(read) != len(own):
        return False
    differing = [(a, b) for a, b in zip(read, own) if a != b]
    return len(differing) == 1 and _one_substitution(*differing[0])


def doc_misread(doc) -> bool:
    """Is this results document's stored candidate name a likely look-alike misread of the student's
    own name, on a document scored genuine or not scored at all? A suspect / fake document keeps the
    red mismatch (2026-11-05 review: 'partial' counts no red chip, so a suspect slip would otherwise
    move Unsure -> Probable). Reads only what is stored; runs no OCR, calls no model."""
    from .genuineness.bands import NOT_CHECKED, canonical_status, stored_status
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    stored = stored_status(vf)
    # 'unchecked' = a not-final higher-results page (semester slip, portal page, in-progress transcript):
    # digital text, so a one-letter difference is more likely a real different name. No tolerance.
    if (stored if isinstance(stored, str) else '').strip().lower() == NOT_CHECKED:
        return False
    if canonical_status(stored, getattr(doc, 'doc_type', None)) not in ('', 'genuine'):
        return False
    fields = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    return one_letter_misread(fields.get('candidate_name') or '', getattr(profile, 'name', '') or '')
