"""Deterministic ("Exact") reader for a Matriculation ACADEMIC TRANSCRIPT — Matric/Diploma exact-read M2.

Bahagian Matrikulasi KPM prints every college's transcript on one layout: a header (Nama, No. KP,
Kolej, No. Matrik), then per SEMESTER a block of course rows — CODE, course, credit, grade, value
point — closed by "PNGS / GPA", then the average-grade box and ONE "PNGK / CGPA", then "STATUS:
LULUS DAN TAMAT PROGRAM MATRIKULASI". This module reads it from the OCR text (a digital PDF's text
layer, every page) or, for a scan / photo, from the Vision WORD BOXES re-linearised into visual rows
(`stpm_parse._rows_of`, the same row builder). Anything else — a semester RESULT SLIP, a skewed
photo whose grades sit between rows, an unknown course — returns None, and the caller falls back to
today's Gemini read.

CONSERVATIVE — a wrong Exact value is far worse than an AI read. Every hit has passed:
  * the layout: Bahagian Matrikulasi + "Transkrip Akademik" and no result-slip title;
  * ONE name (never wrapped onto the next row), ONE IC (every IC-shaped number on the page equal to
    it), the matric number and the college ("KOLEJ MATRIKULASI …");
  * every course row: a matric course code (its last digit is the course's credits; its middle digit
    the semester-of-year, which must equal the course's printed number), a course from the known
    vocabulary, a grade on the scale — a CORE course (4+ credits) with its value point agreeing with
    the letter, English with a language band (B2, C1 …), every other course a letter and no point;
  * every semester's printed PNGS (GPA) equal to the one recomputed from its core courses
    (credits × points, half-up to two places);
  * the FINAL CGPA (owner, 2026-10-29): the ONE "PNGK / CGPA" printed AFTER the last semester, with
    "LULUS DAN TAMAT" (programme completed) printed, a programme of 2 or 4 semesters (1 or 2 years)
    read whole from Semester I, and the CGPA equal to the one recomputed from the semesters it counts
    (all of a 2-semester programme; a 4-semester one's are named by its own note, "PNGK dikira
    berdasarkan keputusan Semester III dan IV" — no note, no read). Never a semester GPA, never the
    first CGPA met. A scan's page 1 that stops before the last semester (production rasterises page
    1 only) therefore never reads Exact.
One misread grade or point breaks a GPA sum. (Two equal-credit core grades swapped would not — the
rows are paired by their own visual row, never re-ordered, so a swap needs a misplaced row, which
the row checks above refuse.)

Output mirrors the Gemini higher-results schema (`higher_results.SCHEMA`): candidate_name, exam,
cgpa, cgpa_label, institution, results [{subject, grade}] (subject NAME only, no code, every
semester in print order), plus nric and matric_no. The caller stores `PARSER_VERSION` beside
`capture`, outside the fields. Pure + deterministic; never raises. PII-free unit tests use synthetic
twins (`tests/test_matric_parse.py`); the real corpus is scored locally by `eval/matric_parse_check.py`.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from .stpm_parse import GRADE_POINTS, _NRIC_RE, _after, _clean_name, _letters, _rows_of

# Parser version — bump on ANY change to the deterministic capture (doc-recognition versioning rule).
# 1.0.0 (2026-10-29): M2 — the KPM Matriculation academic transcript (2 and 4 semesters).
PARSER_VERSION = '1.0.0'

#: English's language bands (CEFR), printed with no value point.
BANDS = frozenset({'A1', 'A2', 'B1', 'B2', 'C1', 'C2'})
_ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
_CODE = re.compile(r'^([A-Z]{2})([0-9OIl]{3})$')
_GP = re.compile(r'^[0-4]\.\d{2}$')
_MATRIC_NO = re.compile(r'^[A-Z]{2}\d{10}$')
_NOTE = re.compile(r'SEMESTER\s+(IV|I{1,3})\s+(?:DAN|AND)\s+(IV|I{1,3})\b')
_CGPA = re.compile(r'PNGK\s*/\s*CGPA\s*:?\s*([0-4]\.\d{2})(?!\d)')
_GPA = re.compile(r'^PNGS\s*/\s*GPA\s*:?\s*([0-4]\.\d{2})$')
#: The courses a Matriculation transcript prints, as letter keys (Malay / English / both, the
#: semester number stripped). A course outside this list → None (Gemini reads it).
_COURSES = frozenset(_letters(c) for c in (
    'MATHEMATICS', 'CHEMISTRY', 'PHYSICS', 'BIOLOGY', 'COMPUTER SCIENCE', 'ACCOUNTING',
    'EKONOMI / ECONOMICS', 'ECONOMICS', 'PENGURUSAN PERNIAGAAN / BUSINESS MANAGEMENT',
    'BUSINESS MANAGEMENT', 'ENGLISH', 'KOKURIKULUM / CO-CURRICULUM', 'CO-CURRICULUM',
    'PENDIDIKAN MORAL / MORAL EDUCATION', 'MORAL EDUCATION', 'PENDIDIKAN ISLAM / ISLAMIC EDUCATION',
    'ISLAMIC EDUCATION', 'PENGAJIAN AM MATRIKULASI / MATRICULATION GENERAL STUDIES',
    'PENGAJIAN AM MATRIKULASI MATRICULATION GENERAL STUDIES', 'MATRICULATION GENERAL STUDIES',
    'CIVIL ENGINEERING', 'ELECTRICAL ENGINEERING', 'MECHANICAL ENGINEERING'))
#: Words that open a header row after the name — the name row must be followed by one (no wrap).
_LABELS = ('KOLEJ', 'NOKP', 'NOMATRIK', 'JANTINA', 'JURUSAN', 'SESI')
#: Label words that may never be part of a name read Exact.
_NOT_IN_NAME = frozenset({'NO', 'KP', 'IC', 'MATRIK', 'MATRIC', 'KOLEJ', 'COLLEGE', 'JANTINA',
                          'GENDER', 'JURUSAN', 'MAJOR', 'SESI', 'SESSION'})
_CORE_CREDITS = 4


def _half_up(x: Decimal) -> str:
    return str(x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _text(row) -> str:
    return ' '.join(row).upper()


def _code(token):
    """(prefix, '015') for a course code — O / I / l misread in the digits mended — or None."""
    m = _CODE.match(token or '')
    if not m:
        return None
    digits = m[2].replace('O', '0').replace('I', '1').replace('l', '1')
    return (m[1], digits) if digits.isdigit() else None


def _course_row(row):
    """A course row → {code, subject, credits, grade, point, sem_of_year}, or None (not a clean row)."""
    code = _code(row[0])
    if code is None:
        return None
    rest = list(row[1:])
    point = rest.pop() if rest and _GP.match(rest[-1]) else None
    grade = rest.pop() if rest and (rest[-1] in GRADE_POINTS or rest[-1] in BANDS) else None
    credits = int(code[1][2])
    digits = []
    while rest and len(digits) < 2 and re.fullmatch(r'\d', rest[-1]):
        digits.insert(0, int(rest.pop()))
    if len(digits) == 2:                        # "… 1 5": the course's number, then its credits
        if digits[1] != credits:
            return None
        rest.append(str(digits[0]))
    elif digits and digits[0] != credits:       # one digit that is not the credits: the number
        rest.append(str(digits[0]))             # (a scan may drop the credit column's digit)
    if grade is None or not rest:
        return None
    numbers = {t for t in rest if t.isdigit()}      # "EKONOMI 1 / ECONOMICS 1" prints it twice
    name_tokens = [t for t in rest if not t.isdigit()]
    if _letters(''.join(name_tokens)) not in _COURSES or not all(
            re.fullmatch(r"[A-Za-z/\-()]+", t) for t in name_tokens):
        return None
    if numbers and numbers != {code[1][1]}:          # "MATHEMATICS 2" is a xx025 course
        return None
    subject = re.sub(r'\s*-\s*', '-', re.sub(r'\s*/\s*', '/ ', ' '.join(rest))).strip()
    return {'code': ''.join(code), 'subject': subject, 'credits': credits, 'grade': grade,
            'point': point, 'english': code[0] == 'WE'}


def _row_ok(r) -> bool:
    """The grade rules per course: core → letter + its own value point; English → a band and no
    point; anything else → a letter and no point."""
    if r['english']:
        return r['grade'] in BANDS and r['point'] is None
    if r['grade'] in BANDS:
        return False
    if r['credits'] >= _CORE_CREDITS:
        return r['point'] is not None and GRADE_POINTS[r['grade']] == r['point']
    return r['point'] is None


def _semesters(rows, start):
    """[(semester number, [course rows], printed GPA)] read from `start`, and the index after the
    last block; None on any row that does not belong."""
    sems, cur, i = [], None, start
    while i < len(rows):
        row, flat = rows[i], _letters(''.join(rows[i]))
        if len(row) == 2 and row[0].upper() == 'SEMESTER' and row[1] in _ROMAN:
            if cur is not None:
                return None                     # a semester with no PNGS
            cur = (_ROMAN[row[1]], [], None)
        elif cur is None and (flat.startswith('PURATA') or flat.startswith('AVERAGE') or 'PNGK' in flat):
            break
        elif flat.startswith('SESI') and re.search(r'20\d\d/20\d\d$', _text(row)):
            pass                                # a 2-year transcript's session line
        elif cur is not None and _code(row[0]):
            course = _course_row(row)
            if course is None or not _row_ok(course):
                return None
            cur[1].append(course)
        elif cur is not None and flat.startswith('PNGS'):
            m = _GPA.match(_text(row))
            if not m or not cur[1]:
                return None
            sems.append((cur[0], cur[1], m.group(1)))
            cur = None
        else:
            return None
        i += 1
    return (sems, i) if cur is None else None


def _gpa(courses):
    core = [c for c in courses if c['credits'] >= _CORE_CREDITS and not c['english']]
    total = sum(c['credits'] for c in core)
    return sum(c['credits'] * Decimal(c['point']) for c in core), total


def _header(rows):
    """{name, nric, matric_no, institution} or None."""
    namas = [i for i, r in enumerate(rows) if _letters(r[0]).startswith('NAMA')]
    if len(namas) != 1 or namas[0] + 1 >= len(rows):
        return None
    i = namas[0]
    if not any(_letters(''.join(rows[i + 1])).startswith(k) for k in _LABELS):
        return None                             # the name may have wrapped onto the next row
    tokens = [t for t in _after(rows[i], 'NAMANAME') if t != ':']
    name = _clean_name(tokens)
    if not name or any(t.strip('.,:') in _NOT_IN_NAME for t in tokens):
        return None
    # "NO. KP / IC NO." (never the "MATRIC NO." row, whose letters also hold "ICNO"); the college
    # label "KOLEJ / COLLEGE" (OCR may read its slash as I).
    ic_rows = [r for r in rows if 'KPICNO' in _letters(''.join(r))]
    mx_rows = [r for r in rows if 'MATRICNO' in _letters(''.join(r))]
    col_rows = [r for r in rows if re.match(r'KOLEJI?COLLEGE', _letters(''.join(r)))]
    if len(ic_rows) != 1 or len(mx_rows) != 1 or len(col_rows) != 1:
        return None
    ic = next((t for t in _after(ic_rows[0], 'KPICNO') if t not in (':', '.', '.:')), '')
    m = _NRIC_RE.fullmatch(ic)
    matric_no = next((t for t in _after(mx_rows[0], 'MATRICNO') if _MATRIC_NO.match(t)), '')
    college = []
    for t in _after(col_rows[0], 'COLLEGE'):
        if t in (':',):
            continue
        if not re.fullmatch(r'[A-Z]+', t):
            break
        college.append(t)
    while college and college[-1] in ('NO',):
        college.pop()
    institution = ' '.join(college)
    if not m or not matric_no or not institution.startswith('KOLEJ MATRIKULASI '):
        return None
    _yy, mm, dd = (int(x) for x in m.groups()[:3])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    return {'name': name, 'nric': ''.join(m.groups()), 'matric_no': matric_no,
            'institution': institution}


def parse(text, words=None):
    """Matriculation transcript OCR text (+ Vision word boxes for a scan) → the higher-results field
    dict, or None to defer to Gemini. Never raises."""
    try:
        return _read_transcript(text, words)
    except Exception:          # a reader bug must fall back to AI, never break a read
        return None


def _read_transcript(text, words):
    rows = _rows_of(text, words)
    flat = _letters(''.join(''.join(r) for r in rows))
    if ('BAHAGIANMATRIKULASI' not in flat or 'TRANSKRIPAKADEMIK' not in flat
            or 'SLIPKEPUTUSAN' in flat or 'RESULTSLIP' in flat):
        return None
    head = _header(rows)
    kod = next((i for i, r in enumerate(rows) if _letters(''.join(r)).startswith('KODKURSUS')
                or _letters(''.join(r)).startswith('CODECOURSE')), -1)
    if head is None or kod < 0:
        return None
    start = kod + 1
    while start < len(rows) and _letters(''.join(rows[start])).startswith(('KOD', 'CODE')):
        start += 1                              # the bilingual header's second row
    read = _semesters(rows, start)
    if read is None:
        return None
    sems, end = read
    numbers = [s[0] for s in sems]
    if numbers not in ([1, 2], [1, 2, 3, 4]):
        return None                             # owner: 1 year (2 semesters) or 2 years (4)
    for _n, courses, printed in sems:
        points, credits = _gpa(courses)
        if not credits or _half_up(points / credits) != printed:
            return None
    tail = [_text(r) for r in rows[end:]]
    cgpas = [m.group(1) for t in tail for m in _CGPA.finditer(t)]
    if len(cgpas) != 1 or not any('LULUS DAN TAMAT' in t for t in tail):
        return None
    counted = [1, 2]
    if numbers == [1, 2, 3, 4]:
        note = _NOTE.search(' '.join(tail))
        if not note:
            return None
        counted = sorted({_ROMAN[note.group(1)], _ROMAN[note.group(2)]})
    totals = [_gpa(c) for n, c, _p in sems if n in counted]
    cgpa = _half_up(sum(p for p, _c in totals) / sum(c for _p, c in totals))
    if cgpa != cgpas[0]:
        return None
    ics = {''.join(m.groups()) for r in rows for m in _NRIC_RE.finditer(' '.join(r))}
    if ics != {head['nric']}:                   # another person's IC on the page
        return None
    return {
        'candidate_name': head['name'], 'exam': 'TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT',
        'nric': head['nric'], 'matric_no': head['matric_no'],
        'cgpa': cgpa, 'cgpa_label': 'PNGK/CGPA', 'institution': head['institution'],
        'results': [{'subject': c['subject'], 'grade': c['grade']} for _n, cs, _p in sems for c in cs],
    }
