"""Offer-letter → chosen-pathway resolution (pure detectors + a conservative catalogue
resolver).

When a verified offer letter settles a pathway the student hadn't yet locked, we mirror
the *apply form's own* two storage shapes (see ``ScholarshipApplication``):

  - **Pre-U** (STPM / Matrikulasi): there is NO catalogue ``course_id`` — the apply form
    itself stores ``chosen_pathway`` + ``pre_u_track`` (stream) + ``pre_u_institution``
    (the school name, as free text). So an offer of "Tingkatan Enam Semester 1 (Sains
    Sosial)" at "SMK X" maps to ``stpm`` + ``sains_sosial`` + "SMK X" — at full parity
    with what a student would have typed.
  - **Tertiary** (Diploma / Asasi / Degree / PISMP): the apply form resolves a canonical
    ``course_id`` through its eligibility filtration. From OCR text we can only *attempt*
    that — ``resolve_catalogue_course`` returns a ``course_id`` ONLY on a confident, unique
    catalogue match; otherwise the caller stores the offer's name + institution as plain
    labels (no fabricated id). This honours the filtration where it exists and never
    invents a precise catalogue entry from blurry OCR.

All functions here are read-only (no model writes). The orchestration + writes live in
``services.autofill_pathway_from_offer``.
"""
from __future__ import annotations

import re

from .pathway_engine import distinctive_tokens


def _norm_inst_name(s: str) -> str:
    """Lower-case, drop trailing/inner parentheticals (e.g. an "(UKM)" acronym) and collapse
    whitespace — so two spellings of the SAME institution compare equal even when the name
    has no distinctive tokens (every word generic, e.g. 'Universiti Kebangsaan Malaysia')."""
    s = re.sub(r'\([^)]*\)', ' ', s or '')
    return ' '.join(s.split()).strip().lower()


def detect_pathway_type(programme: str, institution: str) -> str:
    """Coarse pathway type from the offer's free text — ``'stpm'`` | ``'matric'`` |
    ``'asasi'`` | ``'pismp'`` | ``'diploma'`` | ``'degree'`` | ``''`` (unknown).

    Only ``stpm``/``matric`` are treated as *pre-U* (no catalogue) by the caller; the rest
    go through the catalogue resolver. Order matters — a Form-6 letter says "Tingkatan
    Enam", a matriculation letter "Matrikulasi", and those win over a stray 'diploma'."""
    t = f"{programme} {institution}".lower()
    if any(k in t for k in ('tingkatan enam', 'tingkatan 6', 'form 6', 'form six', 'stpm')):
        return 'stpm'
    if 'matrikulasi' in t or 'matriculation' in t:
        return 'matric'
    if 'asasi' in t or 'foundation' in t:
        return 'asasi'
    if 'pismp' in t or 'perguruan' in t:
        return 'pismp'
    if 'diploma' in t or 'sijil' in t:
        return 'diploma'
    if any(k in t for k in ('ijazah', 'sarjana muda', 'bachelor', 'degree')):
        return 'degree'
    # A bare polytechnic name with no programme keyword (an occasional extraction quirk, #125):
    # a polytechnic's default level is a diploma. LAST — so an "Ijazah/Asasi … @ Politeknik" is
    # still caught by the specific branches above.
    if 'politeknik' in t or 'polytechnic' in t:
        return 'diploma'
    return ''


def is_pre_u(pathway_type: str) -> bool:
    """Pre-U pathways store ``pre_u_*`` fields rather than a catalogue ``course_id``."""
    return pathway_type in ('stpm', 'matric')


