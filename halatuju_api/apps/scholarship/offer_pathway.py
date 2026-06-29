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
    return ''


def is_pre_u(pathway_type: str) -> bool:
    """Pre-U pathways store ``pre_u_*`` fields rather than a catalogue ``course_id``."""
    return pathway_type in ('stpm', 'matric')


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
