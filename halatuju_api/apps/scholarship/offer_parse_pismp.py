"""The PISMP rules lane (OCR-19): a DIGITAL Institut Pendidikan Guru Malaysia (IPGM) offer letter for the teacher
training degree (Program Ijazah Sarjana Muda Perguruan, PISMP), read from its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan or a photo gives no layout, so it refuses (``no_layout``). The reader refuses
on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless OCR_FIRST_LANES holds
``ua:PISMP`` (`offer_exact.ocr_first_lanes`).

The owner's words (`offer_owner_words.OWNER_WORDS['ua:PISMP']`, 27 Nov) and the owner's anchors are the whole rule:

* the name after NAMA, the IC (labelled, source ``label``, under the usual IC guard) after NO. KAD PENGENALAN on the
  very next line;
* the programme: the title "TAWARAN RASMI MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN" gives the degree title
  (the AI's convention, `offer_reader`: "IJAZAH SARJANA MUDA PERGURUAN", no "PROGRAM" wrapper), and the BIDANG
  PENGKHUSUSAN row gives the specialism (``bidang_pengkhususan``);
* the campus after TEMPAT PENGAJIAN ("INSTITUT PENDIDIKAN GURU KAMPUS <name>": the institution is "INSTITUT
  PENDIDIKAN GURU", the campus "KAMPUS <name>"), its address lines after it at the value column (never read);
* the intake "AMBILAN YYYY" from the title's "(PISMP) AMBILAN YYYY" (the answers' convention, measured 27 Nov),
  checked against the AMBILAN/KELUARAN session ("YYYY/YYYY", its first year); the reporting date after TARIKH
  PENDAFTARAN.

Measured on the owner's IPG samples (shapes and counts only, 27 Nov): the 2026 layout prints every owner phrase;
an older layout ("TAWARAN MENGIKUTI ...", no AMBILAN/KELUARAN row, other rows) misses phrases 6 and 9 and refuses
(``owner_words_missing``). The table between the title and the reporting date is pinned as measured
(`_ROWS`: every row label in that order, one colon column, the value column shared); anything else refuses
(``template_changed``). Each anchor is printed ONCE as a row (two NAMA rows, two IC rows, two of any table row:
``second_row``); the anchors in the owner's order (``wrong_order``); the closing words after the reporting date.
The template's numbered conditions list (it holds the closing words and shared withdrawal words as conditions) is
pinned by digest and excused once, in its place only (`CONDITIONS_PINS`, `_conditions_out`; owner fork 1, 27 Nov).
"""
import re

from .offer_parse import _norm_nric, house_date
from .offer_parse_ukm import _own_ic
from .offer_parse_umpsa import _name_words_ok
from .offer_parse_unimap import _pin_digest
from .offer_parse_uum import _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _dotless, _squeeze, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:PISMP'
INSTITUTION = 'INSTITUT PENDIDIKAN GURU'
ISSUER = 'Institut Pendidikan Guru Malaysia, Kementerian Pendidikan'   # the answers' convention
PROGRAMME = 'IJAZAH SARJANA MUDA PERGURUAN'
REPORT_LABEL = 'TARIKH PENDAFTARAN'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE = 'TAWARAN RASMI MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN'
_CLOSING = 'TAWARAN INI AKAN TERBATAL DENGAN SENDIRINYA'
#: A labelled row: the label, spaces, a colon, the value (the colon may touch the value: measured).
_ROW = re.compile(r'^(\S(?:.*?\S)?) *:(?: *)(.*)$')
#: The table rows from BIDANG PENGKHUSUSAN to TARIKH PENDAFTARAN, as measured; MOD PENGAJIAN and TEMPOH PENGAJIAN
#: are never read. Only TEMPAT PENGAJIAN has wrapped lines (the campus address, at most `_ADDRESS_LINES`).
_ROWS = ('BIDANG PENGKHUSUSAN', 'MOD PENGAJIAN', 'TEMPOH PENGAJIAN', 'AMBILAN/KELUARAN', 'TEMPAT PENGAJIAN',
         'TARIKH PENDAFTARAN')
