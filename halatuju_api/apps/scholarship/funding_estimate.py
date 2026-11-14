"""
Check 2 — deterministic per-pathway funding-need ESTIMATE for a B40 student.

Pre-college students can't reliably self-report what they'll need, so we estimate the
realistic **monthly shortfall a top-up assistance would fill, AFTER government coverage
(allowance) and any PTPTN loan**, keyed on the student's pathway, times the typical
programme length. The student's funding checkboxes stay a *signal*; this estimate is the
baseline for award sizing + the officer cockpit.

Figures (RM) are owner-validated and live in ``docs/scholarship/funding-estimate-basis.md``
— keep the two in sync. Pure + no LLM.

Post-SPM scope (decision 1, owner 2026-11-07: these figures do not change): students can't enter a
bachelor's degree directly out of SPM (the one exception, PISMP, is a 5-year degree-level
teacher-training programme and has its own category). So the post-SPM pathway "university" means a
**public-university (Universiti Awam) DIPLOMA**, not a degree.

Degree scope (owner decisions 2-6, 2026-11-07): the Sabah / Ipoh gifts admit STPM-level students, and
the offer realignment stores an STPM degree as 'university'. A DEGREE-BOUND student
(`results_route.degree_bound`, checked FIRST in `classify_pathway`) is estimated as 'degree': living
RM1,200 x 10 study months a year, plus a flat RM2,900/yr fee, less the PTPTN IPTA bachelor maximum
for the course's stream, times the years LEFT. Figures: owner's SLS Model.xlsx.

MARA diplomas (decision 9): Kolej Profesional MARA (`OP4...` ids, the MARA-BPT division pick) and the
MARA skills campuses' TVET Diplomas take the UA-diploma figures under their own key 'mara_diploma'
(MARA students borrow from MARA, not PTPTN). UiTM diplomas stay 'university'.

Skills institutes (decisions 10-12): IKBN / IKTBN 'ilkbs' (free tuition and hostel, ~RM100/month
allowance); ILJTM 'iljtm', Kolej Komuniti 'kkom', a MARA skills certificate 'mara_cert' and every
other TVET course 'tvet' (free tuition and hostel, no allowance assumed: one shared spec), each with
its length read from the catalogue's semesters. No estimate is left only for a genuinely
unknown / undecided pathway: no pathway, no readable programme, or several pathways considered.
"""
from __future__ import annotations

import re

# pathway value (chosen_pathway / intended_pathway / pathways_considered) → estimate
# category. The category IS the pathway key for the pathways we estimate; aliases
# fold in. 'mara' is absent on purpose: its programme decides diploma vs certificate
# (`_mara_diploma`, `_tvet_category`, and the 'mara_cert' fallback in `classify_pathway`).
_PATHWAY_MAP = {
    'matric': 'matric', 'matrik': 'matric', 'matrikulasi': 'matric',
    'stpm': 'stpm',
    'asasi': 'asasi', 'foundation': 'asasi',
    'university': 'university', 'degree': 'university',  # post-SPM "university" = UA diploma
    'poly': 'poly', 'politeknik': 'poly',
    'pismp': 'pismp', 'ipg': 'pismp',
    'ilkbs': 'ilkbs',   # decision 10 (2026-11-07): IKBN / IKTBN
    'iljtm': 'iljtm', 'kkom': 'kkom',   # decision 11 (2026-11-07)
    'tvet': 'tvet', 'tvet_other': 'tvet',   # decision 12 (2026-11-07)
}

