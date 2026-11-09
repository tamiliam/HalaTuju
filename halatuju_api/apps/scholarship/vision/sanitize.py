"""Cleaning a Gemini read: non-names out, the reporting date normalised, expected warnings
dropped (moved verbatim from ``vision.py``, audit sprint A3.1)."""

import re

from .names import name_match, nric_dob_agrees
from .judge import _strip_name_label


# Headings / labels that are never a person's name. If the AI sweeps one into a NAME field
# (a cropped/skewed photo, a section mis-read), we must not let it masquerade as a real name
# and trigger a wrong-person mismatch downstream.
_NON_NAME_MARKERS = ('KERAJAAN MALAYSIA', 'SIJIL KELAHIRAN', 'KANAK-KANAK', 'KANAK KANAK',
                     'PEMBERITAHU', 'PENDAFTAR', 'MAKLUMAT')
# NB: leading field-label stripping ('NAMA :' …) is handled by the existing `_strip_name_label`
# (defined below, used by doc_student_verdict) — reused here, not re-implemented.


def _looks_like_non_name(value: str) -> bool:
    s = (value or '').strip().upper()
    return bool(s) and any(s == m or s.startswith(m + ' ') or s == m.replace('-', ' ')
                           for m in _NON_NAME_MARKERS)


# ── Reporting-date normalisation (offer letter) ───────────────────────────────
# Offers print the report/registration date a dozen ways — "22/06/2026", "20 JUN 2026 (SABTU)",
# "20 Julai 2026 Isnin", "8 HINGGA 9 JUN 2026", "22 JUN 2026 (9.00 PAGI - 2.00 PETANG)". Normalise
# to one clean "D Mon YYYY" (e.g. "22 Jun 2026"): strip the weekday + time/parenthetical, take a
# range's START date, accept DD/MM/YYYY or "D Month YYYY" (Malay or English month).
_RD_MONTHS = {
    'JANUARI': 'Jan', 'JANUARY': 'Jan', 'JAN': 'Jan', 'FEBRUARI': 'Feb', 'FEBRUARY': 'Feb', 'FEB': 'Feb',
    'MAC': 'Mar', 'MARCH': 'Mar', 'MAR': 'Mar', 'APRIL': 'Apr', 'APR': 'Apr', 'MEI': 'May', 'MAY': 'May',
    'JUN': 'Jun', 'JUNE': 'Jun', 'JULAI': 'Jul', 'JULY': 'Jul', 'JUL': 'Jul',
    'OGOS': 'Aug', 'OGO': 'Aug', 'AUGUST': 'Aug', 'AUG': 'Aug', 'SEPTEMBER': 'Sep', 'SEPT': 'Sep', 'SEP': 'Sep',
    'OKTOBER': 'Oct', 'OCTOBER': 'Oct', 'OKT': 'Oct', 'OCT': 'Oct', 'NOVEMBER': 'Nov', 'NOV': 'Nov',
    'DISEMBER': 'Dec', 'DECEMBER': 'Dec', 'DIS': 'Dec', 'DEC': 'Dec',
}
_RD_MONTH_NUM = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
_RD_WEEKDAY = re.compile(r'\b(ISNIN|SELASA|RABU|KHAMIS|JUMAAT|SABTU|AHAD|'
                         r'MON(?:DAY)?|TUE(?:SDAY)?|WED(?:NESDAY)?|THU(?:RSDAY)?|FRI(?:DAY)?|SAT(?:URDAY)?|SUN(?:DAY)?)\b')
_RD_TIME = re.compile(r'\d{1,2}[.:]\d{2}\s*(?:PAGI|PETANG|TENGAH HARI|MALAM|AM|PM)?')


