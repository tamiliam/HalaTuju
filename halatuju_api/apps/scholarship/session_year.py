"""The course-start year a gift's start-year rule reads off an offer letter - owner ruling 2026-11-16.

FOR THE GIFT'S START-YEAR RULE ONLY (`start_year.reading`). The money - the STPM award size and the
funding estimate - reads `pathway_engine.course_start_year`, which is main's reading, unchanged and
pinned by `tests/test_start_year_money.py`. The two readings are kept apart (H3a rebuild).

The owner's reading of an offer letter (16 Nov 2026, replacing the closed-vocabulary reader): "Most
offer letters have a reporting date. Otherwise the title says the year like 2026, or it may say
2024/25 (which means 2024)." A check of 286 real letters bore it out (docs/decisions.md). In order:

  1. the letter's REPORTING DATE (its stored field, already cleaned by `vision.sanitize`) -> its year;
  2. else ONE year on the intake line ("2026", "Ambilan Julai 2026") -> that year;
  3. else a SESSION (2024/2025, 2024/25, 2024-2025) -> its FIRST year; but its SECOND year with a
     second-intake word ("Sesi 2", "Sesi II", "Semester 2", "Semester II", "Ambilan 2"; a Sesi II
     beside a Semester 1 / Year 1 too) or a January-to-April month on a line holding an intake /
     semester word ("Ambilan Sesi 2024/2025: Februari", "Sem 1 2024/2025 Feb": the session's second
     half; "Sesi 2026/2027, tutup 30 April" holds none, so 2026). Another year beside a session counts
     only after an intake word ("Ambilan 2023 Sesi 2025/2026" = 2023) or as a month-year inside the
     session ("Sesi 2024/25 Februari 2025" = 2025); a reference or update year is passed over;
  4. else unknown.

UNKNOWN always, whatever the date: a later term (Year 2+, Semester 3+, final year, Upper Six, Y2S1,
Part 3+, also in the programme / stream words), a readmission or credit-transfer word, and a
confirmation letter (it names the CURRENT session) unless its line writes the intake (Year 1 / Tahun
1 / Lower Six, or an intake / admission word with a month and its year; Semester 1 is only the current
semester; a confirmation reads its line only, never its date). Several different years on the line
with no reporting date, two different sessions, or a first and a second intake together are unknown
too, and so is a year the scan damaged ("2O25"). Exam years are NEVER a start year (owner, 16 Nov): a
line with an exam word in any form (SPM, S.P.M., SPMV, STPM, SVM, STAM, MUET, UEC, O / A-Level, the
long names, "peperiksaan" / "examination"; "SPM2024", "STPM/2024") gives no single year - only the date or the session; else unknown. A year with
a letter glued before it is a code ("kod UH2024"), not a year.

Pure text work: no model, no database.
"""
import re
from typing import NamedTuple, Optional


class GiftReading(NamedTuple):
    """``year`` None = unknown (a person checks). ``why`` says which step read it, or why not."""
    year: Optional[int]
    why: str


_MONTH_NUM = {
    'januari': 1, 'january': 1, 'jan': 1, 'februari': 2, 'february': 2, 'feb': 2,
    'mac': 3, 'march': 3, 'mar': 3, 'april': 4, 'apr': 4, 'mei': 5, 'may': 5, 'june': 6, 'jun': 6,
    'julai': 7, 'july': 7, 'jul': 7, 'ogos': 8, 'august': 8, 'aug': 8, 'september': 9, 'sept': 9,
    'sep': 9, 'oktober': 10, 'october': 10, 'okt': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'disember': 12, 'december': 12, 'dis': 12, 'dec': 12,
}
_MONTH = '(?:' + '|'.join(sorted(_MONTH_NUM, key=len, reverse=True)) + ')'
# Letter look-arounds, not \b, so a month glued to a number still reads ("2024/25Feb"). ASCII only
# (re.A): "DİS" or "ſep" must not fold into a month name the table does not hold.
_MONTH_RE = re.compile(rf'(?<![a-z])({_MONTH})(?![a-z])', re.I | re.A)

