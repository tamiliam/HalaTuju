"""The UMK rules lane (OCR-14 phase 7): a DIGITAL Universiti Malaysia Kelantan degree offer letter read from its
page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UMK`` (`offer_exact.ocr_first_lanes`).

UMK PRINTS THE IC (measured: every text letter prints "NO. KAD PENGENALAN:<12 digits>" in the head's right-hand
column), so the IC guard applies as on UKM (`offer_exact.exact_read`; UMK is NOT in
`offer_exact.ISSUER_PRINTS_NO_IC`): a UMK letter with no IC never locks. The IC is read from that one labelled row
only (source ``label``), as the 12 plain digits every measured letter prints (a hyphen, an en dash, a minus, a slash,
any space or a line split there refuses), and page 1 must print it exactly once. ANY other IC-like number on any
page refuses (`umk_ic_elsewhere`). The matric number ("NO. MATRIK: A99A9999", also inside the student e-mail
address) and the reference are never stored.

Page 1, as measured on the owner's 4 text letters (masked shapes only; the corpus's two UMK letters are scans):

* the letterhead, six lines (`_LETTERHEAD`); the name alone at the left (`offer_parse_uitm.name_ended` must prove
  it ended); one to four address lines; then, in the right-hand column on lines of their own, "NO. KAD
  PENGENALAN:<IC>", "NO. MATRIK: <matric>" and "TARIKH: DD/MM/YYYY" (the offer date); "Saudara/i,". A head whose
  name or address shares its line with the right-hand column (one owner letter) refuses (``no_head``);
* the title "TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN SEMESTER SEPTEMBER SESI AKADEMIK YYYY/YYYY" on one
  or two lines (the intake is what follows "KELANTAN ");
* the greeting "Tahniah, sukacita dimaklumkan ... seperti berikut:-" on one or two lines;
* the table, four rows in this order and nothing between them, each on one line: Program (a "SARJANA MUDA ...
  DENGAN KEPUJIAN" degree), Tahun (must be "PERTAMA"), Fakulti ("FAKULTI ..."), Tempoh ("N SEMESTER");
* "Sila mendaftar pada tarikh, masa dan tempat seperti berikut:-", then the reporting row "Tarikh: DD MON YYYY"
  (an English month abbreviation, as measured), then "Masa: h:mmAM hingga h:mmPM", then "Tempat" (never read).

The reporting date is read ONLY from that labelled row straight after that sentence. Any other value refuses, and so
does any date on the page but the offer date and that row. One owner letter stops page 1 after Tempoh (its reporting
row is on page 2): no date is guessed, it refuses. Any later page with text refuses (``later_page``). Confirmation
letters ("PENGESAHAN") refuse (``status_letter``). The campus row is not read (the campus stays blank).
"""
import datetime
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uthm import _ANY_DATE, _NOT_DEGREE_WORD
from .offer_parse_uum import _LINKERS, _cols, _indent, _one_space, _uum_lines, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UMK'
INSTITUTION = 'UNIVERSITI MALAYSIA KELANTAN'
ISSUER = 'Pusat Pengurusan Akademik, Universiti Malaysia Kelantan'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE_WORDS = 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA KELANTAN'
_LEFT = 12                                      # the name, address, title and table start under this
_RIGHT = 60                                     # the head's right-hand column starts past this
_HEAD_IN = 30                                   # the letterhead starts under this (measured: 0, 20, 21)
#: The letterhead's six lines, one-spaced, each alone on its line.
_LETTERHEAD = (re.compile(r'^PUSAT PENGURUSAN AKADEMIK$'),
               re.compile(r'^PEJABAT TIMBALAN NAIB CANSELOR \(AKADEMIK & ANTARABANGSA\)$'),
               re.compile(r'^UNIVERSITI MALAYSIA KELANTAN$'),
               re.compile(r'^\d{5} BACHOK KELANTAN$'),
               re.compile(r'^TELEFON : \d{2}-\d{3} \d{4}(?:/\d{4}){0,4}$'),
               re.compile(r'^TELEFAX : \d{2}-\d{3} \d{4}$'))