def _normalise_reporting_date(raw: str) -> str:
    """An offer reporting date → 'D Mon YYYY' (e.g. '22 Jun 2026'). Returns the ORIGINAL string
    if it can't confidently parse a day + month + year (never destroys an unparseable value)."""
    s = (raw or '').strip()
    if not s:
        return s
    up = s.upper()
    m = re.search(r'\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(20\d{2})\b', up)   # DD/MM/YYYY
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f'{d} {_RD_MONTH_NUM[mo]} {m.group(3)}'
    cleaned = re.sub(r'\([^)]*\)', ' ', up)        # drop (SABTU) / (9.00 PAGI - ...)
    cleaned = _RD_TIME.sub(' ', cleaned)           # drop bare times (2:30 PETANG)
    cleaned = _RD_WEEKDAY.sub(' ', cleaned)        # drop weekday words
    mon = None                                     # first month token, by position
    for name, eng in _RD_MONTHS.items():
        hit = re.search(r'\b' + name + r'\b', cleaned)
        if hit and (mon is None or hit.start() < mon[0]):
            mon = (hit.start(), eng)
    ym = re.search(r'\b(20\d{2})\b', cleaned)
    if not mon or not ym:
        return s
    day = next((int(g.group(1)) for g in re.finditer(r'\b(\d{1,2})\b', cleaned)
                if 1 <= int(g.group(1)) <= 31), None)
    return f'{day} {mon[1]} {ym.group(1)}' if day else s


def _sanitize_extracted_fields(doc_type: str, data: dict) -> dict:
    """Deterministic post-extraction guards (item B): stop a header/label or a wrong-section
    name passing through as a person's name. Blanking a bad value yields 'unread' (SOFT)
    downstream — never a confident wrong-person mismatch. Pure; never raises."""
    if not isinstance(data, dict):
        return data
    if doc_type in ('results_slip', 'higher_results') and data.get('candidate_name'):
        data['candidate_name'] = _strip_name_label(data['candidate_name'])
    elif doc_type == 'offer_letter' and data.get('reporting_date'):
        data['reporting_date'] = _normalise_reporting_date(data['reporting_date'])
    elif doc_type == 'birth_certificate':
        child = _strip_name_label(data.get('bc_child_name') or '')
        # The child name must come from the KANAK-KANAK block: never a heading, and never
        # identical to a parent's name (the classic section mis-read — BAPA's 'Nama' pulled
        # into the child slot, e.g. #10). Either case → blank ('couldn't read the child'),
        # which is soft, not a wrong-person red.
        if child and (_looks_like_non_name(child)
                      or name_match(child, data.get('bc_father_name') or '') == 'match'
                      or name_match(child, data.get('bc_mother_name') or '') == 'match'):
            child = ''
        data['bc_child_name'] = child
        # ⚠ The child's IC is kept ONLY when the printed date of birth confirms it. The number
        # sits unlabelled beside the barcode next to the register number (which carries
        # letters), so a misread is easy — and unlike a blank, a wrong number reads as a
        # CONFIDENT mismatch against the student's own NRIC and would newly block them.
        if data.get('bc_child_nric') and not nric_dob_agrees(data.get('bc_child_nric'),
                                                             data.get('bc_child_dob') or ''):
            data['bc_child_nric'] = ''
    return data


