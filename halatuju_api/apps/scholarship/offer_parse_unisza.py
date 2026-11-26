"""The UniSZA rules lane (OCR-14 phase 8): a DIGITAL Universiti Sultan Zainal Abidin degree offer letter read from its
page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UniSZA`` (`offer_exact.ocr_first_lanes`).

UniSZA PRINTS THE IC, WITH NO LABEL (measured: every text letter prints the 12 digits in brackets after the name on
the "Nama :" row; the label names the name, not the number). UniSZA is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`, so a
UniSZA letter with no IC never locks. As no label names it, the IC is stored with source ``other``: CORROBORATE-ONLY
under `offer_ic.guard_nric` (kept only when it is exactly the profile IC, else blanked, so no lock), as on UTeM and
USM. It must be the 12 plain digits (a hyphen, an en dash, a minus, a slash, a space or a line split refuses), printed
exactly once; ANY other IC-like number on any page refuses (`unisza_ic_elsewhere`). The reference (its bracketed
number too) is never stored.

Page 1, as measured on the corpus's 2 text letters and the owner's 3 text samples (masked shapes only; one template;
every letter is one page; the letterhead is a picture, not text):

* in the right-hand column: "Rujukan : UniSZA.NNN-N/N/N (NN)" and "Tarikh : D Month YYYY" (the offer date);
* at the left: "Nama : NAME (IC)" (the name ends at the bracket; `offer_parse_uitm.name_ended` must also prove it
  on the "Alamat :" row's value, and no name word may be an address word); "Alamat : ..." with one to four wrapped
  lines under its value; "Saudara/i";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN (UniSZA) SEM|SEMESTER N SESI YYYY/YYYY" on one or
  two lines (the intake is what follows "(UniSZA) ");
* the greeting "Dengan sukacitanya dimaklumkan ... seperti berikut:" on one or two lines;
* the table, its rows in this order, one line each and nothing between them: Program Pengajian ("(IJAZAH) SARJANA
  MUDA ..."), Kod Program Pengajian ("UDnnnnnnn", the only programme code on the page), Fakulti ("FAKULTI ..."),
  Kampus (never read), Tempoh Pengajian ("N TAHUN"), and on one measured letter Mod Pengajian ("SEPENUH MASA");
* "N. Sekiranya menerima tawaran ini, saudara/i dikehendaki mendaftar sebagaimana berikut:", then the reporting row
  "Tarikh : D MONTH YYYY (DAY)" with the right Malay day name, "Masa : h.mm PAGI - h.mm PETANG", "Tempat : ..."
  (never read; at most two wrapped lines); then "Makluman Yuran Pengajian :", the fee header, its four RM amounts
  and a numbered note.

The reporting date is read ONLY from that labelled row straight after that sentence. Any other value refuses, and so
does any date on the page but the offer date and that row. Any later page with text refuses (``later_page``).
Confirmation letters ("PENGESAHAN") refuse (``status_letter``). The campus row is not read (the campus stays blank).

ONE EXCUSE (owner, 27 Nov: the same as UTeM, USM and UMPSA; OCR-14b-1). Every measured UniSZA letter prints the note
`_NOTE_WORDS` ("Adalah dimaklumkan bahawa Pengurusan Universiti berhak menarik balik tawaran kemasukan ini sekiranya
..."); the shared withdrawal check (`offer_ums_refusal._withdrawn_one`) reads its "menarik balik" as a withdrawal.
That exact note is taken out ONCE before the withdrawal check; any other withdrawal or cancel wording still refuses.
"""
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_umk import _SHORT_DATE
from .offer_parse_university import _ADDRESS_START
from .offer_parse_uthm import _ANY_DATE, _DAYS, _NOT_DEGREE_WORD
from .offer_parse_uum import _LINKERS, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UniSZA'
INSTITUTION = 'UNIVERSITI SULTAN ZAINAL ABIDIN'
ISSUER = 'Pendaftar, Universiti Sultan Zainal Abidin'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE_WORDS = 'TAWARAN KEMASUKAN KE UNIVERSITI SULTAN ZAINAL ABIDIN'
_LEFT = 2                                       # the head rows, title, greeting, table and notes (measured: 0)
_WRAP_IN = (10, 20)                             # the address's wrapped lines (measured: 15)
_REPORT_IN = (3, 10)                            # the reporting rows (measured: 5)
_RIGHT = 60                                     # the reference and offer date (measured: 84, 85)
_REFERENCE = re.compile(r'^Rujukan : UniSZA\.\d{1,4}-\d{1,2}/\d{1,2}/\d{1,2} \(\d{1,3}\)$')
_OFFER_DATE = re.compile(r'^Tarikh : (\d{1,2}) ([A-Za-z]{3,9}) (20\d{2})$')
_NAME_IC = re.compile(r'^(\S(?:.*\S)?) {1,2}\(([^()]*)\)$')
_IC = re.compile(r'^\d{12}$')                   # as measured: the 12 digits alone, no separator, no space
_SALUTATION = 'Saudara/i'
_TITLE = re.compile(r'^' + _TITLE_WORDS + r' \(UniSZA\) ((?:SEM|SEMESTER) [1-3] SESI (20\d{2})/(20\d{2}))$')
_GREETING = ('Dengan sukacitanya dimaklumkan bahawa saudara/i ditawarkan mengikuti program pengajian di UniSZA '
             'seperti berikut:')