# A 20xx year that is not part of a longer number. Digit look-arounds, not \b, so a year with a
# letter glued AFTER it ("2024/2025Semester") still reads. (The reporting date's year.)
_YEAR_RE = re.compile(r'(?<!\d)(20\d{2})(?!\d)')
# On the intake line a year with a letter glued BEFORE it is a code, not a year ("kod UH2024").
_LINE_YEAR_RE = re.compile(r'(?<![\dA-Za-z])(20\d{2})(?!\d)')
# A session: "2024/2025", "2024 / 25", "2024-2025", "2024-25" (a dash two-digit tail only with no
# spaces and no date after it: "2025 - 26/02/2026" is a date), and "20242025" glued. Two CONSECUTIVE
# years (checked in code), so a course span "2026/2031" or "6 / 2025 - 12 / 2026" is not one.
_SESSION_RE = re.compile(
    r'(?<!\d)(20\d{2})(?:\s*/\s*(20\d{2}|\d{2})|\s*[-–]\s*(20\d{2})|[-–](\d{2})(?!\s*[/.\-]\s*\d)|(20\d{2}))(?!\d)')

# An exam word in any form (owner 16 Nov 2026: exam years are NEVER a start year). A line holding
# one gives no single year at all - only the reporting date or the session read it. Letter
# look-arounds, not \b, so "SPM2024", "SPM (2024)" and "STPM/2024" count.
_EXAM_RE = re.compile(
    r'(?<![a-z])(?:S(?:\.\s*)?(?:T(?:\.\s*)?)?P(?:\.\s*)?M\.?(?:\s*V\.?)?|S(?:\.\s*)?V(?:\.\s*)?M\.?'
    r'|S(?:\.\s*)?T(?:\.\s*)?A(?:\.\s*)?M\.?'
    r'|UEC|MUET|IGCSE|[OA][\s\-]?Levels?|peperiksaan|exam(?:ination)?s?'
    r'|sijil\s+(?:pelajaran|tinggi\s+persekolahan|vokasional|tinggi\s+agama)\s+malaysia'
    r'|unified\s+examination\s+certificate|malaysian\s+university\s+english\s+test)(?![a-z])', re.I)
# An intake / admission word with a month and its year: what a confirmation letter must write to
# name her intake ("Ambilan September 2025", "Tarikh Mendaftar: 3 Mac 2025").
_ADMIT = r'(?:ambilan|pengambilan|kemasukan|intake|admission|tarikh\s+(?:mendaftar|pendaftaran))'
_ADMIT_MONTH_YEAR_RE = re.compile(
    rf'(?<![a-z]){_ADMIT}(?![a-z])[^\d\n]{{0,12}}?(?:\d{{1,2}}\s*)?(?<![a-z]){_MONTH}(?![a-z])\.?,?\s*20\d{{2}}(?!\d)',
    re.I)
# Year 1 / Tahun 1 / Lower Six on a confirmation letter (Semester 1 is only the CURRENT semester).
_YEAR_ONE_RE = re.compile(
    r'(?<![a-z])(?:tahun|thn|year|yr)(?:\s+(?:pengajian|of\s+study))?\.?\s*[:.\-(]?\s*(?:ke\s*-?\s*)?'
    r'(?:1|satu|pertama|one|i)(?![a-z\d])|\b(?:first|1st)[\s\-]+(?:year|yr)\b|\bY\s*1\s*S\s*\d\b'
    r'|\b(?:tingkatan|form)\s*(?:6|enam|six)\s*(?:bawah|lower)\b|\blower\s*(?:(?:form|tingkatan)\s*)?(?:6|six)\b'
    r'|\bL\s*6\b', re.I)
# A month counts as the INTAKE month only on a line holding an intake / semester word ("Ambilan
# Sesi 2024/2025: Februari", "Sem 1 2024/2025 Feb", "Feb intake"). Sesi / Session is not one:
# "Sesi 2026/2027, tutup 30 April" names no intake month (lead's decision, 16 Nov 2026).
_INTAKE_LINE_RE = re.compile(
    r'(?<![a-z])(?:pengambilan|ambilan|kemasukan|intake|admission|semester|sem)(?![a-z])', re.I | re.A)
