"""The lenient offer-vs-declared pathway MATCHER — moved verbatim out of ``pathway_engine`` (offer
exact-read S6, 2026-11-03, a moves-only split: ``pathway_engine.py`` sat at its line allowance).

Not a line of the bodies below was reworded. ``pathway_engine`` re-exports every name here, so
``from .pathway_engine import distinctive_tokens`` (offer_course_match, offer_pathway, offer_link) and
every other import keep working. A leaf: it imports nothing from ``pathway_engine``,
``offer_pathway`` or ``offer_course_match`` at module level (the two ``offer_pathway`` imports stay
inside their functions). TD-473's level check lands here, beside the matcher it changes.
"""
from __future__ import annotations

import re

from .school_names import school_name_core


# ── Lenient offer-vs-declared pathway matcher ────────────────────────────────
# The student declares a *specific* college/programme at apply time (via the
# eligibility filter, or a pre-U school/track). The offer letter names the same
# two facts. We compare them leniently: an offer counts as "matching" the
# declaration unless it is TOTALLY off (a different place / a different field),
# because catalogue names and printed offer-letter wording differ in harmless
# ways ("KM Melaka" vs "Kolej Matrikulasi Melaka"). We only flag a real clash —
# SMK Temerloh vs SMK Mentakab, Asasi Pertanian vs Asasi Pintar, Dip Horticulture
# vs Dip Electricity at the same UPM — so the student is never nagged on a match.

# Words that carry NO distinguishing signal — institution-type, qualification-type,
# and connectors. Field words (pertanian/pintar/sains/electricity…) and place names
# (melaka/temerloh/mentakab…) are deliberately NOT here: those are what distinguish.
_GENERIC_TOKENS = frozenset({
    # institution type
    'kolej', 'college', 'matrikulasi', 'smk', 'sekolah', 'menengah', 'kebangsaan',
    'kampus', 'campus', 'universiti', 'university', 'uni', 'politeknik', 'polytechnic',
    'institut', 'institute', 'pusat', 'akademi', 'academy', 'tinggi', 'harian',
    'jabatan', 'fakulti', 'faculty', 'school',
    # qualification / pathway type
    'asasi', 'foundation', 'diploma', 'ijazah', 'sarjana', 'muda', 'degree', 'bachelor',
    'program', 'programme', 'sijil', 'certificate', 'persediaan', 'pengajian',
    'tingkatan', 'form', 'stpm', 'matrik', 'matriculation', 'pra',
    # issuer / ministry / administrative boilerplate printed on official letters. NONE of these
    # name a field or a place, so they must never count as a distinguishing token — else an
    # offer whose programme line reads "PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN" would
    # falsely "clash" with a declared stream like "Sains" (#30). Place names + real fields are
    # still kept; only the ministry/administrative wrapper is dropped.
    'kementerian', 'ministry', 'pendidikan', 'pelajaran', 'bahagian', 'malaysia',
    'kpm', 'kpt', 'rasmi', 'surat',
    # enrolment-structure wording on an offer (a Form-6 offer reads "Tingkatan Enam
    # Semester 1 Tahun 2026" — none of which is a FIELD, so it must not "clash" with a
    # declared field like "sains sosial"). Cardinals cover "Semester Satu/Dua", "Tingkatan Enam".
    'semester', 'sesi', 'session', 'intake', 'pengambilan', 'kemasukan', 'tawaran',
    'tahun', 'year', 'satu', 'dua', 'tiga', 'empat', 'lima', 'enam', 'tujuh', 'lapan',
    'sembilan', 'sepuluh',
    # connectors / filler
    'of', 'in', 'the', 'dan', 'and', 'di', 'ke', 'dengan', 'untuk', 'bagi',
    'with', 'for',
})


def distinctive_tokens(text: str) -> set:
    """The place/field tokens that actually distinguish one offer from another:
    lowercase words 3+ chars, excluding pure digits and the generic stopwords."""
    if not text:
        return set()
    toks = re.split(r'[^a-z0-9]+', text.lower())
    return {t for t in toks if len(t) > 2 and not t.isdigit() and t not in _GENERIC_TOKENS}


def _field_status(declared: str, offer: str) -> str:
    """Compare one field (institution OR programme): 'match' (share a distinctive
    token), 'clash' (both distinctive, none shared), or 'unknown' (one side has
    nothing distinctive to compare). Both sides go through ``school_name_core`` (owner, 2026-10-31):
    the school NAME is compared, never the ", TOWN" our lists add to a same-name school."""
    d = distinctive_tokens(school_name_core(declared))
    o = distinctive_tokens(school_name_core(offer))
    if not d or not o:
        return 'unknown'
    return 'match' if (d & o) else 'clash'


