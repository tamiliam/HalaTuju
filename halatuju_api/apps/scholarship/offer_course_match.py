"""An offer letter → ONE catalogue course, across BOTH catalogues (offer realignment, 2026-10-31).

`offer_pathway.resolve_catalogue_course` is a thin caller of `match_offer_course` below. Until this
sprint the matcher searched only `CourseInstitution` — the post-SPM catalogue (asasi, diploma) — so
no "Sarjana Muda" letter could ever resolve: the 1,112 post-STPM degrees live in `StpmCourse`, one
university each. `_campus_rows` already reads both tables; this follows it.

The contract is unchanged: a course comes back ONLY when exactly one qualifies, because a wrong
`course_id` is worse than none. The TD-332 / TD-150 refusals (`catalogue_levels`) all still apply.

What real letters print, and how each is read (live strings, 2026-10-31):

* **Our own course code** — "Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001" (UNIMAS). A code
  that exists in either catalogue wins, unless the letter names a DIFFERENT institution.
* **UiTM's local code in front** — "BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)": dropped.
* **A faculty run on after the name** — "... (KEPUJIAN) FAKULTI SAINS SUKAN DAN ...": cut there.
* **The catalogue's own decorations** — a trailing " #" (the tokeniser drops it) and a campus
  parenthetical, "Diploma Pembangunan Manusia (Kampus Bintulu, Sarawak)": not part of the name.
* **A hostel in the institution line** — "KOLEJ SRI RAJANG", "KOLEJ KEDIAMAN PERWIRA - DEWAN SULTAN
  IBRAHIM": the university is in the ISSUER. `letter_place` decides when the issuer may stand in for
  the institution line, and every reader and writer of the letter's place calls it.
* **UiTM's campus line** — "UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU" names the university only by
  its ACRONYM, so an institution's acronym counts as naming it.
"""
from __future__ import annotations

import re

from .catalogue_levels import (
    course_levels, names_a_specialisation_the_letter_does_not, private_arm_letter)
from .offer_pathway import (
    PREU_COURSE_SLUG, _ALIRAN_SUFFIX_RE, _campus_rows, _name_aligns, _names_another_institution,
    _norm_inst_name, _refers_to_campus, detect_pathway_type)
from .pathway_engine import distinctive_tokens
from .school_names import school_name_core

#: A UPU programme code, the shape BOTH catalogues key every university course by ("UW6526001").
COURSE_CODE_RE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z]{2}\d{7})(?![A-Za-z0-9])')
#: UiTM's own short programme code in front of the name ("BA272 ", "SR241 ").
_LOCAL_CODE_RE = re.compile(r'^\s*[A-Z]{2,3}\d{3}\s+')
#: A faculty or school line the letter runs on after the programme.
_FACULTY_TAIL_RE = re.compile(r'\s(?:FAKULTI|FACULTY|KULLIYYAH|PUSAT PENGAJIAN)\b.*$', re.I | re.S)
#: The catalogue's campus parenthetical.
_CAMPUS_PAREN_RE = re.compile(r'\((?:kampus|cawangan|campus)\b[^)]*\)', re.I)
_TERTIARY = ('asasi', 'pismp', 'diploma', 'degree')


def letter_programme(programme: str) -> str:
    """The programme as a NAME: our code, UiTM's code, a dangling " - " and a faculty tail removed."""
    s = COURSE_CODE_RE.sub(' ', programme or '')
    s = _FACULTY_TAIL_RE.sub('', _LOCAL_CODE_RE.sub('', s))
    return re.sub(r'[\s\-–—]+$', '', s).strip()


def catalogue_name(name: str) -> str:
    """A catalogue course name without its campus parenthetical."""
    return ' '.join(_CAMPUS_PAREN_RE.sub(' ', name or '').split())


def letter_place(course_id: str, institution: str, issuer: str = '') -> str:
    """WHERE the letter says the student is going, for ``course_id`` — the institution line, or the
    ISSUER standing in for it. THE one definition: `institution_agreement`,
    `offer_contradicts_course_institution` and the writer `sync_institution_from_catalogue` all read
    the letter through it (the #48 regression was a writer and a reader drifting apart).

    University letters often put a hostel in the institution line ("KOLEJ SRI RAJANG", "Kolej
    Cempaka") and the university in the letterhead. The issuer stands in only when (a) the
    institution line names NO campus of the course, (b) that line does not EXACTLY name another
    catalogue institution — so a polytechnic or a private college against a public course stays a
    clash (#11, #64, #86, #93, #113) — and (c) the issuer itself names a campus of the course."""
    inst, iss = (institution or '').strip(), (issuer or '').strip()
    if not iss or not (course_id or '').strip():
        return inst
    rows = _campus_rows(course_id)
    if not rows:
        return inst
    if inst and (any(_refers_to_campus(n, a, inst) for n, a in rows)
                 or _names_another_institution('', '', inst)):
        return inst
    return iss if any(_refers_to_campus(n, a, iss) for n, a in rows) else inst


def is_bumiputera_only(course_id: str) -> bool:
    """The COURSE's own Bumiputera-only flag, in whichever catalogue holds it. Never the student's
    answer, which is course-guide only (decisions.md 2026-10-28).

    ⚠ The ONE scholarship-side reader of the course flag, by the owner's realignment rule of
    2026-10-31 (decisions.md). `test_bumiputera_blind` allows this file by path and pins that the
    flag is read here and nowhere else; it is never used to filter what a student is shown."""
    from apps.courses.models import CourseRequirement, StpmRequirement
    cid = (course_id or '').strip()
    return bool(cid) and (
        CourseRequirement.objects.filter(course_id=cid, req_bumiputera=True).exists()
        or StpmRequirement.objects.filter(course_id=cid, req_bumiputera=True).exists())