_TABLE = ('Program Pengajian', 'Kod Program Pengajian', 'Fakulti', 'Kampus', 'Tempoh Pengajian')
_MODE = ('Mod Pengajian', 'SEPENUH MASA')       # one measured letter adds this row; no other value
_CODE = re.compile(r'^UD\d{7}$')                # as measured: every degree code
_ANY_CODE = re.compile(r'(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![0-9])')
_FACULTY = re.compile(r"^FAKULTI [A-Z][A-Z&,'.()\-]*(?: [A-Z&][A-Z&,'.()\-]*)*$")
_CAMPUS = re.compile(r'^[A-Z][A-Z]*(?: [A-Z]+){0,3}$')
_TERM = re.compile(r'^\d TAHUN$')
_REGISTER = re.compile(r'^\d{1,2}\. Sekiranya menerima tawaran ini, saudara/i dikehendaki mendaftar sebagaimana '
                       r'berikut:$')
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) \(([A-Z]{4,6})\)$')
_HOUR = r'\d{1,2}\.\d{2} (?:PAGI|PETANG|TENGAH HARI)'      # measured: PAGI and PETANG
_TIME_VALUE = re.compile(r'^' + _HOUR + ' - ' + _HOUR + r'$')
_FEES_TITLE = 'Makluman Yuran Pengajian :'
_FEES = 'KOS PENGAJIAN YURAN PENGAJIAN YURAN DITANGGUNG KERAJAAN YURAN PENDAFTARAN'
_RM = r'RM ?(?:\d{1,3}(?:,\d{3})+|\d{1,6})\.\d{2}'    # measured: with and without the thousands comma
_FEE_LINE = re.compile(r'^' + ' '.join([_RM] * 4) + r'$')
_NOTE_START = re.compile(r'^\d{1,2}\. \S')
#: The one conditional withdrawal note every measured letter prints (owner, 27 Nov). Taken out ONCE before the
#: withdrawal check; any other withdrawal wording still refuses.
_NOTE_WORDS = ('Adalah dimaklumkan bahawa Pengurusan Universiti berhak menarik balik tawaran kemasukan ini sekiranya '
               'terdapat perkara-perkara yang tidak memenuhi syarat-syarat kelayakan yang telah ditetapkan oleh Senat '
               'Universiti.')
_UNISZA_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _NOTE_WORDS.split()))