_IC_LABEL = 'NO. KAD PENGENALAN'
_IC_VALUE = re.compile(r'^\d{12}$')             # as measured: no separator, no space
_MATRIC_ROW = re.compile(r'^NO\. MATRIK ?: ?[A-Z]\d{2}[A-Z]\d{4}$')
_OFFER_ROW = re.compile(r'^TARIKH ?: ?(\d{2}/\d{2}/20\d{2})$')
_SALUTATION = 'Saudara/i,'
_TITLE = re.compile(r'^' + _TITLE_WORDS + r' (SEMESTER SEPTEMBER SESI AKADEMIK (20\d{2})/(20\d{2}))$')
_GREETING = ('Tahniah, sukacita dimaklumkan anda telah ditawarkan tempat bagi mengikuti program pengajian seperti '
             'berikut:-')
_ROW = re.compile(r'^(Program|Tahun|Fakulti|Tempoh) *:(.*)$')
_TABLE = ('Program', 'Tahun', 'Fakulti', 'Tempoh')
_DEGREE = re.compile(r"^SARJANA MUDA \S.*? DENGAN KEPUJIAN$")
_FACULTY = re.compile(r"^FAKULTI [A-Z][A-Z&,'.()\-]*(?: [A-Z&][A-Z&,'.()\-]*)*$")
_TERM = re.compile(r'^\d{1,2} SEMESTER$')
_REGISTER = 'Sila mendaftar pada tarikh, masa dan tempat seperti berikut:-'
_MON = {m: i for i, m in enumerate(('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV',
                                    'DEC'), 1)}
_REPORT_ROW = re.compile(r'^Tarikh ?: ?(\d{1,2}) (' + '|'.join(_MON) + r') (20\d{2})$')
_HOUR = r'\d{1,2}:\d{2} ?[AP]M'
_TIME_ROW = re.compile(r'^Masa ?: ?' + _HOUR + ' hingga ' + _HOUR + r'$')
_PLACE_ROW = re.compile(r'^Tempat ?:')
#: A date with a month abbreviation, English or Malay ("15 OCT 2026", "3 Ogo. 26"), which `_ANY_DATE` does not
#: read; with it, any date on page 1 but the offer date and the reporting row refuses.
_SHORT_DATE = re.compile(r'(?<!\d)\d{1,2} ?(?:JAN|FEB|MAR|MAC|APR|MAY|MEI|JUN|JUL|AUG|OGO|SEP|OCT|OKT|NOV|DEC|DIS)'
                         r'[A-Z]*\.? ?(?:20)?\d{2}(?!\d)', re.IGNORECASE)


