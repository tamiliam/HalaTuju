"""The course-start year a gift's start-year rule reads off an offer letter - owner ruling 2026-11-16.

FOR THE GIFT'S START-YEAR RULE ONLY (`start_year.reading`). The money - the STPM award size and the
funding estimate - reads `pathway_engine.course_start_year`, which is main's reading, unchanged and
pinned by `tests/test_start_year_money.py`. The two readings are kept apart (H3a rebuild).

The owner's reading of an offer letter (16 Nov 2026, replacing the closed-vocabulary reader): "Most
offer letters have a reporting date. Otherwise the title says the year like 2026, or it may say
2024/25 (which means 2024)." A check of 286 real letters bore it out (docs/decisions.md). In order:

  1. the letter's REPORTING DATE (its stored field, already cleaned by `vision.sanitize`) -> its year.
     A reporting date that is there but holds no 20xx year ("16 Februari", "16/02/25") makes the whole
     reading unknown: the letter names a date the reader cannot date, so no later step guesses;
  2. else ONE year on the intake line ("2026", "Ambilan Julai 2026") -> that year;
  3. else a SESSION (2024/2025, 2024/25, 2024-2025; not one straight after an exam word: "Lepasan STPM
     2024/2025" is an exam line, unknown). Lead's rule, 16 Nov - WHEN IN DOUBT, UNKNOWN:
     a. NO other year, date or month-year on the line -> its FIRST year; its SECOND year with a
        second-intake word ("Sesi 2", "Sesi II", "Semester 2", "Semester II", "Ambilan 2"; a Sesi II
        beside a Semester 1 / Year 1 too) or a January-to-April month NAME on a line holding an intake
        / semester word (Ambilan, Kemasukan, Intake, Admission, Sem, Semester - not Sesi / Session):
        "Ambilan Sesi 2024/2025: Februari" = 2025; "Sesi 2026/2027, tutup 30 April" holds none = 2026;
     b. ONE other date or month-year ("10/03/2025", "17.02.2025", "Feb 2025", "3 March 2025") RIGHT
        AFTER a start word (Ambilan, Kemasukan, Tarikh Kemasukan / Mendaftar / Pendaftaran, Lapor Diri,
        Intake, Admission, mulai, bermula, commencing, starting, Semester / Sem) and in one of the
        session's two years -> that year ("Sesi 2024/2025 mulai 17.02.2025" = 2025). A start word
        straight after a break word is none ("cuti semester bermula 1 Jan 2025"). A plain year
        right after an intake word reads too, whatever the session ("Ambilan 2023 Sesi 2025/2026" = 2023);
     c. ANY other extra year, date or month-year (a closing, letter, update or reference date, two
        dates, no start word, a clash with an intake month or term, a year outside the session, a
        numeric date with a two-digit year - "Lapor Diri 16/02/25" is never read as 2025) ->
        unknown ("Session 2024/25 Feb 2025" has no start word, so unknown);
  4. else unknown.

UNKNOWN always, whatever the date: a later term (Year 2+, Semester 3+, final year, Upper Six, Y2S1,
Part 3+, also in the programme / stream words), a readmission or credit-transfer word, and a
confirmation letter (it names the CURRENT session) unless its line writes the intake (Year 1 / Tahun
1 / Lower Six, or an intake / admission word with a month and its year; Semester 1 is only the current
semester; a confirmation reads its line only, never its date). Several different years on the line
with no reporting date, two different sessions, or a first and a second intake together are unknown
too, and so is a year the scan damaged ("2O25"). Exam years are NEVER a start year (owner, 16 Nov): a
line with an exam word in any form (SPM, S.P.M., S P M, SPMV, STPM, SVM, STAM, SKM, DKM, MUET, UEC,
O / A-Level, the long names incl. Sijil / Diploma Kemahiran Malaysia, "peperiksaan" / "examination";
"SPM2024", "STPM/2024") gives no single year ("Lepasan S P M 2024" is unknown); on a session line the
exam's own year is ignored, not an extra year ("Sesi 2025/2026 (S.P.M. 2024)" = 2025). A year with a
letter glued before it is a code ("kod UH2024"), not a year.

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

# An exam word in any form (owner 16 Nov 2026: exam years are NEVER a start year). A line with no
# session holding one gives no single year at all - only the reporting date reads it. Letter
# look-arounds, not \b, so "SPM2024", "SPM (2024)" and "STPM/2024" count; the letters of an
# initialism may stand apart ("S.P.M.", "S P M"). SKM / DKM (Sijil / Diploma Kemahiran Malaysia) too.
_SEP = r'(?:\.\s*|\s)?'
_EXAM_RE = re.compile(
    rf'(?<![a-z])(?:S{_SEP}(?:T{_SEP})?P{_SEP}M\.?(?:\s*V\.?)?|S{_SEP}V{_SEP}M\.?|S{_SEP}T{_SEP}A{_SEP}M\.?'
    rf'|[SD]{_SEP}K{_SEP}M\.?'
    r'|UEC|MUET|IGCSE|[OA][\s\-]?Levels?|peperiksaan|exam(?:ination)?s?'
    r'|sijil\s+(?:pelajaran|tinggi\s+persekolahan|vokasional|tinggi\s+agama|kemahiran)\s+malaysia'
    r'|diploma\s+kemahiran\s+malaysia'
    r'|unified\s+examination\s+certificate|malaysian\s+university\s+english\s+test)(?![a-z])', re.I)
# The exam's own year, straight after its word ("SPM 2024", "SPM (2024)", "SPM tahun 2024"): on a
# session line it is ignored, not an extra year ("Sesi 2025/2026 (S.P.M. 2024)" = 2025).
_EXAM_YEAR_RE = re.compile(_EXAM_RE.pattern + r"[\s.:;,'(/\-]{0,4}(?:tahun\s*)?(20\d{2})(?!\d)", re.I)
# An intake / admission word with a month and its year: what a confirmation letter must write to
# name her intake ("Ambilan September 2025", "Tarikh Mendaftar: 3 Mac 2025").
_ADMIT = r'(?:ambilan|pengambilan|kemasukan|intake|admission|tarikh\s+(?:mendaftar|pendaftaran))'
_ADMIT_MONTH_YEAR_RE = re.compile(
    rf'(?<![a-z]){_ADMIT}(?![a-z])[^\d\n]{{0,12}}?(?:\d{{1,2}}\s*)?(?<![a-z]){_MONTH}(?![a-z])\.?,?\s*20\d{{2}}(?!\d)',
    re.I)
# Year 1 / Tahun 1 / Lower Six on a confirmation letter (Semester 1 is only the CURRENT semester).
_YEAR_ONE_RE = re.compile(
    r'(?<![a-z])(?:tahun|thn|year|yr)(?:\s+(?:pengajian|of\s+study))?\.?\s*(?:[:.\-(]\s*)?(?:ke\s*(?:-\s*)?)?'
    r'(?:1|satu|pertama|one|i)(?![a-z\d])|\b(?:first|1st)[\s\-]+(?:year|yr)\b|\bY\s*1\s*S\s*\d\b'
    r'|\b(?:tingkatan|form)\s*(?:6|enam|six)\s*(?:bawah|lower)\b|\blower\s*(?:(?:form|tingkatan)\s*)?(?:6|six)\b'
    r'|\bL\s*6\b', re.I)
# A month counts as the INTAKE month only on a line holding an intake / semester word ("Ambilan
# Sesi 2024/2025: Februari", "Sem 1 2024/2025 Feb", "Feb intake"). Sesi / Session is not one:
# "Sesi 2026/2027, tutup 30 April" names no intake month (lead's decision, 16 Nov 2026).
_INTAKE_LINE_RE = re.compile(
    r'(?<![a-z])(?:pengambilan|ambilan|kemasukan|intake|admission|semester|sem)(?![a-z])', re.I | re.A)
# ---- A session line's other dates (lead's rule, 16 Nov 2026: when in doubt, unknown) ----------------
# A word that starts the course. A date or month-year straight after one is the intake's date.
_START_RE = re.compile(
    r'(?<![a-z])(?:tarikh\s+(?:kemasukan|mendaftar|pendaftaran)|lapor\s+diri|pengambilan|ambilan|kemasukan'
    r'|intake|admission|mulai|bermula|commencing|starting|semester|sem)(?![a-z])', re.I | re.A)
# A break word: a start word straight after one starts a holiday, not the course ("cuti semester
# bermula 1 Jan 2025", "semester break starting Feb 2025"). Read on the text just before the start word.
_BREAK_BEFORE_RE = re.compile(r'(?<![a-z])(?:cuti(?:\s+(?:semester|sem))?|break|holidays?)[\s:,\-]*$', re.I | re.A)
# A numeric date with a two-digit year ("16/02/25", "16.2.25"): on a session line it is an extra date
# (unknown), never expanded to 20xx.
_SHORT_DATE_RE = re.compile(r'(?<!\d)\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2}(?!\d)')
# The intake words whose plain year counts beside any session ("Ambilan 2023 Sesi 2025/2026" = 2023).
_INTAKE_WORD_RE = re.compile(r'(?:pengambilan|ambilan|kemasukan|intake|admission)', re.I)
# What may stand between a start word and its date: spaces and stops, a term number ("Semester 1
# (Jan 2025)"), Sesi / Session / Akademik and the session itself (masked '#': "Ambilan Sesi 2023/2024
# Feb 2024").
_GAP_RE = re.compile(r'(?:[\s:;,.\-()#]|(?<![a-z])(?:sesi|session|akademik|academic|\d{1,2}|ii|i)(?![a-z\d]))*',
                     re.I | re.A)
# The date a 20xx year belongs to: "10/03/" or "01/" before it, "-03-10" after it, or a month name
# (and a day) before it ("3 March 2025", "Feb. 2025").
_NUM_BEFORE_RE = re.compile(r'(?<!\d)(\d{1,2})\s*[/.\-]\s*(?:(\d{1,2})\s*[/.\-]\s*)?$')
_NUM_AFTER_RE = re.compile(r'[-.](\d{1,2})(?:[-.]\d{1,2})?(?!\d)')
_MONTH_YEAR_RE = re.compile(rf'(?:(?<!\d)\d{{1,2}}\s*)?(?<![a-z])({_MONTH})\.?,?\s*$', re.I | re.A)
# Line by line, as `str.splitlines` cuts them, keeping each line's place in the text.
_LINE_RE = re.compile(r'[^\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]+')
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
    r'|ambilan|pengambilan|intake)(?:\s+(?:pengajian|of\s+study))?\.?\s*(?:[:.\-(]\s*)?(?:ke\s*(?:-\s*)?)?'
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


def _sessions(text):
    """The distinct sessions ``(S, S+1)`` on the line, and the character places they take. A
    session whose first year is an exam's own year ("Lepasan STPM 2024/2025") is none: an exam line."""
    sessions, taken = set(), set()
    exam_years = {m.start(1) for m in _EXAM_YEAR_RE.finditer(text)}
    for m in _SESSION_RE.finditer(text):
        if m.start(1) in exam_years:
            continue
        a = int(m.group(1))
        tail = next(g for g in m.groups()[1:] if g)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        if b == a + 1:
            sessions.add((a, b))
            taken.update(range(m.start(), m.end()))
    return sessions, taken