# One coarse pathway-TYPE family, collapsing the several vocabularies that name a pathway — the offer's
# DETECTED type (detect_pathway_type: diploma/degree/…), the stored chosen_pathway code (poly/university/…
# — the 8 apply-form codes) AND legacy display labels (Matriculation/Foundation) — so a mere rename is
# never mistaken for a switch. The three pre-U tracks (stpm/matric/asasi) and pismp are distinct
# families; ALL of {diploma, poly, degree, university} collapse to ONE 'tertiary' family — a student on
# the university/UA track who receives a university DIPLOMA (or vice-versa) has NOT switched pathway
# (data 2026-07-18: 9 of 10 flagged rows were this benign case), and any institution-level difference
# is caught by the within-family clash (Case 3), not the type switch. Only a cross-FAMILY change is a
# genuine TYPE switch (STPM→PISMP counts; university→diploma does not). An UNRECOGNISED value → '' so it
# can never spuriously differ from a known family (the caller requires BOTH sides to resolve to a
# known family before treating it as a switch).
_PATHWAY_FAMILY = {
    'stpm': 'stpm',
    'matric': 'matric', 'matriculation': 'matric', 'matrikulasi': 'matric',
    'asasi': 'asasi', 'foundation': 'asasi',
    'pismp': 'pismp',
    'diploma': 'tertiary', 'poly': 'tertiary', 'polytechnic': 'tertiary', 'politeknik': 'tertiary',
    'degree': 'tertiary', 'university': 'tertiary', 'universiti': 'tertiary', 'ua': 'tertiary',
    'ijazah': 'tertiary',
}


def pathway_family(pathway_type: str) -> str:
    """Coarse pathway-TYPE family for a type/label/code — pre-U (stpm/matric/asasi) and pismp are each
    distinct; diploma/poly/degree/university all collapse to 'tertiary' (a level nuance within the same
    track is not a pathway switch). Matriculation≡matric. An unrecognised value → '' (so it never
    spuriously differs from a known family)."""
    return _PATHWAY_FAMILY.get((pathway_type or '').strip().lower(), '')


def parse_stpm_stream(programme: str) -> str:
    """Read the STPM bidang off an offer programme string, or ''. Many Form-6 letters
    print only "Tingkatan Enam Semester 1" (no stream) → '' (leave the track open, never
    guess); some print "(Sains Sosial)" / "(SAINS)" which we map to the apply-form codes."""
    t = (programme or '').lower()
    if 'sains sosial' in t or 'social science' in t or 'sains_sosial' in t:
        return 'sains_sosial'
    if 'sains' in t or 'science' in t:
        return 'sains'
    return ''


def parse_matric_track(programme: str) -> str:
    """Map a Matrikulasi offer's programme text to one of the four KPM tracks
    (``sains`` | ``kejuruteraan`` | ``sains_komputer`` | ``perakaunan``), or '' if the
    letter doesn't state it (many just say "Program Matrikulasi Kementerian Pendidikan").
    Order matters — the specific tracks are checked before the generic 'sains'."""
    t = (programme or '').lower()
    if any(k in t for k in ('perakaunan', 'akaun', 'accounting', 'accountancy')):
        return 'perakaunan'
    if any(k in t for k in ('sains komputer', 'computer science', 'computing', 'komputer')):
        return 'sains_komputer'
    if any(k in t for k in ('kejuruteraan', 'engineering')):
        return 'kejuruteraan'
    if 'sains' in t or 'science' in t:
        return 'sains'
    return ''


# Canonical pre-U course label — the specific stream/jurusan lives in pre_u_track, so the
# course name itself is uniform across all matric / all STPM rows.
_CANONICAL_PRE_U_COURSE = {'matric': 'Program Matrikulasi', 'stpm': 'Tingkatan Enam'}


def canonical_pre_u_course(pathway_type: str) -> str:
    """The standardised display course name for a pre-U pathway — 'Program Matrikulasi'
    (matric) / 'Tingkatan Enam' (STPM), or '' for anything else. The specific stream/jurusan
    is carried by pre_u_track, so the course name itself is uniform."""
    return _CANONICAL_PRE_U_COURSE.get((pathway_type or '').strip().lower(), '')


# SPM elective subjects that mark a science stream (backend grade keys).
_SCIENCE_ELECTIVES = {'phy', 'chem', 'bio', 'addmath', 'add_math'}


