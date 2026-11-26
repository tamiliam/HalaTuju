"""The UKM rules lane (OCR-14 phase 4): a DIGITAL Universiti Kebangsaan Malaysia degree offer letter read from its
page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UKM`` (`offer_exact.ocr_first_lanes`).

UKM PRINTS THE IC (measured: every text offer prints "NO. KAD PENGENALAN : <12 digits>"), so the IC guard applies as
on UM and UiTM (`offer_exact.exact_read`; UKM is NOT in `offer_exact.ISSUER_PRINTS_NO_IC`): a UKM letter with no IC
never locks. The IC is read from that one row only, as the 12 plain digits every measured letter prints (a
hyphen, an en dash, a minus, a slash, any space or a line split there refuses). ANY other IC-like number on any page refuses
(`ukm_ic_elsewhere`: `offer_parse_uum.ic_printed`'s wide shapes once the read IC itself and the footer's phone
numbers are taken out). The registration number ("NO. PENDAFTARAN : A999999") and the reference are never stored.

Page 1, as measured on the corpus letter and the owner's 14 text offers (masked shapes only):

* "Rujukan : UKM.AKA.NNN-N/N/N" then "Tarikh : DD/MM/YYYY" (the offer date), both in the right-hand column; the
  name alone at the left on the next line (`offer_parse_uitm.name_ended` must prove it ended); the address;
  "Saudara/i,";
* the title "TAWARAN KEMASUKAN SESI AKADEMIK YYYY/YYYY", once (the intake, as printed after "TAWARAN KEMASUKAN");
* the greeting "Dengan sukacitanya ... menawarkan tempat pengajian ijazah pertama bagi Sesi Akademik YYYY/YYYY.
  Butir-butir tawaran adalah seperti berikut:" (the title's session);
* the table, its rows in this order and nothing between them: NO. KAD PENGENALAN, NO. PENDAFTARAN, FAKULTI,
  PUSAT PENGAJIAN (not always printed), PROGRAM PENGAJIAN (a "SARJANA MUDA ... DENGAN KEPUJIAN" degree on one
  line), TEMPOH PENGAJIAN, TAHUN PENGAJIAN (must be "SATU"), TEMPAT LAPOR DIRI (never read), TARIKH LAPOR DIRI,
  YURAN PENDAFTARAN, JENIS AMBILAN (must be "AKADEMIK"); then the fee paragraph.

The reporting date is read ONLY from the TARIKH LAPOR DIRI row: "DD/MM/YYYY" with at most a "( HH:MM Pagi -
HH:MM Tengah Hari )" window after it. Any other value refuses, and so does any date on the page but the offer date,
that row and the footer's one "Tarikh Cetak" print stamp. Every measured letter is one page: any later page with
text refuses (``later_page``). Confirmation letters print no offer title (``no_title``).
"""
import datetime
import re

from .offer_parse import _name_ok, _norm_nric, house_date
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uthm import _ANY_DATE, _NOT_DEGREE_WORD
from .offer_parse_uum import _LINKERS, _cols, _indent, _one_space, _uum_lines, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UKM'
INSTITUTION = 'UNIVERSITI KEBANGSAAN MALAYSIA'
ISSUER = 'Pusat Pengurusan Akademik, Universiti Kebangsaan Malaysia'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_OFFICE = 'PUSAT PENGURUSAN AKADEMIK'
_RIGHT = 60                                     # the head's right-hand column starts past this
_LEFT = 12                                      # a name, address or table label starts under this
_REFERENCE = re.compile(r'^Rujukan : UKM\.AKA\.\d{3}-\d{1,2}/\d{1,2}/\d{1,2}$')
_OFFER_DATE = re.compile(r'^Tarikh : (\d{2}/\d{2}/20\d{2})$')
_SALUTATION = 'Saudara/i,'
_TITLE = re.compile(r'^TAWARAN KEMASUKAN (SESI AKADEMIK (20\d{2})/(20\d{2}))$')
_GREETING = re.compile(r'^Dengan sukacitanya saya bagi pihak Universiti Kebangsaan Malaysia mengucapkan tahniah '
                       r'kepada saudara/i dan seterusnya menawarkan tempat pengajian ijazah pertama bagi Sesi '
                       r'Akademik (20\d{2})/(20\d{2})\. Butir-butir tawaran adalah seperti berikut:$')
