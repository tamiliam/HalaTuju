"""The UUM rules lane (OCR-13 phase 3): a DIGITAL Universiti Utara Malaysia degree offer letter read from its page-1
LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse`). The reader
refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless OCR_FIRST_LANES
holds ``ua:UUM`` (`offer_exact.ocr_first_lanes`).

UUM PRINTS NO IC (owner, 26 Nov: "Lock without IC", this lane only). The name line carries a 6-digit number in
brackets ("NAME (NNNNNN)"): it is NOT the IC and is never stored, matched or ink-checked. A UUM lock stores the IC
blank (source 'none'), exactly as the AI read of the same letter does; `offer_exact.ISSUER_PRINTS_NO_IC` lets the
lock stand without one, for this lane only. ANY 12-digit IC-like number on any page refuses (``ic_printed``): a
letter that prints one is not the template this lane was measured on.

Page 1, as measured on the corpus and the owner's samples (masked shapes only):

* the letterhead (left), then a right-hand column: the web address, "Tarikh : D Month YYYY" (the offer date) and
  "Rujukan : UUM/HEA/...";
* the line straight after "Rujukan" is the name with the bracket number, at the left margin; the address follows,
  then "Saudara/i,";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA", once, at the left margin, the session after it on
  the same line ("SEMESTER PERTAMA SESI YYYY/YYYY"): the intake, stored as printed after the title;
* "Program Pengajian : SARJANA MUDA ... (DENGAN KEPUJIAN)", wrapping onto at most two indented lines before
  "Pusat Pengajian / Kolej". Any non-degree word (`offer_parse_uitm.NOT_DEGREE`) refuses;
* "Tarikh Pendaftaran Fizikal (UUM) : DD Month YYYY", once: the reporting date.

English "Admission" letters print no Malay title (``no_title``); a letter that says PENGESAHAN anywhere on page 1
(the senate confirmation letters) refuses (``status_letter``). Later pages: `uum_later_pages`.
"""
import re

from .offer_parse import _IC, _name_ok
from .offer_parse_uitm import NOT_DEGREE, _PRA
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UUM'
INSTITUTION = 'UNIVERSITI UTARA MALAYSIA'
ISSUER = 'Jabatan Hal Ehwal Akademik, Universiti Utara Malaysia'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_COLUMNS = re.compile(r'\s{3,}')
_TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI UTARA MALAYSIA'
_INTAKE = re.compile(r'^(?:SEMESTER (?:PERTAMA|KEDUA|KETIGA|[0-9]{1,2}|[IV]{1,3}) )?SESI (20\d{2})/(20\d{2})$')
_NAME_LINE = re.compile(r'^(\S.*?)\s?\((\d{6})\)$')
_LINKERS = re.compile(r'\b(?:BIN|BINTI|BT|BTE|A\s?/\s?[LP]|ANAK|AK)$')
_RUJUKAN = re.compile(r'^Rujukan\s{0,3}:\s{0,3}UUM/\S{1,40}$')
_MONTH = (r'(?:Januari|Februari|Mac|April|Mei|Jun|Julai|Ogos|September|Oktober|November|Disember|'
          r'January|February|March|May|June|July|August|October|December)')
_WORD_DATE = r'(\d{1,2}) (' + _MONTH + r') (20\d{2})'
_OFFER_DATE = re.compile(r'^Tarikh\s{0,3}:\s{0,3}' + _WORD_DATE + r'$')
_DATE_VALUE = re.compile(r'^' + _WORD_DATE + r'$')
_REPORT_LABEL = 'Tarikh Pendaftaran Fizikal (UUM)'
_PROGRAMME_LABEL = 'Program Pengajian'
_SCHOOL_LABEL = 'Pusat Pengajian / Kolej'
#: A word may open a bracket: "SARJANA MUDA SAINS DENGAN KEPUJIAN (TEKNOLOGI ...)".
_DEGREE = re.compile(r"^SARJANA MUDA(?: \(?[A-Z][A-Z&,'/.()\-]*)+$")
#: Any IC-like number: 12 digits (dashes or a space allowed where an IC prints them), or a longer digit run.
_IC_ANY = re.compile(r'(?<!\d)' + _IC + r'(?!\d)')
_DIGIT_RUN = re.compile(r'\d{12,}')
_PENGESAHAN = re.compile(r'PENGESAHAN')
#: A later page must be one of UUM's own; any other page goes to the AI.
_UUM_PAGE = re.compile(r'Universiti\s{1,3}Utara\s{1,3}Malaysia|uum\.edu\.my|\bUUM\b', re.IGNORECASE)
_MONTH_NO = {m.lower(): i for i, m in enumerate(
    ('januari', 'februari', 'mac', 'april', 'mei', 'jun', 'julai', 'ogos', 'september', 'oktober', 'november',
     'disember'), 1)}
_MONTH_NO.update({'january': 1, 'february': 2, 'march': 3, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
                  'october': 10, 'december': 12})


