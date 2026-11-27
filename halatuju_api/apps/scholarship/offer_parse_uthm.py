"""The UTHM rules lane (OCR-14 phase 3): a DIGITAL Universiti Tun Hussein Onn Malaysia degree offer letter read
from its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UTHM`` (`offer_exact.ocr_first_lanes`).

UTHM PRINTS NO IC (owner, 26 Nov: "Same as UUM"). The table prints the matric number ("No Matrik : XX999999") and
the e-mail built from it: neither is the IC, and neither is ever stored, matched or ink-checked. A UTHM lock stores
the IC blank (source 'none'; `offer_exact.ISSUER_PRINTS_NO_IC`). ANY 12-digit IC-like number on any page refuses
(``ic_printed``), and so does any value after "Rujukan Kami" or "Rujukan Tuan" (``reference_printed``; measured: two
owner samples print a 12-digit number there).

Page 1, as measured on the corpus letter and the owner's 17 text samples (masked shapes only):

* the first line is "Pejabat Pengurusan Akademik" (any case; an underscore rule may come first); then only the
  Tel, Faks, "Rujukan Kami" and "Rujukan Tuan" lines in the right-hand column; then "Tarikh : DD Month YYYY" there
  (the offer date); the name alone at the left on the next line (`offer_parse_uitm.name_ended` must prove it
  ended); the address; "Saudara/i,";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA (UTHM)", once, with "SESI AKADEMIK" after it
  and the session's 8 digits on the next line, or the session ("[SEMESTER n ]SESI 99999999") alone on the next
  line: the intake, as printed;
* the greeting, then the table, its rows in this order and nothing between them: "Program & Kod Program" (a
  "SARJANA MUDA ... DENGAN KEPUJIAN" degree, wrapped onto at most two lines under its value; a trailing 2-4 letter
  bracket code goes to ``programme_code``), Tempoh Program (Tahun), Peringkat Pengajian (must be "SARJANA MUDA"),
  Mod Pengajian, Fakulti, Kampus, No Matrik, Kolej Kediaman, Alamat E-mel, Yuran Kemasukan, Syarat Tawaran (must
  be "LAMPIRAN A").

The reporting date is read ONLY from the "Tarikh" row straight after the sentence "... diminta ... untuk mendaftar
pada tarikh, tempat dan masa seperti butiran berikut :", followed by the Tempat and Masa rows; its value must be
"DD MONTH YYYY (DAY)" with the right Malay day name. No sentence: the date is left blank. A sentence that does not
read so, or any other date on the page, refuses. The venue ("Tempat") is never read. Every measured letter is one
page: any later page with text refuses (``later_page``).
"""
import datetime
import re

from .offer_parse import _name_ok
from .offer_parse_uitm import NOT_DEGREE, name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uum import _LINKERS, _MONTH, _WORD_DATE, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UTHM'
INSTITUTION = 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA'
ISSUER = 'Pejabat Pengurusan Akademik, Universiti Tun Hussein Onn Malaysia'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_LETTERHEAD = 'PEJABAT PENGURUSAN AKADEMIK'
_RULE_LINE = re.compile(r'^_{5,}$')
_RIGHT = 40                                     # the head's right-hand column starts past this
_LEFT = 12                                      # a name, address or table label starts under this
_HEAD_ROWS = ('TEL', 'FAKS', 'RUJUKANKAMI', 'RUJUKANTUAN')
_TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA (UTHM)'
_INTAKE_A = re.compile(r'^(20\d{2})(20\d{2})$')                     # after "... (UTHM) SESI AKADEMIK"
_INTAKE_B = re.compile(r'^(?:SEMESTER (?:[IV]{1,3}|[1-3]|PERTAMA|KEDUA) )?SESI (20\d{2})(20\d{2})$')
_SESSION = re.compile(r'SESI (?:AKADEMIK )?(20\d{2})(20\d{2})$')
_GREETING = re.compile(r'^Tahniah diucapkan kepada saudara/i kerana ditawarkan tempat bagi mengikuti program di '
                       r'(?:UTHM|Universiti ini) seperti butiran berikut ?:$')
_SALUTATION = 'Saudara/i,'
#: The table's rows (labels with every non-word character squeezed out), in printed order.
_TABLE = ('PROGRAMKODPROGRAM', 'TEMPOHPROGRAMTAHUN', 'PERINGKATPENGAJIAN', 'MODPENGAJIAN', 'FAKULTI', 'KAMPUS',
          'NOMATRIK', 'KOLEJKEDIAMAN', 'ALAMATEMEL', 'YURANKEMASUKAN', 'SYARATTAWARAN')
