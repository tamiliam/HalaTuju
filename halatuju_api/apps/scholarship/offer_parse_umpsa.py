"""The UMPSA rules lane (OCR-14b-1): a DIGITAL Universiti Malaysia Pahang Al-Sultan Abdullah degree offer letter in
its 2026/27 layout, read from its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``). The reader refuses on any
doubt; every refusal sends the letter to the AI as before. The lane is OFF unless OCR_FIRST_LANES holds ``ua:UMPSA``
(`offer_exact.ocr_first_lanes`). The 2024 layout ("KOLEJ / FAKULTI", no "SEMESTER I" in the title, a browser print
header) refuses: the owner's words cover the 2026/27 layout ONLY (2024 -> AI). A Diploma letter refuses.

UMPSA PRINTS THE IC WITH A LABEL: "NAME (NO. K/P: 12 digits)" on the line after the head date. It is stored with
source ``label`` and checked by the usual IC guard (UMPSA is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`). It must be the
12 plain digits, printed exactly once; ANY other IC-like number on any page refuses. The reference and the matric
number are never stored.

Page 1, as measured on the owner's 2 text samples in this layout (masked shapes only; one page each; every row at the
left margin):

* "RUJ. KAMI (OUR REF) : UMPSA NN.NN/NNN-N/N/N" then "TARIKH : D MONTH YYYY" (the offer date);
* "NAME (NO. K/P: IC)" (`offer_parse_uitm.name_ended` must prove the name ended on the next line), two to four
  address lines, "Saudara/i,";
* the title "TAWARAN KEMASUKAN KE PROGRAM SARJANA MUDA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH SEMESTER I,
  SESI AKADEMIK YYYY/YYYY" on two lines (the intake is what follows "AL-SULTAN ABDULLAH ");
* the greeting "Dimaklumkan bahawa ... Semester I, Sesi Akademik YYYY/YYYY seperti berikut :" on two lines, its
  session the title's;
* the table, its rows in this order, one line each: PROGRAM PENGAJIAN ("SARJANA MUDA ..."), FAKULTI / PUSAT
  ("FAKULTI ..."), NO. MATRIK (never stored), TAHUN PENGAJIAN, TEMPOH PENGAJIAN, MOD PENGAJIAN ("SEPENUH MASA"),
  YURAN PENGAJIAN, TARIKH PRA-PENDAFTARAN (a date range and its fixed note, one or two wrapped lines; never stored,
  only checked), KAMPUS (never read), and "TARIKH PENDAFTARAN KOLEJ : D MONTH YYYY (h.mm PAGI - h.mm PETANG)
  KEHADIRAN FIZIKAL KE KAMPUS" whose label ends on the next line, "KEDIAMAN";
* then "Maklumat Subsidi Kerajaan:", its header, its three amounts and "Nota:".

The reporting date is read ONLY from that labelled row (the date the corpus answers record: the physical
registration, not the online pre-registration). Any date on the page but the offer date, the pre-registration range
and that row refuses; those are skipped only at the fixed places the reader read them (the head's second line, the
table's TARIKH PRA-PENDAFTARAN row and its wrapped lines, the reporting row), never a line found by its words. Any later page with text refuses (``later_page``). UMPSA prints no programme code.

THE OWNER WORDS. The owner phrase "TARIKH PENDAFTARAN KOLEJ KEDIAMAN" is ONE label the layout splits: its last word
wraps under it, after the row's value. `umpsa_owner_text` joins it back ONLY when the reporting row and the lone
"KEDIAMAN" line under it are exactly as measured; every other owner phrase is checked on the layout as it is.

TWO EXCUSES, both owner-approved on 27 Nov ("A, same as UTeM and USM"), each one exact text taken out once:

* the paragraph. Every measured letter prints the conditional note `_NOTE_WORDS` under "MAKLUMAT PENTING"
  ("Tawaran ini akan terbatal sekiranya ... tidak sah ... juga terbatal sekiranya ..."); the shared withdrawal check
  reads its "tidak sah" and "juga terbatal" as a withdrawal. That exact paragraph is taken out ONCE before the
  withdrawal check; a second copy, and any other withdrawal or cancel wording, still refuses;
* the print note. Every measured letter ends page 1 with `_PRINT_WORDS`, whose "Sila cetak" the shared portal tell
  reads as a portal page. It is taken out before the portal check ONLY at its measured place (`umpsa_portal`): the
  last-but-one line of page 1's layout, alone on its line, indented, right after the signature block and with the
  computer-print line after it. The
  same note anywhere else, or a second copy, still refuses as a portal page.
"""
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_umk import _SHORT_DATE
from .offer_parse_university import _ADDRESS_START
from .offer_parse_uthm import _ANY_DATE, _NOT_DEGREE_WORD
from .offer_parse_uum import _LINKERS, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UMPSA'
INSTITUTION = 'UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH'
ISSUER = 'Pusat Pemasaran dan Kemasukan, Universiti Malaysia Pahang Al-Sultan Abdullah'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE_WORDS = 'TAWARAN KEMASUKAN KE PROGRAM SARJANA MUDA UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH'
_LEFT = 2                                       # every head, table and note row (measured: 0)
_WRAP_IN = (30, 60)                             # the pre-registration note's wrapped line (measured: 46, 47)
_REFERENCE = re.compile(r'^UMPSA \d{1,3}\.\d{1,3}/\d{1,4}-\d{1,2}/\d{1,2}/\d{1,3}$')
_DAY_MONTH_YEAR = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2})$')
_NAME_IC = re.compile(r'^(\S(?:.*\S)?) \(NO\. K/P: (\d{12})\)$')    # the 12 digits alone, no separator
_SALUTATION = 'Saudara/i,'
_TITLE = re.compile(r'^' + _TITLE_WORDS + r' (SEMESTER I, SESI AKADEMIK (20\d{2})/(20\d{2}))$')
_GREETING = ('Dimaklumkan bahawa Universiti Malaysia Pahang Al-Sultan Abdullah (UMPSA) mengucapkan tahniah kepada '
             'saudara/i dan seterusnya menawarkan kemasukan ke program Sarjana Muda UMPSA Semester I, Sesi Akademik '
             '{0}/{1} seperti berikut :')
