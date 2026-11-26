"""The UTeM rules lane (OCR-14 phase 5): a DIGITAL Universiti Teknikal Malaysia Melaka degree offer letter read from
its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UTeM`` (`offer_exact.ocr_first_lanes`).

UTeM PRINTS THE IC, WITH NO LABEL (measured: every text letter prints the 12 digits alone at the left, on the line
between the head's "Tarikh (Date)" row and the name). UTeM is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`, so a UTeM
letter with no IC never locks. As no label names it, the IC is stored with source ``other``: CORROBORATE-ONLY under
`offer_ic.guard_nric` (kept only when it is exactly the profile IC, else blanked, so no lock). It must be the 12 plain
digits (a hyphen, an en dash, a minus, a slash, a space or a line split refuses), printed exactly once; ANY other
IC-like number on any page refuses (`utem_ic_elsewhere`). The matric number ("No. Matrik : B999999999"), the e-mail
built from it, the "No. MHS" number, the e-mail password and the reference are never stored.

Page 1, as measured on the corpus letter and the owner's 9 text samples (masked shapes only; the "variant A" degree
template, 7 of the 9 samples):

* in the right-hand column: "PEJABAT PENDAFTAR"; the Tel | Faks line; "Rujukan Kami (Our Ref) : UTeM.<digits>";
  "Rujukan Tuan (Your Ref) :" (blank); "Tarikh (Date) : D Month YYYY" (the offer date);
* at the left: the IC alone; the name alone (`offer_parse_uitm.name_ended` must prove it ended); the address;
  "Saudara/i";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA SEMESTER I SESI AKADEMIK YYYY/YYYY", once (the
  intake is what follows MELAKA);
* the greeting "Tahniah, sukacita dimaklumkan bahawa anda telah ditawarkan tempat bagi mengikuti Program Pengajian
  seperti berikut : -";
* the table, its rows in this order and nothing between them: Program Pengajian (an "[IJAZAH ]SARJANA MUDA ...
  DENGAN KEPUJIAN" degree, wrapped onto at most two lines under its value), Tahun (must be "Satu (1)"), Mod
  Pengajian (must be "SEPENUH MASA"), Fakulti (a "FAKULTI ..." name), the line "Sila datang mendaftar di : -", Tempat
  (never read), Tarikh, Bayaran, Kemudahan Kolej Kediaman, No. Matrik, E-mel Rasmi Pelajar; then "Anda akan
  mengikut ...".

The reporting date is read ONLY from that Tarikh row under "Sila datang mendaftar di": "DD Month YYYY (Day)" with the
right Malay day name, then the "Masa : h.mm .. - h.mm .." window. Any other value refuses, and so does any date on the
page but the reference, the offer date and that row. The other templates refuse: the diploma letters ("SESI
YYYY/YYYY" title, no ``no_title``), and the second degree template (variant B: "SEMESTER I SESI YYYY/YYYY", an
online-registration date and a second Tarikh block; ``no_title``). Any later page with text refuses (``later_page``).
"""
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uthm import _ANY_DATE, _DAYS, _NOT_DEGREE_WORD, _WIDE_GAP
from .offer_parse_uum import _LINKERS, _WORD_DATE, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UTeM'
INSTITUTION = 'UNIVERSITI TEKNIKAL MALAYSIA MELAKA'
ISSUER = 'Bahagian Pengurusan Akademik, Pejabat Pendaftar, Universiti Teknikal Malaysia Melaka'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_OFFICE = 'PEJABAT PENDAFTAR'
_RIGHT = 40                                     # the head's right-hand column starts past this
_LEFT = 12                                      # the IC, name, address or table label starts under this
_PHONES = re.compile(r'^Tel : \+\d{3} \d{3} \d{4} \| Faks : \+\d{3} \d{3} \d{4}$')
_REFERENCE = re.compile(r'^UTeM\.\d{2,3}(?:\.\d{2}){0,2}(?:/\d{3})?-\d{1,2}/\d{1,2}/\d{1,2}$')
_IC_LINE = re.compile(r'^\d{12}$')              # as measured: the 12 digits alone, no separator, no space
_SALUTATION = 'Saudara/i'
_TITLE = re.compile(r'^TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA MELAKA '
                    r'(SEMESTER I SESI AKADEMIK (20\d{2})/(20\d{2}))$')