# Another year beside a session counts only straight after an intake word ("Ambilan 2023",
# "Intake Sept 2023", "Ambilan bagi Julai 2024"); a reference or update year ("Rujukan UPU/2024/77",
# "dikemaskini 1/12/2024") is passed over and the session decides.
_AFTER_INTAKE_RE = re.compile(
    r'(?<![a-z])(?:pengambilan|ambilan|kemasukan|intake|admission)(?![a-z])[^\d\n]{0,16}'
    r'(?:\d{1,2}\s*[^\d\n]{0,12})?$', re.I)
# A month name straight before a year ("Februari 2025", "Feb. 2025").
_MONTH_BEFORE_RE = re.compile(rf'(?<![a-z]){_MONTH}\.?,?\s*$', re.I | re.A)
# A year the scan damaged ("2O25", "202S"): the line cannot be read safely.
_DAMAGED_YEAR_RE = re.compile(r'(?<![\dA-Za-z])2[0Oo][0-9OoSsIl]{2}(?![\dA-Za-z])')

# ---- Term numbers ---------------------------------------------------------------------------------
# Digits, roman, Malay and English words. "dua belas" before "dua".
_WORDS = {
    'satu': 1, 'pertama': 1, 'one': 1, 'dua belas': 12, 'kedua belas': 12, 'dua': 2, 'kedua': 2,
    'two': 2, 'tiga': 3, 'ketiga': 3, 'three': 3, 'empat': 4, 'keempat': 4, 'four': 4, 'lima': 5,
    'kelima': 5, 'five': 5, 'enam': 6, 'keenam': 6, 'six': 6, 'tujuh': 7, 'ketujuh': 7, 'seven': 7,
    'lapan': 8, 'kelapan': 8, 'eight': 8, 'sembilan': 9, 'kesembilan': 9, 'nine': 9, 'sepuluh': 10,
    'kesepuluh': 10, 'ten': 10, 'sebelas': 11, 'kesebelas': 11, 'eleven': 11, 'twelve': 12,
    'akhir': 99, 'final': 99, 'last': 99,
}
# "ll", "Il", "lI", "I1": a scanned "II".
_ROMAN = {'i': 1, 'ii': 2, 'll': 2, 'il': 2, 'li': 2, 'i1': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6,
          'vii': 7, 'viii': 8, 'ix': 9, 'x': 10, 'xi': 11, 'xii': 12}
_TOKEN = (r'(?:\d{1,2}(?!\d)|(?:xii|xi|ix|x|viii|vii|vi|iv|v|iii|ii|i1|ll|il|li|i)\b|(?:'
          + '|'.join(sorted(_WORDS, key=len, reverse=True)).replace(' ', r'\s+') + r')\b)')
_TOKEN_RE = re.compile(_TOKEN, re.I)
# A term word and its number(s): "Semester 3", "Tahun ke-2", "Year of Study 2", "Sem 1/2", "Part 4".
_TERM_RE = re.compile(
    r'(?<![a-z])(semester|sem|penggal|term|tahun|thn|year|yr|sesi|session|part|bahagian'
    r'|ambilan|pengambilan|intake)(?:\s+(?:pengajian|of\s+study))?\.?\s*[:.\-(]?\s*(?:ke\s*-?\s*)?'
    rf'({_TOKEN}(?:\s*(?:/|,|&|-|\bdan\b|\band\b|\bor\b|\batau\b)\s*{_TOKEN})*)', re.I)
_ORDINALS = {'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3, 'fourth': 4,
             '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6, 'seventh': 7, '7th': 7,
             'eighth': 8, '8th': 8, 'final': 99, 'last': 99, 'senior': 99}
_ORDINAL_RE = re.compile(
    r'\b(' + '|'.join(sorted(_ORDINALS, key=len, reverse=True))
    + r')[\s\-]+(semester|sem|term|year|yr|tahun|thn|intake|session)\b', re.I | re.A)