_TABLE = ('PROGRAM PENGAJIAN', 'FAKULTI / PUSAT', 'NO. MATRIK', 'TAHUN PENGAJIAN', 'TEMPOH PENGAJIAN',
          'MOD PENGAJIAN', 'YURAN PENGAJIAN', 'TARIKH PRA-PENDAFTARAN')
_PROGRAMME = re.compile(r"^SARJANA MUDA [A-Z(][A-Z&,'.()\-]*(?: [A-Z&(][A-Z&,'.()\-]*)*$")
_FACULTY = re.compile(r"^FAKULTI [A-Z][A-Z&,'.()\-]*(?: [A-Z&][A-Z&,'.()\-]*)*$")
_MATRIC = re.compile(r'^[A-Z]{2}\d{5}$')        # as measured; never stored
_YEAR_OF_STUDY = re.compile(r'^TAHUN [1-5]$')
_TERM = re.compile(r'^\d TAHUN$')
_MODE = 'SEPENUH MASA'
_FEES_ROW = 'BAYARAN YURAN Sila Klik'
_RANGE = re.compile(r'^(\d{1,2})(?: ([A-Z]{3,9})(?: (20\d{2}))?)? ?- ?(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) '
                    r'\(CALON WAJIB MEMBUAT PRA - PENDAFTARAN SECARA DALAM TALIAN MENGIKUT TARIKH YANG TELAH '
                    r'DITETAPKAN\)$')
_CAMPUS = re.compile(r'^UNIVERSITI MALAYSIA PAHANG AL-SULTAN ABDULLAH, KAMPUS (?:GAMBANG|PEKAN)$')
_REPORT_LABEL = 'TARIKH PENDAFTARAN KOLEJ'
_REPORT_TAIL = 'KEDIAMAN'
REPORT_LABEL = _REPORT_LABEL + ' ' + _REPORT_TAIL
_HOUR = r'\d{1,2}\.\d{2} (?:PAGI|PETANG|TENGAH HARI)'      # measured: PAGI and PETANG
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) \(' + _HOUR + ' - ' + _HOUR
                           + r'\) KEHADIRAN FIZIKAL KE KAMPUS$')
_SUBSIDY = 'Maklumat Subsidi Kerajaan:'
_SUBSIDY_HEAD = ('Kos Sebenar Pengajian Setahun (RM) Kos Pengajian Dibayar Pelajar Setahun Kos Dibiayai Kerajaan '
                 'Setahun (RM)')
