"""The UniMAP rules lane (OCR-14b-2): a DIGITAL Universiti Malaysia Perlis degree offer letter in its 2025/2026
layout, read from its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``). The reader refuses on any
doubt; every refusal sends the letter to the AI as before. The lane is OFF unless OCR_FIRST_LANES holds ``ua:UniMAP``
(`offer_exact.ocr_first_lanes`). The older layout (a one-line title, other sentences, the page at the left margin)
refuses, and so does a Diploma letter.

UniMAP PRINTS THE IC WITH NO LABEL: 12 plain digits alone on the line under the name. It is read from that one place
and stored with source ``other``: CORROBORATE-ONLY under the usual IC guard (`offer_exact.exact_read`; UniMAP is NOT
in `offer_exact.ISSUER_PRINTS_NO_IC`), kept only when it is exactly the profile IC, as on UniSZA. ANY other IC-like
number on any page refuses. The reference and the matric number are never stored.

Page 1, as measured on the owner's text sample in this layout (masked shapes only). The whole page sits at one base
indent (the title's; measured 42):

* the head, two rows further in (measured base + 38), their colons in one column: "Rujukan Kami : UniMAP/AMD/n/n/
  <programme code>/L/L/<MON><YYYY>(n)" and "Tarikh : D Month YYYY" (the offer date, the month in mixed case);
* at the base: the name (`offer_parse_uitm.name_ended` must prove it ended on the next address line), the IC alone,
  two to five address lines, "TEL : <digits>", "Saudara/i,";
* the title on two lines, its words printed with wide gaps: "TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA PERLIS (UniMAP)
  BAGI SIDANG AKADEMIK" then "YYYY/YYYY" alone (the intake is "SIDANG AKADEMIK YYYY/YYYY");
* the greeting "Sukacita saya bagi pihak Universiti Malaysia Perlis (UniMAP) ... seperti berikut:" on two lines;
* the table (base + 2 to 4, every colon in one column, every value starting in one column, a wrapped line starting
  exactly there): Program Pengajian ("SARJANA MUDA ...", justified, up to two wrapped lines), Kod Program (the
  reference's code), Fakulti, No. Matrik (never stored), Tempoh Pengajian, Yuran Dikenakan;
* "Di bawah adalah butiran berkaitan dengan proses pendaftaran diri :", then Tarikh Pendaftaran ("DD MONTH YYYY
  (DAY)", its day name checked against the date), Masa Pendaftaran and Lokasi Pendaftaran (never read; up to four
  wrapped lines);
* "Sebagai makluman, kos pengajian adalah seperti berikut:", the three-line cost header, the two cost rows and the
  "**" note; then notes 2 and 3 and "Sekian, terima kasih".

The reporting date is read ONLY from the Tarikh Pendaftaran row. Review round 2: there is NO free text. Every line
is read in order at its fixed place, either as fixed template text (exact text, or `TEMPLATE_PINS` for the venue and
the footer) or as a field value of a strict shape (the name letters only, the programme and the faculty upper-case
words with no digit, the IC, code, dates and numbers their measured shapes); the address lines are upper-case words
and numbers with no year. So a date or a code can only sit at its place; the second-code backstop
(`_unimap_second_code`) checks the rest again. Every page after page 1 with text refuses (``later_page``); a blank page refuses too, by the shared drawn
page check (``hidden_page``, `offer_ums_refusal.page_texts_refusal`), with ONE excuse (OCR-14b-3, owner decision B1,
27 Nov; `BLANK_PAGE2_EXCUSE`): page 2 may be blank when the letter's BYTES prove it fully blank
(`pdf_rules_pages.fully_blank_page2`: no text, no image, no drawing, no annotation), passed in as ``blank_page2``.
A blank page 1, a blank page 3, a page 2 the bytes did not prove blank, and every other lane refuse as before.

No other excuse: the portal tell, the withdrawal check and the owner words run on the letter as it is."""
import hashlib
import re