_YS_RE = re.compile(r'\bY\s*(\d{1,2})\s*S\s*(\d{1,2})\b', re.I)          # "Y2S1", "Y3 S1"
_YEAR_WORDS = frozenset({'tahun', 'thn', 'year', 'yr'})
_INTAKE_WORDS = frozenset({'sesi', 'session', 'ambilan', 'pengambilan', 'intake'})

# Words that name a continuing student outright: Upper Six, "Level 200", "Sophomore", "continuing".
_SIX = r'(?:6|enam|six)'
_LATER_WORDS_RE = re.compile(
    rf'\b(?:tingkatan|form)\s*{_SIX}\s*(?:atas|upper)\b|\bupper\s*(?:(?:form|tingkatan)\s*)?{_SIX}\b|\bu\s*6\b'
    r'|\blevel\s*[2-9]00\b|\bsophomore\b|\bcontinuing\b|\breturning\b|\bpelajar\s+(?:lama|senior)\b'
    r'|\blanjutan\s+pengajian\b', re.I)
# Readmission and credit-transfer words: she did not start the course with this letter.
_READMISSION_RE = re.compile(
    r'\b(?:kemasukan|pendaftaran)\s+semula\b|\bre-?\s*admi(?:ssion|tted)\b|\bre-?\s*enrol(?:l)?(?:ment)?\b'
    r'|\bre-?\s*registration\b|\badvanced?\s+standing\b|\bpindah(?:an)?\s+kredit\b|\bcredit\s+transfer\b'
    r'|\bsambung(?:an)?\s+pengajian\b|\b(?:lateral|direct)\s+entry\b|\bkemasukan\s+terus\b', re.I)


def _number(token):
    t = re.sub(r'\s+', ' ', token.strip().lower())
    if t.isdigit():
        return int(t)
    return _ROMAN.get(t) or _WORDS.get(t)


def _terms(text, context=False):
    """The term facts on the line: 'later' (Year 2+, Semester 3+, Part 3+: her PLACE in the course,
    not the intake), 'first' (Semester 1 / Year 1), 'first_intake' (Sesi 1, Ambilan 1),
    'second_intake' (Sesi 2, Semester 2, Ambilan 2). ``context`` (the programme / institution /
    stream words) yields only 'later'."""
    out = set()
    if _LATER_WORDS_RE.search(text):
        out.add('later')
    for m in _TERM_RE.finditer(text):
        key = m.group(1).lower()
        for t in _TOKEN_RE.findall(m.group(2)):
            _add(out, key, _number(t))
    for m in _ORDINAL_RE.finditer(text):
        _add(out, m.group(2).lower(), _ORDINALS.get(m.group(1).lower()))
    for m in _YS_RE.finditer(text):
        _add(out, 'year', int(m.group(1)))
        _add(out, 'semester', int(m.group(2)))
    return out & {'later'} if context else out


def _add(out, key, n):
    """One term fact. A Penggal / Term 2 or a UiTM Part 2 is no second intake (Form 6's second term
    follows a mid-year start): it reads as its session's first year, like no term at all."""
    if n is None:
        return
    if key in _YEAR_WORDS:
        out.add('later' if n >= 2 else 'first')
    elif key in ('semester', 'sem'):
        out.add('later' if n >= 3 else 'first' if n == 1 else 'second_intake')
    elif key in ('penggal', 'term'):
        if n >= 3 or n == 1:
            out.add('later' if n >= 3 else 'first')
    elif key in ('part', 'bahagian'):
        if n >= 3:
            out.add('later')
    elif key in _INTAKE_WORDS and n <= 2:
        # A Sesi II / Ambilan 2 names the intake itself: it outranks a Semester 1 / Year 1 beside it
        # ("Semester 1 Sesi II 2025/2026" is the second intake's first semester).
        out.update(('first_intake',) if n == 1 else ('second_intake', 'second_session'))


def _date_year(reporting_date):
    """The stored reporting date -> its year: ONE 20xx year in a value that reads as a date (a month
    name, or a numeric day / month / year). Else None: the next step reads the intake line."""
    text = reporting_date or ''
    years = {int(y) for y in _YEAR_RE.findall(text)}
    if len(years) != 1:
        return None
    if not (_MONTH_RE.search(text) or re.search(r'\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*20\d{2}'
                                                r'|20\d{2}\s*-\s*\d{1,2}\s*-\s*\d{1,2}', text)):
        return None
    return years.pop()