_GREETING = ('Tahniah, sukacita dimaklumkan bahawa anda telah ditawarkan tempat bagi mengikuti Program Pengajian '
             'seperti berikut : -')
_REGISTER = 'Sila datang mendaftar di : -'
#: The table's rows (labels with every non-word character squeezed out), in printed order; None is the
#: `_REGISTER` line between Fakulti and Tempat.
_TABLE = ('PROGRAMPENGAJIAN', 'TAHUN', 'MODPENGAJIAN', 'FAKULTI', None, 'TEMPAT', 'TARIKH', 'BAYARAN',
          'KEMUDAHANKOLEJKEDIAMAN', 'NOMATRIK', 'EMELRASMIPELAJAR')
_AFTER_TABLE = 'Anda akan mengikut '
_MAX_WRAPS = 2
_DEGREE = re.compile(r'^(?:IJAZAH )?SARJANA MUDA \S.*? DENGAN KEPUJIAN$')
_FEE = re.compile(r'^RM ?\d{1,3}(?:,\d{3})*\.\d{2}$')
_MATRIC = re.compile(r'^B\d{9} No\. MHS : \d{1,4}$')
_EMAIL = re.compile(r'^B\d{9}@student\.utem\.edu\.my Kata Laluan Emel : \S{1,40}$')
_HOUR = r'\d{1,2}[.:]\d{2} ?[A-Za-z]{2,8}\.?'
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z][a-z]{2,8}) (20\d{2}) \(([A-Z][a-z]{3,6})\) Masa : '
                           + _HOUR + r' ?- ?' + _HOUR + r'$')
#: The one conditional withdrawal every genuine UTeM degree letter prints in its notes ("PENTING"). Taken out before
#: the withdrawal check (whose "DITARIK BALIK" would refuse every genuine letter), exactly once; any other
#: withdrawal wording still refuses.
_NOTE_WORDS = 'Tawaran akan ditarik balik sekiranya UTeM mendapati maklumat yang anda beri tidak benar.'
_UTEM_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _NOTE_WORDS.split()))