from .offer_parse import _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_umpsa import _name_words_ok
from .offer_parse_uthm import _DAYS, _NOT_DEGREE_WORD
from .offer_parse_uum import _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UniMAP'
INSTITUTION = 'UNIVERSITI MALAYSIA PERLIS'
ISSUER = 'Pusat Pengurusan Akademik, Universiti Malaysia Perlis'
#: OCR-14b-3: this lane alone excuses a FULLY blank page 2; `offer_exact.blank_page2_excused` reads the bytes only
#: for a lane module that sets it.
BLANK_PAGE2_EXCUSE = True

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_BASE_IN = range(36, 49)                        # the page's base indent (measured: 42)
_HEAD_IN = range(30, 46)                        # the head rows past the base (measured: 38)
_ROW_IN = range(2, 5)                           # the table rows past the base (measured: 3)
_COLON_AT = range(18, 31)                       # a row's colon past its indent (measured: 25)
_VALUE_GAP = range(2, 9)                        # a row's value past its colon (measured: 6)
_TITLE_WORDS = 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA PERLIS (UniMAP) BAGI SIDANG AKADEMIK'
_TITLE_LINE = re.compile(r'\S+(?: {3}\S+)*')     # the title's words, every gap as measured (3)
_SESSION = re.compile(r'^(20\d{2})/(20\d{2})$')
_REFERENCE = re.compile(r'^UniMAP/AMD/\d{1,4}/\d{1,2}/(UR\d{7})/[A-Z]{1,2}/[A-Z]{1,2}/[A-Z]{3,5}(20\d{2})'
                        r'\(\d{1,6}\)$')
_OFFER_DATE = re.compile(r'^\d{1,2} [A-Z][a-z]{2,8} 20\d{2}$')
_IC_LINE = re.compile(r'^\d{12}$')              # the 12 digits alone, no separator
_PHONE = re.compile(r'^TEL : \d{9,11}$')
_SALUTATION = 'Saudara/i,'
_GREETING = ('Sukacita saya bagi pihak Universiti Malaysia Perlis (UniMAP) mengucapkan tahniah dan memaklumkan '
             'bahawa saudara/i ditawarkan tempat untuk mengikuti program pengajian seperti berikut:')
#: (label, most wrapped lines) in order; the registration intro sits between the two groups.
_TABLE = (('Program Pengajian', 2), ('Kod Program', 0), ('Fakulti', 0), ('No. Matrik', 0),
          ('Tempoh Pengajian', 0), ('Yuran Dikenakan', 0))
_REGISTER_INTRO = 'Di bawah adalah butiran berkaitan dengan proses pendaftaran diri :'
_REGISTER = (('Tarikh Pendaftaran', 0), ('Masa Pendaftaran', 0), ('Lokasi Pendaftaran', 4))
REPORT_LABEL = 'Tarikh Pendaftaran'
#: Review round 1: a value line's gaps, as measured. A justified line (the programme's first, a Lokasi line) spreads
#: its gaps evenly (measured 5-6 and 2), never past `_GAP_MAX`; a paragraph's LAST line (and a one-line value) is
#: never stretched (measured: single spaces). Anything else may be a second column: refuse.
_GAP_MAX = 6
_GAP = re.compile(r'(?<=\S) +(?=\S)')
_PROGRAMME = re.compile(r"^SARJANA MUDA [A-Z(][A-Z&,'.()\-]*(?: [A-Z&(][A-Z&,'.()\-]*)*$")
_FACULTY = re.compile(r"^FAKULTI [A-Z][A-Z&,'.()\-]*(?: [A-Z&][A-Z&,'.()\-]*)*$")
_CODE = re.compile(r'^UR\d{7}$')
#: Review round 2: the fixed text the reader reads no field from is PINNED, as measured on the owner's sample: the
#: footer (every line after "Sekian, terima kasih": slogans, signer, post) and the registration venue (the Lokasi
#: value with its wrapped lines; the one variable in it is the session, which must be the title's). Each is kept as
#: the sha256 of its lines one-spaced and joined by a newline (`_pin_digest`; the venue's session written
#: "{session}"), never as text: the footer names a real person. Any extra, missing or changed character refuses
#: (``template_changed``). One measured sample, so one digest each; a letter with another venue or footer goes to
#: the AI.
TEMPLATE_PINS = {
    'footer': frozenset({'0ed6d9f269183fe42ade1e6e5443e52d0298a09e9785aee6da7867c8046ea938'}),
    'venue': frozenset({'f35855067c2b16633896cec72c0bc243f3a053f5e80acfce8587ae9c109bfcc5'}),
}
#: The name: upper-case words, a hyphen, an apostrophe or a dot inside, the link words A/L, A/P and "@" alone.
_NAME = re.compile(r"^[A-Z][A-Z'.\-]*(?: (?:[A-Z][A-Z'.\-]*|A/L|A/P|@))*$")
#: An address line (one-spaced): upper-case words and numbers and , . / - ' ( ) & only. It is never read, so a unit
#: number such as "NO 12-3" or "BLOK 2/3" is fine; a year (a full date), a colon, a lower-case letter or a link word
#: naming another person (`_LINK`) refuses (``address_shape``).
_ADDRESS = re.compile(r"^[A-Z0-9][A-Z0-9 ,./'()&\-]*$")
_YEAR = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
_LINK = re.compile(r'(?<![A-Z])(?:A ?/ ?L|A ?/ ?P|D ?/ ?A|U ?/ ?P|BIN|BINTI|BT|BTE|ANAK)(?![A-Z])|@')
#: Review round 2 backstop (`_unimap_second_code`): two letters and seven digits once every character but a letter or
#: a digit is taken out and the letter O is read as 0.
_CODE_RUN = re.compile(r'[^\W\d_]{2}\d{7}')
_POSTCODE = re.compile(r'\d{5} +[A-Z]')
_MATRIC = re.compile(r'^\d{9}$')                # as measured; never stored
_NUMBERS = ('SATU', 'DUA', 'TIGA', 'EMPAT', 'LIMA', 'ENAM', 'TUJUH')
_TERM = re.compile(r'^([A-Z]{3,5}) \(([1-7])\) TAHUN \((\d{1,2}) SEMESTER\)$')
_FEES = re.compile(r'^RM (?:\d{1,3}(?:,\d{3})+|\d{1,6})\.\d{2}(?:\.\d{2})? \(SEMESTER 1\)$')   # measured: ".00.00"
_HOUR = r'\d{1,2}\.\d{2} (?:PAGI|PETANG|TENGAH HARI)'
_TIME = re.compile(r'^' + _HOUR + ' HINGGA ' + _HOUR + r'$')
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) \(([A-Z]{4,6})\)$')
_COST_INTRO = 'Sebagai makluman, kos pengajian adalah seperti berikut:'
_COST_HEAD = ('Kos Yang Ditanggung Kos Yang', 'Tempoh Pengajian Oleh Pelajar (RM) Ditanggung Kos Keseluruhan (RM)',
              'Oleh Kerajaan')