def _month(token):
    n = int(token)
    return n if 1 <= n <= 12 else None


def _unit(text, m):
    """The date a 20xx year (an `_LINE_YEAR_RE` match) belongs to, as ``(start, end, year, kind,
    month)``: kind 'date' for a numeric date or a month-year (month None when it cannot be read),
    'year' for a plain year."""
    ys, ye = m.span(1)
    year, lo = int(m.group(1)), max(0, ys - 24)
    after = _NUM_AFTER_RE.match(text, ye)
    if after:                                            # "2025-03-10"
        return ys, after.end(), year, 'date', _month(after.group(1))
    num = _NUM_BEFORE_RE.search(text, lo, ys)
    if num:                                              # "10/03/2025", "01/2025"
        return num.start(), ye, year, 'date', _month(num.group(2) or num.group(1))
    name = _MONTH_YEAR_RE.search(text, lo, ys)
    if name:                                             # "3 March 2025", "Feb 2025"
        return name.start(), ye, year, 'date', _MONTH_NUM.get(name.group(1).lower())
    return ys, ye, year, 'year', None


def _extras(text, taken):
    """A session line's other dates (`_unit`s): every 20xx year outside the session, but not an
    exam's own year, and every numeric date with a two-digit year (kind 'short': always unclear).
    It stops at two: two is already unknown."""
    taken = set(taken)
    for m in _EXAM_YEAR_RE.finditer(text):
        taken.add(m.start(1))
    out = []
    for m in _LINE_YEAR_RE.finditer(text):
        if m.start(1) not in taken:
            out.append(_unit(text, m))
            if len(out) == 2:
                return out
    for m in _SHORT_DATE_RE.finditer(text):
        if not any(i in taken for i in range(m.start(), m.end())):
            out.append((m.start(), m.end(), None, 'short', None))
            if len(out) == 2:
                break
    return out


