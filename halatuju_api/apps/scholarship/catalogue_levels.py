"""TD-332 (2026-10-04, review fix): the LEVEL a catalogue course is at, for the tertiary resolver.

``offer_pathway.resolve_catalogue_course`` skips a course whose level differs from a tertiary
letter's. It first judged that from the course NAME by substring, which read "(Diplomasi)" as a
diploma and "Program Asasi Pengurusan" (a Diploma by its ``level``) as asasi. So the course's own
``Course.level`` field decides, by whole words; the name's whole words are read only when the field
is blank. A level nothing here recognises yields NO family, and the resolver then does not skip —
"cannot tell" is never a disagreement.
"""
import re

#: ``Course.level`` words → the ``detect_pathway_type`` families that level may be. "Ijazah Sarjana
#: Muda Pendidikan" is how PISMP courses are levelled, so 'ijazah' may be a degree OR pismp.
_LEVEL_WORDS = {
    'asasi': ('asasi',), 'foundation': ('asasi',), 'pra-u': ('preu',),
    'diploma': ('diploma',), 'sijil': ('diploma',), 'ijazah': ('degree', 'pismp'),
}


def _has_word(word, text):
    return re.search(rf'(?<![\w-]){re.escape(word)}(?![\w-])', text) is not None


def course_levels(course) -> set:
    """The level families of ``course`` (its ``level``, else its name's whole words); may be empty."""
    text = ((getattr(course, 'level', '') or '').strip()
            or (getattr(course, 'course', '') or '')).lower()
    return {f for w, fams in _LEVEL_WORDS.items() if _has_word(w, text) for f in fams}