_AMOUNT = r'(?:\d{1,3}(?:,\d{3})+|\d{1,6})\.\d{2}'
_AMOUNTS = re.compile(r'^' + ' '.join([_AMOUNT] * 3) + r'$')
#: The one conditional note every measured letter prints under "MAKLUMAT PENTING" (owner, 27 Nov). Taken out ONCE
#: before the withdrawal check; any other withdrawal wording still refuses.
_NOTE_WORDS = ('Tawaran ini akan terbatal sekiranya terdapat sebarang maklumat yang tidak tepat, tidak benar, atau '
               'telah dipinda secara tidak sah dalam permohonan atau surat tawaran. Tawaran ini juga terbatal '
               'sekiranya calon tidak hadir mendaftar pada tarikh yang ditetapkan.')
_UMPSA_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _NOTE_WORDS.split()))
#: The one print note every measured letter ends page 1 with, which `offer_parse._PORTAL_TELL` ("SILA CETAK") reads
#: as a portal page (the UKM and UNIMAS precedent). Taken out before the portal check, once, and only at its
#: measured place (`umpsa_portal`, `_print_note_in_place`).
_PRINT_WORDS = 'Nota: Sila cetak dan bawa Surat Tawaran ini semasa hadir ke Kampus.'
_PRINT_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _PRINT_WORDS.split()))
#: The line every measured letter prints after the print note: the last line of page 1's layout.
_COMPUTER_WORDS = 'Surat Tawaran ini adalah cetakan komputer dan tandatangan tidak diperlukan.'
#: The print note's indent on page 1's layout (spaces before it). Measured: 43 and 46 on the two text letters.
_PRINT_INDENT = range(40, 50)
#: The signature block's last line, the line every measured letter prints right before the print note.
_SIGN_LAST = 'Universiti Malaysia Pahang Al-Sultan Abdullah'


def is_umpsa(up: str) -> bool:
    """``up`` (upper-cased) reads as a UMPSA admissions letter: the university and its offer title (degree or not;
    which of them is a degree offer in the measured layout `read_umpsa` decides)."""
    up = _one_space(up)
    return INSTITUTION in up and 'TAWARAN KEMASUKAN KE PROGRAM' in up


def _print_note_in_place(page1_layout: str) -> bool:
    """True when page 1's layout prints the print note exactly once, at its measured place: the last-but-one
    non-empty line, the note alone on it, indented as measured (`_PRINT_INDENT`), right after the signature block's
    last line (`_SIGN_LAST`) and with the computer-print line (`_COMPUTER_WORDS`) the last line after it."""
    lines = [ln for ln in (page1_layout or '').splitlines() if ln.strip()]
    hits = [i for i, ln in enumerate(lines) if _PRINT_NOTE.search(ln)]
    if len(lines) < 3 or hits != [len(lines) - 2]:
        return False
    sign, note, last = lines[-3:]
    return (_one_space(sign) == _SIGN_LAST and _one_space(note) == _PRINT_WORDS and _indent(note) in _PRINT_INDENT
            and _one_space(last) == _COMPUTER_WORDS)


def umpsa_portal(text: str, page1_layout: str) -> bool:
    """True when ``text`` (the whole letter) carries a portal tell (`offer_parse._PORTAL_TELL`) once the one print
    note (`_PRINT_NOTE`) is taken out. It is taken out only when ``text`` prints it exactly once and page 1's
    layout prints it at its measured place (`_print_note_in_place`); anywhere else, or twice, its "Sila cetak"
    stays and counts as a portal page. With no layout (a scan) the note has no place to check, but such a letter
    refuses (``no_layout``) right after, so it is taken out once there and the refusal keeps its own reason."""
    from .offer_parse import _PORTAL_TELL
    text = text or ''
    rest, n = _PRINT_NOTE.subn(' ', text)
    placed = _print_note_in_place(page1_layout) if (page1_layout or '').strip() else True
    if n != 1 or not placed:
        rest = text
    return bool(_PORTAL_TELL.search(rest))


def umpsa_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`offer_parse_ukm._own_ic`); page 1's plain layer: exactly once."""
    return _own_ic(text, nric)[1]