def infer_stpm_bidang(grades, stream_subjects) -> str:
    """Default STPM bidang from the SPM subject profile when neither the offer nor the
    apply form stated it: a science-elective cluster (physics/chemistry/biology/add-maths)
    → ``'sains'``, otherwise ``'sains_sosial'``. A sensible, reviewer-overridable default —
    never authoritative (the bidang is ultimately the student's choice)."""
    subs = set()
    if isinstance(stream_subjects, (list, tuple)):
        subs |= {str(s).lower() for s in stream_subjects}
    if isinstance(grades, dict):
        subs |= {str(k).lower() for k in grades}
    return 'sains' if subs & _SCIENCE_ELECTIVES else 'sains_sosial'


# SPM vernacular subject keys that mark a PISMP school stream (aliran). A PISMP offer letter never
# states the aliran, so this is a picker DEFAULT only (the student confirms it) — never authoritative.
_TAMIL_SUBJECTS = {'bahasa_tamil', 'b_tamil', 'lit_tamil'}
_CHINESE_SUBJECTS = {'bahasa_cina', 'b_cina', 'lit_cina'}


def infer_pismp_aliran(profile) -> str:
    """Best-guess PISMP school stream from the student's SPM vernacular subject: Bahasa Tamil →
    'sjkt', Bahasa Cina → 'sjkc', else 'sk'. A picker DEFAULT the student confirms (the offer letter
    doesn't state the aliran), never authoritative. Safe on a missing/blank profile → 'sk'. Returns
    the LOWERCASE aliran code the FE picker + storage use (PISMP_ALIRAN_ORDER: sk/sjkc/sjkt/khas)."""
    subs = set()
    grades = getattr(profile, 'grades', None)
    if isinstance(grades, dict):
        subs |= {str(k).lower() for k in grades}
    ss = getattr(profile, 'stream_subjects', None)
    if isinstance(ss, (list, tuple)):
        subs |= {str(s).lower() for s in ss}
    if subs & _TAMIL_SUBJECTS:
        return 'sjkt'
    if subs & _CHINESE_SUBJECTS:
        return 'sjkc'
    return 'sk'


def _name_aligns(a: set, b: set) -> bool:
    """True when one name's distinctive tokens are a SUBSET of the other's — i.e. one
    name contains the other. Stricter than a bare intersection, so a single shared
    generic-ish token (e.g. 'malaysia') can't force a false match, while offer-letter
    code prefixes ("DAC - DIPLOMA PERAKAUNAN" → {dac, perakaunan}) still align with the
    catalogue ("Diploma Perakaunan" → {perakaunan}) because catalogue ⊆ offer."""
    if not a or not b:
        return False
    return a <= b or b <= a


def catalogue_institution(course_id: str, hint: str = '') -> str:
    """The recommender catalogue's canonical institution name for a course_id — used ONLY to
    iron out OCR variants of the SAME institution ("…(POLITEKNIK PREMIER)", address tails,
    casing). Returns a catalogue name only when it ALIGNS with ``hint`` (the currently
    recorded institution) — i.e. it's the same place, just cleaner. It deliberately will NOT
    swap one institution for a *different* one: a catalogue institution that conflicts with a
    recorded institution signals a wrong/imprecise course_id (a data-integrity issue to
    surface), not an OCR variant to silently overwrite. With no hint it can't verify → ''."""
    from apps.courses.models import CourseInstitution
    names = [n for n in CourseInstitution.objects.filter(course_id=course_id)
             .values_list('institution__institution_name', flat=True) if n]
    if not names:
        return ''
    hj = distinctive_tokens(hint)
    hn = _norm_inst_name(hint)
    # A match is: distinctive tokens align (same place, cleaner) OR names identical modulo a
    # parenthetical/casing (generic-only names like UKM). Require a UNIQUE match — a course
    # with many campuses (e.g. an STPM bidang has ~250 schools) must not return a wrong one
    # on an ambiguous hint; 0 or >1 → '' (don't guess / surface as a conflict).
    matches = {n for n in names
               if (hj and _name_aligns(hj, distinctive_tokens(n))) or (hn and _norm_inst_name(n) == hn)}
    return next(iter(matches)) if len(matches) == 1 else ''