_ADDRESS_LINES = 4
_HEAD_LABELS = ('RUJ. KAMI', 'NAMA', 'NO. KAD PENGENALAN')
_NAME = re.compile(r"^[A-Z][A-Z'.\-]*(?: (?:[A-Z][A-Z'.\-]*|A/L|A/P|@))*$")
_IC = re.compile(r'^(\d{6})-?(\d{2})-?(\d{4})$')
_BIDANG = re.compile(r"^[A-Z][A-Z&,'()\-]*(?: [A-Z&(][A-Z&,'()\-]*){0,9}$")
_SESSION = re.compile(r'^(20\d{2})/(20\d{2})$')
_CAMPUS = re.compile(r"^INSTITUT PENDIDIKAN GURU (KAMPUS [A-Z][A-Z'.\-]*(?: [A-Z][A-Z'.\-]*){0,5})$")
_ADDRESS = re.compile(r"^[A-Z0-9][A-Z0-9 ,./'()&\-]*$")
_POSTCODE = re.compile(r'(?<!\d)\d{5}(?!\d)')
_YEAR = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
_REPORT_VALUE = re.compile(r'^(\d{1,2}) (JANUARI|FEBRUARI|MAC|APRIL|MEI|JUN|JULAI|OGOS|SEPTEMBER|OKTOBER|NOVEMBER|'
                           r'DISEMBER) (20\d{2})$')
_TITLE_YEAR = re.compile(r'\(PISMP\) AMBILAN (20\d{2})(?!\d)')
#: The one template clause that prints PENGESAHAN (a condition of the offer, measured on every 2026 text letter,
#: 27 Nov), in the squeezed form (letters and digits only): taken out ONCE before the bare PENGESAHAN check; a
#: second copy, or PENGESAHAN anywhere else, still refuses (``status_letter``).
_PENGESAHAN_CLAUSE = 'WALAUPUNPENGESAHANTERSEBUTDITERIMASELEPASMELAPORDIRI'
#: Owner fork 1 (27 Nov, chose A): the 2026 template's numbered conditions list prints shared withdrawal words as
#: conditions of the offer (the closing "akan TERBATAL dengan sendirinya sekiranya" with its GAGAL items, and a
#: right to "menarik balik"). Measured on every 2026 text letter (3 of 3, one digest): it is the run of non-empty
#: lines straight after the TARIKH PENDAFTARAN line, up to the sign-off, and holds the closing words. It is PINNED as
#: (line count, `_pin_digest` of those lines), never as text, and taken out ONCE before the shared withdrawal check
#: (`_conditions_out`). One changed character, a line added inside it or taken out, a second copy, the block
#: anywhere else (any line between it and the TARIKH PENDAFTARAN line), or a withdrawal word anywhere outside it
#: refuses. The old layout has another list (another digest): it refuses.
CONDITIONS_PINS = frozenset({(26, 'a1c0b3a1b95914baf8219de0c216df92e9f004324e514a6770acd1fde2bf1b06')})
_CLOSING_KEY = 'TAWARANINIAKANTERBATALDENGANSENDIRINYA'
#: This lane only (owner fork 1): a replacement letter ("digantikan", "menggantikan", "pengganti") outside the block
#: refuses too; the shared list has no such word and stays as it is. Measured 27 Nov: no word of any IPG sample
#: holds GANTI (in any of the shared spacing forms, `_squeeze` / `_dotless`).
_REPLACED = re.compile(r'GANTI', re.IGNORECASE)


def is_pismp(up: str) -> bool:
    """``up`` (upper-cased) reads as an IPG teacher-training offer: the institute and the PISMP degree title (either
    layout; which layout may lock `read_pismp` and the owner words decide)."""
    up = _one_space(up)
    return 'INSTITUT PENDIDIKAN GURU' in up and 'IJAZAH SARJANA MUDA PERGURUAN' in up


def pismp_ic_elsewhere(text: str, nric: str) -> bool:
    """True when ``text`` prints an IC-like number once ONE copy of the read IC is taken out (`ic_printed`)."""
    rest, copies = _own_ic(text, nric)
    return copies > 1 or ic_printed(rest)