def umpsa_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`) once ONE copy of the read IC is
    taken out: the read IC printed twice counts too. No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _umpsa_row(line: str):
    """(label, value) of a left-margin one-column "LABEL : value" line, else None."""
    if ':' not in line or _indent(line) > _LEFT:
        return None
    label, value = line.strip().split(':', 1)
    if not value.strip() or not label.strip() or len(_cols(value)) != 1 or len(_cols(label)) != 1:
        return None
    return _one_space(label), _one_space(value)


def _left(lines) -> bool:
    """Every line at the left margin, one column."""
    return all(_indent(ln) <= _LEFT and len(_cols(ln)) == 1 for ln in lines)


def _umpsa_title_at(lines) -> tuple:
    """(index, intake, first year, second year): the two-line title once, at the left margin; (-1, '', 0, 0) else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')]
    if len(hits) != 1 or hits[0] + 2 > len(lines) or not _left(lines[hits[0]:hits[0] + 2]):
        return -1, '', 0, 0
    m = _TITLE.match(_one_space(' '.join(lines[hits[0]:hits[0] + 2])))
    return (hits[0], m.group(1), int(m.group(2)), int(m.group(3))) if m else (-1, '', 0, 0)


def _name_words_ok(name: str) -> bool:
    """A name to lock: `_name_ok`, upper case, not ending in a linker, and no word an address word."""
    return (_name_ok(name) and name == name.upper() and not _LINKERS.search(name)
            and not any(_ADDRESS_START.fullmatch(w) for w in name.split()))


def _umpsa_head(lines, at):
    """(name, printed IC, offer date as printed, reason) from the lines before the title."""
    if at < 6 or not _left(lines[2:at]):         # the two head rows are "LABEL : value" (checked by `_row`)
        return '', '', '', 'no_head'
    ref, dated = _umpsa_row(lines[0]), _umpsa_row(lines[1])
    if (not ref or ref[0] != 'RUJ. KAMI (OUR REF)' or not _REFERENCE.match(ref[1]) or not dated
            or dated[0] != 'TARIKH' or not _DAY_MONTH_YEAR.match(dated[1]) or _ymd(dated[1].title()) is None):
        return '', '', '', 'no_head'
    offer_date = dated[1]
    if not 2 <= len(lines[3:at - 1]) <= 4 or _one_space(lines[at - 1]) != _SALUTATION:
        return '', '', offer_date, 'no_head'
    m = _NAME_IC.match(_one_space(lines[2]))
    if not m:
        return '', '', offer_date, 'name_shape'
    name, printed_ic = _one_space(m.group(1)), m.group(2)
    if not _name_words_ok(name):
        return '', printed_ic, offer_date, 'name_shape'
    if not name_ended(lines[3]):
        return '', printed_ic, offer_date, 'name_not_ended'   # the address must open as an address
    return name, printed_ic, offer_date, ''


def _umpsa_table(lines, at, years):
    """({label: value}, index of the reporting row, indices of the pre-registration row and its wrapped lines,
    reason): the greeting, `_TABLE` in order (the pre-registration note's wrapped lines), KAMPUS, the reporting row
    and its "KEDIAMAN" line, then the subsidy block and "Nota:". The indices are the fixed positions the reader
    read ((), -1 unless every step holds)."""
    rows, report_at, why = _umpsa_table_rows(lines, at, years)
    if why:
        return rows, -1, (), why
    return rows, report_at, tuple(range(at + 4 + len(_TABLE) - 1, report_at - 1)), ''


def _umpsa_table_rows(lines, at, years):
    """`_umpsa_table` without the read lines: (rows, index of the reporting row, reason)."""
    g = at + 4
    if (g > len(lines) or not _left(lines[at + 2:g])
            or _one_space(' '.join(lines[at + 2:g])) != _GREETING.format(*years)):
        return {}, -1, 'no_table'
    rows = {}
    for k, want in enumerate(_TABLE):
        got = _umpsa_row(lines[g + k]) if g + k < len(lines) else None
        if not got or got[0] != want:
            return rows, -1, 'table_shape'
        rows[want] = got[1]
    i = g + len(_TABLE)
    wraps = []
    while i < len(lines) and len(wraps) < 2 and _WRAP_IN[0] <= _indent(lines[i]) <= _WRAP_IN[1] \
            and len(_cols(lines[i])) == 1:
        wraps.append(_one_space(lines[i]))
        i += 1
    rows['range'] = _one_space(' '.join([rows['TARIKH PRA-PENDAFTARAN']] + wraps))
    campus, report = (_umpsa_row(lines[i + k]) if i + k < len(lines) else None for k in (0, 1))
    if not campus or campus[0] != 'KAMPUS' or not _CAMPUS.match(campus[1]):
        return rows, -1, 'table_shape'
    if (not report or report[0] != _REPORT_LABEL or i + 2 >= len(lines)
            or _one_space(lines[i + 2]) != _REPORT_TAIL or _indent(lines[i + 2]) > _LEFT):
        return rows, -1, 'reporting_shape'
    rows['report'] = report[1]
    j = i + 3
    block = [_one_space(ln) for ln in lines[j:j + 5]]
    if (len(block) == 5 and block[0] == _SUBSIDY and _indent(lines[j]) <= _LEFT and len(_cols(lines[j + 1])) == 3
            and block[1] == _SUBSIDY_HEAD and block[2] == '(RM)' and _AMOUNTS.match(block[3])
            and block[4] == 'Nota:' and _indent(lines[j + 4]) <= _LEFT):
        return rows, i + 1, ''                  # the middle header's "(RM)" alone on the line under it (measured)
    return rows, -1, 'table_shape'


def _umpsa_when(day, month, year):
    """A real calendar date from its printed parts, else None."""
    return _ymd(f'{day} {month.title()} {year}')


def _range(value):
    """(first day, last day) of the pre-registration range, else None. A start with no month or year takes the
    end's."""
    m = _RANGE.match(value or '')
    if not m:
        return None
    end = _umpsa_when(m.group(4), m.group(5), m.group(6))
    start = _umpsa_when(m.group(1), m.group(2) or m.group(5), m.group(3) or m.group(6))
    return (start, end) if start and end and start <= end else None


def _values(rows) -> tuple:
    """(programme, printed reporting date, house reporting date, reason) from the table's rows."""
    programme, faculty = rows.get('PROGRAM PENGAJIAN', ''), rows.get('FAKULTI / PUSAT', '')
    if um_not_degree(programme) or not _PROGRAMME.match(programme) or not _FACULTY.match(faculty):
        return '', '', '', 'programme_shape'
    if any(w in _SQUEEZE_OUT.sub('', programme + ' ' + faculty) for w in NOT_DEGREE) or \
            _PRA.search(programme + ' ' + faculty):
        return programme, '', '', 'not_degree'
    if (not _MATRIC.match(rows.get('NO. MATRIK', '')) or not _YEAR_OF_STUDY.match(rows.get('TAHUN PENGAJIAN', ''))
            or not _TERM.match(rows.get('TEMPOH PENGAJIAN', '')) or rows.get('MOD PENGAJIAN') != _MODE
            or rows.get('YURAN PENGAJIAN') != _FEES_ROW or _range(rows.get('range')) is None):
        return programme, '', '', 'table_shape'
    m = _REPORT_VALUE.match(rows.get('report', ''))
    if not m or _umpsa_when(m.group(1), m.group(2), m.group(3)) is None:
        return programme, '', '', 'reporting_shape'
    printed = f'{m.group(1)} {m.group(2)} {m.group(3)}'
    return programme, printed, house_date(f'{m.group(1)} {m.group(2).title()} {m.group(3)}'), ''


def _dates_sane(years, offer_date: str, printed: str, rng) -> bool:
    """The session's years run on; the offer date in the year before the session or its first, not after the
    pre-registration's first day; the range and the reporting date in the session's years, the reporting date not
    before the range's first day."""
    y1, y2 = years
    offered, reported = _ymd(offer_date.title()), _ymd(printed.title())
    if y2 != y1 + 1 or offered is None or reported is None or rng is None:
        return False
    start, end = rng
    return (y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and y1 <= start.year and end.year <= y2
            and offered <= start and start <= reported)


def _umpsa_read(lines):
    """Every reader step on page 1's layout lines: (years, intake, head, (reporting index, reason), values, rows,
    the pre-registration row's and its wrapped lines' indices); None before the title holds."""
    at, intake, y1, y2 = _umpsa_title_at(lines)
    if at < 0:
        return None
    head = _umpsa_head(lines, at)
    rows, report_at, range_at, why_table = _umpsa_table(lines, at, (y1, y2))
    values = _values(rows) if not why_table else ('', '', '', '')
    return (y1, y2), intake, head, (report_at, why_table), values, rows, range_at


def read_umpsa(source: str):
    """``(fields, reason)`` for a UMPSA letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    got = _umpsa_read(lines)
    if got is None:
        return None, 'no_title'
    years, intake, (name, printed_ic, offer_date, why_head), (report_at, why_table), values, rows, range_at = got
    programme, printed, reported, why_values = values
    nric = _norm_nric(printed_ic) if printed_ic else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': reported,
        'reporting_date_label': REPORT_LABEL if reported else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != 2]
    if umpsa_ic_elsewhere('\n'.join(rest), '') or umpsa_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 3:
        return fields, 'not_degree'           # the title, the greeting and the programme row only
    known = {0, 1, report_at, *range_at}        # the fixed lines the reader read, never a line found by its words
    if any(_ANY_DATE.search(_one_space(ln)) or _SHORT_DATE.search(_one_space(ln))
           for k, ln in enumerate(lines) if k not in known):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _dates_sane(years, offer_date, printed, _range(rows.get('range'))):
        return fields, 'dates_not_sane'
    return fields, ''


def umpsa_owner_text(page1_layout: str) -> str:
    """``page1_layout`` with the one split owner label joined back: the reporting row's "TARIKH PENDAFTARAN KOLEJ"
    and the lone "KEDIAMAN" on the line straight under it become "TARIKH PENDAFTARAN KOLEJ KEDIAMAN : value". Only
    when exactly one such pair exists, both at the left margin; else the layout unchanged (the phrase stays
    missing, so the lane refuses)."""
    lines = (page1_layout or '').splitlines()
    pairs = [k for k in range(len(lines) - 1)
             if (_umpsa_row(lines[k]) or ('',))[0] == _REPORT_LABEL and _one_space(lines[k + 1]) == _REPORT_TAIL
             and _indent(lines[k + 1]) <= _LEFT]
    if len(pairs) != 1:
        return page1_layout or ''
    k = pairs[0]
    value = lines[k].split(':', 1)[1]
    return '\n'.join(lines[:k] + [f'{REPORT_LABEL} :{value}'] + lines[k + 2:])


def umpsa_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`umpsa_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one` once the one measured note `_UMPSA_NOTE` is taken out, once; the head being
    the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if umpsa_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(_UMPSA_NOTE.sub(' ', one, count=1), hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def umpsa_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''. Measured: every 2026/27 letter is
    one page."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


def diagnose_umpsa(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None) -> dict:
    """The UMPSA branch of `offer_parse.diagnose` (via `offer_parse_lanes`), in `diagnose_unisza`'s order: a portal
    page refuses; a scan refuses (``no_layout``); the drawn page texts (``hidden_page``); `read_umpsa`; the owner
    phrases (on `umpsa_owner_text`); the whole letter (`umpsa_letter_refusal`); ``foreign_letters``;
    ``name_not_plain``; the read IC not printed exactly once in page 1's plain layer (``ic_not_plain``); any other
    IC-like number in page 1's plain layer or any page text (``ic_printed``); last, any later page with text."""
    from .offer_parse import _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = umpsa_portal(text, page1_layout)
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_umpsa(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, umpsa_owner_text(page1_layout), text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or umpsa_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and umpsa_ic_copies(page1_text, nric) != 1:
        reason = 'ic_not_plain'
    if not reason and (umpsa_ic_elsewhere(page1_text, nric) or any(umpsa_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = umpsa_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'umpsa', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_umpsa` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'institution', 'campus', 'issuer', 'stream', 'reporting_date_label',
               'reporting_venue', 'programme_code')


def _printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "D MONTH YYYY") exactly as page 1 prints them, ('', '') when not read."""
    got = _umpsa_read(_uum_lines(page1_layout))
    if got is None:
        return '', ''
    _years, _intake, head, (_r, why_table), values, _rows, _range_at = got
    return (head[1] if not head[3] else ''), (values[1] if not why_table and not values[3] else '')


def umpsa_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UMPSA lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``, the split label joined back: `umpsa_owner_text`) and every field read off the page (`INK_LABELS`; the
    IC and the reporting date as printed). A required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, umpsa_owner_text(page1_layout), INK_LABELS, INK_OPTIONAL, values)
