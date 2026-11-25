"""The UiTM rules lane (OCR-13 phase 2): a DIGITAL UiTM degree offer letter read from its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse`). The reader
refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless OCR_FIRST_LANES
holds ``ua:UiTM`` (`offer_exact.ocr_first_lanes`).

Page 1, as measured on the corpus and the owner's samples (masked shapes only):

* the title "SURAT TAWARAN" stands alone on its line, after at most a "www.uitm.edu.my" line;
* the line straight after it holds three columns: the name, "No. Kad Pengenalan" and the IC. Anything else there
  (a wrapped name, an older template with the label lower down) refuses;
* "Program", then the programme code alone in its column; the next one or two indented lines hold the programme
  name, and "Mod Pengajian" follows. A degree code has '2' as its THIRD character, and the name must read
  "(IJAZAH )SARJANA MUDA ..." with no non-degree word in it (`NOT_DEGREE`, look-alike letters folded first);
* "Sesi Kemasukan" holds "SESI N YYYY/YYYY"; "Tarikh" holds the reporting date (DD/MM/YYYY), within a few lines
  after "Sila hadir mendaftar". No offer date is printed. The faculty is printed but no field stores it.

The right-hand column of notes shares lines with the left-hand fields, so only the FIRST column of a line is read.
Later pages repeat the office footer and notes words; they refuse only on a second IC that differs, any programme
code, a date that is not the browser's print stamp and differs from the reporting date, or a page that is not a
UiTM page at all (`later_pages_refusal`).
"""
import re

from .offer_parse import _IC, _IC_END, _name_ok, _norm_nric, house_date
from .offer_ums_refusal import (_DATE_SEP, _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said)

LANE = 'ua:UiTM'
INSTITUTION = 'Universiti Teknologi MARA'
ISSUER = INSTITUTION

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_COLUMNS = re.compile(r'\s{3,}')
_TITLE = 'SURAT TAWARAN'
_WEB = re.compile(r'^(?:https?://)?www\.uitm\.edu\.my/?$', re.IGNORECASE)
_IC_LABEL = re.compile(r'^No\.\s?Kad\s{1,2}Pengenalan$')
_IC_VALUE = re.compile(r'^' + _IC + _IC_END + r'$')
_IC_ANY = re.compile(r'(?<!\d)' + _IC + _IC_END)
_CODE = re.compile(r'^[A-Z]{2}\d{3}$')
_CODE_ANY = re.compile(r'(?<![A-Z0-9])[A-Z]{2}\s{0,2}\d{3}(?![0-9])')
_DEGREE = re.compile(r"^(?:IJAZAH )?SARJANA MUDA(?: [A-Z][A-Z&,'/.\-]*)+(?: \(KEPUJIAN\)| KEPUJIAN)?"
                     r"(?: [A-Z][A-Z&,'/.\-]*)*$")
#: Non-degree words: anywhere in the programme (spaces, dots and dashes squeezed out; look-alikes folded) the
#: programme is not a degree and goes to the AI. PRA only as a word (a degree may say "PRASARANA").
NOT_DEGREE = ('DIPLOMA', 'ASASI', 'SIJIL', 'FOUNDATION', 'CERTIFICATE', 'PERSEDIAAN', 'MATRIK')
_PRA = re.compile(r'(?<![A-Z])PRA(?![A-Z])|PRAUNIVERSITI|PRADIPLOMA|PRASISWAZAH')
_SESI = re.compile(r'^SESI ([0-9]{1,2}|[IV]{1,3}) (20\d{2})/(20\d{2})$')
_DATE_VALUE = re.compile(r'^(\d{1,2})/(\d{1,2})/(20\d{2})$')
_ANY_DATE = re.compile(r'(?<!\d)(\d{1,2})\s{0,2}' + _DATE_SEP + r'\s{0,2}(\d{1,2})\s{0,2}' + _DATE_SEP
                       + r'\s{0,2}(\d{2,4})(?!\d)(,?\s{0,3}\d{1,2}[:.]\d{2})?')