def _pismp_row(line: str):
    """(label, value, colon column) of a labelled row, upper-cased label one-spaced; None when not a row."""
    m = _ROW.match(line.strip())
    if not m:
        return None
    return _one_space(m.group(1)).upper(), _one_space(m.group(2)), line.index(':')


def _pismp_find(lines) -> tuple:
    """({anchor: [line indices]}, title index or -1): every row whose label is an anchor or a table row, and the
    title line (one-spaced, upper-cased, starting with the title words)."""
    found = {k: [] for k in _HEAD_LABELS + _ROWS}
    for i, ln in enumerate(lines):
        row = _pismp_row(ln)
        if row and row[0] in found:
            found[row[0]].append(i)
    titles = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith(_TITLE)]
    return found, (titles[0] if len(titles) == 1 else -1 if not titles else -2)


def _pismp_table(lines, start: int, end: int) -> tuple:
    """({row label: value}, reason) for the table lines ``start``..``end`` (the BIDANG and TARIKH rows)."""
    values, labels, colons, address = {}, [], set(), []
    for ln in lines[start:end + 1]:
        row = _pismp_row(ln)
        if row and row[0] in _ROWS:
            labels.append(row[0])
            colons.add(row[2])
            values[row[0]] = row[1]
        elif labels and labels[-1] == 'TEMPAT PENGAJIAN':
            address.append(ln)
        else:
            return values, 'template_changed'
    if tuple(labels) != _ROWS or len(colons) != 1:
        return values, 'template_changed'
    colon = colons.pop()
    if not 1 <= len(address) <= _ADDRESS_LINES:
        return values, 'address_shape'
    for ln in address:                           # at the value column, address words, no year, no colon
        flat = _one_space(ln)
        if not colon < len(ln) - len(ln.lstrip()) <= colon + 3 or not _ADDRESS.match(flat) or _YEAR.search(flat):
            return values, 'address_shape'
    if not any(_POSTCODE.search(ln) for ln in address):
        return values, 'address_shape'
    return values, ''