_AMOUNT = r'RM (?:\d{1,3}(?:,\d{3})+|\d{1,6})\.\d{2}'
_COST_ROW = re.compile(r'^(\* )?([A-Z][a-z]{2,4}) \(([1-7])\) Tahun ' + ' '.join([_AMOUNT] * 3) + r'$')
_COST_NOTE = '** jumlah kos pengajian yang sebenar bergantung kepada tempoh pengajian yang diikuti pelajar.'
_NOTES = ('2. Sila rujuk Lampiran A, B, C, D dan E serta lengkapkan butiran berkaitan.',
          '3. Tawaran ini adalah muktamad dan sebarang pertukaran program adalah tidak dibenarkan.',
          'Sekian, terima kasih')


def is_unimap(up: str) -> bool:
    """``up`` (upper-cased) reads as a UniMAP admissions letter: the university and its offer title (degree or not;
    which of them is a degree offer in the measured layout `read_unimap` decides)."""
    up = _one_space(up)
    return 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA PERLIS' in up


def unimap_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number (`offer_parse_uum.ic_printed`) once ONE copy of the read IC is
    taken out: the read IC printed twice counts too. No IC read (``nric`` blank): any IC-like number counts."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _unimap_at(lines, base, extra=0) -> bool:
    """Every line exactly at ``base`` + ``extra``."""
    return all(_indent(ln) == base + extra for ln in lines)


def _unimap_row(line: str, colon: int, start: int):
    """(label, value as printed) of a table line whose colon is at column ``colon`` and value starts at column
    ``start``, the label one column; else None. The value's spacing is `_unimap_spaced`'s."""
    if len(line) <= start or line[colon] != ':' or line[colon + 1:start].strip() or line[start] == ' ':
        return None
    label, value = line[:colon], line[start:]
    if not label.strip() or len(_cols(label)) != 1 or ':' in label:
        return None
    return _one_space(label), value.strip()


def _unimap_wrapped(line: str, start: int) -> bool:
    """A value's wrapped line: starting exactly at column ``start`` (its spacing is `_unimap_spaced`'s)."""
    return _indent(line) == start


