"""The course-start years a gift's start-year rule may assume - H3a, rebuilt 2026-11-15.

FOR THE GIFT'S START-YEAR RULE ONLY (`start_year.reading`). The money - the STPM award size and
the funding estimate - reads `pathway_engine.course_start_year`, which is main's reading, unchanged
and pinned by `tests/test_start_year_money.py`. An adversarial review failed the branch that made
one reading serve both: a fix for the gift moved money. So the two readings are kept apart.

`gift_start_years` is CONSERVATIVE. It names a year only when the letter makes it sure, and else
returns the empty set: unknown, a person checks (owner rule: an unsure year is never an automatic
fail, and a reviewer still decides). It may also return BOTH years of a session, S and S+1, when
the course could have started in either; `start_year.reading` then passes it only when both are
in the gift's years, fails it only when both are out, and otherwise leaves it to a person.

Pure text work: no model, no database.
"""
import re

EMPTY = frozenset()

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
# A two-digit tail that is really the DAY of a date: "Julai 2025 - 26 Februari 2026" (a Form 6
# date range) or "2025 - 26/02/2026" is not session 2025/26.
_DAY_MONTH_YEAR_RE = re.compile(rf'\s*{_MONTH}\b\.?,?\s*(?:20)?\d{{2}}\b', re.I)
_NUMERIC_DATE_RE = re.compile(r'\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:20)?\d{2}\b')
# After a DASH a month name alone makes the tail a day too ("Julai 2025 - 26 Feb"). After a slash it
# does not: "Session 2024/25 February intake" is a session with its intake month.
_MONTH_AFTER_RE = re.compile(rf'\s*{_MONTH}\b', re.I)

# A month WITH its year on the intake line ("Intake Jan 2025", "Ambilan September 2025").
_MONTH_YEAR_RE = re.compile(rf'\b({_MONTH})\b\.?,?\s*(20\d{{2}})\b', re.I)
_MONTH_ALONE_RE = re.compile(rf'\b({_MONTH})\b', re.I)
# A month with no year inside a session S/S+1: September to November can only be S, January to
# April only S+1. Any other month (May to August, December: "Ambilan Disember") could be either.
_FIRST_MONTHS, _SECOND_MONTHS = {9, 10, 11}, {1, 2, 3, 4}

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
_KEYWORD = r'(semester|sem|penggal|term|tahun|year|sesi|session)'
_TERM_RE = re.compile(
    rf'\b{_KEYWORD}\.?\s*[:.\-]?\s*({_TOKEN}(?:\s*(?:/|,|&|-|\bdan\b|\band\b|\bor\b|\batau\b)\s*{_TOKEN})*)',
    re.I)
_TOKEN_RE = re.compile(_TOKEN, re.I)
_ORDINALS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4,
             '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6, 'seventh': 7, '7th': 7,
             'eighth': 8, '8th': 8, 'final': 99, 'last': 99}
_ORDINAL_RE = re.compile(
    r'\b(' + '|'.join(sorted(_ORDINALS, key=len, reverse=True)) + r')\s+(semester|sem|term|year|tahun)\b',
    re.I)
# Upper Six is the second year of Form 6: a continuing student.
_UPPER_SIX_RE = re.compile(r'\b(?:tingkatan|form)\s*(?:6|enam|six)\s*atas\b|\bupper\s*(?:6|six)\b', re.I)
_STPM_WORDS_RE = re.compile(r'\b(?:tingkatan\s*(?:6|enam)|form\s*(?:6|six)|stpm|penggal)\b', re.I)


def _number(token):
    t = re.sub(r'\s+', ' ', token.strip().lower())
    if t.isdigit():
        return int(t)
    return _ROMAN.get(t) or _WORDS.get(t)


def _terms(text):
    """The term facts on the line, as a set of: 'later' (Semester 3+, Year 2+, Upper Six - the
    student's PLACE in the course, not the intake), 'first', 'second', 'either' (a polytechnic
    "Sesi II", which starts in December of S or January of S+1), 'penggal' (a Form 6 term)."""
    out = set()
    if _UPPER_SIX_RE.search(text):
        out.add('later')
    found = [(m.group(1).lower(), [_number(t) for t in _TOKEN_RE.findall(m.group(2))])
             for m in _TERM_RE.finditer(text)]
    found += [(m.group(2).lower(), [_ORDINALS[m.group(1).lower()]]) for m in _ORDINAL_RE.finditer(text)]
    for key, nums in found:
        if key == 'penggal':
            out.add('penggal')
        for n in nums:
            if n is None:
                continue
            if key in ('tahun', 'year'):
                if n >= 2:
                    out.add('later')
            elif n >= 3:
                out.add('later')
            elif key in ('sesi', 'session'):
                out.add('first' if n == 1 else 'either')
            else:
                out.add('first' if n == 1 else 'second')
    return out