_MAX_WRAPS = 2
_WIDE_GAP = re.compile(r'\S {13,}\S')            # a gap wider than a justified line's: another column
_DEGREE = re.compile(r'^(SARJANA MUDA \S.*? DENGAN KEPUJIAN)(?: \(([A-Z]{2,4})\))?$')
_MATRIC = re.compile(r'^[A-Z]{2}\d{6}$')
_REPORT_SENTENCE = re.compile(r'^\d{1,2}\. Saudara/i diminta (?:datang )?untuk mendaftar pada tarikh, tempat dan '
                              r'masa seperti butiran berikut ?:$')
_MONTHS = ('JANUARI', 'FEBRUARI', 'MAC', 'APRIL', 'MEI', 'JUN', 'JULAI', 'OGOS', 'SEPTEMBER', 'OKTOBER',
           'NOVEMBER', 'DISEMBER')
_DAYS = ('ISNIN', 'SELASA', 'RABU', 'KHAMIS', 'JUMAAT', 'SABTU', 'AHAD')    # Monday first (`date.weekday`)
_REPORT_VALUE = re.compile(r'^(\d{1,2}) ([A-Z]{3,9}) (20\d{2}) \(([A-Z]{4,6})\)$')
#: Any date the stray-date checks must see (every lane that imports it: UTHM, UKM, UMK, UTeM, USM, UniSZA, UMPSA).
#: OCR-14b-1 fix 1 widened it (only more refusals): "11hb Oktober 2026" / "11 haribulan Oktober", a day and month
#: with no year ("11 Oktober"), a month and year with no day ("Oktober 2026") and year-first numbers ("2026-10-11").
_ANY_DATE = re.compile(_WORD_DATE + r'|(?<!\d)\d{1,2}\s?[/.-]\s?\d{1,2}\s?[/.-]\s?(?:20)?\d{2}(?!\d)'
                       r'|(?<!\d)\d{1,2}\s{0,2}(?:hb\.?|haribulan)?\s{0,2}' + _MONTH + r'(?![a-z])'
                       r'|(?<![a-z])' + _MONTH + r'\.?,?\s{0,2}20\d{2}(?!\d)'
                       r'|(?<!\d)20\d{2}\s?[/.-]\s?\d{1,2}\s?[/.-]\s?\d{1,2}(?!\d)', re.IGNORECASE)
_NOT_DEGREE_WORD = re.compile(r'(?<![A-Z])(?:DIPLOMA|ASASI|PERSEDIAAN|FOUNDATION|SIJIL)(?![A-Z])')