_DIGIT_RUN = re.compile(r'\d{12,}')
#: The one conditional cancellation every genuine UiTM letter prints in its notes. Taken out before the
#: withdrawal check (whose "TIDAK SAH" and unconditioned "TERBATAL" would refuse every genuine letter); any
#: other cancellation wording still refuses.
_NOTE_CANCEL = re.compile(r'Tawaran\s{1,40}ini\s{1,40}adalah\s{1,40}terbatal\s{1,40}sekiranya\s{1,40}terdapat\s{1,40}'
                          r'maklumat\s{1,40}yang\s{1,40}salah,\s{1,40}tidak\s{1,40}benar\s{1,40}atau\s{1,40}'
                          r'dipinda\s{1,40}secara\s{1,40}tidak\s{1,40}sah')
#: A later page must be one of UiTM's own (its office footer or web address); any other page goes to the AI.
_UITM_PAGE = re.compile(r'Bahagian\s{1,3}Pengambilan\s{1,3}Pelajar|uitm\.edu\.my', re.IGNORECASE)


def is_uitm(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UiTM offer: the title and the admissions office's name."""
    return ('SURAT TAWARAN' in up and 'BAHAGIAN PENGAMBILAN PELAJAR' in up
            and ('UNIVERSITI TEKNOLOGI MARA' in up or bool(re.search(r'\bUITM\b', up))))


def _lines(text: str) -> list:
    """The non-blank lines, right-stripped, leading spaces kept (an indented line is a wrapped value)."""
    return [ln.rstrip() for ln in (text or '').splitlines() if ln.strip()]


def _cols(line: str) -> list:
    """A layout line's columns (3+ spaces apart)."""
    return _COLUMNS.split(line.strip())


def _left(line: str) -> str:
    """The first column of a line, '' when the line starts in the right-hand notes (60+ spaces in)."""
    return '' if len(line) - len(line.lstrip()) >= 60 else _cols(line)[0]


def _labelled(lines, label: str) -> list:
    """The indices of lines whose first column is exactly ``label`` (the label starts the line)."""
    return [i for i, ln in enumerate(lines) if len(ln) - len(ln.lstrip()) < 20 and _cols(ln)[0] == label]


def _title_at(lines) -> int:
    """The title line's index: "SURAT TAWARAN" alone, once, with only the web address above it; else -1."""
    hits = [i for i, ln in enumerate(lines) if ln.strip() == _TITLE]
    if len(hits) != 1 or hits[0] > 2 or not all(_WEB.match(ln.strip()) for ln in lines[:hits[0]]):
        return -1
    return hits[0]


def _head(lines, at):
    """(name, nric, reason) from the line straight after the title: name | No. Kad Pengenalan | IC."""
    if at + 1 >= len(lines):
        return '', '', 'no_head'
    cols = _cols(lines[at + 1])
    if len(cols) != 3 or not _IC_LABEL.match(cols[1]):
        return '', '', 'wrapped_name'
    name, ic = ' '.join(cols[0].split()), cols[2]
    if not _IC_VALUE.match(ic):
        return name, '', 'empty:candidate_nric'
    if not _name_ok(name) or re.search(r'\b(?:BIN|BINTI|BT|BTE|A\s?/\s?[LP]|ANAK|AK)$', name):
        return name, _norm_nric(ic), 'name_shape'          # an unread or wrapped name ("... BINTI")
    return name, _norm_nric(ic), ''


def not_degree(programme: str) -> bool:
    """True when the programme is not a plain degree: a non-degree word (`NOT_DEGREE`, `_PRA`), raw or
    look-alike folded, spaced or dotted, or a name that is not "(IJAZAH )SARJANA MUDA ..." in plain capitals."""
    folded = fold_lookalikes(programme or '').upper()
    key = _SQUEEZE_OUT.sub('', folded)
    return (any(w in key for w in NOT_DEGREE) or bool(_PRA.search(folded)) or bool(_PRA.search(key[:3]))
            or not _DEGREE.match(programme or ''))


def _programme(lines, at):
    """(code, programme, reason): the one "Program | CODE" line after the head, its 1-2 indented value lines,
    then "Mod Pengajian"."""
    hits = [i for i in _labelled(lines, 'Program') if i > at + 1]
    if len(hits) != 1 or len(_labelled(lines, 'Program')) != 1:
        return '', '', 'no_programme' if not hits else 'programme_twice'
    i = hits[0]
    cols = _cols(lines[i])
    if len(cols) < 2 or not _CODE.match(cols[1]):
        return '', '', 'no_code'
    code, parts, j = cols[1], [], i + 1
    while j < len(lines) and j <= i + 4:
        ln = lines[j]
        if _left(ln) == 'Mod Pengajian' or _cols(ln)[0] == 'Mod Pengajian':
            break
        if _left(ln):
            if len(ln) - len(ln.lstrip()) < 10:
                return code, '', 'programme_shape'          # an unindented line: not the value
            parts.append(_left(ln))
        j += 1
    if j >= len(lines) or _cols(lines[j])[0] != 'Mod Pengajian' or not 1 <= len(parts) <= 2:
        return code, '', 'programme_shape'
    programme = ' '.join(' '.join(parts).split())
    if code[2] != '2' or not_degree(programme):
        return code, programme, 'not_degree'
    return code, programme, ''


def _one_value(lines, label, after=-1):
    """The second column of the ONE line labelled ``label`` (after line ``after``); '' when none or two."""
    hits = _labelled(lines, label)
    if len(hits) != 1 or hits[0] <= after:
        return '', hits
    cols = _cols(lines[hits[0]])
    return (cols[1] if len(cols) >= 2 else ''), hits


def _reporting(lines, at):
    """The reporting date as printed ("DD/MM/YYYY"): the one "Tarikh" line, 1-4 lines after the one
    "Sila hadir mendaftar" line."""
    sila = [i for i, ln in enumerate(lines) if _left(ln).startswith('Sila hadir mendaftar')]
    value, hits = _one_value(lines, 'Tarikh', at)
    if len(sila) != 1 or len(hits) != 1 or not 1 <= hits[0] - sila[0] <= 4:
        return ''
    return value if _DATE_VALUE.match(value) else ''


def printed_date(page1_layout: str) -> str:
    """The reporting date exactly as page 1 prints it ("DD/MM/YYYY"), '' when it cannot be read."""
    lines = _lines(page1_layout)
    at = _title_at(lines)
    return _reporting(lines, at) if at >= 0 else ''


def _valid_dmy(printed: str) -> bool:
    import datetime
    m = _DATE_VALUE.match(printed or '')
    try:
        return bool(m) and bool(datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
    except ValueError:                           # "31/02/2027": not a real day
        return False


def _sane(intake: str, printed: str) -> bool:
    """The reporting date is a real date inside the session's two years, and the years run on."""
    m, d = _SESI.match(intake or ''), _DATE_VALUE.match(printed or '')
    if not m or not d or not _valid_dmy(printed) or int(m.group(3)) != int(m.group(2)) + 1:
        return False
    return int(m.group(2)) <= int(d.group(3)) <= int(m.group(3))


def withdrawn(text: str, head) -> bool:
    """`offer_ums_refusal._withdrawn` for a UiTM text with its one genuine conditional cancellation note taken
    out (`_NOTE_CANCEL`): raw or look-alike folded, either refusing refuses."""
    folded = fold_lookalikes(text or '')
    return any(_withdrawn_one(_NOTE_CANCEL.sub(' ', one), hd)
               for one, hd in ((text or '', head), (folded, [fold_lookalikes(h) for h in head])))


def read_uitm(source: str):
    """``(fields, reason)`` for a UiTM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    if status_said(source) or status_said(fold_lookalikes(source)):
        return None, 'status_letter'
    lines = _lines(source)
    at = _title_at(lines)
    if at < 0:
        return None, 'no_title'
    # No withdrawal check here: the layout interleaves the notes column with the fields, so the genuine
    # conditional note (`_NOTE_CANCEL`) is broken up. `letter_refusal` checks the whole letter's PLAIN text
    # (every page, page 1 included), where the note runs whole (measured: all 14 sample letters).
    name, nric, why_head = _head(lines, at)
    code, programme, why_prog = _programme(lines, at)
    intake, _h = _one_value(lines, 'Sesi Kemasukan', at)
    intake = intake if _SESI.match(intake) else ''
    printed = _reporting(lines, at)
    campus, _h = _one_value(lines, 'Kampus', at)
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': campus,
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if _valid_dmy(printed) else '',
        'reporting_date_label': 'Tarikh', 'reporting_venue': '', 'offer_date': '', 'issuer': ISSUER,
    }
    if why_head and not why_head.startswith('empty:'):
        return fields, why_head
    if why_prog:
        return fields, why_prog
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _sane(intake, printed):
        return fields, 'dates_not_sane'
    return fields, ''


def letter_refusal(text: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'not_an_offer' (`withdrawn`, the head being
    the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if ' '.join(ln.split()).upper() == _TITLE), -1)
    return 'not_an_offer' if withdrawn(text, lines[:at + 1] if at >= 0 else []) else ''


def _dmy_key(d: str, m: str, y: str) -> tuple:
    y = int(y)
    return int(d), int(m), (2000 + y if y < 100 else y)


def later_pages_refusal(pages, nric: str, printed_date: str) -> str:
    """Why a later page (page 2 on) refuses the lock: 'unknown_page' (no UiTM footer or web address on it),
    'second_ic' (a 12-digit IC, or a longer digit run, that is not the letter's IC), 'second_programme' (any
    programme code), 'second_date' (a numeric date that is not the print stamp's and not the reporting date);
    '' when none. Each page is checked raw and look-alike folded. Common words never refuse."""
    want = _norm_nric(nric)
    report = _DATE_VALUE.match(printed_date or '')
    report_key = _dmy_key(*report.groups()) if report else None
    for page in pages or ():
        for one in (page or '', fold_lookalikes(page or '')):
            if not _UITM_PAGE.search(one):
                return 'unknown_page'
            if any(_norm_nric(m.group(1)) != want for m in _IC_ANY.finditer(one)):
                return 'second_ic'
            if any(r != want.replace('-', '') for r in _DIGIT_RUN.findall(one)):
                return 'second_ic'
            if _CODE_ANY.search(one.upper()):
                return 'second_programme'
            for m in _ANY_DATE.finditer(one):
                if m.group(4):                       # "DD/MM/YYYY, H:MM": the browser's print stamp
                    continue
                if report_key is None or _dmy_key(m.group(1), m.group(2), m.group(3)) != report_key:
                    return 'second_date'
    return ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1.
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'programme_code': 'v:code', 'campus': 'v:campus', 'intake': 'v:intake', 'reporting_date': 'v:date'}
#: Read from the page but optional: ink-checked only when read.
INK_OPTIONAL = ('campus',)
#: The fields `read_uitm` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'institution', 'issuer', 'stream', 'reporting_date_label',
               'reporting_venue', 'offer_date')


def ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UiTM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the reporting date as printed, the IC as
    printed). A required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import OWNER_WORDS, _shown
    shown = _shown(LANE, page1_layout or '')
    phrases = [(f'p{k + 1}', p) for k, p in enumerate(OWNER_WORDS[LANE]) if k in shown]
    f = fields if isinstance(fields, dict) else {}
    lines = _lines(page1_layout)
    at = _title_at(lines)
    head = _cols(lines[at + 1]) if 0 <= at < len(lines) - 1 else []
    printed = {**{k: f.get(k) or '' for k in INK_LABELS},
               'reporting_date': printed_date(page1_layout),
               'candidate_nric': head[2] if len(head) == 3 else ''}
    values = [(label, printed[k]) for k, label in INK_LABELS.items()
              if k not in INK_OPTIONAL or str(printed[k]).strip()]
    return phrases, values