def _start_word(text, at, taken):
    """The start word (`_START_RE`) that the date at ``at`` follows straight on (only `_GAP_RE`
    between, the session masked as '#'), else None. A start word straight after a break word
    (`_BREAK_BEFORE_RE`) is none."""
    last = None
    for m in _START_RE.finditer(text, 0, at):
        if not _BREAK_BEFORE_RE.search(text, max(0, m.start() - 24), m.start()):
            last = m
    if last is None:
        return None
    gap = ''.join('#' if i in taken else c for i, c in enumerate(text[last.end():at], last.end()))
    return last if _GAP_RE.fullmatch(gap) else None


def _session_reading(text, session, taken, terms):
    """One session's line (lead's rule, 16 Nov 2026; module docstring step 3)."""
    s, s1 = session
    extras = _extras(text, taken)
    # The months written without a year; those on a line holding an intake / semester word are
    # intake months.
    loose, months = set(), set()
    for line in _LINE_RE.finditer(text):
        intake_line = _INTAKE_LINE_RE.search(line.group(0))
        for w in _MONTH_RE.finditer(text, line.start(), line.end()):
            mo = _MONTH_NUM.get(w.group(1).lower())
            if mo and not any(e[0] <= w.start() < e[1] for e in extras):
                loose.add(mo)
                if intake_line:
                    months.add(mo)
    early = any(mo <= 4 for mo in months)              # January to April: the session's second half
    second = 'second_intake' in terms
    # A first and a second intake together: "Semester 1 / 2", "Sesi I Ambilan Februari",
    # "Ambilan September / Februari". (Semester 1 with a February month is a February starter's first
    # semester, and Semester 1 / Year 1 with a Sesi II is the second intake's: no clash.)
    if ('first' in terms and second and 'second_session' not in terms) \
            or ('first_intake' in terms and (second or early)) \
            or (early and any(mo >= 5 for mo in months)):
        return GiftReading(None, 'both_intakes')
    if not extras:
        return GiftReading(s1, 'session_second') if second or early else GiftReading(s, 'session_first')
    if len(extras) > 1:
        return GiftReading(None, 'unclear_date')
    (start, _, year, kind, month), = extras
    if kind == 'short':
        return GiftReading(None, 'unclear_date')
    word = _start_word(text, start, taken)
    if kind == 'year':
        # The owner's step 2: a plain year straight after an intake word, whatever the session.
        if word and _INTAKE_WORD_RE.fullmatch(word.group(0)) \
                and re.fullmatch(r'[\s:.\-(]*', text[word.end():start]):
            return GiftReading(year, 'intake_year')
        return GiftReading(None, 'unclear_date')
    # A date or month-year after a start word, in the session, with no other month or intake beside it.
    if word is None or year not in session or loose - {month} or (second and year != s1) \
            or ('first_intake' in terms and year != s):
        return GiftReading(None, 'unclear_date')
    return GiftReading(year, 'intake_date')


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
    if confirmation:
        # It writes the intake: Year 1 / Tahun 1 / Lower Six, or an intake / admission word with a
        # month and its year. Semester 1 or a bare month-year is only the CURRENT semester.
        if not (_YEAR_ONE_RE.search(text) or _ADMIT_MONTH_YEAR_RE.search(text)):
            return GiftReading(None, 'confirmation')
    else:
        rd_year = _date_year(reporting_date)
        if rd_year is not None:
            return GiftReading(rd_year, 'reporting_date')
        if (reporting_date or '').strip() and not _YEAR_RE.search(reporting_date):
            # A date is there but has no 20xx year ("16 Februari", "16/02/25"): no step guesses.
            return GiftReading(None, 'undated_reporting_date')
    sessions, taken = _sessions(text)
    if len(sessions) > 1:
        return GiftReading(None, 'several_sessions')
    if sessions:
        return _session_reading(text, next(iter(sessions)), taken, terms)
    years = set() if _EXAM_RE.search(text) else {int(y) for y in _LINE_YEAR_RE.findall(text)}
    if len(years) == 1:
        return GiftReading(next(iter(years)), 'intake_year')
    if years:
        return GiftReading(None, 'several_years')
    return GiftReading(None, 'exam_line' if _EXAM_RE.search(text) else 'no_year')


def gift_start_year(intake, reporting_date='', **kw):
    """`gift_reading`'s year alone (None = unknown)."""
    return gift_reading(intake, reporting_date, **kw).year
