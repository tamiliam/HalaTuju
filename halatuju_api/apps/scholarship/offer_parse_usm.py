"""The USM rules lane (OCR-14 phase 6): a DIGITAL Universiti Sains Malaysia degree offer letter read from its page-1
LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:USM`` (`offer_exact.ocr_first_lanes`).

USM PRINTS THE IC, WITH NO LABEL (measured: every text letter prints the 12 digits in brackets after the name, two
spaces apart, on the head's third line). USM is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`, so a USM letter with no IC
never locks. As no label names it, the IC is stored with source ``other``: CORROBORATE-ONLY under
`offer_ic.guard_nric` (kept only when it is exactly the profile IC, else blanked, so no lock). It must be the 12 plain
digits (a hyphen, an en dash, a minus, a slash, a space or a line split refuses), printed exactly once; ANY other
IC-like number on any page refuses (`usm_ic_elsewhere`). The matric number ("NO MATRIK : 99999999") and the reference
are never stored.

Page 1, as measured on the corpus letter and the owner's 7 text samples (masked shapes only; one template; every
letter is one page; "Jabatan Pendaftar" is in the letterhead picture, not the text):

* at the left: "No.Rujukan : 99/USnnnnnnn/9999" (the programme code inside it); "Tarikh : D MONTH YYYY" (the offer
  date); "NAME  (IC)"; the address (`offer_parse_uitm.name_ended` must prove the name ended);
* the title "TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA, UNIVERSITI SAINS MALAYSIA (UNIVERSITI BERSTATUS APEX),
  SIDANG AKADEMIK YYYY/YYYY" on one or two lines (the intake is what follows "APEX), ");
* the greeting "Tahniah, saudara/i telah berjaya ditawarkan tempat ... seperti berikut:";
* the table, its rows in this order and nothing between them: NAMA (the head's name again), NO MATRIK, PROGRAM
  PENGAJIAN ("USnnnnnnn - SARJANA MUDA ... DENGAN KEPUJIAN", wrapped onto at most two more lines under its value; the
  code must be the reference's and the only programme code on the page), TEMPOH PENGAJIAN, YURAN PENGAJIAN, TARIKH
  LAPOR DIRI/MASA, TEMPAT LAPOR DIRI (never read), PENGINAPAN; then the fee header, its RM line and the notes.

The Programme label caution: "PROGRAM PENGAJIAN" (owner phrase 5) also sits inside the second note ("Program
pengajian yang ditawarkan ... muktamad", phrase 8): the programme is read ONLY from the upper-case table row at its
place in the table. No faculty is printed. The reporting date is read ONLY from the TARIKH LAPOR DIRI/MASA row:
"D MONTH YYYY (DAY) / h:mm PAGI|PETANG|TENGAH HARI - h:mm ..." with the right Malay day name. Any other value
refuses, and so does any date on the page but the offer date and that row. Any later page with text refuses.
"""
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uthm import _ANY_DATE, _DAYS, _NOT_DEGREE_WORD, _WIDE_GAP
from .offer_parse_uum import _LINKERS, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:USM'
INSTITUTION = 'UNIVERSITI SAINS MALAYSIA'
ISSUER = 'Jabatan Pendaftar, Universiti Sains Malaysia'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_LEFT = 12                                      # the head, address, title and notes start under this
_TABLE_IN = (16, 30)                            # the table's labels start between these (measured: 22)
_REFERENCE = re.compile(r'^No\.Rujukan : \d{2}/(US\d{7})/\d{4}$')
_OFFER_DATE = re.compile(r'^Tarikh : (\d{1,2}) ([A-Z]{3,9}) (20\d{2})$')
_NAME_IC = re.compile(r'^(\S(?:.*\S)?) {1,2}\(([^()]*)\)$')
_IC = re.compile(r'^\d{12}$')                   # as measured: the 12 digits alone, no separator, no space
_TITLE = re.compile(r'^TAWARAN KEMASUKAN PROGRAM IJAZAH SARJANA MUDA, UNIVERSITI SAINS MALAYSIA \(UNIVERSITI '
                    r'BERSTATUS APEX\), (SIDANG AKADEMIK (20\d{2})/(20\d{2}))$')
