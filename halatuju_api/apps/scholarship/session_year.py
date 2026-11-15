"""The course-start years a gift's start-year rule may assume - H3a, rebuilt 2026-11-15.

FOR THE GIFT'S START-YEAR RULE ONLY (`start_year.reading`). The money - the STPM award size and
the funding estimate - reads `pathway_engine.course_start_year`, which is main's reading, unchanged
and pinned by `tests/test_start_year_money.py`. An adversarial review failed the branch that made
one reading serve both: a fix for the gift moved money. So the two readings are kept apart.

The lead's rule (second fix round): only OUTSIDE changes a result (a red Pathway fact, a student
note, QC's floor), so OUTSIDE must be SURE; INSIDE needs a clear first-year signal; any doubt is
UNKNOWN (a reviewer line that moves nothing). `gift_reading` therefore returns:

  * ``years`` - the years the course may have started in (EMPTY = unknown);
  * ``first_year`` - the letter clearly names a FIRST-YEAR intake (a first term, Year 1, Lower Six,
    an intake word, a written intake month and year, or a lone year and nothing else). Without it
    the student may be a continuing one, who started EARLIER than the years read, so
    `start_year.decide` passes nobody and fails only a case whose every year is before the gift's;
  * ``may_fail`` - False when the line itself holds clashing years: never outside.

Pure text work: no model, no database.
"""
import re
from typing import NamedTuple

EMPTY = frozenset()


class GiftReading(NamedTuple):
    years: frozenset
    first_year: bool = False
    may_fail: bool = True


UNKNOWN = GiftReading(EMPTY, False, False)

_MONTH_NUM = {
    'januari': 1, 'january': 1, 'jan': 1, 'februari': 2, 'february': 2, 'feb': 2,
    'mac': 3, 'march': 3, 'mar': 3, 'april': 4, 'apr': 4, 'mei': 5, 'may': 5, 'june': 6, 'jun': 6,
    'julai': 7, 'july': 7, 'jul': 7, 'ogos': 8, 'august': 8, 'aug': 8, 'september': 9, 'sept': 9,
    'sep': 9, 'oktober': 10, 'october': 10, 'okt': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'disember': 12, 'december': 12, 'dis': 12, 'dec': 12,
}
_MONTH = '(?:' + '|'.join(sorted(_MONTH_NUM, key=len, reverse=True)) + ')'

# "2024/2025", "2024 / 25", "2024-2025": a session is two CONSECUTIVE years (checked in code), so a
# Form 6 range "6 / 2025 - 12 / 2026" is never read as one.
_SESSION_RE = re.compile(r'\b(20\d{2})\s*([/\-–])\s*(20\d{2}|\d{2})\b')
# After a DASH, a two-digit tail may be the DAY of a date: "Julai 2025 - 26 Februari 2026" or
# "2025 - 26/02/2026" is not session 2025/26. After a SLASH it never is: "Session 2024/25 Feb 2025"
# is a session with its intake month.
_DAY_TAIL_RE = re.compile(rf'\s*(?:{_MONTH}\b|[/.\-]\s*\d{{1,2}}\s*[/.\-]\s*(?:20)?\d{{2}}\b)', re.I)
_YEAR_RE = re.compile(r'\b(20\d{2})\b')

# A month WITH its year ("Intake Jan 2025", "Ambilan September 2025").
_MONTH_YEAR_RE = re.compile(rf'\b({_MONTH})\b\.?,?\s*(20\d{{2}})\b', re.I)
_MONTH_ALONE_RE = re.compile(rf'\b({_MONTH})\b', re.I)
# A month with no year inside a session S/S+1: September to November can only be S, January to
# April only S+1. Any other month (May to August, December: "Ambilan Disember") could be either.
_FIRST_MONTHS, _SECOND_MONTHS = {9, 10, 11}, {1, 2, 3, 4}

# An exam year is not a start year: "SPM 2024, Ambilan 2025", "(2024 lulus SPM)".
_EXAM = r'(?:SPM|STPM|SVM|STAM|UEC|MUET|IGCSE|O[\s\-]?Levels?|A[\s\-]?Levels?)'
_EXAM_YEAR_RE = re.compile(
    rf'\b{_EXAM}\b\s*(?:tahun|year)?\s*[:\-]?\s*(20\d{{2}})\b'
    rf'|\b(20\d{{2}})\s*\(?\s*(?:lulus|keputusan|results?\s+of)\s+{_EXAM}\b', re.I)
_INTAKE_RE = re.compile(r'\b(?:ambilan|pengambilan|intake|kemasukan|admission|enrol(?:l?ment)?)\b', re.I)