def is_uthm(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UTHM admissions letter: the university and its academic
    office. Which of them is a degree offer `read_uthm` decides."""
    return 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA' in up and _LETTERHEAD in up


def _uthm_key(label: str) -> str:
    return _SQUEEZE_OUT.sub('', (label or '').upper())


def _uthm_row(line: str):
    """(key, value, value column) of a "Label : value" layout line, or None. The key is the label with every
    non-word character squeezed out; the value is one-spaced."""
    if ':' not in line:
        return None
    colon = line.index(':')
    rest = line[colon + 1:]
    return _uthm_key(line[:colon]), _one_space(rest), colon + 1 + _indent(rest)


def _uthm_title_at(lines) -> tuple:
    """(index of the title, index of the session line, intake): the title once, at the left, one column; (-1, -1,
    '') else."""
    hits = [i for i, ln in enumerate(lines) if 'TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN' in _one_space(ln).upper()]
    if len(hits) != 1 or hits[0] + 1 >= len(lines) or _indent(lines[hits[0]]) > _LEFT:
        return -1, -1, ''
    i = hits[0]
    title, nxt = _one_space(lines[i]), _one_space(lines[i + 1])
    if _indent(lines[i + 1]) > _LEFT or len(_cols(lines[i + 1])) != 1:
        return -1, -1, ''
    if title == _TITLE + ' SESI AKADEMIK' and _INTAKE_A.match(nxt):
        return i, i + 1, 'SESI AKADEMIK ' + nxt
    if title == _TITLE and _INTAKE_B.match(nxt):
        return i, i + 1, nxt
    return -1, -1, ''


def _uthm_head(lines, at):
    """(name, offer_date, index of the offer-date line, reason) from the lines before the title (see the module
    docstring). The Rujukan values must be blank."""
    first = 1 if lines and _RULE_LINE.match(lines[0].strip()) else 0
    if len(lines) <= first or _one_space(lines[first]).upper() != _LETTERHEAD or len(_cols(lines[first])) != 1:
        return '', '', -1, 'not_letterhead'
    j, seen = first + 1, []
    while j < at and _indent(lines[j]) >= _RIGHT and (_uthm_row(lines[j]) or ('',))[0] != 'TARIKH':
        got = _uthm_row(lines[j])
        kind = next((k for k in _HEAD_ROWS if got and got[0].startswith(k)), '')
        if not kind:
            return '', '', -1, 'no_head'
        if kind.startswith('RUJUKAN') and got[1]:
            return '', '', -1, 'reference_printed'
        seen.append(kind)
        j += 1
    if sorted(k for k in seen if k.startswith('RUJUKAN')) != ['RUJUKANKAMI', 'RUJUKANTUAN']:
        return '', '', -1, 'no_head'
    dated = _uthm_row(lines[j]) if j < at and _indent(lines[j]) >= _RIGHT else None
    if not dated or dated[0] != 'TARIKH' or not re.fullmatch(_WORD_DATE, dated[1]) or j + 2 >= at:
        return '', '', -1, 'no_head'
    offer_date, n = dated[1], j + 1
    name = _one_space(lines[n])
    if (_indent(lines[n]) > _LEFT or len(_cols(lines[n])) != 1 or not _name_ok(name) or name != name.upper()
            or _LINKERS.search(name)):
        return '', offer_date, j, 'name_shape'    # an unread or wrapped name ("... BINTI")
    if not name_ended(lines[n + 1]):
        return '', offer_date, j, 'name_not_ended'   # the rest of the name may be on the next line
    if (_one_space(lines[at - 1]) != _SALUTATION or _indent(lines[at - 1]) > _LEFT
            or not 1 <= at - 1 - (n + 1) <= 6 or any(_SALUTATION in ln for ln in lines[n + 1:at - 1])):
        return '', offer_date, j, 'no_head'
    return name, offer_date, j, ''


def _uthm_table(lines, start):
    """(programme, code, index of the last table line, reason): the greeting from ``start``, then the table's rows
    in `_TABLE` order with nothing between them but at most `_MAX_WRAPS` programme lines under its value."""
    g = next((k for k in range(start, min(start + 3, len(lines))) if _uthm_row(lines[k]) and _uthm_row(lines[k])[0] == _TABLE[0]),
             -1)
    if g < 0 or not _GREETING.match(_one_space(' '.join(lines[start:g]))):
        return '', '', -1, 'no_table'
    rows, i = {}, g
    for want in _TABLE:
        got = _uthm_row(lines[i]) if i < len(lines) and _indent(lines[i]) <= _LEFT else None
        if not got or got[0] != want or not got[1]:
            return '', '', -1, 'table_shape'
        rows[want], i = got, i + 1
        if want == _TABLE[0]:
            parts = [got[1]]
            while i < len(lines) and ':' not in lines[i] and abs(_indent(lines[i]) - got[2]) <= 2:
                parts.append(_one_space(lines[i]))
                i += 1
            raw = [lines[g][lines[g].index(':') + 1:]] + lines[g + 1:i]     # the value, not its label's gap
            if len(parts) > 1 + _MAX_WRAPS or any(_WIDE_GAP.search(ln) for ln in raw):
                return '', '', -1, 'programme_shape'
            rows[want] = (want, ' '.join(parts), got[2])
    m = _DEGREE.match(rows['PROGRAMKODPROGRAM'][1])
    if not m:
        return '', '', -1, 'programme_shape'
    programme, code = m.group(1), m.group(2) or ''
    faculty = rows['FAKULTI'][1]
    if (um_not_degree(programme) or rows['PERINGKATPENGAJIAN'][1] != 'SARJANA MUDA'
            or not faculty.startswith('FAKULTI ') or any(w in _uthm_key(faculty) for w in NOT_DEGREE)):
        return programme, code, i - 1, 'not_degree'
    if not _MATRIC.match(rows['NOMATRIK'][1]):
        return programme, code, i - 1, 'no_matrik'
    if rows['SYARATTAWARAN'][1] != 'LAMPIRAN A':
        return programme, code, i - 1, 'conditions_shape'
    return programme, code, i - 1, ''


def _uthm_report_ymd(value: str):
    """A real date from "DD MONTH YYYY (DAY)" whose Malay day name is that date's, else None."""
    m = _REPORT_VALUE.match(value or '')
    if not m or m.group(2) not in _MONTHS:
        return None
    try:
        day = datetime.date(int(m.group(3)), _MONTHS.index(m.group(2)) + 1, int(m.group(1)))
    except ValueError:                           # "31 SEPTEMBER 2027": not a real day
        return None
    return day if _DAYS[day.weekday()] == m.group(4) else None


def _uthm_reporting(lines, after):
    """(printed value, index of its line, reason) of the reporting date: the sentence on the line after the table
    (``after``), then the Tarikh, Tempat and Masa rows. ('', -1, '') when no sentence is printed anywhere."""
    sentence = [k for k, ln in enumerate(lines) if 'DIMINTA' in ln.upper() or 'MENDAFTAR' in ln.upper()]
    if not sentence:
        return '', -1, ''
    k = after + 1
    if sentence != [k] or not _REPORT_SENTENCE.match(_one_space(lines[k])) or k + 3 >= len(lines):
        return '', -1, 'reporting_shape'
    got = [_uthm_row(lines[k + d]) if _indent(lines[k + d]) <= _LEFT else None for d in (1, 2, 3)]
    if [g[0] if g else '' for g in got] != ['TARIKH', 'TEMPAT', 'MASA'] or _uthm_report_ymd(got[0][1]) is None:
        return '', -1, 'reporting_shape'
    return got[0][1], k + 1, ''


def _uthm_dates_sane(intake: str, offer_date: str, reported) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first; a
    reporting date (when read) falls in the session's years, not before the offer date."""
    m, offered = _SESSION.search(intake or ''), _ymd(offer_date)
    if not m or offered is None or int(m.group(2)) != int(m.group(1)) + 1:
        return False
    if not int(m.group(1)) - 1 <= offered.year <= int(m.group(1)):
        return False
    return reported is None or (int(m.group(1)) <= reported.year <= int(m.group(2)) and offered <= reported)


def read_uthm(source: str):
    """``(fields, reason)`` for a UTHM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock. The IC is always blank; the
    reporting date is blank unless printed under the registration sentence."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at, session_at, intake = _uthm_title_at(lines)
    if at < 0:
        return None, 'no_title'
    if ic_printed(source):
        return None, 'ic_printed'
    name, offer_date, dated_at, why_head = _uthm_head(lines, at)
    programme, code, last, why_table = _uthm_table(lines, session_at + 1)
    printed, report_at, why_report = _uthm_reporting(lines, last) if last >= 0 else ('', -1, '')
    from .offer_parse import house_date
    fields = {
        'candidate_name': name, 'candidate_nric': '', 'candidate_nric_source': 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed.rsplit(' (', 1)[0]) if printed else '',
        'reporting_date_label': 'Tarikh' if printed else '', 'reporting_venue': '',
        'offer_date': offer_date if _ymd(offer_date) else '', 'issuer': ISSUER,
    }
    for why in (why_head, why_table, why_report):
        if why:
            return fields, why
    if '{' in source or '}' in source:
        return fields, 'placeholder'          # an unfilled template field ("{tarikh_...}")
    if _NOT_DEGREE_WORD.search(_one_space(folded).upper()):
        return fields, 'not_degree'
    if any(_ANY_DATE.search(_one_space(ln)) for k, ln in enumerate(lines) if k not in (dated_at, report_at)):
        return fields, 'stray_date'           # a date the reader did not read: never guessed, never skipped
    empty = [k for k in ('candidate_name', 'programme', 'intake', 'offer_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _uthm_dates_sane(intake, offer_date, _uthm_report_ymd(printed) if printed else None):
        return fields, 'dates_not_sane'
    return fields, ''


def uthm_printed_date(page1_layout: str) -> str:
    """The reporting date exactly as page 1 prints it ("DD MONTH YYYY (DAY)"), '' when it is not read."""
    fields, reason = read_uthm(page1_layout)
    if fields is None or reason or not fields.get('reporting_date'):
        return ''
    lines = _uum_lines(page1_layout)
    _at, session_at, _intake = _uthm_title_at(lines)
    _p, _c, last, _why = _uthm_table(lines, session_at + 1)
    return _uthm_reporting(lines, last)[0]


def uthm_letter_refusal(text: str) -> str:
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


def uthm_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text (every measured UTHM letter is one page;
    any other page may hold a second programme, a date or an IC the reader never measured), else ''."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1. No IC: UTHM
#: prints none, and the matric is never a value. The reporting date is checked as printed, when read.
INK_LABELS = {'candidate_name': 'v:name', 'programme': 'v:programme', 'programme_code': 'v:code',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Read from the page but optional: ink-checked only when read (the code and the reporting date).
INK_OPTIONAL = ('programme_code', 'reporting_date')
#: The fields `read_uthm` returns that are not read off the page (constants, blanks and the reader's own label).
NOT_PRINTED = ('candidate_nric', 'candidate_nric_source', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def uthm_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UTHM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the reporting date as printed, or the stored value
    when it cannot be re-read, which then fails the check). A required value left blank stays in, so the ink check
    refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    values = {k: f.get(k) or '' for k in INK_LABELS}
    if values['reporting_date']:
        values['reporting_date'] = uthm_printed_date(page1_layout) or values['reporting_date']
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