_GREETING = ('Tahniah, saudara/i telah berjaya ditawarkan tempat untuk mengikuti program Ijazah Sarjana Muda (Penuh '
             'Masa) di Universiti Sains Malaysia. Butir-butir lanjut tawaran adalah seperti berikut:')
#: The table's rows as printed (upper case, one-spaced), in order, each with the most wrap lines it may have.
_TABLE = (('NAMA', 0), ('NO MATRIK', 0), ('PROGRAM PENGAJIAN', 2), ('TEMPOH PENGAJIAN', 0),
          ('YURAN PENGAJIAN', 0), ('TARIKH LAPOR DIRI/MASA', 0), ('TEMPAT LAPOR DIRI', 3), ('PENGINAPAN', 2))
_FEES = 'Yuran Pengajian Setahun Yuran dibiayai Kerajaan Setahun Yuran dibayar Pelajar Setahun'
_RM = r'RM ?\d{1,3}(?:,\d{3})*\.\d{2}'
_FEE_LINE = re.compile(r'^' + _RM + ' ' + _RM + ' ' + _RM + r'$')
_NOTE_START = re.compile(r'^\d{1,2}\. \S')
_CODED = re.compile(r'^(US\d{7}) - (SARJANA MUDA \S.*? DENGAN KEPUJIAN)$')
_ANY_CODE = re.compile(r'(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![0-9])')
_MATRIC = re.compile(r'^\d{8}$')
_TERM = re.compile(r'^\d TAHUN$')
_YEAR_FEE = re.compile(r'^' + _RM + r' SETAHUN$')
_HOUR = r'\d{1,2}:\d{2} (?:PAGI|PETANG|TENGAH HARI)'     # measured: these three
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) \(([A-Z]{4,6})\) / ' + _HOUR + ' - ' + _HOUR + '$')
#: The one conditional withdrawal every genuine USM letter prints in its notes. Taken out before the withdrawal
#: check (`_cancel_said` reads "menarik balik" in it: measured, every genuine letter) and the not-a-degree word check
#: (its "sijil-sijil"), exactly once; any other withdrawal wording still refuses.
_NOTE_WORDS = ('Pihak universiti berhak menarik balik tawaran ini sekiranya terdapat keraguan terhadap keterangan '
               'atau salinan sijil-sijil yang dikemukakan oleh saudara/i semasa permohonan.')
_USM_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _NOTE_WORDS.split()))