def _pismp_read(lines) -> tuple:
    """(fields, reason) from page 1's layout lines; fields None before the title holds."""
    found, at = _pismp_find(lines)
    if at == -1:
        return None, 'no_title'
    if at == -2 or any(len(v) > 1 for v in found.values()):
        return None, 'second_row'
    if any(not v for v in found.values()):
        return None, 'no_row'
    ruj, nama, ic_at = (found[k][0] for k in _HEAD_LABELS)
    bidang_at, tarikh_at = found['BIDANG PENGKHUSUSAN'][0], found['TARIKH PENDAFTARAN'][0]
    before, after = (_one_space(' '.join(part)).upper() for part in (lines[:tarikh_at + 1], lines[tarikh_at + 1:]))
    if not (ruj < nama < ic_at < at < bidang_at < tarikh_at) or ic_at != nama + 1 or _CLOSING in before \
            or after.count(_CLOSING) != 1:
        return None, 'wrong_order'           # the closing words once, after the reporting date (may wrap)
    name, printed_ic = _pismp_row(lines[nama])[1], _pismp_row(lines[ic_at])[1]
    table, why = _pismp_table(lines, bidang_at, tarikh_at)
    bidang, session = table.get('BIDANG PENGKHUSUSAN', ''), table.get('AMBILAN/KELUARAN', '')
    campus_m, report_m = _CAMPUS.match(table.get('TEMPAT PENGAJIAN', '')), _REPORT_VALUE.match(table.get(REPORT_LABEL, ''))
    ic_m = _IC.match(printed_ic)
    title_m = _TITLE_YEAR.search(_one_space(lines[at]).upper())
    fields = {
        'candidate_name': name if _NAME.match(name) and _name_words_ok(name) else '',
        'candidate_nric': _norm_nric(''.join(ic_m.groups())) if ic_m else '',
        'candidate_nric_source': 'label' if ic_m else 'none',
        'programme': PROGRAMME, 'programme_code': '', 'bidang_pengkhususan': bidang if _BIDANG.match(bidang) else '',
        'institution': INSTITUTION, 'campus': campus_m.group(1) if campus_m else '', 'stream': '',
        'intake': f'AMBILAN {title_m.group(1)}' if title_m and _SESSION.match(session) else '',
        'reporting_date': house_date(table[REPORT_LABEL]) if report_m else '',
        'reporting_date_label': REPORT_LABEL if report_m else '', 'reporting_venue': '', 'offer_date': '',
        'issuer': ISSUER,
    }
    if why:
        return fields, why
    empty = [k for k in ('candidate_name', 'candidate_nric', 'bidang_pengkhususan', 'campus', 'intake',
                         'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    return fields, _pismp_dates(lines[at], session, report_m)


def _pismp_dates(title: str, session: str, report_m) -> str:
    """'' when the title's AMBILAN year is the session's first year, the course runs 3 to 6 years, and the
    reporting date is a real day in that first year; else 'dates_not_sane'."""
    y1, y2 = (int(y) for y in _SESSION.match(session).groups())
    said = _TITLE_YEAR.search(_one_space(title).upper())
    day, month, year = report_m.groups()
    real = _ymd(f'{day} {month.title()} {year}')
    ok = said is not None and int(said.group(1)) == y1 and 3 <= y2 - y1 <= 6 and real is not None and int(year) == y1
    return '' if ok else 'dates_not_sane'


def read_pismp(source: str):
    """``(fields, reason)`` for a PISMP letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    squeezed = _SQUEEZE_OUT.sub('', folded.upper()).replace(_PENGESAHAN_CLAUSE, '', 1)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in squeezed:
        return None, 'status_letter'
    if '{' in source or '}' in source:
        return None, 'placeholder'               # an unfilled template field
    lines = _uum_lines(source)
    fields, reason = _pismp_read(lines)
    if fields is None or reason:
        return fields, reason
    ic_at = next(i for i, ln in enumerate(lines) if (_pismp_row(ln) or ('',))[0] == 'NO. KAD PENGENALAN')
    rest = '\n'.join(ln for k, ln in enumerate(lines) if k != ic_at)
    if pismp_ic_elsewhere(rest, '') or pismp_ic_elsewhere(source, fields['candidate_nric']):
        return fields, 'second_ic'
    return fields, ''


def _conditions_out(text: str):
    """``text`` with the ONE pinned conditions block (`CONDITIONS_PINS`) taken out, or None when it is not there as
    pinned: the TARIKH PENDAFTARAN line printed once, the block the very next non-empty lines, holding the closing
    words, which the whole letter prints once."""
    if _SQUEEZE_OUT.sub('', text.upper()).count(_CLOSING_KEY) != 1:
        return None
    lines = text.splitlines()
    at = [i for i, ln in enumerate(lines) if REPORT_LABEL in _one_space(ln).upper()]
    if len(at) != 1:
        return None
    after = [i for i in range(at[0] + 1, len(lines)) if lines[i].strip()]
    for count, digest in CONDITIONS_PINS:
        block = after[:count]
        if (len(block) == count and _pin_digest([lines[i] for i in block]) == digest
                and _CLOSING_KEY in _SQUEEZE_OUT.sub('', ' '.join(lines[i] for i in block).upper())):
            return '\n'.join(lines[:block[0]] + lines[block[-1] + 1:])
    return None


def pismp_letter_refusal(text: str, nric: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'second_ic', then the shared withdrawal check
    (`offer_ums_refusal._withdrawn_one`; the head being the lines up to the title) on the letter with its pinned
    conditions block taken out (`_conditions_out`), raw and folded: 'not_an_offer' when it fires on the letter as it
    is with no pinned block, or on what is left; 'template_changed' when the block is not pinned and nothing else
    fires; else ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if pismp_ic_elsewhere(text, nric):
        return 'second_ic'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith('TAWARAN')), -1)
    head = lines[:at + 1] if at >= 0 else []
    forms = ((text, head), (folded, [fold_lookalikes(h) for h in head]))
    rests = [(_conditions_out(one), hd) for one, hd in forms]
    if any(rest is None for rest, _hd in rests):
        return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in forms) else 'template_changed'
    replaced = any(_REPLACED.search(f) for rest, _hd in rests for f in (rest, _squeeze(rest), *_dotless(rest)))
    return 'not_an_offer' if replaced or any(_withdrawn_one(rest, hd) for rest, hd in rests) else ''


def pismp_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 with text, else ''."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


def diagnose_pismp(out: dict, text: str, page1_text: str, page1_layout: str, page_texts=None,
                   blank_page2: bool = False) -> dict:
    """The PISMP branch of `offer_parse.diagnose` (via `offer_parse_lanes`), in `diagnose_unimap`'s order: a portal
    page refuses (no excuse); a scan refuses (``no_layout``); the drawn page texts (``hidden_page``); `read_pismp`;
    the owner phrases; the whole letter (`pismp_letter_refusal`); ``foreign_letters``; ``name_not_plain``; the read
    IC not printed exactly once in page 1's plain layer (``ic_not_plain``); any other IC-like number in page 1's
    plain layer or any page text (``ic_printed``); last, any later page with text. No blank-page excuse
    (``blank_page2`` is accepted for the shared signature and never read)."""
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
    fields, reason = read_pismp(page1_layout)
    out['fields'], out['titled'] = fields, fields is not None
    nric = (fields or {}).get('candidate_nric', '')
    early = page_texts_refusal(pages)
    if not early and not reason:
        out['owner_words_missing'] = missing(LANE, page1_layout, text_pdf=True)
        early = 'owner_words_missing' if out['owner_words_missing'] else ''
    reason = early or reason or pismp_letter_refusal(text, nric)
    if not reason and foreign_letters(text, page1_text, page1_layout, *pages):
        reason = 'foreign_letters'
    if not reason and not name_in_plain(fields['candidate_name'], page1_text, page1_layout):
        reason = 'name_not_plain'
    if not reason and _own_ic(page1_text, nric)[1] != 1:
        reason = 'ic_not_plain'
    if not reason and (pismp_ic_elsewhere(page1_text, nric) or any(pismp_ic_elsewhere(p, nric) for p in pages)):
        reason = 'ic_printed'
    if not reason:
        reason = pismp_later_pages(pages[1:])
    if reason.startswith('empty:'):
        out['empty_required'] = reason[len('empty:'):].split(',')
    elif reason:
        out['guard'] = reason
    else:
        out['locked'] = {**fields, '_family': 'pismp', 'rules_lane': LANE, '_offer_parser_version': PARSER_VERSION}
    return out


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1 (the IC and the
#: reporting date as printed; the intake as the title prints it; the campus as its printed line).
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'bidang_pengkhususan': 'v:bidang',
              'campus': 'v:campus', 'intake': 'v:intake', 'reporting_date': 'v:date'}
#: Every value is required (the template prints them all).
INK_OPTIONAL = ()
#: The fields `read_pismp` returns that are not read off the page as such (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'programme', 'programme_code', 'institution', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue', 'offer_date')


def _pismp_printed(page1_layout: str) -> dict:
    """{field: the value exactly as page 1 prints it} for the ink check; {} when the table is not read."""
    lines = _uum_lines(page1_layout)
    found, at = _pismp_find(lines)
    if at < 0 or any(len(v) != 1 for v in found.values()):
        return {}
    row = {k: _pismp_row(lines[v[0]])[1] for k, v in found.items()}
    said = _TITLE_YEAR.search(_one_space(lines[at]).upper())
    return {'candidate_nric': row['NO. KAD PENGENALAN'], 'reporting_date': row[REPORT_LABEL],
            'intake': f'AMBILAN {said.group(1)}' if said else '', 'campus': row['TEMPAT PENGAJIAN']}


def pismp_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a PISMP lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`, as printed). A required value left blank stays in,
    so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed = _pismp_printed(page1_layout)
    values = {**{k: f.get(k) or '' for k in INK_LABELS}, **{k: printed.get(k, '') for k in
                                                            ('candidate_nric', 'reporting_date', 'intake', 'campus')}}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, values)