# category → estimate. 'monthly' = est. RM monthly SHORTFALL a top-up would fill (living
# costs − government allowance − PTPTN loan), rounded. 'months' = typical programme
# length. 'variable' = cost varies a lot by institution/field → show a caveat.
# 'practical' = has an internship/practical term that may add travel.
PATHWAY_ESTIMATES = {
    'stpm':       {'monthly': 500, 'months': 18, 'variable': False, 'practical': False},
    'matric':     {'monthly': 200, 'months': 10, 'variable': False, 'practical': False},
    'asasi':      {'monthly': 700, 'months': 10, 'variable': True,  'practical': False},
    'poly':       {'monthly': 120, 'months': 36, 'variable': False, 'practical': True},
    'university': {'monthly': 220, 'months': 30, 'variable': True,  'practical': True},
    'pismp':      {'monthly': 180, 'months': 60, 'variable': False, 'practical': True},
    # Decision 10 (owner 2026-11-07; figure the lead's derivation, owner may adjust): IKBN / IKTBN
    # teach and house free with a ~RM100/month allowance, Matrikulasi's shape. Matrikulasi's basis
    # implies ~RM450/month living (RM200 shortfall + RM250 BSHP), so 450 - 100 = RM350. 'months' is
    # the fallback only: the course's own semesters x 6 decide (`_semester_months`).
    'ilkbs':      {'monthly': 350, 'months': 24, 'variable': False, 'practical': False},
}
# Decisions 11-12 (owner 2026-11-07; same derivation, owner may adjust): ILJTM, Kolej Komuniti, a
# MARA skills certificate and every other TVET course teach and house free with NO allowance
# assumed: ~RM450/month living − 0. ONE spec; the keys differ only so the cockpit label can.
_TVET_SPEC = {'monthly': 450, 'months': 24, 'variable': False, 'practical': False}
for _key in ('iljtm', 'kkom', 'mara_cert', 'tvet'):
    PATHWAY_ESTIMATES[_key] = dict(_TVET_SPEC)
# Decision 9 (owner 2026-11-07): a MARA diploma takes the UA-diploma figures exactly, under its own
# key so the cockpit can name the MARA education loan instead of PTPTN. One home for the numbers.
PATHWAY_ESTIMATES['mara_diploma'] = dict(PATHWAY_ESTIMATES['university'])

#: Decisions 10-11: these pathways' length is the catalogue's `courses.semesters` x 6; no course /
#: no semesters → the spec's 'months' (24).
SEMESTER_LENGTH_PATHWAYS = ('ilkbs', 'iljtm', 'kkom', 'mara_cert', 'tvet')
MONTHS_PER_SEMESTER = 6

# ── Degree (owner decisions 2-6, 2026-11-07; source: owner's SLS Model.xlsx) ─────────────────────
#: Decision 2: living costs at university, RM per study month, and study months per year.
DEGREE_LIVING_MONTHLY = 1200
DEGREE_STUDY_MONTHS_PER_YEAR = 10
#: Decision 3: one flat fee, RM/yr (the SLS UM IPTA bachelor mean of RM2,100-3,400). `variable` caveat.
DEGREE_FEE_PER_YEAR = 2900
#: Decision 4: PTPTN IPTA bachelor maximum, RM/yr, by `stpm_courses.stream`. Any other stream
#: (no catalogue id, or the catalogue's 'both') → arts: the smaller loan, the larger need.
DEGREE_PTPTN_BY_STREAM = {'arts': 6180, 'science': 6650}
DEGREE_DEFAULT_STREAM = 'arts'
#: Decision 5: programme length in years. By NAME first (medicine / dentistry 5, education 4), then
#: by stream (arts 3, science 4), else 4. Medicine and dentistry are matched as the qualification's
#: own words ("Doktor Perubatan", "Sarjana Muda Perubatan", "Pembedahan Pergigian"), so an allied
#: degree that merely names the field ("Pengimejan Perubatan", "Bioperubatan") keeps its stream.
DEGREE_YEARS_BY_NAME = (
    (r'doktor perubatan|sarjana muda perubatan|doktor pergigian|pembedahan pergigian'
     r'|medicine|dentistry|dental surgery', 5),
    (r'pendidikan|education', 4),
)
DEGREE_YEARS_BY_STREAM = {'arts': 3, 'science': 4}
DEGREE_DEFAULT_YEARS = 4