def _unimap_spaced(parts) -> bool:
    """A value's lines as printed, set as measured (`_GAP_MAX`): plain spaces only, no colon, each line's gaps even
    (widest minus narrowest at most 1) and at most `_GAP_MAX`, the last line single-spaced."""
    for part in parts:
        gaps = [len(g) for g in _GAP.findall(part)]
        if re.search(r'[^\S ]', part) or ':' in part or (gaps and (max(gaps) - min(gaps) > 1 or max(gaps) > _GAP_MAX)):
            return False
    return all(len(g) == 1 for g in _GAP.findall(parts[-1]))


def _unimap_title_at(lines) -> tuple:
    """(index, base indent, intake, first year, second year): the two-line title once, at one indent; (-1, ...)
    else."""
    none = -1, 0, '', 0, 0
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')]
    if len(hits) != 1 or hits[0] + 2 > len(lines):
        return none
    at = hits[0]
    base = _indent(lines[at])
    first, second = lines[at].strip(), lines[at + 1].strip()
    m = _SESSION.match(second)
    if (base not in _BASE_IN or not _unimap_at(lines[at:at + 2], base) or not _TITLE_LINE.fullmatch(first)
            or _one_space(first) != _TITLE_WORDS or not m):
        return none
    return at, base, 'SIDANG AKADEMIK ' + second, int(m.group(1)), int(m.group(2))


def _unimap_head(lines, at, base):
    """(name, printed IC, offer date as printed, reference code, reference year, reason) from the lines before the
    title."""
    none = ('', '', '', '', 0)
    if at < 8 or _indent(lines[0]) - base not in _HEAD_IN or _indent(lines[1]) != _indent(lines[0]):
        return (*none, 'no_head')
    ref, dated = (ln.strip().split(':', 1) if ln.count(':') == 1 else ('', '') for ln in lines[:2])
    m = _REFERENCE.match(ref[1].strip())
    if (_one_space(ref[0]) != 'Rujukan Kami' or _one_space(dated[0]) != 'Tarikh' or not m
            or lines[0].index(':') != lines[1].index(':') or not _OFFER_DATE.match(dated[1].strip())
            or _ymd(dated[1].strip()) is None):
        return (*none, 'no_head')
    offer_date, code, ref_year = dated[1].strip(), m.group(1), int(m.group(2))
    body = lines[2:at]
    if (not _unimap_at(body, base) or not 2 <= len(body) - 4 <= 5 or not _PHONE.match(_one_space(body[-2]))
            or _one_space(body[-1]) != _SALUTATION):
        return ('', '', offer_date, code, ref_year, 'no_head')
    name, printed_ic = _one_space(body[0]), body[1].strip()
    if not _IC_LINE.match(printed_ic) or len(_cols(body[0])) != 1:
        return ('', '', offer_date, code, ref_year, 'name_shape')
    if not _name_words_ok(name) or not _NAME.match(name):
        return ('', printed_ic, offer_date, code, ref_year, 'name_shape')
    if not name_ended(body[2][base:]):
        return ('', printed_ic, offer_date, code, ref_year, 'name_not_ended')   # the address must open as one
    return name, printed_ic, offer_date, code, ref_year, ''


def _unimap_rows(lines, i, want, colon, start, rows, parts_of):
    """Read the rows ``want`` ((label, most wrapped lines) in order) from line ``i`` into ``rows``, each value's lines
    as printed into ``parts_of``: (next line, {label: line index}), (-1, {}) on any doubt (`_unimap_spaced`)."""
    where = {}
    for label, most in want:
        got = _unimap_row(lines[i], colon, start) if i < len(lines) else None
        if not got or got[0] != label:
            return -1, {}
        where[label], parts, i = i, [got[1]], i + 1
        while i < len(lines) and len(parts) <= most and _unimap_wrapped(lines[i], start):
            parts.append(lines[i].strip())
            i += 1
        if not _unimap_spaced(parts):
            return -1, {}
        rows[label], parts_of[label] = _one_space(' '.join(parts)), parts
    return i, where