def is_umk(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UMK admissions letter: the university and its offer title.
    Which of them is a degree offer `read_umk` decides."""
    return INSTITUTION in up and _TITLE_WORDS in up


def umk_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`offer_parse_ukm._own_ic`); page 1's plain layer must print it
    exactly once."""
    return _own_ic(text, nric)[1]


def umk_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`) once ONE copy of the read IC is
    taken out: the read IC printed twice counts too. No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _dmy(printed: str):
    """A real calendar date from "DD/MM/YYYY", else None."""
    m = re.fullmatch(r'(\d{2})/(\d{2})/(20\d{2})', printed or '')
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
    except ValueError:                           # "31/09/2027": not a real day
        return None


def _report_day(printed: str):
    """A real calendar date from "D MON YYYY" (`_MON`), else None."""
    m = _REPORT_ROW.match('Tarikh:' + (printed or ''))
    try:
        return datetime.date(int(m.group(3)), _MON[m.group(2)], int(m.group(1))) if m else None
    except ValueError:                           # "31 SEP 2027": not a real day
        return None


def _umk_title_at(lines) -> tuple:
    """(index, index after the title, intake, first year, second year): the title once, at the left margin, one
    column, on one line or two; (-1, -1, '', 0, 0) else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')]
    if len(hits) != 1 or _indent(lines[hits[0]]) > _LEFT or len(_cols(lines[hits[0]])) != 1:
        return -1, -1, '', 0, 0
    at = hits[0]
    for end in (at + 1, at + 2):
        if end > len(lines) or any(_indent(ln) > _LEFT or len(_cols(ln)) != 1 for ln in lines[at:end]):
            break
        m = _TITLE.match(_one_space(' '.join(lines[at:end])))
        if m:
            return at, end, m.group(1), int(m.group(2)), int(m.group(3))
    return -1, -1, '', 0, 0


def _right_row(line: str) -> str:
    """A right-hand-column line, one-spaced; '' when it does not start past `_RIGHT`."""
    return _one_space(line) if _indent(line) >= _RIGHT else ''


def _umk_head(lines, at):
    """(name, printed IC, offer date, index of the IC line, index of the offer-date line, reason) from the lines
    before the title (see the module docstring)."""
    none = ('', '', '', -1, -1)
    if at < 12 or any(_indent(ln) > _HEAD_IN or len(_cols(ln)) != 1 or not rx.match(_one_space(ln))
                      for ln, rx in zip(lines[:6], _LETTERHEAD)):
        return none + ('no_head',)
    ic_at, dated_at = at - 4, at - 2
    if _one_space(lines[at - 1]) != _SALUTATION or _indent(lines[at - 1]) > _LEFT:
        return none + ('no_head',)
    ic_line, dated = lines[ic_at].strip(), _OFFER_ROW.match(_right_row(lines[dated_at]))
    if (_indent(lines[ic_at]) < _RIGHT or ':' not in ic_line or _one_space(ic_line[:ic_line.index(':')]) != _IC_LABEL
            or not _MATRIC_ROW.match(_right_row(lines[at - 3])) or not dated or _dmy(dated.group(1)) is None):
        return none + ('no_head',)
    offer_date, printed_ic = dated.group(1), ic_line[ic_line.index(':') + 1:].strip()
    body = lines[6:ic_at]                         # the name and its address
    if not 2 <= len(body) <= 5 or any(_indent(ln) > _LEFT or len(_cols(ln)) != 1 for ln in body):
        return '', '', offer_date, ic_at, dated_at, 'no_head'
    if not _IC_VALUE.match(printed_ic):
        return '', '', offer_date, ic_at, dated_at, 'ic_shape'
    name = _one_space(body[0])
    if not _name_ok(name) or name != name.upper() or _LINKERS.search(name):
        return '', printed_ic, offer_date, ic_at, dated_at, 'name_shape'   # an unread or wrapped name ("... BINTI")
    if not name_ended(body[1]):
        return '', printed_ic, offer_date, ic_at, dated_at, 'name_not_ended'  # the rest may be on the next line
    return name, printed_ic, offer_date, ic_at, dated_at, ''


def _umk_table(lines, end):
    """({label: value}, index of the reporting row, reason): the greeting after the title, then `_TABLE` in order,
    one line each, then the registration sentence, the reporting row, the time row and the place row."""
    g = next((k for k in range(end, min(end + 3, len(lines))) if _ROW.match(lines[k].strip())), -1)
    if (g < 0 or _one_space(' '.join(lines[end:g])) != _GREETING
            or any(_indent(ln) > _LEFT or len(_cols(ln)) != 1 for ln in lines[end:g])):
        return {}, -1, 'no_table'
    rows = {}
    for k, want in enumerate(_TABLE):
        m = _ROW.match(lines[g + k].strip()) if g + k < len(lines) and _indent(lines[g + k]) <= _LEFT else None
        if not m or m.group(1) != want or not m.group(2).strip() or len(_cols(m.group(2))) != 1:
            return rows, -1, 'table_shape'
        rows[want] = _one_space(m.group(2))
    i = g + len(_TABLE)
    if (i + 3 >= len(lines) or _one_space(lines[i]) != _REGISTER
            or any(_indent(ln) > _LEFT for ln in lines[i:i + 4])):
        return rows, -1, 'reporting_shape'
    report = _REPORT_ROW.match(_one_space(lines[i + 1]))
    if (not report or len(_cols(lines[i + 1])) != 1 or not _TIME_ROW.match(_one_space(lines[i + 2]))
            or not _PLACE_ROW.match(_one_space(lines[i + 3]))):
        return rows, -1, 'reporting_shape'
    rows['report'] = f'{report.group(1)} {report.group(2)} {report.group(3)}'
    return rows, i + 1, ''


def _umk_values(rows) -> tuple:
    """(programme, reason) from the table's rows."""
    programme, faculty = rows.get('Program', ''), rows.get('Fakulti', '')
    if not _DEGREE.match(programme) or um_not_degree(programme) or not _FACULTY.match(faculty):
        return '', 'programme_shape'
    if any(w in _SQUEEZE_OUT.sub('', programme + ' ' + faculty) for w in NOT_DEGREE) or \
            _PRA.search(programme + ' ' + faculty):
        return programme, 'not_degree'
    if rows.get('Tahun') != 'PERTAMA' or not _TERM.match(rows.get('Tempoh', '')):
        return programme, 'table_shape'
    if _report_day(rows.get('report', '')) is None:
        return programme, 'reporting_shape'
    return programme, ''


def _umk_dates_sane(years, offer_date: str, printed: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; the
    reporting date is a real date in the session's years, not before the offer date."""
    y1, y2 = years
    offered, reported = _dmy(offer_date), _report_day(printed)
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and offered <= reported


def _umk_read(lines):
    """Every reader step on page 1's layout lines: (years, intake, head, (rows, reporting index, reason),
    (programme, reason)); None before the title holds."""
    at, end, intake, y1, y2 = _umk_title_at(lines)
    if at < 0:
        return None
    head = _umk_head(lines, at)
    rows, report_at, why_table = _umk_table(lines, end)
    values = _umk_values(rows) if not why_table else ('', '')
    return (y1, y2), intake, head, (rows, report_at, why_table), values


def read_umk(source: str):
    """``(fields, reason)`` for a UMK letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    got = _umk_read(lines)
    if got is None:
        return None, 'no_title'
    years, intake, (name, printed_ic, offer_date, ic_at, dated_at, why_head), (rows, report_at, why_table), \
        (programme, why_values) = got
    nric = _norm_nric(printed_ic) if printed_ic else ''
    printed = rows.get('report', '') if not why_table and not why_values else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if printed else '',
        'reporting_date_label': 'Tarikh' if printed else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    ic_line = lines[ic_at]
    rest = [ln for k, ln in enumerate(lines) if k != ic_at] + [ic_line[:ic_line.index(':')]]
    if umk_ic_elsewhere('\n'.join(rest), '') or umk_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 1 or flat.count('KAD PENGENALAN') != 1:
        return fields, 'not_degree'
    if any(_ANY_DATE.search(_one_space(ln)) or _SHORT_DATE.search(_one_space(ln))
           for k, ln in enumerate(lines) if k not in (dated_at, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _umk_dates_sane(years, offer_date, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def umk_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`umk_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one`, the head being the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if umk_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def umk_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''. Measured: two of the owner's text
    letters run onto a page 2 (the closing, the IC again, and on one the reporting rows); no page-2 excuse is made
    (owner decision 26 Nov), so they refuse."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_umk` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'programme_code', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def _umk_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "D MON YYYY") exactly as page 1 prints them, ('', '') when not read."""
    got = _umk_read(_uum_lines(page1_layout))
    if got is None:
        return '', ''
    _years, _intake, head, (rows, _r, why_table), (_p, why_values) = got
    return (head[1] if not head[5] else ''), (rows.get('report', '') if not why_table and not why_values else '')


def umk_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UMK lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _umk_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