# The UP_TVET programmes' TVET-<id_kursus> ids (Bumi Sprint F1) are read by their provider family,
# whatever their name says (`_tvet_category`). Before 2026-11-07 every kkom / ijtm / iljtm / ikbn /
# iktbn / ilkbs / tvet id was un-estimated; decisions 9-12 estimate them all.
_TVET_ID_PREFIX = 'tvet'
#: `course_pathway.course_pathway_type` families (`tvet_families.TVET_CATEGORY_PATHWAY`) with their
#: own key. MARA splits by level (decisions 9 / 12); any other family, or none, → 'tvet'.
_TVET_FAMILY_CATEGORY = {'ilkbs': 'ilkbs', 'iljtm': 'iljtm'}
# course_id prefixes that pin an estimate category.
_PROGRAMME_ID_PREFIXES = (
    ('poly', 'poly'),
    ('pismp', 'pismp'), ('ipg', 'pismp'),
    ('ikbn', 'ilkbs'), ('iktbn', 'ilkbs'), ('ilkbs', 'ilkbs'),
    ('kkom', 'kkom'), ('ijtm', 'iljtm'), ('iljtm', 'iljtm'),
)
#: Decision 9: Kolej Profesional MARA diplomas (MOHE-coded under MARA's education division).
_MARA_DIPLOMA_ID_PREFIX = 'op4'
#: A programme name that reads as a DIPLOMA (whole word; "Sijil" is a certificate and stays out).
_DIPLOMA_WORD = re.compile(r'(?<![a-z])diploma(?![a-z])')
# Ordered course_name keyword scan (first match wins). Specific pathways are checked
# before the generic 'diploma' (a non-Politeknik diploma = a public-university diploma).
_PROGRAMME_NAME_KEYWORDS = (
    ('matrikulasi', 'matric'),
    ('asasi', 'asasi'), ('foundation', 'asasi'),
    ('tingkatan enam', 'stpm'), ('stpm', 'stpm'),
    ('pismp', 'pismp'), ('perguruan', 'pismp'),
    ('politeknik', 'poly'),
    ('diploma', 'university'),
)


def _norm_strip_lower(value) -> str:
    """Strip and lower-case, and nothing else — punctuation and accents survive intact.

    Named for its exact rule by code health H7: this app had four `_norm`s and no two agreed.
    This is the gentlest, because it compares course-name and pathway substrings rather than
    people's names, and a course id like `poly-dip.01` must keep its punctuation to match.
    """
    return (value or '').strip().lower()


def _classify_programme(programme) -> str | None:
    """Infer the estimate category from a chosen programme (the actual course the student
    picked, e.g. auto-filled from their offer letter), or None if it can't be read or has
    an un-estimated cost structure. course_id prefix first, then a course_name scan."""
    if not isinstance(programme, dict):
        return None
    cid = _norm_strip_lower(programme.get('course_id'))
    if cid.startswith(_TVET_ID_PREFIX):
        return _tvet_category(str(programme.get('course_id')).strip())
    name = _norm_strip_lower(programme.get('course_name'))
    if 'kolej komuniti' in name:
        return 'kkom'       # decision 11 (2026-11-07); was no estimate
    # A foundation LEVEL named in the course (Asasi / Foundation) DEFINES the pathway even
    # when the course is hosted/coded under the Polytechnic system — JPPKK runs Asasi
    # programmes at a Politeknik, so the 'poly' course_id prefix below must NOT win over it.
    # (#11: "Asasi Teknologi Kejuruteraan" issued by JPPKK / Politeknik Ungku Omar is an
    # Asasi pathway, not a poly diploma — mis-classing it would size funding as poly ~RM4.3k
    # instead of asasi ~RM7k.) The genuineness scorer separately, and correctly, calls this
    # a 'polytechnic'-ISSUED document — that is the issuer family, not the programme level.
    if 'asasi' in name or 'foundation' in name:
        return 'asasi'
    for prefix, cat in _PROGRAMME_ID_PREFIXES:
        if cid.startswith(prefix):
            return cat
    for kw, cat in _PROGRAMME_NAME_KEYWORDS:
        if kw in name:
            return cat
    return None


def _catalogue_course(course_id):
    """(level, semesters) of an SPM-catalogue course, or (None, None). One query."""
    from apps.courses.models import Course
    row = Course.objects.filter(course_id=course_id).values_list('level', 'semesters').first()
    return row if row else (None, None)


def _tvet_category(course_id) -> str:
    """A `TVET-<id>` course by its provider family (`course_pathway.course_pathway_type`):
    ILKBS → 'ilkbs' and ILJTM → 'iljtm', any level (decisions 10-11); MARA at the Diploma level →
    'mara_diploma' (decision 9), at any other level → 'mara_cert' (decision 12); everything else
    ('tvet_other', a course whose campuses span families, a course not in the catalogue) → 'tvet'
    (decision 12)."""
    from apps.courses import public as courses_public
    family = courses_public.course_pathway_type(course_id)
    if family in _TVET_FAMILY_CATEGORY:
        return _TVET_FAMILY_CATEGORY[family]
    if family == 'mara':
        level = (_catalogue_course(course_id)[0] or '').strip().lower()
        return 'mara_diploma' if level == 'diploma' else 'mara_cert'
    return 'tvet'