def is_usm(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a USM admissions letter: the university and the "TAWARAN
    KEMASUKAN PROGRAM" title. Which of them is a degree offer `read_usm` decides."""
    return 'UNIVERSITI SAINS MALAYSIA' in up and 'TAWARAN KEMASUKAN PROGRAM' in up


def usm_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`offer_parse_ukm._own_ic`); page 1's plain layer must print it
    exactly once."""
    return _own_ic(text, nric)[1]


def usm_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`) once ONE copy of the read IC is
    taken out: the read IC printed twice counts too. No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def usm_head_plain(page1_text: str, name: str) -> str:
    """Page 1's plain layer with its ONE table row "NAMA : <name>" (one-spaced, exact) taken out, so the name's
    glue check (`offer_parse_university.name_in_plain`) reads the head copy alone: USM prints the name twice.
    No such row, or more than one: '' (the check then refuses)."""
    lines = (page1_text or '').splitlines()
    rows = [i for i, ln in enumerate(lines) if _one_space(ln) == 'NAMA : ' + name]
    return '\n'.join(ln for i, ln in enumerate(lines) if i != rows[0]) if name and len(rows) == 1 else ''


def _usm_title_at(lines) -> tuple:
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


def _usm_head(lines, at):
    """(name, printed IC, offer date as printed, reference code, reason) from the lines before the title."""
    if at < 4 or any(_indent(ln) > _LEFT for ln in lines[:at]):
        return '', '', '', '', 'no_head'
    ref, dated = _REFERENCE.match(_one_space(lines[0])), _OFFER_DATE.match(_one_space(lines[1]))
    if not ref or not dated or _ymd(f'{dated.group(1)} {dated.group(2).title()} {dated.group(3)}') is None:
        return '', '', '', '', 'no_head'
    offer_date = f'{dated.group(1)} {dated.group(2)} {dated.group(3)}'
    m = _NAME_IC.match(lines[2].strip())
    if not m or len(_cols(lines[2])) != 1:
        return '', '', offer_date, ref.group(1), 'name_shape'
    if not _IC.match(m.group(2)):
        return '', '', offer_date, ref.group(1), 'ic_shape'
    name, printed_ic = _one_space(m.group(1)), m.group(2)
    if not _name_ok(name) or name != name.upper() or _LINKERS.search(name):
        return '', printed_ic, offer_date, ref.group(1), 'name_shape'
    if not name_ended(lines[3]):
        return '', printed_ic, offer_date, ref.group(1), 'name_not_ended'  # the rest may be on the next line
    if not 1 <= at - 3 <= 6:
        return name, printed_ic, offer_date, ref.group(1), 'no_head'
    return name, printed_ic, offer_date, ref.group(1), ''


def _usm_row(line: str):
    """(label, value, value column) of a table line "LABEL : value" at the table's indent, or None."""
    if ':' not in line or not _TABLE_IN[0] <= _indent(line) <= _TABLE_IN[1]:
        return None
    colon = line.index(':')
    rest = line[colon + 1:]
    return _one_space(line[:colon]), _one_space(rest), colon + 1 + _indent(rest)


def _usm_table(lines, end):
    """({label: value}, index of the reporting row, reason): the greeting after the title, then `_TABLE` in order with
    nothing between them but each row's wrap lines under its value, then the fee header, its RM line and a note."""
    g = next((k for k in range(end, min(end + 4, len(lines))) if (_usm_row(lines[k]) or ('',))[0] == 'NAMA'), -1)
    if g < 0 or _one_space(' '.join(lines[end:g])) != _GREETING or any(_indent(ln) > _LEFT for ln in lines[end:g]):
        return {}, -1, 'no_table'
    rows, i, report_at = {}, g, -1
    for want, wraps in _TABLE:
        got = _usm_row(lines[i]) if i < len(lines) else None
        if not got or got[0] != want or not got[1]:
            return rows, -1, 'table_shape'
        report_at = i if want == 'TARIKH LAPOR DIRI/MASA' else report_at
        first, parts, i = i, [got[1]], i + 1
        while i < len(lines) and ':' not in lines[i] and abs(_indent(lines[i]) - got[2]) <= 2:
            parts.append(_one_space(lines[i]))
            i += 1
        raw = [lines[first][lines[first].index(':') + 1:]] + lines[first + 1:i]     # the value, not its label's gap
        if len(parts) > 1 + wraps or any(_WIDE_GAP.search(ln) for ln in raw):
            return rows, -1, 'table_shape'
        rows[want] = ' '.join(parts)
    if (i + 2 >= len(lines) or _one_space(lines[i]) != _FEES or not _FEE_LINE.match(_one_space(lines[i + 1]))
            or not _NOTE_START.match(_one_space(lines[i + 2])) or _indent(lines[i + 2]) > _LEFT):
        return rows, -1, 'table_shape'
    return rows, report_at, ''


def _usm_report(value: str):
    """(printed "D MONTH YYYY", house date) from "D MONTH YYYY (DAY) / h:mm .. - h:mm .." whose Malay day name is
    that date's, else None."""
    m = _REPORT_VALUE.match(value or '')
    if not m:
        return None
    day = _ymd(f'{m.group(1)} {m.group(2).title()} {m.group(3)}')
    if day is None or _DAYS[day.weekday()] != m.group(4):
        return None
    return f'{m.group(1)} {m.group(2)} {m.group(3)}', house_date(f'{m.group(1)} {m.group(2).title()} {m.group(3)}')