#: The table's rows in printed order; PUSAT PENGAJIAN is not printed on every letter.
_ROWS = ('NO. KAD PENGENALAN', 'NO. PENDAFTARAN', 'FAKULTI', 'PUSAT PENGAJIAN', 'PROGRAM PENGAJIAN',
         'TEMPOH PENGAJIAN', 'TAHUN PENGAJIAN', 'TEMPAT LAPOR DIRI', 'TARIKH LAPOR DIRI', 'YURAN PENDAFTARAN',
         'JENIS AMBILAN')
_OPTIONAL_ROWS = ('PUSAT PENGAJIAN',)
_AFTER_TABLE = 'Maklumat Yuran Pengajian adalah seperti berikut:'
_IC_VALUE = re.compile(r'^\d{12}$')                # as measured: no separator, no space
_REGISTRATION = re.compile(r'^[A-Z]\d{5,7}$')
_WORDS = r"[A-Z][A-Z&,'.()\-]*(?: [A-Z&][A-Z&,'.()\-]*)*"
_FACULTY = re.compile(r'^' + _WORDS + r'$')
_SCHOOL = re.compile(r'^PUSAT PENGAJIAN ' + _WORDS + r'$')
_DEGREE = re.compile(r"^SARJANA MUDA \S.*? DENGAN KEPUJIAN(?: \([A-Z][A-Z &,'/.\-]*\))?$")
_DURATION = re.compile(r'^\d(?:\.\d)? TAHUN$')
_FEE = re.compile(r'^RM ?\d{1,3}(?:,\d{3})*\.\d{2}$')
_HOUR = r'\d{1,2}[:.]\d{2} (?:Pagi|Tengah Hari|Petang)'
_REPORT_VALUE = re.compile(r'^(\d{2}/\d{2}/20\d{2})(?: \( ?' + _HOUR + r' - ' + _HOUR + r' ?\))?$')
_PRINT_STAMP = re.compile(r'(?:^|\s)Tarikh Cetak : \d{2}/\d{2}/20\d{2}$')
#: The footer's phone numbers: the university switchboard ("Tel: +603-8911NNNN") and its 4-digit extensions, which
#: `ic_printed`'s wide shapes read as an IC ("NNNNNNNN/NNNN" is 6 + 2 + 4). Pinned to the measured run (OCR-14 review
#: r1: every owner and corpus footer is +603-8911 with 1-12 extensions 81NN-84NN), so a phone-shaped IC run is not
#: excused. Taken out before the IC-elsewhere check; printed more than once on a page, it refuses (`ukm_ic_elsewhere`).
_TEL = re.compile(r'Tel: \+603-8911\d{4}(?:/8[1-4]\d{2}){1,12}(?![\d/])')
#: The one portal sentence every UKM letter prints ("... dicetak di Portal Semakan Kemasukan ke UKM ..."), which
#: `offer_parse._PORTAL_TELL` reads as a portal page. Taken out before the plain portal check (`ukm_portal`).
_PORTAL_WORDS = ('sila rujuk Panduan Pendaftaran Pelajar Baharu yang boleh dicetak di Portal Semakan Kemasukan ke '
                 'UKM dipautan http://appsmu.ukm.my/edaftar/.')
_PORTAL_SENTENCE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _PORTAL_WORDS.split()), re.IGNORECASE)