def _mara_diploma(application) -> bool:
    """Decision 9, the cases a stored pathway code would otherwise beat (an `OP4...` course is
    stored 'university'): a Kolej Profesional MARA diploma id; or, with no catalogue id, a diploma
    named under MARA's education division or under the 'mara' code. Pure: no DB read (a MARA
    TVET diploma is read with its catalogue row in `_classify_programme`)."""
    prog = getattr(application, 'chosen_programme', None)
    if not isinstance(prog, dict):
        return False
    cid = _norm_strip_lower(prog.get('course_id'))
    if cid:
        return cid.startswith(_MARA_DIPLOMA_ID_PREFIX)
    if not _DIPLOMA_WORD.search(_norm_strip_lower(prog.get('course_name'))):
        return False
    from apps.courses.views_offerings import MARA_DIVISION
    return (str(prog.get('institution_id') or '').strip() == MARA_DIVISION
            or _norm_strip_lower(getattr(application, 'chosen_pathway', '')) == 'mara')


def classify_pathway(application) -> str:
    """The student's pathway category, or 'unknown'. Priority: DEGREE-BOUND (owner 2026-11-07:
    `results_route.degree_bound`, before any stored code, which can lag the course: #251's stale
    'stpm'), then a MARA diploma (decision 9: an `OP4...` course is stored 'university'), then a
    SURE chosen_pathway, then chosen_pathway/intended_pathway (older rows), then the chosen
    PROGRAMME (the concrete course — e.g. auto-filled from the offer letter — which pins the
    pathway type even when the pathway-type fields are blank), then a single pathways_considered
    entry."""
    from .results_route import degree_bound
    if degree_bound(application):
        return 'degree'
    if _mara_diploma(application):
        return 'mara_diploma'
    if _norm_strip_lower(getattr(application, 'chosen_pathway', '')) == 'mara':
        # Decision 12: a MARA pathway whose programme is not a diploma (a TVET certificate, or
        # nothing readable) is a MARA skills certificate; a readable programme still decides
        # (a MARA Asasi stays 'asasi', a TVET diploma 'mara_diploma').
        return _classify_programme(getattr(application, 'chosen_programme', None)) or 'mara_cert'
    if _norm_strip_lower(getattr(application, 'pathway_certainty', '')) == 'sure':
        cat = _PATHWAY_MAP.get(_norm_strip_lower(application.chosen_pathway))
        if cat:
            return cat
    # chosen_pathway even without the 'sure' flag (older rows), then intended_pathway.
    for raw in (getattr(application, 'chosen_pathway', ''), getattr(application, 'intended_pathway', '')):
        cat = _PATHWAY_MAP.get(_norm_strip_lower(raw))
        if cat:
            return cat
    # A concrete chosen programme beats a list of merely-considered pathways.
    cat = _classify_programme(getattr(application, 'chosen_programme', None))
    if cat:
        return cat
    considered = application.pathways_considered
    if isinstance(considered, list) and len(considered) == 1:
        cat = _PATHWAY_MAP.get(_norm_strip_lower(considered[0]))
        if cat:
            return cat
    return 'unknown'


def _round100(n) -> int:
    """Round to the nearest RM100 — these are ballpark estimates, not invoices."""
    return int(round(n / 100.0)) * 100


def _degree_stream(application) -> str:
    """The chosen degree's `stpm_courses.stream` ('arts' / 'science' / 'both'), or '' with no
    catalogue id. One query."""
    prog = getattr(application, 'chosen_programme', None)
    cid = str((prog if isinstance(prog, dict) else {}).get('course_id') or '').strip()
    if not cid:
        return ''
    from apps.courses.models import StpmCourse
    return (StpmCourse.objects.filter(course_id=cid).values_list('stream', flat=True).first() or '')


