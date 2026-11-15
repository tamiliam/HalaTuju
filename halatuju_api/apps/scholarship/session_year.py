"""An academic SESSION on an offer letter -> the calendar year the course started (H3a, 2026-11-15).

Moved out of `pathway_engine` (which keeps `session_start_year` under the same name) so that file
stays under the 600-line standard. Pure text work: no model, no database.

A session "S/S+1" runs from about September of S to the middle of S+1, so "Sesi 2024/2025
Semester II" starts in February 2025, not 2024. Three readers use this module:

  * `session_start_year` - the one year for every reader of `intake_year` (the STPM award size,
    the funding estimate, the gift's start-year rule);
  * `bare_session` - the two years of a session that names no term and has no reporting date. The
    gift's start-year rule reads that line as EITHER year (`pathway_engine.course_start_span`,
    lead's ruling, 2026-11-15); the money keeps the first year.
"""
import re

# "2024/2025", "2024 / 25", "2024-2025": a session is two CONSECUTIVE years (checked in code), so a
# Form 6 range "6 / 2025 - 12 / 2026" is never read as one.
_SESSION_RE = re.compile(r'\b(20\d{2})\s*([/\-–])\s*(20\d{2}|\d{2})\b')
_MONTH = (r'(?:januari|january|jan|februari|february|feb|mac|march|mar|april|apr|mei|may|june|jun|'
          r'julai|july|jul|ogos|august|aug|september|sept|sep|oktober|october|okt|oct|november|nov|'
          r'disember|december|dis|dec)')
# A two-digit tail that is really the DAY of a date: "Julai 2025 - 26 Februari 2026" (a Form 6
# date range) or "2025 - 26/02/2026". Read as a session it said 2025/26, a 2026 start, and sized an
# STPM continuing student's award as a fresh entrant's (RM1,000 -> RM3,000; the H3a review).
_DAY_MONTH_YEAR_RE = re.compile(rf'\s*{_MONTH}\b\.?,?\s*(?:20)?\d{{2}}\b', re.I)
_NUMERIC_DATE_RE = re.compile(r'\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:20)?\d{2}\b')
# After a DASH, a month name alone makes the tail a day too ("Julai 2025 - 26 Feb"). After a slash
# it does not: "Session 2024/25 February intake" is a session with its intake month.
_MONTH_AFTER_RE = re.compile(rf'\s*{_MONTH}\b', re.I)

_TERM = r'(?:semester|sem\.?|sesi|session|term)\s*[:.\-]?\s*'
_FIRST_TERM_RE = re.compile(
    rf'\b{_TERM}(?:1|i|one|pertama|satu)\b|\b(?:first|1st)\s+(?:semester|sem|term)\b', re.I)
_SECOND_TERM_RE = re.compile(
    rf'\b{_TERM}(?:2|ii|two|kedua|dua)\b|\b(?:second|2nd)\s+(?:semester|sem|term)\b', re.I)
# Semester 3 and up is the student's PLACE in the course (a continuing student's letter), not the
# intake: the start year cannot be told from it, whatever date the letter carries.
_LATER_TERM_RE = re.compile(
    r'\b(?:semester|sem\.?)\s*[:.\-]?\s*(?:[3-9]|1[0-2]|iii|iv|v|vi|tiga|ketiga|empat|keempat)\b'
    r'|\b(?:third|3rd|fourth|4th|fifth|5th|sixth|6th)\s+(?:semester|sem)\b', re.I)
_FIRST_MONTH_RE = re.compile(r'\b(?:sep|sept|september|okt|oktober|oct|october)\b', re.I)
_SECOND_MONTH_RE = re.compile(r'\b(?:feb|februari|february|mac|march)\b', re.I)


def _tail_is_a_day(text, m):
    """True when the two-digit tail of a `_SESSION_RE` match is the day of a date."""
    if len(m.group(3)) != 2:
        return False
    after = text[m.end():]
    if _DAY_MONTH_YEAR_RE.match(after) or _NUMERIC_DATE_RE.match(after):
        return True
    return m.group(2) != '/' and bool(_MONTH_AFTER_RE.match(after))


def session_years(intake):
    """``(S, S+1)`` for the first academic session in the intake line, or None."""
    text = intake or ''
    for m in _SESSION_RE.finditer(text):
        a, tail = int(m.group(1)), m.group(3)
        b = int(tail) if len(tail) == 4 else (a // 100) * 100 + int(tail)
        if b == a + 1 and not _tail_is_a_day(text, m):
            return a, b
    return None


def _reading(intake, reporting_date):
    """``(year, bare)`` - see `session_start_year` for the year; ``bare`` is True only for a
    session with no term, no intake month and no reporting year (read S)."""
    years = session_years(intake)
    if years is None:
        return None, False
    first, second = years
    if _LATER_TERM_RE.search(intake):            # before the date: a Semester 3 letter's date is
        return '', False                         # when THAT semester starts, not the course
    rdm = re.search(r'\b(20\d{2})\b', reporting_date or '')
    if rdm:
        rd_year = int(rdm.group(1))
        return (str(rd_year) if rd_year in (first, second) else ''), False
    says_first = bool(_FIRST_TERM_RE.search(intake) or _FIRST_MONTH_RE.search(intake))
    says_second = bool(_SECOND_TERM_RE.search(intake) or _SECOND_MONTH_RE.search(intake))
    if says_first and says_second:
        return '', False
    if says_second:
        return str(second), False
    return str(first), not says_first


def session_start_year(intake, reporting_date=''):
    """The course-start year off an ACADEMIC SESSION intake line, as a string; '' when the session
    is there but this line cannot tell the year; None when the intake holds no session (the caller
    then reads the first year in it, as before). Best evidence first:

      1. Semester 3 and up (a continuing student) -> '', even with a reporting date: that date is
         when the later semester starts (the H3a review: "Semester 3 Sesi 2024/2025" with
         "3 Mac 2025" read 2025 and passed a 2024 starter on a 2025-2026 gift).
      2. the letter's reporting date, when its year is S or S+1: a calendar date beats a term name
         (it also settles a polytechnic "Sesi II" that starts in December of S). A reporting year
         outside the session is a clash: ''.
      3. the term: Semester I / September or October intake -> S; Semester II / February or March
         intake -> S+1. Both -> ''.
      4. no term at all (a bare session) -> S, the main intake of a session (see `bare_session`).

    What '' becomes is the caller's: `pathway_engine.course_start_year` (the money) then falls back
    to the stored reporting date; the gift's start-year rule (`course_start_span`) does not take
    the letter's own date back, so a person checks (`start_year.UNKNOWN`)."""
    return _reading(intake or '', reporting_date)[0]


def bare_session(intake, reporting_date=''):
    """``(S, S+1)`` when the line is a BARE session (no term, no intake month, no reporting year),
    else None. Lead's ruling (2026-11-15): for the gift's start-year rule only, such a line is read
    as either year; the money keeps S (`session_start_year`)."""
    year, bare = _reading(intake or '', reporting_date)
    return session_years(intake) if bare and year else None