def match_offer_course(programme: str, institution: str, issuer: str = ''):
    """``{course_id, course_name, institution}`` for the ONE catalogue course the letter names, else
    None. A printed course code first; then the name, at the institutions the institution line
    names, or — when that finds no course and the line names no catalogue institution — at the
    institutions the issuer names. ``institution`` is the catalogue's own spelling."""
    if private_arm_letter(programme, f'{institution or ""} {issuer or ""}'):
        return None                                 # the issuer may be the only line naming SATU
    coded = _printed_course(programme, institution, issuer)
    if coded is not None:
        return coded or None                        # {} = the code names another place: no match
    name = letter_programme(programme)
    pj = distinctive_tokens(name)
    if not pj:
        return None
    ltype = detect_pathway_type(name, '') or detect_pathway_type(name, institution)
    hits = _named_courses(pj, ltype, _institutions(institution, contained=False))
    if not hits and (issuer or '').strip() and not _names_another_institution('', '', institution):
        hits = _named_courses(pj, ltype, _institutions(issuer, contained=True))
    return next(iter(hits.values())) if len(hits) == 1 else None


def _printed_course(programme, institution, issuer):
    """The course a printed code names: its row, ``{}`` when the letter names another place, or
    None when no printed code is in either catalogue."""
    for code in dict.fromkeys(c.upper() for c in COURSE_CODE_RE.findall(programme or '')):
        row = _course_row(code, institution, issuer)
        if row is None:
            continue
        place = letter_place(code, institution, issuer)
        rows = _campus_rows(code)
        if place and not any(_refers_to_campus(n, a, place) for n, a in rows) \
                and _names_another_institution('', '', place):
            return {}
        return row
    return None


def _course_row(course_id, institution, issuer):
    from apps.courses.models import Course, StpmCourse
    stpm = StpmCourse.objects.filter(course_id=course_id).values_list('course_name', 'university').first()
    if stpm:
        return {'course_id': course_id, 'course_name': stpm[0], 'institution': (stpm[1] or '').strip()}
    name = Course.objects.filter(course_id=course_id).values_list('course', flat=True).first()
    if name is None:
        return None
    campuses = {n.strip() for n, _a in _campus_rows(course_id) if (n or '').strip()}
    if len(campuses) > 1:
        place = letter_place(course_id, institution, issuer)
        named = {n.strip() for n, a in _campus_rows(course_id) if place and _refers_to_campus(n, a, place)}
        campuses = named if len(named) == 1 else set()
    return {'course_id': course_id, 'course_name': name,
            'institution': next(iter(campuses)) if len(campuses) == 1 else ''}


def _institutions(hint, *, contained):
    """[(institution_id, name)] the hint names: distinctive words (either way round, or — for an
    issuer, ``contained`` — the institution's own words inside the hint), the bracket-stripped name,
    or the acronym as a whole word."""
    from apps.courses.models import Institution
    hint = school_name_core(hint or '')
    ht, hn = distinctive_tokens(hint), _norm_inst_name(hint)
    if not ht and not hn:
        return []
    out = []
    for iid, name, acr in Institution.objects.values_list('institution_id', 'institution_name', 'acronym'):
        nt = distinctive_tokens(name)
        words = bool(nt) and (nt <= ht if contained else _name_aligns(ht, nt))
        acr = (acr or '').strip().lower()
        if words or (hn and _norm_inst_name(name) == hn) or (acr and acr in ht):
            out.append((iid, name))
    return out


def _named_courses(pj, ltype, institutions):
    """{course_id: row} for every course at ``institutions`` whose name the letter's words name."""
    from apps.courses.models import CourseInstitution, StpmCourse
    if not institutions:
        return {}
    ids = [iid for iid, _n in institutions]
    tertiary = ltype in _TERTIARY
    uniq = {}
    offers = CourseInstitution.objects.filter(institution_id__in=ids)
    if tertiary:
        offers = offers.exclude(course_id__in=PREU_COURSE_SLUG.values())
    for off in offers.select_related('course', 'institution'):
        if tertiary and (fams := course_levels(off.course)) and ltype not in fams:
            continue
        if _names(pj, off.course.course):
            uniq[off.course.course_id] = {'course_id': off.course.course_id,
                                          'course_name': off.course.course,
                                          'institution': off.institution.institution_name}
    if ltype not in ('degree', ''):
        return uniq                                # StpmCourse holds degrees only
    for cid, cname, uni in StpmCourse.objects.filter(institution_id__in=ids).values_list(
            'course_id', 'course_name', 'university'):
        if _names(pj, cname):
            uniq[cid] = {'course_id': cid, 'course_name': cname, 'institution': (uni or '').strip()}
    return uniq


def _names(pj, course_name):
    """Do the letter's words name this catalogue course? Aligned, and not a specialisation the
    letter never states (TD-150); the PISMP aliran suffix is not a specialisation."""
    base = catalogue_name(course_name)
    return (_name_aligns(pj, distinctive_tokens(base))
            and not names_a_specialisation_the_letter_does_not(
                pj, distinctive_tokens(_ALIRAN_SUFFIX_RE.sub('', base))))