def _degree_years(name: str, stream: str) -> int:
    """Decision 5: the degree's length in years, by name keyword first, then by stream."""
    for pattern, years in DEGREE_YEARS_BY_NAME:
        if re.search(rf'(?<![a-z])(?:{pattern})(?![a-z])', name):
            return years
    return DEGREE_YEARS_BY_STREAM.get(stream, DEGREE_DEFAULT_YEARS)


def _years_done(application) -> int:
    """Decision 6: whole years already studied = cohort year − course-start year, at least 0;
    0 when either is unknown (then the full length is estimated)."""
    from .pathway_engine import course_start_year
    cohort_year = getattr(getattr(application, 'cohort', None), 'year', None)
    start = course_start_year(application)
    if not (cohort_year and start):
        return 0
    return max(0, cohort_year - start)


def _estimate_degree(application) -> dict:
    """Decisions 2-6: annual shortfall = living (1,200 x 10) + fee (2,900) − PTPTN (by stream),
    for the years LEFT (at least 1). Arts 8,720/yr (≈872 per study month), science 8,250."""
    stream = _degree_stream(application)
    loan_stream = stream if stream in DEGREE_PTPTN_BY_STREAM else DEGREE_DEFAULT_STREAM
    annual = (DEGREE_LIVING_MONTHLY * DEGREE_STUDY_MONTHS_PER_YEAR + DEGREE_FEE_PER_YEAR
              - DEGREE_PTPTN_BY_STREAM[loan_stream])
    prog = getattr(application, 'chosen_programme', None)
    name = _norm_strip_lower((prog if isinstance(prog, dict) else {}).get('course_name'))
    years = _degree_years(name, stream)
    done = _years_done(application)
    left = max(1, years - done)
    return {
        'pathway': 'degree',
        'known': True,
        'monthly': int(round(annual / DEGREE_STUDY_MONTHS_PER_YEAR)),
        'months': DEGREE_STUDY_MONTHS_PER_YEAR * left,
        'total': _round100(annual * left),
        'variable': True,
        'practical': False,
        'study_months': True,
        'continuing': done > 0,
    }


def _semester_months(application, default: int) -> int:
    """Decisions 10-12: an IKBN / IKTBN, ILJTM, Kolej Komuniti, MARA certificate or other TVET
    course's length = its catalogue semesters x 6; no catalogue course or no semesters → ``default`` (24)."""
    prog = getattr(application, 'chosen_programme', None)
    cid = str((prog if isinstance(prog, dict) else {}).get('course_id') or '').strip()
    semesters = _catalogue_course(cid)[1] if cid else None
    return semesters * MONTHS_PER_SEMESTER if semesters else default


def estimate_funding(application) -> dict:
    """The funding-need estimate for an application: the monthly shortfall, the typical
    programme length in months, and the rounded whole-programme total for award sizing,
    plus 'variable' (cost swings by institution) and 'practical' (an internship term may
    add travel) flags. The duration is the per-pathway figure from the basis table — NOT
    the student's stated programme_months, which is rounded to whole years and so is less
    accurate than the known programme length (e.g. STPM is 18 months, not a "2-year" 24).
    For an un-estimated/unknown pathway, ``known=False`` and no figures — fall back to the
    student's self-report.

    A 'degree' (owner 2026-11-07) counts STUDY months (10 a year) for the years left, and adds
    two keys: ``study_months`` (True) and ``continuing`` (started before the cohort year). A
    skills / TVET course ('ilkbs', 'iljtm', 'kkom', 'mara_cert', 'tvet') takes its length from the
    catalogue. Every other pathway's dict is as before."""
    pathway = classify_pathway(application)
    if pathway == 'degree':
        return _estimate_degree(application)
    spec = PATHWAY_ESTIMATES.get(pathway)
    if spec is None:
        return {'pathway': pathway, 'known': False, 'monthly': 0,
                'months': None, 'total': 0,
                'variable': False, 'practical': False}
    months = spec['months']
    if pathway in SEMESTER_LENGTH_PATHWAYS:
        months = _semester_months(application, months)
    monthly = spec['monthly']
    return {
        'pathway': pathway,
        'known': True,
        'monthly': monthly,
        'months': months,
        'total': _round100(monthly * months),
        'variable': spec['variable'],
        'practical': spec['practical'],
    }