def is_ukm(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UKM admissions letter: the university and its academic
    management centre. Which of them is a degree offer `read_ukm` decides."""
    return 'UNIVERSITI KEBANGSAAN MALAYSIA' in up and _OFFICE in up


def ukm_portal(text: str) -> bool:
    """True when ``text`` (the whole letter) carries a portal tell (`offer_parse._PORTAL_TELL`) once the one
    portal sentence (`_PORTAL_SENTENCE`) is taken out; a letter that prints it more than once counts as a portal
    page."""
    from .offer_parse import _PORTAL_TELL
    rest, n = _PORTAL_SENTENCE.subn(' ', text or '')
    return n > 1 or bool(_PORTAL_TELL.search(rest))


def _own_ic(text: str, nric: str) -> tuple:
    """(``text`` with every standalone copy of the read IC taken out, how many there were). A copy is its 12 digits
    plain or with one hyphen or one space between the parts, with no digit, dash look-alike or slash on either
    side."""
    digits = (nric or '').replace('-', '')
    if len(digits) != 12 or not digits.isdigit():
        return text or '', 0
    own = digits[:6] + '[- ]?' + digits[6:8] + '[- ]?' + digits[8:]
    return re.subn(r'(?<![\d\-‐-―−/])' + own + r'(?![\d\-‐-―−/])', ' ', text or '')


def ukm_ic_copies(text: str, nric: str) -> int:
    """How many times ``text`` prints the read IC (`_own_ic`); page 1's plain layer must print it exactly once."""
    return _own_ic(text, nric)[1]


def ukm_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`: every dash look-alike, a slash,
    a whitespace run, a line break, a digit run of 12+) once ONE copy of the read IC (`_own_ic`) and the footer's
    phone numbers (`_TEL`, at most once) are taken out: the read IC printed twice counts too (page 1's row is its
    one home). No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    rest, tels = _TEL.subn(' ', rest)
    return copies > 1 or tels > 1 or ic_printed(rest)


def _dmy(printed: str):
    """A real calendar date from "DD/MM/YYYY", else None."""
    m = re.fullmatch(r'(\d{2})/(\d{2})/(20\d{2})', printed or '')
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:                           # "31/09/2027": not a real day
        return None


def _ukm_title_at(lines) -> tuple:
    """(index, intake, first year, second year) of the title: once, at the left margin, one column; (-1, '', 0, 0)
    else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')]
    if len(hits) != 1 or _indent(lines[hits[0]]) > _LEFT or len(_cols(lines[hits[0]])) != 1:
        return -1, '', 0, 0
    m = _TITLE.match(_one_space(lines[hits[0]]))
    return (hits[0], m.group(1), int(m.group(2)), int(m.group(3))) if m else (-1, '', 0, 0)


def _ukm_head(lines, at):
    """(name, offer_date, index of the offer-date line, reason) from the lines before the title (see the module
    docstring)."""
    if at < 5:
        return '', '', -1, 'no_head'
    if (_indent(lines[0]) < _RIGHT or len(_cols(lines[0])) != 1 or not _REFERENCE.match(_one_space(lines[0]))
            or _indent(lines[1]) < _RIGHT or len(_cols(lines[1])) != 1):
        return '', '', -1, 'no_head'
    dated = _OFFER_DATE.match(_one_space(lines[1]))
    if not dated or _dmy(dated.group(1)) is None:
        return '', '', -1, 'no_head'
    offer_date, ln = dated.group(1), lines[2]
    name = _one_space(ln)
    if (_indent(ln) > _LEFT or len(_cols(ln)) != 1 or not _name_ok(name) or name != name.upper()
            or _LINKERS.search(name)):
        return '', offer_date, 1, 'name_shape'    # an unread or wrapped name ("... BINTI")
    if not name_ended(lines[3]):
        return '', offer_date, 1, 'name_not_ended'   # the rest of the name may be on the next line
    if (_one_space(lines[at - 1]) != _SALUTATION or _indent(lines[at - 1]) > _LEFT
            or not 1 <= at - 1 - 3 <= 6 or any(_SALUTATION in x for x in lines[3:at - 1])):
        return name, offer_date, 1, 'no_head'
    return name, offer_date, 1, ''


def _ukm_row(line: str):
    """(label, raw value) of a "LABEL : value" table line at the left margin, or None. The value is stripped, not
    one-spaced (the IC is matched raw)."""
    if ':' not in line or _indent(line) > _LEFT:
        return None
    colon = line.index(':')
    return _one_space(line[:colon]), line[colon + 1:].strip()


def _ukm_table(lines, at, years):
    """(rows, index of the IC row, index of the reporting row, reason): the greeting after the title (its session
    must be the title's), then `_ROWS` in order with nothing between them, then the fee paragraph."""
    g = next((k for k in range(at + 2, min(at + 5, len(lines))) if _ukm_row(lines[k])
              and _ukm_row(lines[k])[0] == _ROWS[0]), -1)
    m = _GREETING.match(_one_space(' '.join(lines[at + 1:g]))) if g > 0 else None
    if not m or (int(m.group(1)), int(m.group(2))) != years:
        return {}, -1, -1, 'no_table'
    rows, i, found = {}, g, {}
    for want in _ROWS:
        got = _ukm_row(lines[i]) if i < len(lines) else None
        if want in _OPTIONAL_ROWS and (not got or got[0] != want):
            continue
        if not got or got[0] != want or not got[1]:
            return rows, -1, -1, 'table_shape'
        rows[want], found[want], i = got[1], i, i + 1
    if i >= len(lines) or not _one_space(lines[i]).startswith(_AFTER_TABLE) or _indent(lines[i]) > _LEFT:
        return rows, -1, -1, 'table_shape'
    return rows, found[_ROWS[0]], found['TARIKH LAPOR DIRI'], ''


def _ukm_values(rows) -> tuple:
    """(nric, printed IC, programme, printed reporting date, reason) from the table's rows."""
    printed_ic = rows.get('NO. KAD PENGENALAN', '')
    nric = _norm_nric(printed_ic) if _IC_VALUE.match(printed_ic) else ''
    programme = _one_space(rows.get('PROGRAM PENGAJIAN', ''))
    report = _REPORT_VALUE.match(_one_space(rows.get('TARIKH LAPOR DIRI', '')))
    printed = report.group(1) if report else ''
    one = {k: _one_space(v) for k, v in rows.items()}
    faculty, school = one.get('FAKULTI', ''), one.get('PUSAT PENGAJIAN')
    if not nric:
        return '', printed_ic, programme, printed, 'ic_shape'
    if not _REGISTRATION.match(one.get('NO. PENDAFTARAN', '')):
        return nric, printed_ic, programme, printed, 'registration_shape'
    if (not _DEGREE.match(programme) or um_not_degree(programme) or not _FACULTY.match(faculty)
            or (school is not None and not _SCHOOL.match(school))):
        return nric, printed_ic, programme, printed, 'programme_shape'
    if any(w in _SQUEEZE_OUT.sub('', (faculty + ' ' + (school or '')).upper()) for w in NOT_DEGREE) or \
            _PRA.search(faculty + ' ' + (school or '')):
        return nric, printed_ic, programme, printed, 'not_degree'
    if (not _DURATION.match(one.get('TEMPOH PENGAJIAN', '')) or one.get('TAHUN PENGAJIAN') != 'SATU'
            or not _FEE.match(one.get('YURAN PENDAFTARAN', '')) or one.get('JENIS AMBILAN') != 'AKADEMIK'):
        return nric, printed_ic, programme, printed, 'table_shape'
    if not printed or _dmy(printed) is None:
        return nric, printed_ic, programme, '', 'reporting_shape'
    return nric, printed_ic, programme, printed, ''


def _ukm_stray_date(lines, keep) -> bool:
    """True when a line not in ``keep`` (the reference, offer-date and reporting lines) prints a date; the footer's
    one "Tarikh Cetak" print stamp is taken out first."""
    stamps = [k for k, ln in enumerate(lines) if _PRINT_STAMP.search(_one_space(ln))]
    if len(stamps) > 1:
        return True
    for k, ln in enumerate(lines):
        flat = _one_space(ln)
        if k in stamps:
            flat = _PRINT_STAMP.sub('', flat)
        if k not in keep and _ANY_DATE.search(flat):
            return True
    return False


def _ukm_dates_sane(years, offer_date: str, printed: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; the
    reporting date is a real date in the session's years, not before the offer date."""
    y1, y2 = years
    offered, reported = _dmy(offer_date), _dmy(printed)
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and y1 <= reported.year <= y2 and offered <= reported


def read_ukm(source: str):
    """``(fields, reason)`` for a UKM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at, intake, y1, y2 = _ukm_title_at(lines)
    if at < 0:
        return None, 'no_title'
    name, offer_date, dated_at, why_head = _ukm_head(lines, at)
    rows, ic_at, report_at, why_table = _ukm_table(lines, at, (y1, y2))
    nric, _printed_ic, programme, printed, why_values = _ukm_values(rows) if not why_table else ('', '', '', '', '')
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if printed else '',
        'reporting_date_label': 'TARIKH LAPOR DIRI' if printed else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != ic_at] + [lines[ic_at][:lines[ic_at].index(':')]]
    if ukm_ic_elsewhere('\n'.join(rest), '') or ukm_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 1 or flat.count('KAD PENGENALAN') != 1:
        return fields, 'not_degree'
    if _ukm_stray_date(lines, (0, dated_at, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _ukm_dates_sane((y1, y2), offer_date, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def _ukm_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date) exactly as page 1 prints them, ('', '') when the table is not read."""
    lines = _uum_lines(page1_layout)
    at, _intake, y1, y2 = _ukm_title_at(lines)
    rows, _i, _r, why = _ukm_table(lines, at, (y1, y2)) if at >= 0 else ({}, -1, -1, 'no_title')
    if why:
        return '', ''
    _n, printed_ic, _p, printed, _why = _ukm_values(rows)
    return printed_ic, printed


def ukm_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`ukm_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one`, the head being the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if ukm_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def ukm_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text (every measured UKM letter is one page),
    else ''."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_ukm` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'programme_code', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def ukm_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UKM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _ukm_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
