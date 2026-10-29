"""Deterministic ("Exact") reader for a polytechnic Diploma ACADEMIC TRANSCRIPT — Matric/Diploma M3.

The polytechnics of Jabatan Pendidikan Politeknik dan Kolej Komuniti print one transcript layout
(provisional and final): a header (NAME, REG.NO, IC NO, PROGRAMME, STATUS), the polytechnic's name,
then per SEMESTER ("FIRST SEMESTER (I : 2023/2024)") the course rows — CODE, course, credit, grade
— and a summary box: Grade Point Average (GPA), Cumulative Grade Point Average (CGPA), Credit
Earned, Total Credits ("52.0 / 92.0"). A last semester may be INDUSTRIAL TRAINING, with credits and
no grades. The page is two columns, so a digital PDF's text layer (pypdf 5.9.0, production's
locked library) lays the summary boxes out of step with their semesters; they are paired here by
their own running total, never by position.

TEXT LAYER ONLY. The corpus holds ONE such transcript (a digital PDF); a scan's word boxes of this
two-column page have never been seen, so a scan (``words`` given) is never read Exact — Gemini
reads it. A semester RESULT SLIP ("Keputusan Penilaian Akhir Semester", its HPNM a running figure)
and the student-portal screen are never this layout.

CONSERVATIVE — a wrong Exact value is far worse than an AI read. Every hit has passed:
  * the layout: "ACADEMIC TRANSCRIPT" (or "… (PROVISIONAL)"), STATUS COMPLETED, ONE polytechnic
    name line ("POLITEKNIK …", never the JPPKK department line), ONE name, ONE registration number,
    ONE IC (every IC-shaped number on the page equal to it);
  * every course row read whole: a polytechnic course code, a name, a credit and a grade on the
    scale (A+ … D), and nothing else on the row (a remark such as [CE] → None);
  * every semester's credits equal to its box's Credit Earned — a dropped (or extra) row refuses;
    the boxes' Total Credits rising by exactly each Credit Earned, ending at the programme's total;
  * every semester's GPA, and every running CGPA, equal to the ones recomputed from its rows
    (credits × grade points, half-up to two places) — so every graded row is proven by a sum;
  * a programme of 5 or 6 semesters (owner, 2026-10-29: 2.5 or 3 years) read whole from the first,
    an industrial-training semester only as the LAST, with credits and no rows;
  * the FINAL CGPA: the box whose Total Credits equal the programme's total (92.0 / 92.0) — never a
    semester GPA, never the first CGPA met — equal to the recomputed one.
Only the rows a sum proves are returned: a 0-credit course (the PISPA co-curricular units) counts
in no sum, so it is left out of `results`, never guessed. (Two equal-credit grades of one semester
exchanged would add up the same; the text layer prints each row whole on its own line, so that needs
a misplaced line, which the row checks refuse.)

Output mirrors the Gemini higher-results schema (`higher_results.SCHEMA`): candidate_name, exam,
cgpa, cgpa_label, institution, results [{subject, grade}], plus nric and reg_no. The caller stores
`PARSER_VERSION` beside `capture`. Pure + deterministic; never raises. PII-free unit tests use
synthetic twins (`tests/test_poly_diploma_parse.py`); the corpus is scored locally by
`eval/poly_parse_check.py`.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

# Parser version — bump on ANY change to the deterministic capture (doc-recognition versioning rule).
# 1.0.0 (2026-10-29): M3 — the JPPKK polytechnic academic transcript (text layer, 5 or 6 semesters).
# 1.1.0 (2026-10-29): review — every header line known; a name never ends on a connector; a
#   Diploma programme only; a wrapped row holds no credit or remark; an IC with spaces is an IC.
PARSER_VERSION = '1.1.0'

#: The polytechnic grade scale (the result slips print A+ as 4.00). Anything else → None.
GRADE_POINTS = {'A+': '4.00', 'A': '4.00', 'A-': '3.67', 'B+': '3.33', 'B': '3.00', 'B-': '2.67',
                'C+': '2.33', 'C': '2.00', 'C-': '1.67', 'D+': '1.33', 'D': '1.00'}
_ORDINALS = ('FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH')
_HEADER = re.compile(r'^(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH) SEMESTER \((?:I|II|1|2) : 20\d\d/20\d\d\)'
                     r'( - INDUSTRIAL TRAINING)?$')
_GRADE = r'(A\+|A-|A|B\+|B-|B|C\+|C-|C|D\+|D)'
_CODE = r'[A-Z]{3}\d{5}'
_ROW = re.compile(rf'^({_CODE}) (\S.*?) (\d{{1,2}}\.\d) {_GRADE}$')
_ROW_OPEN = re.compile(rf'^({_CODE}) ([A-Z][A-Z0-9 ,&()\-/*.]*)$')
_ROW_CLOSE = re.compile(rf'^(\d{{1,2}}\.\d) {_GRADE}$')
_NAME_PART = re.compile(r'^[A-Z][A-Z0-9 ,&()\-/*.]*$')
_GPA_LINE = re.compile(r'^:\s*([0-4]\.\d\d)\s*Grade Point Average \(GPA\)$')
_VALUE = re.compile(r'^:\s*([0-4]\.\d\d)$')
_EARNED = re.compile(r'^:\s*(\d{1,3}\.\d)$')
_TOTAL = re.compile(r'^:\s*(\d{1,3}\.\d)\s*/\s*(\d{1,3}\.\d)$')
_NRIC = re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{2})\s*-?\s*(\d{2})\s*-?\s*(\d{4})(?!\d)')
_END = '~~~~~End of results~~~~~'
_COLUMNS = 'CODE COURSE CREDIT GRADE REMARK'
_NOT_IN_NAME = frozenset({'NAME', 'REG', 'NO', 'IC', 'PROGRAMME', 'STATUS', 'MALE', 'FEMALE',
                          'LELAKI', 'PEREMPUAN', 'WANITA', 'GENDER', 'JANTINA', 'BANGSA', 'AGAMA',
                          'WARGANEGARA'})
#: A name never ENDS on one of these: the rest of it was cut off or wrapped (review, 2026-10-29).
CONNECTORS = frozenset({'BIN', 'BINTI', 'BTE', 'BT', 'B', 'A/L', 'A/P', 'AL', 'AP', 'S/O', 'D/O',
                        'ANAK', 'AK', '@', 'VAN', 'DE', 'BINTE'})
#: Words of a remark or a repeat that must never be read into a course name (review, 2026-10-29).
_REMARKS = re.compile(r'\b(?:REPEAT|ULANG|ULANGAN|GAGAL|FAIL|FAILED|EXEMPTION|RIG|CE|CTV|CTH|CA|C1|C2)\b'
                      r'|\(R\)|\[|\]')
_CREDIT_TOKEN = re.compile(r'(?<![\d.])\d{1,2}\.\d(?![\d.])')
#: Words of an address glued after the polytechnic's name — never part of it.
_ADDRESS = frozenset({'JALAN', 'HUB', 'BATU', 'LOT', 'KAMPUS', 'PETI', 'SURAT', 'EDUCATION', 'KM',
                      'BANDAR', 'TAMAN', 'PERSIARAN', 'LEBUH', 'KAWASAN', 'PERINDUSTRIAN'})


def _half_up(x: Decimal) -> str:
    return str(x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _one(lines, pattern):
    """The ONE match of ``pattern`` over the lines (a group), or None (none, or two)."""
    hits = [m for m in (re.match(pattern, ln) for ln in lines) if m]
    return hits[0] if len(hits) == 1 else None


def _poly_header(lines):
    """{name, nric, reg_no, institution} or None. The text layer prints each value BEFORE its label
    (" : VALUENAME"); the value must end exactly where the label begins."""
    name = _one(lines, r'^\s*:\s*([A-Z][A-Z@\'/.\- ]*[A-Z])NAME$')
    reg = _one(lines, r'^\s*:\s*(\d{2}[A-Z]{3}\d{2}[A-Z]\d{4})REG\.NO$')
    ic = _one(lines, r'^\s*:\s*(\d{6}-\d{2}-\d{4})IC NO$')
    inst = [ln for ln in lines if re.fullmatch(r'POLITEKNIK [A-Z ]+', ln.strip())]
    if not (name and reg and ic) or len(inst) != 1 or not _header_area_known(lines, inst[0]):
        return None
    words = name.group(1).split()
    if len(words) < 2 or any(w.strip('.') in _NOT_IN_NAME for w in words) or words[-1] in CONNECTORS:
        return None
    place = inst[0].split()[1:]
    if not place or len(place) > 5 or any(w in _ADDRESS for w in place):
        return None                             # an address glued to the name: not just the name
    m = _NRIC.fullmatch(ic.group(1))
    if not m or not (1 <= int(m[2]) <= 12 and 1 <= int(m[3]) <= 31):
        return None
    if not any(re.fullmatch(r'STATUS\s*:\s*COMPLETED', ln.strip()) for ln in lines):
        return None
    return {'name': ' '.join(words), 'nric': ''.join(m.groups()), 'reg_no': reg.group(1),
            'institution': inst[0].strip()}


#: The header area's fixed lines (before the first semester heading). Anything else there — a
#: wrapped name's second line, a second document — refuses (review, 2026-10-29).
_HEADER_LINES = (
    r'PROVISIONAL', r'ACADEMIC TRANSCRIPT(?: \(PROVISIONAL\))?', r":\s*[A-Z][A-Z@'/.\- ]*[A-Z]NAME",
    r':\s*\d{2}[A-Z]{3}\d{2}[A-Z]\d{4}REG\.NO', r':\s*\d{6}-\d{2}-\d{4}IC NO', r'PROGRAMME',
    r'INTAKE SESSION', r'STATUS\s*:\s*COMPLETED', r':\s*DIPLOMA [A-Z][A-Z ()&,\-]*',
    r':\s*(?:I|II) : 20\d\d/20\d\d', r'MEDIUM OF INSTRUCTION\s*:\s*[A-Z ]+',
    r'DATE\s*:\s*\d{1,2} [A-Z]+ 20\d\d', r'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI',
    re.escape(_COLUMNS), r'Cumulative Grade Point Average \(CGPA\)', r'Credit Earned', r'Total Credits',
    r':\s*[0-4]\.\d\d\s*Grade Point Average \(GPA\)', r':\s*\d{1,3}\.\d{1,2}(?:\s*/\s*\d{1,3}\.\d)?')


def _header_area_known(lines, institution):
    """Is every line before the first semester heading a known header line? The polytechnic's
    address (between its name and the JPPKK line) is free text; ONE programme line, a DIPLOMA."""
    first = next((i for i, ln in enumerate(lines) if _HEADER.match(ln)), None)
    if first is None:
        return False
    area = lines[:first]
    if any(re.match(r'KOLEJ KOMUNITI\b', ln) for ln in area):
        return False                            # a Kolej Komuniti's own transcript
    if sum(1 for ln in area if re.fullmatch(r':\s*DIPLOMA [A-Z][A-Z ()&,\-]*', ln)) != 1:
        return False                            # a Diploma programme, printed once (never a SIJIL / BACHELOR)
    jppkk = area.index('JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI') if (
        'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI' in area) else -1
    at = area.index(institution) if institution in area else -1
    if at < 0 or jppkk < at:
        return False
    return all(any(re.fullmatch(p, ln) for p in _HEADER_LINES)
               for i, ln in enumerate(area) if i != at and not at < i < jppkk)


def _boxes(lines):
    """Every summary box: (GPA or None, CGPA, earned, total, programme total). The four labels
    then the three values, exactly; None if any box is broken."""
    boxes, i = [], 0
    while i < len(lines):
        if lines[i] == 'Cumulative Grade Point Average (CGPA)':
            seq = lines[i + 1:i + 6]
            gpa = _GPA_LINE.match(lines[i - 1]) if i > 0 else None
            if (len(seq) != 5 or seq[0] != 'Credit Earned' or seq[1] != 'Total Credits'
                    or not _VALUE.match(seq[2]) or not _EARNED.match(seq[3]) or not _TOTAL.match(seq[4])):
                return None
            total = _TOTAL.match(seq[4])
            boxes.append((gpa.group(1) if gpa else None, _VALUE.match(seq[2]).group(1),
                          Decimal(_EARNED.match(seq[3]).group(1)), Decimal(total.group(1)),
                          Decimal(total.group(2))))
            i += 6
            continue
        i += 1
    return boxes


def _semesters(lines):
    """[(ordinal index, industrial training?, [rows])] in print order, or None on a line that does
    not belong. A row is (code, name, credit, grade); a wrapped name joins its next lines."""
    sems, cur, opened = [], None, None
    start = next((i for i, ln in enumerate(lines) if _HEADER.match(ln)), None)
    end = next((i for i, ln in enumerate(lines) if ln == _END), None)
    if start is None or end is None:
        return None
    box_lines = {'Cumulative Grade Point Average (CGPA)', 'Credit Earned', 'Total Credits', _COLUMNS}
    for ln in lines[start:end]:
        h = _HEADER.match(ln)
        if h:
            if opened is not None:
                return None
            cur = (_ORDINALS.index(h.group(1)), bool(h.group(2)), [])
            sems.append(cur)
            continue
        if ln in box_lines or _GPA_LINE.match(ln) or _VALUE.match(ln) or _EARNED.match(ln) or _TOTAL.match(ln):
            if opened is not None:
                return None
            continue
        if cur[1]:                              # industrial training: company, duration, remarks
            continue
        row = _ROW.match(ln)
        if row and opened is None:
            if _REMARKS.search(row[2]) or _CREDIT_TOKEN.search(row[2]):
                return None                     # a remark or a second credit inside the name
            cur[2].append((row[1], row[2].strip(), Decimal(row[3]), row[4]))
            continue
        if _REMARKS.search(ln) or (opened is not None or _ROW_OPEN.match(ln)) and not _ROW_CLOSE.match(
                ln) and _CREDIT_TOKEN.search(ln):
            return None                         # a failed / remarked row is never read into a name
        if opened is None and _ROW_OPEN.match(ln):
            opened = [_ROW_OPEN.match(ln)[1], _ROW_OPEN.match(ln)[2].strip()]
            continue
        close = _ROW_CLOSE.match(ln)
        if opened is not None and close:
            cur[2].append((opened[0], ' '.join(opened[1:]), Decimal(close[1]), close[2]))
            opened = None
            continue
        if opened is not None and _NAME_PART.match(ln) and len(opened) < 4:
            opened.append(ln.strip())
            continue
        return None
    return sems if opened is None else None


def read_poly_transcript(text, words=None):
    """Polytechnic transcript TEXT LAYER → the higher-results field dict, or None to defer to Gemini.
    A scan (``words`` given) is never read Exact (see the module docstring). Never raises."""
    if words:
        return None
    try:
        return _read_transcript(text)
    except Exception:          # a reader bug must fall back to AI, never break a read
        return None


def _read_transcript(text):
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    title = [ln for ln in lines if ln in ('ACADEMIC TRANSCRIPT', 'ACADEMIC TRANSCRIPT (PROVISIONAL)')]
    if len(title) != 1 or 'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI' not in lines:
        return None
    head, sems, boxes = _poly_header(lines), _semesters(lines), _boxes(lines)
    if head is None or not sems or not boxes:
        return None
    if [s[0] for s in sems] != list(range(len(sems))) or len(sems) not in (5, 6):
        return None                             # owner: 2.5 or 3 years — 5 or 6 semesters
    if any(s[1] for s in sems[:-1]) or any(not s[2] for s in sems if not s[1]):
        return None                             # industrial training only last; a graded one has rows
    boxes = sorted(boxes, key=lambda b: b[3])
    if len(boxes) != len(sems) or len({b[4] for b in boxes}) != 1:
        return None
    running = Decimal(0)
    for b in boxes:                             # each Total Credits = the last + this Credit Earned
        running += b[2]
        if b[3] != running:
            return None
    if boxes[-1][3] != boxes[-1][4]:
        return None                             # the programme's credits not all earned: not final
    points = credits = Decimal(0)
    for (_n, training, rows), (gpa, cgpa, earned, _t, _p) in zip(sems, boxes):
        if training:
            if gpa is not None or earned <= 0 or credits == 0 or _half_up(points / credits) != cgpa:
                return None
            continue
        sem_cr = sum(r[2] for r in rows)
        sem_pt = sum(r[2] * Decimal(GRADE_POINTS[r[3]]) for r in rows)
        if sem_cr != earned or not sem_cr or gpa is None or _half_up(sem_pt / sem_cr) != gpa:
            return None
        points, credits = points + sem_pt, credits + sem_cr
        if _half_up(points / credits) != cgpa:
            return None
    final = boxes[-1][1]
    ics = {''.join(m.groups()) for m in _NRIC.finditer(text)}
    if ics != {head['nric']}:                   # another person's IC on the page
        return None
    return {
        'candidate_name': head['name'], 'exam': title[0], 'nric': head['nric'], 'reg_no': head['reg_no'],
        'cgpa': final, 'cgpa_label': 'CGPA', 'institution': head['institution'],
        # Only the rows a sum proves: a 0-credit course counts in none (module docstring).
        'results': [{'subject': r[1], 'grade': r[3]} for s in sems for r in s[2] if r[2] > 0],
    }
