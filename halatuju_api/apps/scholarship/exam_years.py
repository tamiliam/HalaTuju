"""Which exam YEAR is the expected one for each results document of an application — route-aware.

Owner rule, approved 2026-11-01 (decisions.md). The cohort year is C. The route is the results the
student HOLDS (`results_route.held` — the one route source; nothing here re-derives it):

    route (held)                      expected — anything else is amber ('off')
    none / SPM only                   SPM C−1
    STPM                              STPM C−1; SPM C−3
    Matriculation                     Matriculation C; SPM C−2
    Asasi (as matriculation)          Asasi C; SPM C−2
    Diploma (polytechnic / diploma)   Diploma C−1 or C; SPM C−4

An unknown route keeps the rule this replaced (SPM C−1). A document kind the route lists no year for
gets no colour at all ('' — "we cannot say"), never amber.

DISPLAY ONLY. `exam_year_status` is read by the cockpit's year chips (the Documents drawer and the
Academic card's merit line) and by nothing that decides, queries or pays: the Check-2 "exam year
unknown" question reads `exam_year` (is there a year?), never its status.

TD-735 (25 Nov 2026): a Matriculation, Asasi or Diploma transcript's year (`transcript_year`) — also
DISPLAY ONLY. It reads the year off the upload's OCR text (else the document's own title), stored
beside the read as `vision_fields.exam_year_read`, never in its fields.
"""
import re

#: The rule of the transcript-year reader, stamped on every stored read (`exam_year_read.reader`) so a
#: later rule can find and re-derive the reads made under this one (lesson 188).
TRANSCRIPT_YEAR_READER = '1.0.0'

#: A LABELLED academic session: "SESI / SESSION : 2024/2025", "SESI AKADEMIK 2024/2025", "ACADEMIC
#: SESSION 2024/25". The year is anchored to its label (lesson 461), never the first 20xx on a page.
_LABEL = r'(?:SESI(?:[ \t]+AKADEMIK)?|(?:ACADEMIC[ \t]+)?SESSION)'
_SESSION = re.compile(rf'\b{_LABEL}(?:[ \t]*/[ \t]*{_LABEL})?[ \t]*:?[ \t]*(20\d\d)[ \t]*/[ \t]*(20\d\d|\d\d)\b',
                      re.IGNORECASE)
#: A polytechnic semester heading: "FIRST SEMESTER (I : 2023/2024)".
_SEMESTER = re.compile(r'\(\s*(?:I|II|III)\s*:\s*(20\d\d)\s*/\s*(20\d\d)\s*\)')
#: Any session pair, for the document's own TITLE only ("... PROGRAM MATRIKULASI 2024/2025").
_PAIR = re.compile(r'\b(20\d\d)[ \t]*/[ \t]*(20\d\d|\d\d)\b')
#: A line that names an intake, not a result ("INTAKE SESSION 2022/2023", "Ambilan Sesi 2024/2025").
_INTAKE = re.compile(r'INTAKE|AMBILAN|KEMASUKAN|ENROL', re.IGNORECASE)
_YEAR = re.compile(r'20\d\d')


def _session_end(m, text) -> str:
    """The END year of a session match ("2024/2025" -> 2025, owner 25 Nov), or '' when the pair is not
    one academic year (a course span "2024/2027") or its line names an intake."""
    start, tail = m.group(1), m.group(2)
    end = int(start[:2] + tail if len(tail) == 2 else tail)
    line = text[text.rfind('\n', 0, m.start()) + 1:m.start()]
    return str(end) if end == int(start) + 1 and not _INTAKE.search(line) else ''


def _latest(patterns, text, label):
    years = [y for rx in patterns for m in rx.finditer(text or '') if (y := _session_end(m, text))]
    return (max(years), label) if years else ('', '')


def transcript_year(text) -> tuple:
    """``(year, label)`` off a Matriculation / Asasi / Diploma transcript's text: the END year of its
    LATEST labelled session or semester heading (a polytechnic's last semester; a matriculation
    transcript's last "SESI"), labelled 'session' or 'semester'. ``('', '')`` when none is read — a
    bare 20xx, a print date or an intake session is never a result year (no guess)."""
    year, label = _latest((_SESSION,), text, 'session')
    return (year, label) if year else _latest((_SEMESTER,), text, 'semester')


def title_year(title) -> tuple:
    """``(year, 'title')`` off the document's own printed title (``fields.exam``): the end year of a
    session pair in it, or ``('', '')``. A lone year in a title is not read (no guess)."""
    return _latest((_PAIR,), str(title or ''), 'title')


def read_transcript_year(text, title='') -> dict:
    """The stored read (`vision_fields.exam_year_read`): the OCR text first, else the title."""
    year, label = transcript_year(text)
    if not year:
        year, label = title_year(title)
    return {'year': year, 'label': label, 'reader': f'transcript_year {TRANSCRIPT_YEAR_READER}'}


def stored_transcript_year(vision_fields, fields) -> str:
    """The year to SERVE for a Matriculation / Asasi / Diploma read: the stored read's, else (a document
    read before TD-735) its stored title's. '' when neither carries one — the merit then shows bare."""
    read = vision_fields.get('exam_year_read') if isinstance(vision_fields, dict) else None
    year = str(read.get('year') or '') if isinstance(read, dict) else ''
    return year if _YEAR.fullmatch(year) else title_year((fields or {}).get('exam'))[0]


#: The route → {document kind: years before the cohort year that are expected}. 0 = the cohort year.
_EXPECTED = {
    'spm': {'spm': (1,)},
    'stpm': {'stpm': (1,), 'spm': (3,)},
    'matric': {'matric': (0,), 'spm': (2,)},
    'asasi': {'asasi': (0,), 'spm': (2,)},
    'diploma': {'diploma': (1, 0), 'spm': (4,)},
}


def expected_years(application) -> dict:
    """``{document kind: {year strings}}`` expected for this application, or ``{}`` with no cohort."""
    from .results_route import held
    cohort = getattr(getattr(application, 'cohort', None), 'year', None)
    if not cohort:
        return {}
    route = held(application) if application is not None else ''
    rows = _EXPECTED.get(route or 'spm', _EXPECTED['spm'])     # unknown route → the old SPM C−1 rule
    return {kind: {str(cohort - back) for back in backs} for kind, backs in rows.items()}


def year_status(application, kind, year) -> str:
    """``'current'`` when ``year`` is an expected year for a ``kind`` document of this application,
    ``'off'`` when the route expects another year, ``''`` when there is no year, no cohort, or the
    route names no year for that kind."""
    year = str(year or '').strip()
    if not year:
        return ''
    expected = expected_years(application).get(kind)
    if not expected:
        return ''
    return 'current' if year in expected else 'off'
