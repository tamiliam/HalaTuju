"""A results document whose name is ONE LETTER off the student's: a likely misread, not another
person (org request #56, 2026-11-05).

A BrightPath matriculation transcript came back from the AI fallback reader with one letter of
the given name read as "Q" for "O". The stored verdict (`vision.doc_student_verdict`, the strict
`name_match`) said 'name_mismatch', and the Documents step blocked the student.

The rule, deliberately narrow (owner-approved plan):

* The two names are compared PART BY PART, IN PRINTED ORDER (`vision._canonical_name_seq`, so
  "A/P", "BIN" and other parentage words drop out the same way they do for the strict match).
* They must have the SAME number of parts, and every part but ONE must be identical.
* The one differing part must be the same length in both, at least ``MIN_PART_LETTERS`` long,
  and differ by exactly ONE SUBSTITUTED letter (O -> Q). A letter added or dropped is not a
  misread under this rule — an OCR misread swaps a glyph, it does not invent one.
* Compared against the STUDENT'S OWN name only (never a guardian's): the stored verdict already
  checks the household, and a near-miss of a parent's name is not the student's document.

Anything else — two letters, one letter in each of two parts, a missing or extra part, a short
part — stays 'mismatch' and blocks exactly as before. The caller (`academic_engine.
_slip_name_status`) turns a likely misread into 'partial': never a block, an amber chip, and a
reviewer note ("differs by one letter, please check"). Read-time only: no stored field changes.
"""

MIN_PART_LETTERS = 4   # parts of 1-3 letters (LIM, ALI, NG) get no tolerance: one letter is too much of them


def _one_substitution(a: str, b: str) -> bool:
    """Same length, at least MIN_PART_LETTERS, exactly one position differs."""
    if len(a) != len(b) or len(a) < MIN_PART_LETTERS:
        return False
    return sum(1 for x, y in zip(a, b) if x != y) == 1


def one_letter_misread(read_name: str, own_name: str) -> bool:
    """True iff `read_name` is `own_name` with exactly one letter substituted in exactly one
    part of at least MIN_PART_LETTERS letters, every other part identical and in the same order."""
    from .vision import _canonical_name_seq, _strip_name_label
    read = _canonical_name_seq(_strip_name_label(read_name or ''))
    own = _canonical_name_seq(own_name or '')
    if not read or len(read) != len(own):
        return False
    differing = [(a, b) for a, b in zip(read, own) if a != b]
    return len(differing) == 1 and _one_substitution(*differing[0])


def doc_misread(doc) -> bool:
    """Is this results document's stored candidate name a likely one-letter misread of the
    student's own name? Reads only what is stored; runs no OCR, calls no model."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    fields = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    return one_letter_misread(fields.get('candidate_name') or '', getattr(profile, 'name', '') or '')
