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
  * ``may_fail`` - False when the line itself holds clashing years, or when the line or the date is
    not made ONLY of known words (`_sure`): never outside.

Fifth review (lead's redesign, not a patch): OUTSIDE is a CLOSED VOCABULARY. Messy text kept leaking
wrong reds through every patched pattern, so OUTSIDE may now fire only when EVERY token of the
intake line is known (an intake / session word, a month, one clean 20xx year, one clean session
S/S+1, a first-term word, filler) and the letter's date is one clean date with one year. Anything
else - an unknown word, letters glued to digits ("2024/2025Semester", "2O25"), a dash tail that may
be a day ("2024-25 Feb"), a second date, a date range, an intake month the date's month disagrees
with, a December intake (the year's turn) - may still read inside or unknown, never outside.

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
# A day before a month ("1 Julai 2025", "3 hb. Mac"), or a numeric day/month/year: a full date.
# Not a session's tail ("2024/25 Feb") nor a term's number ("Sem 1 Okt"): see `_full_date`.
_DAY_MONTH_RE = re.compile(
    rf'(?<![\d/\-–])(?<![/\-–]\s)\b(\d{{1,2}})\s*(?:hb\.?\s*)?{_MONTH}\b'
    rf'|(?<![\d/\-–])\b(\d{{1,2}})\s*[/.\-]\s*\d{{1,2}}\s*[/.\-]\s*20\d{{2}}\b', re.I)
_TERM_BEFORE_RE = re.compile(r'(?:sem|semester|term|penggal|tahun|year|yr|thn|sesi|session|level|tingkatan|form)\.?\s*$', re.I)


# A dash two-digit tail with a number after it ("2024 - 25 2024", "2024-25 8"): no sure session.
_DASH_DIGIT_RE = re.compile(r'\b20\d{2}\s*[\-–]\s*\d{2}\s+\d')


def _full_date(text):
    """True when the line holds a full date (a day and a month), not a term number before a month."""
    return any(not _TERM_BEFORE_RE.search(text[:m.start()]) for m in _DAY_MONTH_RE.finditer(text))
# A month with no year inside a session S/S+1: September to November can only be S, January to
# April only S+1. Any other month (May to August, December: "Ambilan Disember") could be either.
_FIRST_MONTHS, _SECOND_MONTHS = {9, 10, 11}, {1, 2, 3, 4}

# An exam year is not a start year: "SPM 2024, Ambilan 2025", "(2024 lulus SPM)".
_EXAM = r'(?:SPM|STPM|SVM|STAM|UEC|MUET|IGCSE|O[\s\-]?Levels?|A[\s\-]?Levels?)'
_EXAM_YEAR_RE = re.compile(
    rf'\b{_EXAM}\b\s*(?:tahun|year)?\s*[:\-]?\s*(20\d{{2}})\b'
    rf'|\b(20\d{{2}})\s*\(?\s*(?:lulus|keputusan|results?\s+of)\s+{_EXAM}\b', re.I)
_INTAKE_RE = re.compile(r'\b(?:ambilan|pengambilan|intake|kemasukan|admission|enrol(?:l?ment)?)\b', re.I)
# An intake word right before its year ("Ambilan 2025", "Intake: Julai 2025"): with an exam year set
# aside, the start year must be named this way, or which year is which is in doubt.
_INTAKE_YEAR_RE = re.compile(
    rf'\b(?:ambilan|pengambilan|intake|kemasukan|admission|enrol(?:l?ment)?)\b\s*:?\s*(?:{_MONTH}\b\.?,?\s*)?20\d{{2}}\b',
    re.I)

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
_KEYWORD = r'(semester|sem|penggal|term|tahun|thn|year|yr|sesi|session|part|bahagian|tahap|level)'
_TERM_RE = re.compile(
    rf'\b{_KEYWORD}(?:\s+(?:pengajian|of\s+study))?\.?\s*[:.\-]?\s*(?:ke\s*-?\s*)?'
    rf'({_TOKEN}(?:\s*(?:/|,|&|-|\bdan\b|\band\b|\bor\b|\batau\b)\s*{_TOKEN})*)', re.I)
_TOKEN_RE = re.compile(_TOKEN, re.I)
_ORDINALS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4,
             '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6, 'seventh': 7, '7th': 7,
             'eighth': 8, '8th': 8, 'final': 99, 'last': 99, 'senior': 99}
_ORDINAL_RE = re.compile(
    r'\b(' + '|'.join(sorted(_ORDINALS, key=len, reverse=True))
    + r')[\s\-]+(semester|sem|term|year|yr|tahun|thn)\b', re.I)
_YS_RE = re.compile(r'\bY\s*(\d{1,2})\s*S\s*(\d{1,2})\b', re.I)          # "Y2S1", "Y3 S1"
# Upper Six is the second year of Form 6; these words name a continuing student outright. So do a
# "Level 200" (and up) and "Sophomore".
_SIX = r'(?:6|enam|six)'
_LATER_WORDS_RE = re.compile(
    rf'\b(?:tingkatan|form)\s*{_SIX}\s*(?:atas|upper)\b|\bupper\s*(?:(?:form|tingkatan)\s*)?{_SIX}\b|\bu\s*6\b'
    r'|\blevel\s*[2-9]00\b|\bsophomore\b'
    r'|\blanjutan\b|\bpelajar\s+(?:lama|senior)\b|\bcontinuing\b|\breturning\b', re.I)
_LOWER_SIX_RE = re.compile(
    rf'\b(?:tingkatan|form)\s*{_SIX}\s*(?:rendah|lower)\b|\blower\s*(?:(?:form|tingkatan)\s*)?{_SIX}\b', re.I)
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
    if key in ('tahun', 'thn', 'year', 'yr', 'tahap', 'level'):
        if n >= 2:
            out.add('later')
        elif key in ('tahun', 'thn', 'year', 'yr'):
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


# ---- The closed vocabulary OUTSIDE needs (fifth review, lead's redesign) -------------------------

#: Every word an OUTSIDE line may hold: intake / session / academic words (Malay, English), the year
#: words, the first-term words and harmless filler. Months are added below.
_KNOWN_WORDS = frozenset({
    'ambilan', 'pengambilan', 'intake', 'kemasukan', 'admission', 'enrolment', 'enrollment',
    'sesi', 'session', 'akademik', 'academic', 'pengajian',
    'semester', 'sem', 'term', 'penggal', 'tahun', 'year',
    'first', 'pertama', 'satu', 'one', 'i', '1',
    'bagi', 'for', 'the', 'of',
}) | frozenset(_MONTH_NUM)
#: A first-term number counts only straight after one of these ("Semester 1", "Tahun Satu"); "first"
#: only straight before one ("First Semester"). So "Sesi 1" / "Sesi I" (not a first-term word) fails.
_TERM_WORDS = frozenset({'semester', 'sem', 'term', 'penggal', 'tahun', 'year'})
_FIRST_NUMBERS = frozenset({'1', 'i', 'satu', 'one', 'pertama'})
_FILLER_MARKS = frozenset(':-/,()[]')
_GLUED_RE = re.compile(r'[^\W\d_]\d|\d[^\W\d_]')          # "2024/2025Sem", "2O25", "202S", "25Feb"
_SURE_SESSION_RE = re.compile(
    r"(?<![\w/\-.'])(20\d{2})(?:\s*/\s*(20\d{2}|\d{2})|-(20\d{2}|\d{2})|\s+-\s+(20\d{2}))(?![\w/\-.])")
_SURE_YEAR_RE = re.compile(r"(?<![\w/\-.'])(20\d{2})(?![\w/\-.])")
# After "2024-25" a month or a number may make the "25" a DAY ("2024-25 Feb"): never sure.
_DASH_DAY_RE = re.compile(rf'\s*(?:{_MONTH}\b|\d)', re.I)
_SESSION_MARK, _YEAR_MARK, _BAD_MARK = '\x01', '\x02', '\x03'
_SURE_TOKEN_RE = re.compile(r'[\x01\x02\x03]|\d+|[^\W\d_]+|\S')


def _sure_line(text):
    """True when the intake line is made ONLY of known tokens (see `_KNOWN_WORDS`): at most one clean
    session S/S+1 and at most one clean standalone 20xx year, nothing glued, no other number."""
    if _GLUED_RE.search(text):
        return False

    def session(m):
        a = int(m.group(1))
        tail = m.group(2) or m.group(3) or m.group(4)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        if b != a + 1 or (m.group(3) and len(tail) == 2 and _DASH_DAY_RE.match(text, m.end())):
            return _BAD_MARK
        return f' {_SESSION_MARK} '

    rest = _SURE_YEAR_RE.sub(f' {_YEAR_MARK} ', _SURE_SESSION_RE.sub(session, text))
    tokens = [t.lower() for t in _SURE_TOKEN_RE.findall(rest)]
    if _BAD_MARK in tokens or tokens.count(_SESSION_MARK) > 1 or tokens.count(_YEAR_MARK) > 1:
        return False
    words = [t for t in tokens if t not in _FILLER_MARKS and t not in (_SESSION_MARK, _YEAR_MARK)]
    if any(t not in _KNOWN_WORDS for t in words):
        return False
    for i, t in enumerate(words):
        if t in _FIRST_NUMBERS and (i == 0 or words[i - 1] not in _TERM_WORDS):
            return False
        if t == 'first' and (i + 1 == len(words) or words[i + 1] not in _TERM_WORDS):
            return False
    return True


_DATE_FORMS = (
    re.compile(rf'(?P<d>\d{{1,2}})\s+(?P<mn>{_MONTH})\.?,?\s+(?P<y>20\d{{2}})', re.I),      # 8 Sept 2025
    re.compile(rf'(?P<mn>{_MONTH})\.?\s+(?P<d>\d{{1,2}}),?\s+(?P<y>20\d{{2}})', re.I),       # Sept 8, 2025
    re.compile(rf'(?P<mn>{_MONTH})\.?,?\s+(?P<y>20\d{{2}})', re.I),                         # Mac 2025
    re.compile(r'(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>20\d{2})'),                              # 8/9/2025
    re.compile(r'(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>20\d{2})'),
    re.compile(r'(?P<d>\d{1,2})-(?P<m>\d{1,2})-(?P<y>20\d{2})'),
    re.compile(r'(?P<y>20\d{2})-(?P<m>\d{1,2})-(?P<d>\d{1,2})'),                              # 2025-09-08
    re.compile(r'(?P<y>20\d{2})'),
)


# "Isnin, 8 September 2025": a weekday in front is harmless.
_WEEKDAY_RE = re.compile(
    r'^(?:isnin|selasa|rabu|khamis|jumaat|sabtu|ahad|monday|tuesday|wednesday|thursday|friday|saturday'
    r'|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\.?,?\s+', re.I)


def _clean_date(text):
    """The letter's reporting date -> ``(year, month or None)`` when it is ONE clean date holding
    exactly one 20xx year, else None. A range, two dates, a session or any other word is not."""
    t = _WEEKDAY_RE.sub('', (text or '').strip())
    if len(_YEAR_RE.findall(t)) != 1:
        return None
    for form in _DATE_FORMS:
        m = form.fullmatch(t)
        if not m:
            continue
        g = m.groupdict()
        month = _MONTH_NUM[g['mn'].lower()] if g.get('mn') else int(g['m']) if g.get('m') else None
        if (month is not None and not 1 <= month <= 12) or (g.get('d') and not 1 <= int(g['d']) <= 31):
            return None
        return int(g['y']), month
    return None


def _sure(text, reporting_date, rd):
    """True when OUTSIDE may fire on this line and date (the closed vocabulary). ``rd`` is
    `_clean_date(reporting_date)`."""
    if reporting_date.strip() and rd is None:
        return False                                  # a messy date: a range, two dates, a session
    if not _sure_line(text):
        return False
    months = {_MONTH_NUM[m.group(1).lower()] for m in _MONTH_ALONE_RE.finditer(text)}
    rd_month = rd[1] if rd else None
    if rd_month is not None:
        months_all = months | {rd_month}
        if months and rd_month not in months:
            return False                              # the intake month and the date's disagree
    else:
        months_all = months
    # A December intake sits at the year's turn (registration in December, classes from January;
    # a polytechnic Sesi II): it is counted with either year, so never sure.
    return 12 not in months_all


_NUMBER_MARKS = frozenset('/-.:,;()[]\'"')


def _damaged(text):
    """True when a number run on the line has a letter or a symbol glued to it ("2O25", "20g21",
    "2024/2025Semester", "2024—2025", "A23CS0001"): its true year may be hidden, so the
    line is not read at all (neither inside nor outside). A single digit glued to a word
    ("Semester1", "2nd") is a term, read by `_terms`."""
    for run in text.split():
        digits = sum(ch.isdigit() for ch in run)
        if digits >= 2 and any(not ch.isdigit() and ch not in _NUMBER_MARKS for ch in run):
            return True
    return False


def gift_reading(intake, reporting_date='', *, context='', confirmation=False, stpm=False):
    """The letter's start years for the gift's rule, as a `GiftReading` (see `_reading`). A line
    with a damaged number run is UNKNOWN (`_damaged`). OUTSIDE is then allowed (``may_fail``) only
    when the line and the date pass the closed vocabulary (`_sure`); otherwise the same years read
    inside or unknown, never outside."""
    text, rd_text = intake or '', reporting_date or ''
    if _damaged(text):
        return UNKNOWN
    rd = _clean_date(rd_text)
    if rd_text.strip() and rd is None:
        return UNKNOWN                             # a messy date (a range, two dates, "2O25"): doubt
    r = _reading(text, rd, context=context, confirmation=confirmation,
                 stpm=stpm or looks_stpm(text))
    if r.years and r.may_fail and not _sure(text, rd_text, rd):
        r = r._replace(may_fail=False)
    return r


def _reading(intake, rd, *, context='', confirmation=False, stpm=False):
    """The years and signals before the closed vocabulary. ``intake`` is the letter's own line;
    ``rd`` its reporting date as `_clean_date` reads it (None when there is none or it is messy: a
    messy date is not used at all). Never the application's stored date (an old letter's, or
    typed). ``context`` the programme / institution / stream words; ``confirmation`` is True for a
    confirmation-of-studies letter, ``stpm`` for a Form 6 one.

    UNKNOWN for: a later term or a continuing word (on the line or in the context); a second term
    (Semester 2 / II, Penggal 2: the student's place, which a new or a continuing student shares);
    a polytechnic Sesi II on a confirmation or STPM letter; first and second terms together; two
    sessions; any year on a session line outside the session's two (SPM / STPM exam years are not
    start years and are set aside); two written month-years; a confirmation letter without a first
    term or a written month-year (it names the CURRENT session, not the intake); a date whose year
    the line does not allow, or a date in the wrong half of the session (September to December of
    S+1, January to April of S); a first term or Sesi I with a date in S+1; a Sesi I / II with no
    session.

    Else, on a session S/S+1 line: a written month-year in the session wins; else September-November
    -> S; January-April -> S+1; else BOTH (a bare session, Sesi I / II, and a first term too: her own
    Semester 1 may be a February intake's, in S+1); the letter's date then picks one. With no
    session: the one year on the line (agreeing with the date), or the date's year if the line has
    none; several years -> the date's year if it is among them (never a fail), else unknown.

    ``first_year`` is a first term, Year 1, Lower Six, an intake word, a written month-year, or a
    lone year with nothing else; but on a CONFIRMATION letter only Year 1 / Lower Six (its Semester 1
    or intake line may be the session's, shared by every year); on a FORM 6 line with no session a
    term is not one ("Penggal 1 2025" may name an exam sitting; the Form 6 year spans two calendar
    years); and when the year comes from the date alone, only an intake word or Year 1 is one (a
    "Semester 1" with a September date is every year's Semester 1)."""
    text = intake or ''
    rd_year, rd_month = rd if rd else (None, None)
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
    months = {_MONTH_NUM[m.group(1).lower()] for m in _MONTH_ALONE_RE.finditer(text)}
    if len(months) > 1:
        return UNKNOWN                             # two months on one line: two dates, or a span
    if exam and (not _INTAKE_YEAR_RE.search(text) or _full_date(text)):
        return UNKNOWN                             # "September SPM 2022 12/1/2025": which is which?
    if confirmation and not (terms & {'first', 'year1'} or w is not None):
        return UNKNOWN
    intake_word = bool(_INTAKE_RE.search(text))
    if confirmation:
        first_year = 'year1' in terms
    elif stpm and not sessions:
        first_year = 'year1' in terms or w is not None or intake_word
    else:
        first_year = bool(terms & {'first', 'year1'}) or w is not None or intake_word
    if sessions:
        if len({(s, s1) for _m, s, s1 in sessions}) > 1:
            return UNKNOWN
        s, s1 = sessions[0][1], sessions[0][2]
        if any(y not in (s, s1) for y in others.values()):
            return UNKNOWN
        if _DASH_DIGIT_RE.search(text) or any(
                m.group(2) != '/' and len(m.group(3)) == 2 and re.search(r'\s', m.group(0))
                for m, _s, _s1 in sessions):
            return UNKNOWN                         # "2024 - 25 2024", "Mac 2024 - 25": a session or a date?
        if _full_date(text):
            return UNKNOWN                         # a full date beside the session is a second date
        cand = {s, s1}
        first_term = bool(terms & {'first', 'sesi1'})
        if w is not None:
            (wm,) = months
            if (w == s and wm <= 4) or (w == s1 and wm >= 5):
                return UNKNOWN                     # "Jan 2026 Sesi 2026/27", "Julai 2025 Sesi 2024/25"
            cand = {w}
        else:
            to_s = bool(months & _FIRST_MONTHS)
            to_s1 = bool(months & _SECOND_MONTHS)
            # A first term or Sesi I with a January-April month clashes, as does a Sesi II with a
            # September-November one (Sesi II runs from December).
            if (to_s and to_s1) or (first_term and to_s1) or ('either' in terms and to_s):
                return UNKNOWN
            cand = {s} if to_s else {s1} if to_s1 else cand
        if rd_year is not None:
            if rd_year not in cand:
                return UNKNOWN
            if rd_month is not None and ((rd_year == s1 and rd_month >= 9) or (rd_year == s and rd_month <= 4)):
                return UNKNOWN                     # the date is in the next or the last session
            if first_term and w is None and not months and rd_year == s1:
                return UNKNOWN                     # the session's first term is in S; hers may be S+1
            cand = {rd_year}
        return GiftReading(frozenset(cand), first_year)
    if terms & {'sesi1', 'either'}:
        return UNKNOWN
    years = sorted(set(others.values()))
    if not years:
        if rd_year is None:
            return UNKNOWN
        return GiftReading(frozenset({rd_year}), first_year and (intake_word or 'year1' in terms))
    if len(years) > 1:
        return GiftReading(frozenset({rd_year}), first_year, False) if rd_year in years else UNKNOWN
    if rd_year is not None and rd_year != years[0]:
        return UNKNOWN
    lone = not terms and not confirmation
    return GiftReading(frozenset(years), first_year or lone)


def gift_start_years(intake, reporting_date='', **kw):
    """`gift_reading`'s years alone (EMPTY = unknown)."""
    return gift_reading(intake, reporting_date, **kw).years