# Term numbers: digits, roman, Malay and English words. "dua belas" before "dua".
_WORDS = {
    'satu': 1, 'pertama': 1, 'one': 1, 'dua belas': 12, 'kedua belas': 12, 'dua': 2, 'kedua': 2,
    'two': 2, 'tiga': 3, 'ketiga': 3, 'three': 3, 'empat': 4, 'keempat': 4, 'four': 4, 'lima': 5,
    'kelima': 5, 'five': 5, 'enam': 6, 'keenam': 6, 'six': 6, 'tujuh': 7, 'ketujuh': 7, 'seven': 7,
    'lapan': 8, 'kelapan': 8, 'eight': 8, 'sembilan': 9, 'kesembilan': 9, 'nine': 9, 'sepuluh': 10,
    'kesepuluh': 10, 'ten': 10, 'sebelas': 11, 'kesebelas': 11, 'eleven': 11, 'twelve': 12,
    'akhir': 99, 'final': 99, 'last': 99,
}
_ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9,
          'x': 10, 'xi': 11, 'xii': 12}
_TOKEN = (r'(?:\d{1,2}(?!\d)|(?:xii|xi|ix|x|viii|vii|vi|iv|v|iii|ii|i)\b|(?:'
          + '|'.join(sorted(_WORDS, key=len, reverse=True)).replace(' ', r'\s+') + r')\b)')
# "Part" / "Bahagian" are UiTM's semesters; "Tahap" / "Level" count like years (2+ = later).
_KEYWORD = r'(semester|sem|penggal|term|tahun|year|sesi|session|part|bahagian|tahap|level)'
_TERM_RE = re.compile(
    rf'\b{_KEYWORD}(?:\s+(?:pengajian|of\s+study))?\.?\s*[:.\-]?\s*(?:ke\s*-?\s*)?'
    rf'({_TOKEN}(?:\s*(?:/|,|&|-|\bdan\b|\band\b|\bor\b|\batau\b)\s*{_TOKEN})*)', re.I)
_TOKEN_RE = re.compile(_TOKEN, re.I)
_ORDINALS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4,
             '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6, 'seventh': 7, '7th': 7,
             'eighth': 8, '8th': 8, 'final': 99, 'last': 99, 'senior': 99}
_ORDINAL_RE = re.compile(
    r'\b(' + '|'.join(sorted(_ORDINALS, key=len, reverse=True))
    + r')[\s\-]+(semester|sem|term|year|tahun)\b', re.I)
_YS_RE = re.compile(r'\bY\s*(\d{1,2})\s*S\s*(\d{1,2})\b', re.I)          # "Y2S1", "Y3 S1"
# Upper Six is the second year of Form 6; these words name a continuing student outright.
_LATER_WORDS_RE = re.compile(
    r'\b(?:tingkatan|form)\s*(?:6|enam|six)\s*atas\b|\bupper\s*(?:6|six)\b'
    r'|\blanjutan\b|\bpelajar\s+(?:lama|senior)\b|\bcontinuing\b|\breturning\b', re.I)
_LOWER_SIX_RE = re.compile(r'\b(?:tingkatan|form)\s*(?:6|enam|six)\s*rendah\b|\blower\s*(?:6|six)\b', re.I)
_STPM_WORDS_RE = re.compile(r'\b(?:tingkatan\s*(?:6|enam)|form\s*(?:6|six)|stpm|penggal)\b', re.I)


def _number(token):
    t = re.sub(r'\s+', ' ', token.strip().lower())
    if t.isdigit():
        return int(t)
    return _ROMAN.get(t) or _WORDS.get(t)


def _add(out, key, n):
    """One term fact: 'later' (Semester 3+, Year 2+ - her PLACE in the course, not the intake),
    'first' (a first term), 'year1', 'second', 'sesi1' / 'either' (a polytechnic Sesi I / II)."""
    if n is None:
        return
    if key in ('tahun', 'year', 'tahap', 'level'):
        if n >= 2:
            out.add('later')
        elif key in ('tahun', 'year'):
            out.add('year1')
    elif n >= 3:
        out.add('later')
    elif key in ('sesi', 'session'):
        out.add('sesi1' if n == 1 else 'either')
    else:
        out.add('first' if n == 1 else 'second')


def _terms(text, context=False):
    """The term facts on the line. ``context`` (the programme / institution / stream words) yields
    only 'later', and ignores "Tahap" / "Level" there (a qualification's level, "SKM Tahap 3")."""
    out = set()
    if _LATER_WORDS_RE.search(text):
        out.add('later')
    if _LOWER_SIX_RE.search(text):
        out.add('year1')
    for m in _TERM_RE.finditer(text):
        key = m.group(1).lower()
        if context and key in ('tahap', 'level'):
            continue
        if key == 'penggal':
            out.add('penggal')
        for t in _TOKEN_RE.findall(m.group(2)):
            _add(out, key, _number(t))
    for m in _ORDINAL_RE.finditer(text):
        _add(out, m.group(2).lower(), _ORDINALS[m.group(1).lower()])
    for m in _YS_RE.finditer(text):
        _add(out, 'year', int(m.group(1)))
        _add(out, 'semester', int(m.group(2)))
    return out & {'later'} if context else out