def poly_institution_from_live_offer(application):
    """READ-TIME disambiguation of a POLY diploma's campus from the student's latest LIVE
    genuine offer — the campus source of last resort for a multi-campus course whose stored
    ``chosen_programme.institution`` is blank (the selection tree offers only a programme, so the
    OFFER is the sole campus source — owner 2026-07-17). Mirrors the catalogue-validated logic the
    write-side merge uses (``services.autofill_pathway_from_offer``) so display can never go stale
    waiting for a re-run. POLY-scoped; returns the canonical catalogue campus, or '' when the pick
    isn't a poly diploma / there's no offer / the offer names no valid campus of that course. A
    non-blank stored institution is the caller's to protect — this only ever RESOLVES, never
    overwrites. Read-only."""
    from .models import ApplicantDocument
    from .pathway_engine import student_offer_check
    cp = application.chosen_programme if isinstance(getattr(application, 'chosen_programme', None), dict) else {}
    cid = (cp.get('course_id') or '').strip()
    if not cid.startswith('POLY-'):   # poly diplomas only (never a degree; owner scope)
        return ''
    offer = (ApplicantDocument.objects.filter(
                application=application, doc_type='offer_letter', superseded_at__isnull=True)
             .order_by('-uploaded_at').first())
    if offer is None:
        return ''
    chk = student_offer_check(offer)
    if chk.get('name') == 'mismatch' or chk.get('ic') == 'mismatch':
        return ''   # not this student's letter — never adopt its campus
    hint = (chk.get('institution') or '').strip()
    # catalogue_institution validates the offer's campus IS one of this course's campuses
    # (unique match) and returns the canonical catalogue casing — so a wrong/imprecise campus
    # yields '' rather than a contradictory fill.
    return catalogue_institution(cid, hint) if hint else ''


# Pre-U virtual course ids in the recommender catalogue (the /course/<slug> pages) — the
# single source of truth for matric colleges / STPM schools (linked via CourseInstitution).
PREU_COURSE_SLUG = {
    ('matric', 'sains'): 'matric-sains',
    ('matric', 'kejuruteraan'): 'matric-kejuruteraan',
    ('matric', 'sains_komputer'): 'matric-sains-komputer',
    ('matric', 'perakaunan'): 'matric-perakaunan',
    ('stpm', 'sains'): 'stpm-sains',
    ('stpm', 'sains_sosial'): 'stpm-sains-sosial',
}


def preu_course_id(pathway: str, track: str) -> str:
    """The recommender virtual course_id for a pre-U pathway+track (e.g. matric + perakaunan →
    'matric-perakaunan'), or '' — used to reach its catalogue institution list."""
    return PREU_COURSE_SLUG.get(((pathway or '').strip().lower(), (track or '').strip().lower()), '')


_SCHOOL_POSTCODE = re.compile(r'\b\d{5}\b')
_SCHOOL_ACRONYM_EXPAND = {
    'SMK': 'Sekolah Menengah Kebangsaan',
    'SMJK': 'Sekolah Menengah Jenis Kebangsaan',
    'SMKA': 'Sekolah Menengah Kebangsaan Agama',
    'KTE': 'Kolej Tingkatan Enam',
    'SM': 'Sekolah Menengah',
}


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


# Acronyms in a programme name that must stay UPPER-CASE when a shouty (all-caps) offer
# programme is re-cased. (Parenthesised short tokens like "(PISMP)" are also kept upper by the
# length heuristic below, so this is just the un-parenthesised / borderline set.)
_PROGRAMME_ACRONYMS = {
    'PISMP', 'SJKT', 'SJKC', 'SK', 'SR', 'IT', 'ICT', 'TVET', 'STEM',
    'UKM', 'UM', 'USM', 'UPM', 'UTM', 'UIA', 'UPSI', 'UMS', 'UNIMAS', 'IPG', 'UiTM',
}
# Connectors that stay lower-case in a Malay/English programme title (never the first word).
_PROGRAMME_CONNECTORS = {
    'dan', 'dengan', 'dari', 'untuk', 'di', 'ke', 'dalam', 'serta',
    'of', 'and', 'the', 'in', 'for', 'with',
}