def is_uum(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UUM admissions letter: the university and its academic
    affairs department (Malay or English). Which of them is a degree offer `read_uum` decides."""
    return 'UNIVERSITI UTARA MALAYSIA' in up and ('HAL EHWAL' in up or 'ACADEMIC AFFAIRS' in up)


def _uum_lines(text: str) -> list:
    """The non-blank lines, right-stripped, leading spaces kept (an indented line is a wrapped value)."""
    return [ln.rstrip() for ln in (text or '').splitlines() if ln.strip()]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _cols(line: str) -> list:
    """A layout line's columns (3+ spaces apart)."""
    return _COLUMNS.split(line.strip())


def _one_space(s: str) -> str:
    return ' '.join((s or '').split())


def _title_at(lines):
    """(index, intake) of the title line: the title at the left margin, ONCE, the session alone after it;
    (-1, '') else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).startswith(_TITLE)]
    if len(hits) != 1 or _indent(lines[hits[0]]) > 4:
        return -1, ''
    rest = _one_space(lines[hits[0]])[len(_TITLE):].strip()
    return hits[0], (rest if _INTAKE.match(rest) else '')


def _labelled(lines, label: str) -> list:
    """The indices of lines whose first column is ``label`` (the label starts the line, at most 10 in)."""
    return [i for i, ln in enumerate(lines) if _indent(ln) <= 10 and _one_space(_cols(ln)[0]) == label]


def _value(line: str) -> str:
    """The one value after a label's colon: the line holds exactly two columns, the second ": VALUE"."""
    cols = _cols(line)
    if len(cols) != 2 or not cols[1].startswith(':'):
        return ''
    return _one_space(cols[1][1:])


def _head(lines, at):
    """(name, offer_date, reason): the one "Rujukan" line in the right-hand column before the title; the line
    straight after it is "NAME (NNNNNN)" at the left margin. The bracket number is dropped, never kept."""
    ref = [i for i, ln in enumerate(lines[:at]) if _indent(ln) >= 60 and _RUJUKAN.match(_one_space(ln))]
    if len(ref) != 1 or ref[0] + 1 >= at:
        return '', '', 'no_head'
    dated = [i for i, ln in enumerate(lines[:ref[0]]) if _indent(ln) >= 60 and _OFFER_DATE.match(_one_space(ln))]
    offer_date = ''
    if len(dated) == 1:
        offer_date = ' '.join(_OFFER_DATE.match(_one_space(lines[dated[0]])).groups())
    ln = lines[ref[0] + 1]
    m = _NAME_LINE.match(_one_space(ln))
    if _indent(ln) > 4 or len(_cols(ln)) != 1 or not m:
        return '', offer_date, 'name_shape'
    name = m.group(1).strip()
    if not _name_ok(name) or _LINKERS.search(name):
        return '', offer_date, 'name_shape'       # an unread or wrapped name ("... BINTI")
    if not any(_one_space(x) == 'Saudara/i,' for x in lines[ref[0] + 2:at]):
        return '', offer_date, 'no_head'
    return name, offer_date, ''


def not_degree(programme: str) -> bool:
    """True when the programme is not a plain degree: a non-degree word (`NOT_DEGREE`, PRA as a word), raw or
    look-alike folded, spaced or dotted, or a name that is not "SARJANA MUDA ..." in plain capitals."""
    folded = fold_lookalikes(programme or '').upper()
    key = _SQUEEZE_OUT.sub('', folded)
    return (any(w in key for w in NOT_DEGREE) or bool(_PRA.search(folded)) or bool(_PRA.search(key[:3]))
            or not _DEGREE.match(programme or ''))


def _uum_programme(lines, at):
    """(programme, reason): the one "Program Pengajian" line after the title, its value plus up to two wrapped
    lines (indented 30+, one column), then "Pusat Pengajian / Kolej"."""
    every = _labelled(lines, _PROGRAMME_LABEL)
    if len(every) != 1 or every[0] <= at:
        return '', 'no_programme' if not every else 'programme_twice'
    i = every[0]
    parts, j = [_value(lines[i])], i + 1
    if not parts[0]:
        return '', 'programme_shape'
    while j < len(lines) and j <= i + 3 and _one_space(_cols(lines[j])[0]) != _SCHOOL_LABEL:
        if _indent(lines[j]) < 30 or len(_cols(lines[j])) != 1:
            return '', 'programme_shape'
        parts.append(_one_space(lines[j]))
        j += 1
    if j >= len(lines) or _one_space(_cols(lines[j])[0]) != _SCHOOL_LABEL or len(parts) > 3:
        return '', 'programme_shape'
    programme = ' '.join(parts)
    return programme, ('not_degree' if not_degree(programme) else '')


def _reporting(lines, at) -> str:
    """The reporting date as printed ("DD Month YYYY"): the one "Tarikh Pendaftaran Fizikal (UUM)" line."""
    hits = _labelled(lines, _REPORT_LABEL)
    if len(hits) != 1 or hits[0] <= at:
        return ''
    value = _value(lines[hits[0]])
    return value if _DATE_VALUE.match(value) else ''


def printed_date(page1_layout: str) -> str:
    """The reporting date exactly as page 1 prints it ("DD Month YYYY"), '' when it cannot be read."""
    lines = _uum_lines(page1_layout)
    at, _intake = _title_at(lines)
    return _reporting(lines, at) if at >= 0 else ''


def _ymd(printed: str):
    """A real calendar date from "DD Month YYYY", else None."""
    import datetime
    m = _DATE_VALUE.match(printed or '')
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), _MONTH_NO[m.group(2).lower()], int(m.group(1)))
    except (KeyError, ValueError):               # "31 September 2027": not a real day
        return None