def _drop_expected_warnings(doc_type: str, warnings: list) -> list:
    """Strip warnings a document is EXPECTED to trip — noise that misleads the officer. Belt-and-
    braces with the prompt hint, since Gemini's free-text warnings aren't fully steerable.
      * birth_certificate — the child carries NO IC (issued one later), so a 'child NRIC missing'
        note is normal.
      * salary_slip — the NRIC and the year-to-date GROSS are OPTIONAL: many Malaysian SME payslips
        identify the employee by an employee number + name (no IC printed) and show only the current
        month's earnings (no YTD column). Flagging them 'missing' makes a perfectly valid slip look
        deficient (the earner is still cross-checked by NAME, and one month's gross still counts)."""
    if doc_type == 'birth_certificate':
        def _is_child_nric_noise(w) -> bool:
            s = (w or '').lower()
            return 'child' in s and any(k in s for k in
                                        ('nric', 'kad pengenalan', 'ic number', 'identity card', 'no. kad'))
        return [w for w in warnings if not _is_child_nric_noise(w)]
    if doc_type == 'salary_slip':
        def _is_optional_salary_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'absent', 'unavailable', 'no ')):
                return False
            nric = any(k in s for k in ('nric', 'ic number', 'ic no', 'kad pengenalan', 'k/p', 'mykad'))
            # Explicit year-to-date phrasing ONLY — a bare 'year' + 'date' anywhere over-matches a
            # legit "pay period (month/year)… pay date" warning (which must be kept).
            ytd = any(k in s for k in ('ytd', 'gross_income_ytd', 'terkumpul',
                                       'year to date', 'year-to-date', 'year to-date'))
            return nric or ytd
        return [w for w in warnings if not _is_optional_salary_noise(w)]
    if doc_type == 'offer_letter':
        # Supplementary DATA-POINT fields are OPTIONAL on an offer letter — not every issuer prints
        # an offer/reporting date, intake, candidate address, or stream/specialisation. Their absence
        # is not a problem (the chip just omits the data point); a "missing" note is noise. The CORE
        # facts — candidate name / NRIC (Name·IC), programme/institution (Pathway), issuer +
        # genuineness (Official) — are handled by the chip, NOT these warnings, so a warning about
        # THEM is never suppressed here.
        def _is_optional_offer_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'not specified', 'not stated', 'not explicitly',
                                        'not clearly', 'absent', 'unavailable', 'no ')):
                return False
            return any(k in s for k in ('offer_date', 'offer date', 'reporting_date', 'reporting date',
                                        'intake', 'address', 'stream', 'bidang', 'elektif', 'aliran',
                                        'specialis', 'specializ', 'campus', 'reporting venue',
                                        'reporting_venue', 'programme code', 'programme_code',
                                        'course code'))
        return [w for w in warnings if not _is_optional_offer_noise(w)]
    if doc_type == 'semester_result':
        # Only Name / NRIC / CGPA matter on a semester slip (owner): Name·IC drive the red/green
        # chip, CGPA is optional (a single-semester slip like STPM Sem 1 has no cumulative figure).
        # So a "missing FIELD" note — CGPA, institution, programme, semester, and even name/NRIC
        # (whose absence already reds the chip) — is noise. Keep only SUBSTANTIVE warnings (a wrong
        # document / an unreadable slip), which carry no field-name keyword.
        def _is_semester_field_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'not specified', 'not stated', 'not explicitly',
                                        'not clearly', 'not available', 'unclear', 'absent',
                                        'unavailable', 'semester-only', 'semester only', 'no ')):
                return False
            return any(k in s for k in ('name', 'nric', 'kad pengenalan', 'ic ', 'cgpa', 'pngk',
                                        'hpnm', 'gpa', 'kumulatif', 'cumulative', 'semester',
                                        'institution', 'college', 'university', 'programme',
                                        'program', 'course'))
        return [w for w in warnings if not _is_semester_field_noise(w)]
    if doc_type in ('water_bill', 'electricity_bill'):
        # Belt-and-braces with _WARNING_VOICE for existing/legacy notes: drop the extraction
        # BOOKKEEPING the officer doesn't need — which RM figure was chosen (Caj Semasa vs Caj
        # Penggunaan and its surcharge), a credit balance "left empty as per instructions", and any
        # note written in field-name / engineer register. Keep the SUBSTANTIVE ones (a bill date or
        # tariff that reads oddly, an unreadable amount) — those are reviewer-worthy.
        def _is_utility_note_noise(w) -> bool:
            s = (w or '').lower()
            return ("'amount'" in s or "'unpaid_balance'" in s or "'tunggakan'" in s
                    or 'field' in s or 'as per instruction' in s or 'as instructed' in s
                    or ('caj ' in s and any(k in s for k in ('exclud', 'includ', 'surcharge')))
                    or ('negative' in s and 'credit' in s))
        return [w for w in warnings if not _is_utility_note_noise(w)]
    return warnings