def _recase_programme_token(tok: str, *, first: bool) -> str:
    """Re-case ONE whitespace token of a shouty programme name, preserving acronyms, short
    parentheticals and punctuation. A pure-punctuation token (``#``, ``&``) passes through."""
    core = tok.strip('()[].,#/-')  # the alphabetic heart, minus surrounding punctuation
    if not core:
        return tok
    if core.upper() in _PROGRAMME_ACRONYMS:
        new = core.upper()
    elif tok[:1] == '(' and tok[-1:] == ')' and len(core) <= 6:
        new = core.upper()  # a short parenthesised token is an acronym, e.g. "(PISMP)", "(SK)"
    elif (not first) and core.lower() in _PROGRAMME_CONNECTORS:
        new = core.lower()
    else:
        new = core[:1].upper() + core[1:].lower()
    return tok.replace(core, new, 1)  # keep the original surrounding punctuation


def title_case_programme(name: str) -> str:
    """Rescue a programme name that arrived SHOUTY (fully upper-case) from an offer letter —
    e.g. "PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)" → "Program Ijazah Sarjana Muda
    Perguruan (PISMP)". Preserves acronyms ((PISMP)/SJKT/UKM…), connectors (dan/of…) and
    punctuation (#, &). A name that is ALREADY mixed-case is returned UNCHANGED byte-for-byte:
    we only rescue a fully-uppercase string, never re-case a deliberately-styled one (e.g.
    "Diploma Teknologi Maklumat (Software & App Development)"). Idempotent."""
    s = (name or '').strip()
    letters = [c for c in s if c.isalpha()]
    if not letters or any(c.islower() for c in letters):
        return s
    return ' '.join(_recase_programme_token(t, first=(i == 0)) for i, t in enumerate(s.split()))


def resolve_catalogue_course(programme: str, institution: str):
    """Best-effort canonical match for a TERTIARY offer. Returns
    ``{course_id, course_name, institution}`` ONLY when exactly one catalogue course —
    offered at an institution whose name aligns with the offer's — has a programme name
    that aligns with the offer's. Any ambiguity (zero or >1) → ``None`` (caller falls back
    to labels). Conservative by design: a wrong ``course_id`` is worse than no id."""
    from apps.courses.models import Institution, CourseInstitution

    pj = distinctive_tokens(programme)
    ij = distinctive_tokens(institution)
    if not pj or not ij:
        return None

    inst_ids = [
        inst.institution_id for inst in Institution.objects.all()
        if _name_aligns(ij, distinctive_tokens(inst.institution_name))
    ]
    if not inst_ids:
        return None

    uniq = {}
    for off in (CourseInstitution.objects
                .filter(institution_id__in=inst_ids)
                .select_related('course', 'institution')):
        if _name_aligns(pj, distinctive_tokens(off.course.course)):
            uniq[off.course.course_id] = {
                'course_id': off.course.course_id,
                'course_name': off.course.course,
                'institution': off.institution.institution_name,
            }
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None


def offer_is_resolvable(programme: str, institution: str) -> bool:
    """True when an offer pins a SPECIFIC pathway we can fill into the course tree by itself: a
    pre-U offer whose stream/jurusan parses (stpm/matric), or a tertiary offer that resolves to a
    UNIQUE catalogue ``course_id``. False = AMBIGUOUS — e.g. a PISMP offer that names the campus but
    NOT the aliran (SK / SJKT / SJKC), so the student must pick their exact course on the profile
    page (owner 2026-07-15). Pure (bar the catalogue read inside ``resolve_catalogue_course``)."""
    ptype = detect_pathway_type(programme, institution)
    if is_pre_u(ptype):
        track = parse_matric_track(programme) if ptype == 'matric' else parse_stpm_stream(programme)
        return bool(track)
    match = resolve_catalogue_course(programme, institution)
    return bool(match and match.get('course_id'))