def _uum_dates_sane(intake: str, printed: str, offer_date: str) -> bool:
    """The reporting date is a real date inside the session's two years, the years run on, and the offer date
    (when read) is a real date not after it."""
    m, report = _INTAKE.match(intake or ''), _ymd(printed)
    if not m or report is None or int(m.group(2)) != int(m.group(1)) + 1:
        return False
    if not int(m.group(1)) <= report.year <= int(m.group(2)):
        return False
    offered = _ymd(offer_date) if offer_date else None
    return not offer_date or (offered is not None and offered <= report)


def ic_printed(text: str) -> bool:
    """True when ``text`` (raw or look-alike folded) prints any IC-like number: 12 digits in an IC's shape or a
    longer digit run. UUM prints none, so one means another template: the AI reads it."""
    return any(_IC_ANY.search(one) or _DIGIT_RUN.search(one) for one in (text or '', fold_lookalikes(text or '')))


def read_uum(source: str):
    """``(fields, reason)`` for a UUM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock. The IC is always blank."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or _PENGESAHAN.search(_SQUEEZE_OUT.sub('', folded.upper())):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at, intake = _title_at(lines)
    if at < 0:
        return None, 'no_title'
    if ic_printed(source):
        return None, 'ic_printed'
    name, offer_date, why_head = _head(lines, at)
    programme, why_prog = _uum_programme(lines, at)
    printed = _reporting(lines, at)
    from .offer_parse import house_date
    fields = {
        'candidate_name': name, 'candidate_nric': '', 'candidate_nric_source': 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if _ymd(printed) else '',
        'reporting_date_label': _REPORT_LABEL, 'reporting_venue': '', 'offer_date': offer_date, 'issuer': ISSUER,
    }
    if why_head:
        return fields, why_head
    if why_prog:
        return fields, why_prog
    empty = [k for k in ('candidate_name', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _uum_dates_sane(intake, printed, offer_date):
        return fields, 'dates_not_sane'
    return fields, ''


def uum_letter_refusal(text: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'ic_printed', 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one`, the head being the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if ic_printed(text):
        return 'ic_printed'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith(_TITLE)), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def uum_later_pages(pages, programme: str, printed_date: str) -> str:
    """Why a later page (page 2 on) refuses the lock: 'unknown_page' (no UUM name or web address on it),
    'ic_printed' (any IC-like number), 'second_programme' (a "SARJANA MUDA" / non-degree programme that is not
    page 1's), 'second_date' (a word date labelled as the physical registration date that differs from page 1's);
    '' when none. Each page is checked raw and look-alike folded. Footer and notes words never refuse."""
    want = _SQUEEZE_OUT.sub('', (programme or '').upper())
    for page in pages or ():
        for one in (page or '', fold_lookalikes(page or '')):
            if not _UUM_PAGE.search(one):
                return 'unknown_page'
            if ic_printed(one):
                return 'ic_printed'
            flat = _one_space(one)
            for m in re.finditer(r'SARJANA MUDA(?: \(?[A-Z][A-Z&,\'/.()\-]*)+', flat):
                if _SQUEEZE_OUT.sub('', m.group(0)) not in want:
                    return 'second_programme'
            up = flat.upper()
            if any(re.search(r'(?<![A-Z])' + w + r'(?![A-Z])', up) for w in ('DIPLOMA', 'ASASI', 'PERSEDIAAN')):
                return 'second_programme'
            for m in re.finditer(r'Pendaftaran\s{0,3}Fizikal[^:]{0,20}:\s{0,3}(' + _WORD_DATE + ')', flat, re.I):
                if _ymd(_one_space(m.group(1))) != _ymd(printed_date):
                    return 'second_date'
    return ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1. No IC: UUM
#: prints none, and the bracket number is never a value.
INK_LABELS = {'candidate_name': 'v:name', 'programme': 'v:programme', 'intake': 'v:intake',
              'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Read from the page but optional: ink-checked only when read.
INK_OPTIONAL = ('offer_date',)
#: The fields `read_uum` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric', 'candidate_nric_source', 'programme_code', 'institution', 'campus', 'issuer',
               'stream', 'reporting_date_label', 'reporting_venue')


def uum_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UUM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the reporting date as printed). A required value
    left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed = {**{k: f.get(k) or '' for k in INK_LABELS}, 'reporting_date': printed_date(page1_layout)}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, printed)