def _unimap_table(lines, at, base):
    """({label: value}, places, reason): the greeting, `_TABLE` in order, the registration intro, `_REGISTER` in
    order, then the cost block and the closing notes, every step as measured. ``places``: the fixed places the
    reader read ('at' the title, 'venue' the Lokasi value's lines as printed and 'venue_at' their indexes, 'cut' the
    lines read whole by a strict shape that may print digits, 'end' the first line after the notes); {} on a
    refusal."""
    rows, parts_of = {}, {}
    g = at + 4
    if g >= len(lines) or not _unimap_at(lines[at + 2:g], base) or _one_space(' '.join(lines[at + 2:g])) != _GREETING:
        return rows, {}, 'no_table'
    row_in = _indent(lines[g])
    colon = lines[g].find(':')
    start = colon + 1 + len(lines[g][colon + 1:]) - len(lines[g][colon + 1:].lstrip()) if colon > 0 else -1
    if row_in - base not in _ROW_IN or colon - row_in not in _COLON_AT or start - colon not in _VALUE_GAP:
        return rows, {}, 'table_shape'
    i, where = _unimap_rows(lines, g, _TABLE, colon, start, rows, parts_of)
    if i < 0 or i >= len(lines) or _one_space(lines[i]) != _REGISTER_INTRO or not _unimap_at(lines[i:i + 1], base):
        return rows, {}, 'table_shape'
    i, more = _unimap_rows(lines, i + 1, _REGISTER, colon, start, rows, parts_of)
    where.update(more)
    if i < 0:
        return rows, {}, 'reporting_shape'
    block = lines[i:i + 10]
    tidy = [_one_space(ln) for ln in block]
    costs = [_COST_ROW.match(t) for t in tidy[4:6]] if len(tidy) == 10 else []
    if (len(tidy) != 10 or tidy[0] != _COST_INTRO or not _unimap_at(block[:1], base) or tuple(tidy[1:4]) != _COST_HEAD
            or any(_indent(ln) <= row_in for ln in block[1:6]) or not all(costs) or not _unimap_at(block[6:7], row_in)
            or tidy[6] != _COST_NOTE or tuple(tidy[7:10]) != _NOTES or not _unimap_at(block[7:10], base)):
        return rows, {}, 'table_shape'
    one, two = costs
    years = two.group(2).upper()
    if (one.group(1) or one.group(2) != 'Satu' or one.group(3) != '1' or not two.group(1)
            or years not in _NUMBERS or _NUMBERS.index(years) + 1 != int(two.group(3))):
        return rows, {}, 'table_shape'      # "Satu (1) Tahun", then "* <Word> (n) Tahun", its word its number
    venue_at = where['Lokasi Pendaftaran']
    cut = {0, 1, 3, at - 2, at + 1, i + 4, i + 5} | {where[k] for k in ('Kod Program', 'No. Matrik', 'Tempoh Pengajian',
                                                                     'Yuran Dikenakan', REPORT_LABEL, 'Masa Pendaftaran')}
    venue = parts_of['Lokasi Pendaftaran']
    return rows, {'at': at, 'venue': venue, 'venue_at': range(venue_at, venue_at + len(venue)), 'cut': cut,
                  'end': i + 10}, ''


def _pin_digest(lines, session: str = '') -> str:
    """`TEMPLATE_PINS`' digest of ``lines``: the sha256 of each line one-spaced, joined by a newline, ``session`` (when
    given) written "{session}"."""
    text = '\n'.join(_one_space(ln) for ln in lines)
    return hashlib.sha256((text.replace(session, '{session}') if session else text).encode('utf-8')).hexdigest()


def _unimap_second_code(lines, places, session: str) -> bool:
    """Review round 2 backstop: True when ANY text but the fixed places prints a code-like run (`_CODE_RUN`), read as
    printed and with look-alike letters folded, every character but a letter or a digit taken out (across lines too)
    and O read as 0. The fixed places are the lines read whole by a strict shape (``cut``: the reference, the offer
    date, the IC, the phone, the session, the Kod Program and other number rows, the cost rows) and the session in
    the pinned venue; each is a break, so nothing joins across it. An address line that opens with a postcode (five
    digits, then a word) is a break before it too, so a unit number ("ARAS 1-2") never joins the postcode."""
    pieces, venue, address = [''], set(places['venue_at']), range(4, places['at'] - 2)
    for k, ln in enumerate(lines):
        if k in places['cut'] or (k in address and _POSTCODE.match(ln.strip())):
            pieces.append('')
        if k in places['cut']:
            continue
        for j, bit in enumerate(ln.split(session) if k in venue else [ln]):
            if j:
                pieces.append('')
            pieces[-1] += bit + '\n'
    for piece in pieces:
        for one in (piece, fold_lookalikes(piece)):
            if _CODE_RUN.search(re.sub(r'[\W_]', '', one).upper().replace('O', '0')):
                return True
    return False