def offer_pathway_match(declared_programme: str, declared_institution: str,
                        offer_programme: str, offer_institution: str,
                        declared_track: str = '', offer_stream: str = '',
                        institution_agreement: str = '',
                        programme_agreement: str = '') -> str:
    """'match' / 'mismatch' / 'unknown' for an offer vs the declared pathway.

    A clash on the institution, the programme, OR the STREAM/TRACK makes it a mismatch (the
    offer is for a genuinely different place, field, or stream). Otherwise a shared distinctive
    token — or an agreeing canonical track — makes it a match. 'unknown' means there was nothing
    specific enough to compare (the student declared only a pathway type, or the offer body didn't
    read) — treated as no-conflict downstream.

    #117 (b) — the STREAM was never in the comparison, so an offer summoning the student to
    ``Bidang SAINS`` against a declared ``sains_sosial`` (#33 / #99 / #117) read as no-conflict.
    Both sides are canonicalised through ``parse_stpm_stream`` (``SAINS`` → ``sains`` vs
    ``SAINS SOSIAL`` → ``sains_sosial`` — distinct codes, so the shared 'sains' substring can't
    produce a false match), and the clash is counted ONLY when BOTH read a stream: a letter that
    prints no stream (``''``) never clashes.

    ``institution_agreement`` — when the caller has resolved the institution dimension through the
    CATALOGUE (``offer_pathway.institution_agreement``), pass its verdict here and it REPLACES the
    token comparison. Load-bearing: two spellings of ONE institution share no distinctive token
    ("UTHM - KAMPUS (CAWANGAN PAGOH)" vs "Universiti Tun Hussein Onn Malaysia"), so the token test
    called a correct pathway a mismatch the moment the recorded institution was filled from the
    catalogue — #48, owner 2026-07-25: red Pathway chip, lost Institution tick, a red chip docked off
    the verdict band, and a student asked to confirm a pathway that was already right. The token path
    remains for a FREE-TEXT declaration with no course_id, where there is no catalogue to ask.

    ``programme_agreement`` — the same, for the PROGRAMME axis (request #9, 2026-08-01). A PISMP
    letter names the umbrella ("Program Ijazah Sarjana Muda Perguruan (PISMP)") while the record
    names the specific option ("Sejarah Pendidikan Rendah (SK)"): one thing at two levels of
    detail, sharing no distinctive token, so the token test called it a clash and painted a correct
    record as a mismatch — which then withheld the Institution tick too, because a tick is never
    green while the pathway is a mismatch. Passing the catalogue's verdict here REPLACES the token
    comparison for a catalogue-linked course, exactly as the institution one does.
    """
    from .offer_pathway import parse_stpm_stream
    inst = institution_agreement or _field_status(declared_institution, offer_institution)
    prog = programme_agreement or _field_status(declared_programme, offer_programme)
    dtrack, otrack = parse_stpm_stream(declared_track), parse_stpm_stream(offer_stream)
    track_clash = bool(dtrack and otrack and dtrack != otrack)
    track_match = bool(dtrack and otrack and dtrack == otrack)
    if inst == 'clash' or prog == 'clash' or track_clash:
        return 'mismatch'
    if inst == 'match' or prog == 'match' or track_match:
        return 'match'
    return 'unknown'


def _declared_pathway(application) -> tuple:
    """The student's declared (programme, institution) from the apply-form fields.
    Prefers the structured ``chosen_programme`` (eligibility-filter pick), falling back to the
    pre-U SCHOOL for the institution. Either may be ''.

    #117 (c) — break the circularity. ``services.autofill_pathway_from_offer`` writes
    ``chosen_programme`` FROM the offer letter and stamps ``source='offer_letter_auto'``; using that
    value AS "the declaration" means ``offer_pathway_match`` compares the offer against ITSELF (45
    live applications carry this source, so their pathway clash is invisible). When the pick came
    from the offer it is NOT a student declaration — fall back to the student's own pre-U
    school/track. This can only REVEAL clashes we are currently blind to, never create a false one.

    ⚠⚠ THE PROGRAMME NO LONGER FALLS BACK TO ``pre_u_track``, AND MUST NOT BE MADE TO AGAIN
    (2026-09-10). A track is a STREAM ('sains'); the offer's ``programme`` is a COURSE NAME
    ('Program Matrikulasi'). Those two can never agree on MEANING — they agreed on a WORD, because
    most matriculation letters print the jurusan inside the programme line and our own parser's
    f-string glued it there. That coincidence carried 26 matric students. App #142's letter carried
    a DATE in that position instead, so the comparison read 'sains' against 'jun', called it a
    clash, and painted a correct offer with a red Pathway chip, no Institution tick (a tick is never
    green while the pathway is a mismatch), and a student asked to confirm a pathway already right.

    The track is NOT lost: it reaches ``offer_pathway_match`` through ``declared_track``, its own
    axis, compared against the letter's own ``stream``. This removes a DUPLICATE, mis-typed use.

    Measured on all 58 live pre-U records before the change: the INSTITUTION axis matches on every
    one of them, so the programme axis had never once decided a pre-U verdict — pure exposure
    carrying no signal. Measured again after the offer-parser fix landed: dropping it changes
    **zero** records."""
    cp = getattr(application, 'chosen_programme', None)
    cp = cp if isinstance(cp, dict) else {}
    from_offer = cp.get('source') == 'offer_letter_auto'
    prog = '' if from_offer else (cp.get('course_name') or '').strip()
    inst = '' if from_offer else (cp.get('institution') or '').strip()
    if not inst and application is not None:
        # TD-145: a course_id-only pick declares the catalogue's ONE campus, ahead of a stale pre-U
        # school. Feeds pathway_confirm's "you told us X"; the course_id's institution VERDICT stays
        # `offer_pathway.institution_agreement`'s.
        inst = catalogue_declared_institution(application)
    if not inst:
        inst = (getattr(application, 'pre_u_institution', '') or '').strip()
    return prog, inst


def catalogue_declared_institution(application) -> str:
    """TD-145: the institution a degree pick DECLARES when the form stored only `course_id` —
    the catalogue's campus when the course has exactly ONE (`sole_catalogue_institution`), else
    ''. A multi-campus course resolves to nothing, never a guess; a recorded institution, an
    offer-autofilled pick, or no course_id → ''. Read-only."""
    cp = getattr(application, 'chosen_programme', None)
    cp = cp if isinstance(cp, dict) else {}
    cid = (cp.get('course_id') or '').strip()
    if not cid or cp.get('source') == 'offer_letter_auto' or (cp.get('institution') or '').strip():
        return ''
    from .offer_pathway import sole_catalogue_institution
    return sole_catalogue_institution(cid)