def _sessions(text):
    """``[(match, S, S+1), ...]`` for every academic session on the line."""
    out = []
    for m in _SESSION_RE.finditer(text):
        a, tail = int(m.group(1)), m.group(3)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        day = len(tail) == 2 and m.group(2) != '/' and _DAY_TAIL_RE.match(text, m.end())
        if b == a + 1 and not day:
            out.append((m, a, b))
    return out


def looks_stpm(text):
    """True when a letter's words name Form 6 (Tingkatan 6, STPM, a Penggal)."""
    return bool(_STPM_WORDS_RE.search(text or ''))


def gift_reading(intake, reporting_date='', *, context='', confirmation=False, stpm=False):
    """The letter's start years for the gift's rule, as a `GiftReading`. ``intake`` and
    ``reporting_date`` are the letter's own lines (never the application's stored date: it may be
    an old letter's, or typed); ``context`` the programme / institution / stream words;
    ``confirmation`` is True for a confirmation-of-studies letter, ``stpm`` for a Form 6 one.

    UNKNOWN for: a later term or a continuing word (on the line or in the context); a second term
    (Semester 2 / II, Penggal 2: the student's place, which a new or a continuing student shares);
    a polytechnic Sesi II on a confirmation or STPM letter; first and second terms together; two
    sessions; any year on a session line outside the session's two (SPM / STPM exam years are not
    start years and are set aside); two written month-years; a confirmation letter without a first
    term or a written month-year (it names the CURRENT session, not the intake); a date whose year
    the line does not allow; a Sesi I / II with no session.

    Else, on a session S/S+1 line: a written month-year in the session wins; else a first term,
    Sesi I or September-November -> S; January-April -> S+1; else both (Sesi II, a bare session);
    the letter's date then picks one. With no session: the one year on the line (agreeing with
    the date), or the date's year if the line has none; several years -> the date's year if it is
    among them (never a fail), else unknown."""
    text = intake or ''
    rdm = _YEAR_RE.search(reporting_date or '')
    rd_year = int(rdm.group(1)) if rdm else None
    terms = _terms(text) | _terms(context or '', context=True)
    if 'later' in terms or 'second' in terms:
        return UNKNOWN
    if 'either' in terms and (confirmation or stpm or 'penggal' in terms):
        return UNKNOWN
    sessions = _sessions(text)
    taken = {p for m, _s, _s1 in sessions for p in (m.start(1), m.start(3))}
    exam = {m.start(1) if m.group(1) else m.start(2) for m in _EXAM_YEAR_RE.finditer(text)}
    others = {m.start(1): int(m.group(1)) for m in _YEAR_RE.finditer(text)
              if m.start(1) not in taken and m.start(1) not in exam}
    written = {int(m.group(2)) for m in _MONTH_YEAR_RE.finditer(text) if m.start(2) in others}
    if len(written) > 1:
        return UNKNOWN
    w = next(iter(written), None)
    if confirmation and not (terms & {'first', 'year1'} or w is not None):
        return UNKNOWN
    first_year = bool(terms & {'first', 'year1'}) or w is not None or bool(_INTAKE_RE.search(text))
    if sessions:
        if len({(s, s1) for _m, s, s1 in sessions}) > 1:
            return UNKNOWN
        s, s1 = sessions[0][1], sessions[0][2]
        if any(y not in (s, s1) for y in others.values()):
            return UNKNOWN
        cand = {s, s1}
        if w is not None:
            cand = {w}
        else:
            months = {_MONTH_NUM[m.group(1).lower()] for m in _MONTH_ALONE_RE.finditer(text)}
            to_s = bool(terms & {'first', 'sesi1'} or months & _FIRST_MONTHS)
            to_s1 = bool(months & _SECOND_MONTHS)
            # A Sesi II with a September-November month clashes (Sesi II runs from December).
            if (to_s and to_s1) or ('either' in terms and months & _FIRST_MONTHS):
                return UNKNOWN
            cand = {s} if to_s else {s1} if to_s1 else cand
        if rd_year is not None:
            if rd_year not in cand:
                return UNKNOWN
            cand = {rd_year}
        return GiftReading(frozenset(cand), first_year)
    if terms & {'sesi1', 'either'}:
        return UNKNOWN
    years = sorted(set(others.values()))
    if not years:
        return GiftReading(frozenset({rd_year}), first_year) if rd_year is not None else UNKNOWN
    if len(years) > 1:
        return GiftReading(frozenset({rd_year}), first_year, False) if rd_year in years else UNKNOWN
    if rd_year is not None and rd_year != years[0]:
        return UNKNOWN
    lone = not terms and not confirmation
    return GiftReading(frozenset(years), first_year or lone)


def gift_start_years(intake, reporting_date='', **kw):
    """`gift_reading`'s years alone (EMPTY = unknown)."""
    return gift_reading(intake, reporting_date, **kw).years