def _tail_is_a_day(text, m):
    """True when the two-digit tail of a `_SESSION_RE` match is the day of a date."""
    if len(m.group(3)) != 2:
        return False
    after = text[m.end():]
    if _DAY_MONTH_YEAR_RE.match(after) or _NUMERIC_DATE_RE.match(after):
        return True
    return m.group(2) != '/' and bool(_MONTH_AFTER_RE.match(after))


def _sessions(text):
    """``[(start index, S, S+1), ...]`` for every academic session on the line."""
    out = []
    for m in _SESSION_RE.finditer(text):
        a, tail = int(m.group(1)), m.group(3)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        if b == a + 1 and not _tail_is_a_day(text, m):
            out.append((m.start(), a, b))
    return out


def looks_stpm(text):
    """True when a letter's words name Form 6 (Tingkatan 6, STPM, a Penggal)."""
    return bool(_STPM_WORDS_RE.search(text or ''))


def gift_start_years(intake, reporting_date='', stored_year=None, confirmation=False, stpm=False):
    """The years the course may have started in, as a frozenset; EMPTY = unknown (a person checks).

    ``intake`` and ``reporting_date`` are the letter's own lines; ``stored_year`` is the year of the
    application's stored reporting date (an officer may have typed it); ``confirmation`` is True for
    a confirmation-of-studies letter and ``stpm`` for a Form 6 student or letter. In order:

      1. a later term anywhere on the line (Semester 3+, Year 2+, final year, Upper Six) -> unknown,
         whatever date the letter or the application carries: that date is when THAT term starts;
      2. a second term (Semester 2 / II, Penggal 2, Sesi II) on a confirmation or STPM letter ->
         unknown: it names the student's place in the course, not the intake;
      3. no session on the line: the first year on it, else the letter's date year, else the stored
         year (main's order). A letter date whose year is not on the intake line -> unknown;
      4. two different sessions -> unknown;
      5. a month written WITH its year ("Intake Jan 2025 (Session 2024/2025)") wins, if it sits
         inside the session and agrees with the letter's date;
      6. else the terms and month names: a first term or September-November -> S; a second term or
         January-April -> S+1; both -> unknown; a polytechnic "Sesi II", another month or nothing
         at all (a bare session) -> both S and S+1;
      7. the letter's date then picks one of those years, or, if its year is not among them (term
         and date disagree, or a date outside the session), unknown.

    A session line never takes the stored date: if the letter itself cannot tell, nor can a copy."""
    text = intake or ''
    rdm = re.search(r'\b(20\d{2})\b', reporting_date or '')
    rd_year = int(rdm.group(1)) if rdm else None
    terms = _terms(text)
    if 'later' in terms:
        return EMPTY
    if (confirmation or stpm or 'penggal' in terms) and terms & {'second', 'either'}:
        return EMPTY
    sessions = _sessions(text)
    if not sessions:
        years = [int(y) for y in re.findall(r'\b(20\d{2})\b', text)]
        if years:
            return EMPTY if rd_year is not None and rd_year not in years else frozenset({years[0]})
        if rd_year is not None:
            return frozenset({rd_year})
        return frozenset({int(stored_year)}) if stored_year else EMPTY
    if len({(s, s1) for _i, s, s1 in sessions}) > 1:
        return EMPTY
    starts = {i for i, _s, _s1 in sessions}
    first, second = sessions[0][1], sessions[0][2]
    written = {int(m.group(2)) for m in _MONTH_YEAR_RE.finditer(text) if m.start(2) not in starts}
    if written:
        year = next(iter(written)) if len(written) == 1 else None
        ok = year in (first, second) and rd_year in (None, year)
        return frozenset({year}) if ok else EMPTY
    months = {_MONTH_NUM[m.group(1).lower()] for m in _MONTH_ALONE_RE.finditer(text)}
    says_first = 'first' in terms or bool(months & _FIRST_MONTHS)
    says_second = 'second' in terms or bool(months & _SECOND_MONTHS)
    if says_first and says_second:
        return EMPTY
    if says_first:
        cand = {first}
    elif says_second:
        cand = {second}
    else:
        cand = {first, second}
    if rd_year is not None:
        return frozenset({rd_year}) if rd_year in cand else EMPTY
    return frozenset(cand)
