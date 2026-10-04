"""TD-332 (2026-10-04, review fix): the LEVEL a catalogue course is at, for the tertiary resolver.

``offer_pathway.resolve_catalogue_course`` skips a course whose level differs from a tertiary
letter's. It first judged that from the course NAME by substring, which read "(Diplomasi)" as a
diploma and "Program Asasi Pengurusan" (a Diploma by its ``level``) as asasi. So the course's own
``Course.level`` field decides, by whole words; the name's whole words are read only when the field
is blank. A level nothing here recognises yields NO family, and the resolver then does not skip —
"cannot tell" is never a disagreement.

TD-150 (2026-10-04) adds the resolver's two other "cannot tell" refusals, by the same rule — a
wrong ``course_id`` is worse than none, so an offer that cannot be pinned stays label-only:

* ``names_a_specialisation_the_letter_does_not`` — the letter's programme words are a STRICT subset
  of the course's: the course is a specialisation (or a recommender "major") the letter never names,
  so the letter cannot say WHICH. A generic "Diploma Teknologi Maklumat" offer at Politeknik Ungku
  Omar was pinned to "… (Pembangunan Perisian dan Aplikasi)" (#95). The reverse — the LETTER carrying
  more words, e.g. a code prefix "DAC - DIPLOMA PERAKAUNAN" — still matches.
* ``private_arm_letter`` — the letter is from a public university's PRIVATE arm (SPACE, Pendidikan
  Berterusan, Saluran Terbuka (SATU)) or a Sdn. Bhd. operator: an IPTS offer the public catalogue
  does not hold, however closely its words nest (#31, SATU). The phrases are the genuineness check's
  own (`genuineness.results_doc._private_arm_offer`, owner-ruled), never a second list.
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


#: Catalogue words that say nothing about WHICH course, so a letter that omits them is not "less
#: specific" (review fix, 2026-10-04): the award class ("… dengan Kepujian"), UPU's "Baru" marker
#: on a newly offered programme (a trailing "#" marker is dropped by the tokeniser already), and
#: "Bacelor", the Malay spelling of the generic "bachelor".
_NON_SPECIFYING_WORDS = frozenset({'kepujian', 'honours', 'honors', 'hons', 'baru', 'bacelor'})


def names_a_specialisation_the_letter_does_not(letter_tokens: set, course_tokens: set) -> bool:
    """TD-150: True when the course's distinctive words strictly CONTAIN the letter's — the course
    is more specific than anything the letter says. (Pass the course name with any PISMP aliran
    suffix stripped: "(SJKT)" is the school type, which no letter states.)"""
    letter, course = letter_tokens - _NON_SPECIFYING_WORDS, course_tokens - _NON_SPECIFYING_WORDS
    return bool(letter) and letter < course


def private_arm_letter(programme: str, institution: str) -> bool:
    """TD-150: True when the offer is from a private arm or a Sdn. Bhd. operator (see above)."""
    from .genuineness.results_doc import _private_arm_offer
    return _private_arm_offer(f'{programme or ""} {institution or ""}')