def _unimap_template(lines, places, name: str, session: str) -> str:
    """Review round 2: every line the reader read no field from must be the measured template. The footer and the
    venue must match `TEMPLATE_PINS` exactly ('template_changed'); each address line must be `_ADDRESS`'s shape,
    with no year and no link word (`_LINK`), plain spaces only, any width (measured up to 12) ('address_shape'); the
    read name nowhere but its own line ('second_name'); else ''."""
    if (_pin_digest(lines[places['end']:]) not in TEMPLATE_PINS['footer']
            or _pin_digest(places['venue'], session) not in TEMPLATE_PINS['venue']):
        return 'template_changed'
    for ln in lines[4:places['at'] - 2]:
        tidy = [_one_space(one) for one in (ln, fold_lookalikes(ln))]
        if re.search(r'[^\S ]', ln) or any(not _ADDRESS.match(t) or _YEAR.search(t) or _LINK.search(t) for t in tidy):
            return 'address_shape'
    said = re.compile(r'(?<![A-Z])' + re.escape(_one_space(name).upper()) + r'(?![A-Z])')
    if name and any(said.search(_one_space(t).upper()) for k, ln in enumerate(lines) if k != 2
                    for t in (ln, fold_lookalikes(ln))):
        return 'second_name'
    return ''


def _unimap_values(rows, code) -> tuple:
    """(programme, printed reporting date, house reporting date, reason) from the table's rows; ``code`` the
    reference's programme code."""
    programme, faculty = rows.get('Program Pengajian', ''), rows.get('Fakulti', '')
    if um_not_degree(programme) or not _PROGRAMME.match(programme) or not _FACULTY.match(faculty):
        return '', '', '', 'programme_shape'
    if any(w in _SQUEEZE_OUT.sub('', programme + ' ' + faculty) for w in NOT_DEGREE) or \
            _PRA.search(programme + ' ' + faculty):
        return programme, '', '', 'not_degree'
    term = _TERM.match(rows.get('Tempoh Pengajian', ''))
    if (not _CODE.match(rows.get('Kod Program', '')) or rows['Kod Program'] != code
            or not _MATRIC.match(rows.get('No. Matrik', '')) or not term or term.group(1) not in _NUMBERS
            or _NUMBERS.index(term.group(1)) + 1 != int(term.group(2))
            or not 1 <= int(term.group(3)) <= 3 * int(term.group(2)) or not _FEES.match(rows.get('Yuran Dikenakan', ''))
            or not _TIME.match(rows.get('Masa Pendaftaran', '')) or not rows.get('Lokasi Pendaftaran')):
        return programme, '', '', 'table_shape'
    m = _REPORT_VALUE.match(rows.get(REPORT_LABEL, ''))
    day = _ymd(f'{m.group(1)} {m.group(2).title()} {m.group(3)}') if m else None
    if day is None or _DAYS[day.weekday()] != m.group(4):
        return programme, '', '', 'reporting_shape'
    printed = f'{m.group(1)} {m.group(2)} {m.group(3)}'
    return programme, printed, house_date(f'{m.group(1)} {m.group(2).title()} {m.group(3)}'), ''


def _unimap_dates_sane(years, offer_date: str, printed: str, ref_year: int) -> bool:
    """The session's years run on; the offer date in the year before the session or its first, in the reference's
    year, not after the reporting date; the reporting date in the session's years."""
    y1, y2 = years
    offered, reported = _ymd(offer_date), _ymd(printed.title())
    if y2 != y1 + 1 or offered is None or reported is None:
        return False
    return y1 - 1 <= offered.year <= y1 and offered.year == ref_year and y1 <= reported.year <= y2 \
        and offered <= reported


def _unimap_read(lines):
    """Every reader step on page 1's layout lines: (years, intake, head, (places, reason), values); None before the
    title holds."""
    at, base, intake, y1, y2 = _unimap_title_at(lines)
    if at < 0:
        return None
    head = _unimap_head(lines, at, base)
    rows, places, why_table = _unimap_table(lines, at, base)
    values = _unimap_values(rows, head[3]) if not why_table and not head[5] else ('', '', '', '')
    return (y1, y2), intake, head, (places, why_table), values