def _sessions_and_years(text):
    """``(sessions, years)``: the distinct sessions ``(S, S+1)`` and the distinct other years on the
    line; no other years at all on a line with an exam word (`_EXAM_RE`). Beside a session another
    year counts only straight after an intake word, or as a month-year inside the session; else
    the session decides."""
    sessions, taken = set(), set()
    for m in _SESSION_RE.finditer(text):
        a = int(m.group(1))
        tail = next(g for g in m.groups()[1:] if g)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        if b == a + 1:
            sessions.add((a, b))
            taken.update(range(m.start(), m.end()))
    if _EXAM_RE.search(text):
        return sessions, set()
    years = set()
    spans = {y for s in sessions for y in s}
    for m in _LINE_YEAR_RE.finditer(text):
        if m.start(1) in taken:
            continue
        before, year = text[:m.start(1)], int(m.group(1))
        if not sessions or _AFTER_INTAKE_RE.search(before) \
                or (year in spans and _MONTH_BEFORE_RE.search(before)):
            years.add(year)
    return sessions, years


def gift_reading(intake, reporting_date='', *, context='', confirmation=False):
    """The letter's course-start year for the gift's rule, as a `GiftReading` (see the module
    docstring). ``intake`` is the letter's intake line, ``reporting_date`` its stored reporting date,
    ``context`` its programme / institution / stream words, ``confirmation`` True for a
    confirmation-of-studies letter."""
    text = intake or ''
    terms = _terms(text) | _terms(context or '', context=True)
    if 'later' in terms:
        return GiftReading(None, 'later_term')
    if _READMISSION_RE.search(text) or _READMISSION_RE.search(context or ''):
        return GiftReading(None, 'readmission')
    if any(not m.group(0).isdigit() for m in _DAMAGED_YEAR_RE.finditer(text)):
        return GiftReading(None, 'damaged_year')
    sessions, years = _sessions_and_years(text)
    if confirmation:
        # It writes the intake: Year 1 / Tahun 1 / Lower Six, or an intake / admission word with a
        # month and its year. Semester 1 or a bare month-year is only the CURRENT semester.
        if not (_YEAR_ONE_RE.search(text) or _ADMIT_MONTH_YEAR_RE.search(text)):
            return GiftReading(None, 'confirmation')
    else:
        rd_year = _date_year(reporting_date)
        if rd_year is not None:
            return GiftReading(rd_year, 'reporting_date')
    if len(years) == 1:
        return GiftReading(next(iter(years)), 'intake_year')
    if years:
        return GiftReading(None, 'several_years')
    if len(sessions) > 1:
        return GiftReading(None, 'several_sessions')
    if not sessions:
        return GiftReading(None, 'exam_line' if _EXAM_RE.search(text) else 'no_year')
    (s, s1), = sessions
    # Only a month on a line holding an intake / semester word is the intake month.
    months = {_MONTH_NUM.get(w.lower()) for line in text.splitlines() if _INTAKE_LINE_RE.search(line)
              for w in _MONTH_RE.findall(line)} - {None}
    early = any(mo <= 4 for mo in months)              # January to April: the session's second half
    second = 'second_intake' in terms
    # A first and a second intake together: "Semester 1 / 2", "Sesi I Ambilan Februari",
    # "Ambilan September / Februari". (Semester 1 with a February month is a February starter's first
    # semester, and Semester 1 / Year 1 with a Sesi II is the second intake's: no clash.)
    if ('first' in terms and second and 'second_session' not in terms) \
            or ('first_intake' in terms and (second or early)) \
            or (early and any(mo >= 5 for mo in months)):
        return GiftReading(None, 'both_intakes')
    if second or early:
        return GiftReading(s1, 'session_second')
    return GiftReading(s, 'session_first')


def gift_start_year(intake, reporting_date='', **kw):
    """`gift_reading`'s year alone (None = unknown)."""
    return gift_reading(intake, reporting_date, **kw).year