def _usm_values(rows, name: str, ref_code: str) -> tuple:
    """(programme, code, printed reporting date, house reporting date, reason) from the table's rows."""
    m = _CODED.match(rows.get('PROGRAM PENGAJIAN', ''))
    if not m or um_not_degree(m.group(2)):
        return '', '', '', '', 'programme_shape'
    code, programme = m.group(1), m.group(2)
    if code != ref_code:
        return programme, code, '', '', 'code_mismatch'
    if any(w in _SQUEEZE_OUT.sub('', programme) for w in NOT_DEGREE) or _PRA.search(programme):
        return programme, code, '', '', 'not_degree'
    if (rows.get('NAMA') != name or not _MATRIC.match(rows.get('NO MATRIK', ''))
            or not _TERM.match(rows.get('TEMPOH PENGAJIAN', ''))
            or not _YEAR_FEE.match(rows.get('YURAN PENGAJIAN', ''))):
        return programme, code, '', '', 'table_shape'
    report = _usm_report(rows.get('TARIKH LAPOR DIRI/MASA', ''))
    if report is None:
        return programme, code, '', '', 'reporting_shape'
    return programme, code, report[0], report[1], ''


def _usm_dates_sane(years, offer_date: str, printed: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; the
    reporting date is a real date in the session's years, not before the offer date."""
    y1, y2 = years
    offered, reported = _ymd(offer_date.title()), _ymd(printed.title())
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and offered <= reported


def _usm_read(lines):
    """Every reader step on page 1's layout lines: (title index, years, intake, head, table, values)."""
    at, end, intake, y1, y2 = _usm_title_at(lines)
    if at < 0:
        return None
    head = _usm_head(lines, at)
    rows, report_at, why_table = _usm_table(lines, end)
    values = _usm_values(rows, head[0], head[3]) if not why_table else ('', '', '', '', '')
    return at, (y1, y2), intake, head, (report_at, why_table), values


def read_usm(source: str):
    """``(fields, reason)`` for a USM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    got = _usm_read(lines)
    if got is None:
        return None, 'no_title'
    _at, years, intake, (name, printed_ic, offer_date, _ref, why_head), (report_at, why_table), values = got
    programme, code, printed, reported, why_values = values
    nric = _norm_nric(printed_ic) if printed_ic else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'other' if nric else 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': reported,
        'reporting_date_label': 'TARIKH LAPOR DIRI/MASA' if reported else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != 2]
    if usm_ic_elsewhere('\n'.join(rest), '') or usm_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if any(c != code for c in _ANY_CODE.findall(source)):
        return fields, 'second_code'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(_USM_NOTE.sub(' ', folded, count=1)).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 3:
        return fields, 'not_degree'           # the title, the greeting and the programme
    if any(_ANY_DATE.search(_one_space(ln)) for k, ln in enumerate(lines) if k not in (1, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'programme_code', 'intake', 'reporting_date')
             if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _usm_dates_sane(years, offer_date, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def usm_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`usm_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one` once the one genuine note `_USM_NOTE` is taken out, the head being the lines
    up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if usm_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(_USM_NOTE.sub(' ', one, count=1), hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def usm_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''. Measured: every USM letter is one
    page; any other page may hold a second programme, a date or an IC the reader never measured."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'programme_code': 'v:code', 'intake': 'v:intake', 'reporting_date': 'v:date',
              'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_usm` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'institution', 'campus', 'issuer', 'stream', 'reporting_date_label',
               'reporting_venue')


def _usm_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "D MONTH YYYY") exactly as page 1 prints them, ('', '') when not read."""
    got = _usm_read(_uum_lines(page1_layout))
    if got is None:
        return '', ''
    _at, _years, _intake, head, (_r, why_table), values = got
    return (head[1] if not head[4] else ''), (values[2] if not why_table and not values[4] else '')


def usm_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a USM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _usm_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
