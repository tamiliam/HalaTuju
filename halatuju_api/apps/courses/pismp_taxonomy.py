"""
PISMP (teacher-training) taxonomy — read-time derivation, no DB persistence.

PISMP degrees are hierarchical: Laluan → Aliran (school type) → Bidang (major) →
Elektif (minor). The catalogue stores them flat (73 rows, source_type='pismp'),
with the Aliran encoded in the course NAME suffix — "(SJKC)", "(SJKT)", "(Khas)" —
and corroborated by the 6th character of the internal course_id ('50PD0<aliran>…'):
1/5 = SK, 3 = SJKC, 4 = SJKT, 6 = Khas. An Elektif variant is flagged by the word
"Elektif" in the name OR an id whose 2nd-to-last group is "[89]M" (e.g. …M9MP, …V8MP).

We DERIVE these on read rather than persist them (validated against all 73 prod rows,
0 aliran mismatches between name-suffix and id-digit). Rationale: the `courses` table
is a synced golden master, the catalogue is a fuzzy superset across laluan with the
odd duplicate/malformed id, and a one-line parser tweak beats correcting frozen rows.
See docs/lessons.md (read-time fallback > one-shot backfill; cross-source identity is fuzzy).
"""
import re

# Aliran (school type) — the stable, user-facing facet.
ALIRAN_SK = 'sk'
ALIRAN_SJKC = 'sjkc'
ALIRAN_SJKT = 'sjkt'
ALIRAN_KHAS = 'khas'
ALIRAN_VALUES = (ALIRAN_SK, ALIRAN_SJKC, ALIRAN_SJKT, ALIRAN_KHAS)

# Display labels (Malay) — the same Aliran terms students see on their offer letter.
ALIRAN_LABELS = {
    ALIRAN_SK: 'Sekolah Kebangsaan (SK)',
    ALIRAN_SJKC: 'Sekolah Jenis Kebangsaan Cina (SJKC)',
    ALIRAN_SJKT: 'Sekolah Jenis Kebangsaan Tamil (SJKT)',
    ALIRAN_KHAS: 'Pendidikan Khas',
}

# course_id 6th char → aliran (cross-check only; the name suffix is authoritative).
_ID_DIGIT_ALIRAN = {'1': ALIRAN_SK, '5': ALIRAN_SK, '3': ALIRAN_SJKC,
                    '4': ALIRAN_SJKT, '6': ALIRAN_KHAS}

# Elektif id marker: the group just before the final char is a digit 8/9 then 'M'.
_ELEKTIF_ID_RE = re.compile(r'[89]M.$')


def aliran_of(course_name: str, course_id: str = '') -> str:
    """The Aliran for a PISMP course. Name suffix is authoritative; falls back to
    the course_id 6th-char map (they agree on all 73 prod rows). Defaults to SK."""
    name = course_name or ''
    if '(SJKC)' in name:
        return ALIRAN_SJKC
    if '(SJKT)' in name:
        return ALIRAN_SJKT
    if '(Khas)' in name:
        return ALIRAN_KHAS
    if len(course_id) > 5:
        return _ID_DIGIT_ALIRAN.get(course_id[5], ALIRAN_SK)
    return ALIRAN_SK


def is_elektif(course_name: str, course_id: str = '') -> bool:
    """True if the course is an Elektif (minor) variant rather than a Bidang (major)."""
    if 'elektif' in (course_name or '').lower():
        return True
    return bool(_ELEKTIF_ID_RE.search(course_id or ''))


def classify_pismp(course_id: str, course_name: str) -> dict:
    """Derive the PISMP facets for one course → {'aliran', 'is_elektif'}."""
    return {
        'aliran': aliran_of(course_name, course_id),
        'is_elektif': is_elektif(course_name, course_id),
    }
