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

from .pathway_engine import _distinctive_tokens


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


def _name_aligns(a: set, b: set) -> bool:
    """True when one name's distinctive tokens are a SUBSET of the other's — i.e. one
    name contains the other. Stricter than a bare intersection, so a single shared
    generic-ish token (e.g. 'malaysia') can't force a false match, while offer-letter
    code prefixes ("DAC - DIPLOMA PERAKAUNAN" → {dac, perakaunan}) still align with the
    catalogue ("Diploma Perakaunan" → {perakaunan}) because catalogue ⊆ offer."""
    if not a or not b:
        return False
    return a <= b or b <= a


def resolve_catalogue_course(programme: str, institution: str):
    """Best-effort canonical match for a TERTIARY offer. Returns
    ``{course_id, course_name, institution}`` ONLY when exactly one catalogue course —
    offered at an institution whose name aligns with the offer's — has a programme name
    that aligns with the offer's. Any ambiguity (zero or >1) → ``None`` (caller falls back
    to labels). Conservative by design: a wrong ``course_id`` is worse than no id."""
    from apps.courses.models import Institution, CourseInstitution

    pj = _distinctive_tokens(programme)
    ij = _distinctive_tokens(institution)
    if not pj or not ij:
        return None

    inst_ids = [
        inst.institution_id for inst in Institution.objects.all()
        if _name_aligns(ij, _distinctive_tokens(inst.institution_name))
    ]
    if not inst_ids:
        return None

    uniq = {}
    for off in (CourseInstitution.objects
                .filter(institution_id__in=inst_ids)
                .select_related('course', 'institution')):
        if _name_aligns(pj, _distinctive_tokens(off.course.course)):
            uniq[off.course.course_id] = {
                'course_id': off.course.course_id,
                'course_name': off.course.course,
                'institution': off.institution.institution_name,
            }
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None