def read_unimap(source: str):
    """``(fields, reason)`` for a UniMAP letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    got = _unimap_read(lines)
    if got is None:
        return None, 'no_title'
    years, intake, (name, printed_ic, offer_date, code, ref_year, why_head), (places, why_table), values = got
    programme, printed, reported, why_values = values
    nric = _norm_nric(printed_ic) if printed_ic else ''
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'other' if nric else 'none',
        'programme': programme, 'programme_code': code if programme else '', 'institution': INSTITUTION,
        'campus': '', 'stream': '', 'intake': intake, 'reporting_date': reported,
        'reporting_date_label': REPORT_LABEL if reported else '', 'reporting_venue': '',
        'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_values):
        if why:
            return fields, why
    rest = [ln for k, ln in enumerate(lines) if k != 3]
    if unimap_ic_elsewhere('\n'.join(rest), '') or unimap_ic_elsewhere(source, nric):
        return fields, 'second_ic'
    session = intake.split()[-1]
    if _unimap_second_code(lines, places, session):
        return fields, 'second_code'          # the reference's and the Kod Program row's, nowhere else
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field
    flat = _one_space(folded).upper()
    if _NOT_DEGREE_WORD.search(flat) or flat.count('SARJANA MUDA') != 1:
        return fields, 'not_degree'           # the programme row only
    why_free = _unimap_template(lines, places, name, session)   # no free text: a date can only be at its place
    if why_free:
        return fields, why_free
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _unimap_dates_sane(years, offer_date, printed, ref_year):
        return fields, 'dates_not_sane'
    return fields, ''


def unimap_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic' (`unimap_ic_elsewhere`), 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one` on the letter as it is, no excuse; the head being the lines up to the
    title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if unimap_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN KEMASUKAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def unimap_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


def diagnose_unimap(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None,
                    blank_page2: bool = False) -> dict:
    """The UniMAP branch of `offer_parse.diagnose` (via `offer_parse_lanes`), in `diagnose_umpsa`'s order: a portal
    page refuses (`offer_parse._PORTAL_TELL`, no excuse); a scan refuses (``no_layout``); the drawn page texts
    (``hidden_page``); `read_unimap`; the owner phrases; the whole letter (`unimap_letter_refusal`);
    ``foreign_letters``; ``name_not_plain``; the read IC not printed exactly once in page 1's plain layer
    (``ic_not_plain``); any other IC-like number in page 1's plain layer or any page text (``ic_printed``); last,
    any later page with text. ``blank_page2`` (the bytes proved page 2 fully blank, `BLANK_PAGE2_EXCUSE`) excuses
    that one page from the drawn page check, and only when its text is ''; nothing else changes."""
    from .offer_parse import _PORTAL_TELL, _SPACES, _ZERO_WIDTH, PARSER_VERSION
    from .offer_owner_words import missing
    from .offer_parse_university import name_in_plain
    from .offer_ums_refusal import foreign_letters, page_texts_refusal
    out['portal'] = bool(_PORTAL_TELL.search(text or ''))
    if out['portal']:
        return out
    if not page1_layout.strip():
        out['guard'] = 'no_layout'
        return out
    if not page1_text.strip():
        out['guard'] = 'no_plain_layer'
        return out
    pages = [_SPACES.sub(' ', _ZERO_WIDTH.sub('', t or '')) for t in (page_texts or ())]
    fields, reason = read_unimap(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    excused = blank_page2 is True and len(pages) >= 2 and pages[1] == ''          # OCR-14b-3: the one excuse
    early = page_texts_refusal([pages[0], 'blank page 2 (excused)'] + pages[2:] if excused else pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or unimap_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and _own_ic(page1_text, nric)[1] != 1:
        reason = 'ic_not_plain'
    if not reason and (unimap_ic_elsewhere(page1_text, nric) or any(unimap_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = unimap_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'unimap', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'programme_code': 'v:code', 'intake': 'v:intake', 'reporting_date': 'v:date',
              'offer_date': 'v:offer_date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_unimap` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'institution', 'campus', 'issuer', 'stream', 'reporting_date_label',
               'reporting_venue')


def _unimap_printed(page1_layout: str) -> tuple:
    """(printed IC, printed reporting date "DD MONTH YYYY") exactly as page 1 prints them, ('', '') when not read."""
    got = _unimap_read(_uum_lines(page1_layout))
    if got is None:
        return '', ''
    _years, _intake, head, (_places, why_table), values = got
    return (head[1] if not head[5] else ''), (values[1] if not why_table and not values[3] else '')


def unimap_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UniMAP lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed_ic, printed = _unimap_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic, 'reporting_date': printed}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