def is_unisza(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UniSZA admissions letter: the university and its offer title.
    Which of them is a degree offer `read_unisza` decides."""
    return INSTITUTION in up and _TITLE_WORDS in up


def unisza_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`offer_parse_ukm._own_ic`); page 1's plain layer must print it
    exactly once."""
    return _own_ic(text, nric)[1]


def unisza_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`) once ONE copy of the read IC is
    taken out: the read IC printed twice counts too. No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _unisza_row(line: str, indent=(0, _LEFT)):
    """(label, value) of a one-column "Label : value" line whose indent is within ``indent``, else None. The value
    must not hold a second column."""
    if ':' not in line or not indent[0] <= _indent(line) <= indent[1]:
        return None
    label, value = line.strip().split(':', 1)
    value = value.strip()
    if not value or not label.strip() or len(_cols(value)) != 1 or len(_cols(label)) != 1:
        return None
    return _one_space(label), _one_space(value)


def _unisza_title_at(lines) -> tuple:
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


def _name_words_ok(name: str) -> bool:
    """A name to lock: `_name_ok`, upper case, not ending in a linker ("... BIN"), and no word an address word
    (`offer_parse_university._ADDRESS_START`: "KAMPUNG", "JALAN", "NO", ...)."""
    return (_name_ok(name) and name == name.upper() and not _LINKERS.search(name)
            and not any(_ADDRESS_START.fullmatch(w) for w in name.split()))


def _unisza_head(lines, at):
    """(name, printed IC, offer date as printed, reason) from the lines before the title (see the module
    docstring)."""
    if at < 5:
        return '', '', '', 'no_head'
    ref, dated = _REFERENCE.match(_one_space(lines[0])), _OFFER_DATE.match(_one_space(lines[1]))
    if (not ref or not dated or _indent(lines[0]) < _RIGHT or _indent(lines[1]) < _RIGHT
            or _ymd(f'{dated.group(1)} {dated.group(2).title()} {dated.group(3)}') is None):
        return '', '', '', 'no_head'
    offer_date = f'{dated.group(1)} {dated.group(2)} {dated.group(3)}'
    named, lived = _unisza_row(lines[2]), _unisza_row(lines[3])
    if not named or named[0] != 'Nama' or not lived or lived[0] != 'Alamat':
        return '', '', offer_date, 'no_head'
    wraps = lines[4:at - 1]
    if (not 1 <= len(wraps) <= 4 or _one_space(lines[at - 1]) != _SALUTATION or _indent(lines[at - 1]) > _LEFT
            or any(not _WRAP_IN[0] <= _indent(ln) <= _WRAP_IN[1] or len(_cols(ln)) != 1 for ln in wraps)):
        return '', '', offer_date, 'no_head'
    m = _NAME_IC.match(named[1])
    if not m:
        return '', '', offer_date, 'name_shape'
    if not _IC.match(m.group(2)):
        return '', '', offer_date, 'ic_shape'
    name, printed_ic = _one_space(m.group(1)), m.group(2)
    if not _name_words_ok(name):
        return '', printed_ic, offer_date, 'name_shape'
    if not name_ended(lived[1]):
        return '', printed_ic, offer_date, 'name_not_ended'   # the address must open as an address
    return name, printed_ic, offer_date, ''


def _unisza_table(lines, end):
    """({label: value}, index of the reporting row, reason): the greeting after the title, then `_TABLE` in order
    (`_MODE` may follow), then the registration sentence, the reporting rows, the fee block and a note."""
    g = next((k for k in range(end, min(end + 3, len(lines))) if (_unisza_row(lines[k]) or ('',))[0] == _TABLE[0]), -1)
    if (g < 0 or _one_space(' '.join(lines[end:g])) != _GREETING
            or any(_indent(ln) > _LEFT or len(_cols(ln)) != 1 for ln in lines[end:g])):
        return {}, -1, 'no_table'
    rows = {}
    for k, want in enumerate(_TABLE):
        got = _unisza_row(lines[g + k]) if g + k < len(lines) else None
        if not got or got[0] != want:
            return rows, -1, 'table_shape'
        rows[want] = got[1]
    i = g + len(_TABLE)
    if i < len(lines) and _unisza_row(lines[i]) == _MODE:
        i += 1
    if i + 3 >= len(lines) or not _REGISTER.match(_one_space(lines[i])) or _indent(lines[i]) > _LEFT:
        return rows, -1, 'reporting_shape'
    report, hours, place = (_unisza_row(lines[i + k], _REPORT_IN) for k in (1, 2, 3))
    if (not report or report[0] != 'Tarikh' or not hours or hours[0] != 'Masa' or not _TIME_VALUE.match(hours[1])
            or not place or place[0] != 'Tempat'):
        return rows, -1, 'reporting_shape'
    rows['report'] = report[1]
    j = i + 4
    while j < len(lines) and j < i + 6 and ':' not in lines[j] and _indent(lines[j]) >= 15:
        j += 1                                  # the place's wrapped lines (never read)
    if (j + 3 >= len(lines) or _one_space(lines[j]) != _FEES_TITLE or _one_space(lines[j + 1]) != _FEES
            or not _FEE_LINE.match(_one_space(lines[j + 2])) or not _NOTE_START.match(_one_space(lines[j + 3]))
            or _indent(lines[j]) > _LEFT or _indent(lines[j + 3]) > _LEFT):
        return rows, -1, 'table_shape'
    return rows, i + 1, ''


def _unisza_report(value: str):
    """(printed "D MONTH YYYY", house date) from "D MONTH YYYY (DAY)" whose Malay day name is that date's, else
    None."""
    m = _REPORT_VALUE.match(value or '')
    if not m:
        return None
    day = _ymd(f'{m.group(1)} {m.group(2).title()} {m.group(3)}')
    if day is None or _DAYS[day.weekday()] != m.group(4):
        return None
    return f'{m.group(1)} {m.group(2)} {m.group(3)}', house_date(f'{m.group(1)} {m.group(2).title()} {m.group(3)}')


def _unisza_values(rows) -> tuple:
    """(programme, code, printed reporting date, house reporting date, reason) from the table's rows."""
    programme, code, faculty = rows.get('Program Pengajian', ''), rows.get('Kod Program Pengajian', ''), \
        rows.get('Fakulti', '')
    if um_not_degree(programme) or not _FACULTY.match(faculty):
        return '', '', '', '', 'programme_shape'
    if any(w in _SQUEEZE_OUT.sub('', programme + ' ' + faculty) for w in NOT_DEGREE) or \
            _PRA.search(programme + ' ' + faculty):
        return programme, '', '', '', 'not_degree'
    if not _CODE.match(code):
        return programme, '', '', '', 'programme_shape'
    if not _CAMPUS.match(rows.get('Kampus', '')) or not _TERM.match(rows.get('Tempoh Pengajian', '')):
        return programme, code, '', '', 'table_shape'
    report = _unisza_report(rows.get('report', ''))
    if report is None:
        return programme, code, '', '', 'reporting_shape'
    return programme, code, report[0], report[1], ''


def _unisza_dates_sane(years, offer_date: str, printed: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; the
    reporting date is a real date in the session's years, not before the offer date."""
    y1, y2 = years
    offered, reported = _ymd(offer_date.title()), _ymd(printed.title())
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and offered <= reported


def _unisza_read(lines):
    """Every reader step on page 1's layout lines: (years, intake, head, (reporting index, reason), values); None
    before the title holds."""
    at, end, intake, y1, y2 = _unisza_title_at(lines)
    if at < 0:
        return None
    head = _unisza_head(lines, at)
    rows, report_at, why_table = _unisza_table(lines, end)
    values = _unisza_values(rows) if not why_table else ('', '', '', '', '')
    return (y1, y2), intake, head, (report_at, why_table), values


def read_unisza(source: str):
    """``(fields, reason)`` for a UniSZA letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    got = _unisza_read(lines)
    if got is None:
        return None, 'no_title'
    years, intake, (name, printed_ic, offer_date, why_head), (report_at, why_table), values = got
    programme, code, printed, reported, why_values = values
    nric = _norm_nric(printed_ic) if printed_ic else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'other' if nric else 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': reported,
        'reporting_date_label': 'Tarikh' if reported else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != 2]
    if unisza_ic_elsewhere('\n'.join(rest), '') or unisza_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if any(c != code for c in _ANY_CODE.findall(source)) or _ANY_CODE.findall(folded).count(code) != 1:
        return fields, 'second_code'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 1:
        return fields, 'not_degree'           # the programme row only
    if any(_ANY_DATE.search(_one_space(ln)) or _SHORT_DATE.search(_one_space(ln))
           for k, ln in enumerate(lines) if k not in (1, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'programme_code', 'intake', 'reporting_date')
             if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _unisza_dates_sane(years, offer_date, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def unisza_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`unisza_ic_elsewhere`),
    'not_an_offer' (`offer_ums_refusal._withdrawn_one` once the one measured note `_UNISZA_NOTE` is taken out, once;
    the head being the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if unisza_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(_UNISZA_NOTE.sub(' ', one, count=1), hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def unisza_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''. Measured: every UniSZA letter is
    one page; no later-page excuse is made (owner decision 26 Nov)."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'programme_code': 'v:code', 'intake': 'v:intake', 'reporting_date': 'v:date',
              'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_unisza` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'institution', 'campus', 'issuer', 'stream', 'reporting_date_label',
               'reporting_venue')


def _unisza_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "D MONTH YYYY") exactly as page 1 prints them, ('', '') when not read."""
    got = _unisza_read(_uum_lines(page1_layout))
    if got is None:
        return '', ''
    _years, _intake, head, (_r, why_table), values = got
    return (head[1] if not head[3] else ''), (values[2] if not why_table and not values[4] else '')


def unisza_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UniSZA lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _unisza_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