def is_utem(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UTeM admissions letter: the university and its registrar's
    office. Which of them is a degree offer `read_utem` decides."""
    return 'UNIVERSITI TEKNIKAL MALAYSIA MELAKA' in up and _OFFICE in up


def utem_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`offer_parse_ukm._own_ic`); page 1's plain layer must print it
    exactly once."""
    return _own_ic(text, nric)[1]


def utem_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`: every dash look-alike, a slash, a
    whitespace run, a line break, a digit run of 12+) once ONE copy of the read IC is taken out: the read IC printed
    twice counts too. No IC read (``nric`` blank): any IC-like number counts. No phone-number excuse (measured: the
    UTeM Tel line is no IC shape)."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _utem_key(label: str) -> str:
    return _SQUEEZE_OUT.sub('', (label or '').upper())


def _utem_row(line: str):
    """(key, value, value column) of a "Label : value" layout line, or None. The key is the label with every
    non-word character squeezed out; the value is one-spaced."""
    if ':' not in line:
        return None
    colon = line.index(':')
    rest = line[colon + 1:]
    return _utem_key(line[:colon]), _one_space(rest), colon + 1 + _indent(rest)


def _utem_title_at(lines) -> tuple:
    """(index, intake, first year, second year) of the title: once, at the left margin, one column; (-1, '', 0, 0)
    else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')]
    if len(hits) != 1 or _indent(lines[hits[0]]) > _LEFT or len(_cols(lines[hits[0]])) != 1:
        return -1, '', 0, 0
    m = _TITLE.match(_one_space(lines[hits[0]]))
    return (hits[0], m.group(1), int(m.group(2)), int(m.group(3))) if m else (-1, '', 0, 0)


def _right_row(lines, k, key):
    """The value of the right-hand head row ``k`` when its key is ``key``, else None."""
    got = _utem_row(lines[k]) if _indent(lines[k]) >= _RIGHT else None
    return got[1] if got and got[0] == key else None


def _utem_head(lines, at):
    """(name, printed IC, offer_date, reason) from the lines before the title (see the module docstring)."""
    if at < 9 or _one_space(lines[0]) != _OFFICE or _indent(lines[0]) < _RIGHT:
        return '', '', '', 'no_head'
    if _indent(lines[1]) < _RIGHT or not _PHONES.match(_one_space(lines[1])):
        return '', '', '', 'no_head'
    ours, yours = _right_row(lines, 2, 'RUJUKANKAMIOURREF'), _right_row(lines, 3, 'RUJUKANTUANYOURREF')
    dated = _right_row(lines, 4, 'TARIKHDATE')
    if not ours or not _REFERENCE.match(ours) or yours != '' or not dated or not re.fullmatch(_WORD_DATE, dated) \
            or _ymd(dated) is None:
        return '', '', '', 'no_head'
    printed_ic = lines[5].strip()
    if _indent(lines[5]) > _LEFT or not _IC_LINE.match(printed_ic):
        return '', '', dated, 'ic_shape'
    name = _one_space(lines[6])
    if (_indent(lines[6]) > _LEFT or len(_cols(lines[6])) != 1 or not _name_ok(name) or name != name.upper()
            or _LINKERS.search(name)):
        return '', printed_ic, dated, 'name_shape'      # an unread or wrapped name ("... BINTI")
    if not name_ended(lines[7]):
        return '', printed_ic, dated, 'name_not_ended'  # the rest of the name may be on the next line
    if (_one_space(lines[at - 1]) != _SALUTATION or _indent(lines[at - 1]) > _LEFT
            or not 1 <= at - 1 - 7 <= 6 or any(_SALUTATION in ln for ln in lines[7:at - 1])):
        return name, printed_ic, dated, 'no_head'
    return name, printed_ic, dated, ''


def _utem_table(lines, at):
    """({key: value}, index of the reporting row, reason): the greeting after the title, then `_TABLE` in order with
    nothing between them but at most `_MAX_WRAPS` programme lines under its value, then "Anda akan mengikut"."""
    g = next((k for k in range(at + 1, min(at + 4, len(lines)))
              if (_utem_row(lines[k]) or ('',))[0] == _TABLE[0] and _indent(lines[k]) <= _LEFT), -1)
    if g < 0 or _one_space(' '.join(lines[at + 1:g])) != _GREETING:
        return {}, -1, 'no_table'
    rows, i, report_at = {}, g, -1
    for want in _TABLE:
        if i >= len(lines) or _indent(lines[i]) > _LEFT:
            return rows, -1, 'table_shape'
        if want is None:
            if _one_space(lines[i]) != _REGISTER:
                return rows, -1, 'table_shape'
            i += 1
            continue
        got = _utem_row(lines[i])
        if not got or got[0] != want or not got[1]:
            return rows, -1, 'table_shape'
        report_at = i if want == 'TARIKH' else report_at
        rows[want], i = got[1], i + 1
        if want == _TABLE[0]:
            parts = [got[1]]
            while i < len(lines) and ':' not in lines[i] and abs(_indent(lines[i]) - got[2]) <= 2:
                parts.append(_one_space(lines[i]))
                i += 1
            raw = [lines[g][lines[g].index(':') + 1:]] + lines[g + 1:i]     # the value, not its label's gap
            if len(parts) > 1 + _MAX_WRAPS or any(_WIDE_GAP.search(ln) for ln in raw):
                return rows, -1, 'programme_shape'
            rows[want] = ' '.join(parts)
    if i >= len(lines) or not _one_space(lines[i]).startswith(_AFTER_TABLE) or _indent(lines[i]) > _LEFT:
        return rows, -1, 'table_shape'
    return rows, report_at, ''


def _utem_report_ymd(value: str):
    """A real date from "DD Month YYYY (Day) Masa : ..." whose Malay day name is that date's, else None."""
    m = _REPORT_VALUE.match(value or '')
    if not m:
        return None
    day = _ymd(f'{m.group(1)} {m.group(2)} {m.group(3)}')
    return day if day is not None and _DAYS[day.weekday()] == m.group(4).upper() else None


def _utem_values(rows) -> tuple:
    """(programme, printed reporting date "DD Month YYYY", reason) from the table's rows."""
    programme, faculty = rows.get('PROGRAMPENGAJIAN', ''), rows.get('FAKULTI', '')
    if not _DEGREE.match(programme) or um_not_degree(programme):
        return programme, '', 'programme_shape'
    if (not faculty.startswith('FAKULTI ') or any(w in _utem_key(faculty) for w in NOT_DEGREE)
            or _PRA.search(faculty)):
        return programme, '', 'not_degree'
    if rows.get('TAHUN') != 'Satu (1)' or rows.get('MODPENGAJIAN') != 'SEPENUH MASA':
        return programme, '', 'not_degree'
    if (not _FEE.match(rows.get('BAYARAN', '')) or not re.fullmatch(r'[A-Za-z ]{3,30}', rows.get(
            'KEMUDAHANKOLEJKEDIAMAN', '')) or not _MATRIC.match(rows.get('NOMATRIK', ''))
            or not _EMAIL.match(rows.get('EMELRASMIPELAJAR', ''))):
        return programme, '', 'table_shape'
    value = rows.get('TARIKH', '')
    if _utem_report_ymd(value) is None:
        return programme, '', 'reporting_shape'
    return programme, value.split(' (', 1)[0], ''


def _utem_dates_sane(years, offer_date: str, printed: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; the
    reporting date is a real date in the session's years, not before the offer date."""
    y1, y2 = years
    offered, reported = _ymd(offer_date), _ymd(printed)
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and offered <= reported


def read_utem(source: str):
    """``(fields, reason)`` for a UTeM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at, intake, y1, y2 = _utem_title_at(lines)
    if at < 0:
        return None, 'no_title'
    name, printed_ic, offer_date, why_head = _utem_head(lines, at)
    rows, report_at, why_table = _utem_table(lines, at)
    programme, printed, why_values = _utem_values(rows) if not why_table else ('', '', '')
    nric = _norm_nric(printed_ic) if printed_ic else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'other' if nric else 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if printed else '',
        'reporting_date_label': 'Tarikh' if printed else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != 5]
    if utem_ic_elsewhere('\n'.join(rest), '') or utem_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 1:
        return fields, 'not_degree'
    if any(_ANY_DATE.search(_one_space(ln)) for k, ln in enumerate(lines) if k not in (2, 4, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _utem_dates_sane((y1, y2), offer_date, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def utem_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`utem_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one` once the one genuine note `_UTEM_NOTE` is taken out, the head being the lines
    up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if utem_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(_UTEM_NOTE.sub(' ', one, count=1), hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def utem_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''. Measured: the degree letters' page
    2, when it draws text, is the conditions page ("SYARAT-SYARAT TAWARAN KEMASUKAN"), whose withdrawal, deferral
    and failure clauses the checks cannot tell from a real withdrawal: it refuses."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_utem` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'programme_code', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def _utem_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "DD Month YYYY") exactly as page 1 prints them, ('', '') when not read."""
    lines = _uum_lines(page1_layout)
    at, _intake, _y1, _y2 = _utem_title_at(lines)
    if at < 0:
        return '', ''
    _name, printed_ic, _offer, why = _utem_head(lines, at)
    rows, _r, why_table = _utem_table(lines, at)
    _p, printed, why_values = _utem_values(rows) if not why_table else ('', '', 'no_table')
    return (printed_ic if not why else ''), (printed if not why_values else '')


def utem_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UTeM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _utem_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
