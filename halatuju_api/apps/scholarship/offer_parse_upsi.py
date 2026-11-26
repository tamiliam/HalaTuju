"""The UPSI rules lane (OCR-13 phase 5): a DIGITAL Universiti Pendidikan Sultan Idris degree offer letter read from
its page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UPSI`` (`offer_exact.ocr_first_lanes`).

UPSI PRINTS NO IC (owner, 26 Nov: "Same as UUM", this lane and UUM only). The head prints the matric number ("No.
Matrik : X" and 11 digits, and once more alone above it): it is NOT the IC and is never stored, matched or
ink-checked. A UPSI lock stores the IC blank (source 'none'); `offer_exact.ISSUER_PRINTS_NO_IC` lets the lock stand
without one. ANY 12-digit IC-like number on any page refuses (``ic_printed``): a letter that prints one is not the
template this lane was measured on.

Page 1, as measured on the corpus and the owner's samples (masked shapes only):

* a right-hand column: "Rujukan Tuan :", "Rujukan Kami : UPSI/...", "Tarikh : D Month YYYY / <the Hijri date>" (the
  offer date: the part before the slash), the matric alone, then "No. Matrik :" and the matric;
* the line straight after "No. Matrik" is the name, alone at the left margin; the address follows, then
  "Saudara/i,";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)" alone on its line, once;
* labelled lines "Label : Value" at the left margin: "Program" ("XXNN - (Ijazah )Sarjana Muda ..."; the code goes to
  ``programme_code``, the rest is the programme as printed; it never wraps, "Fakulti" is the next line), "Sesi
  Akademik" ("Semester N Sesi YYYY/YYYY", the intake, as printed) and "Tarikh Mendaftar" ("DD Month YYYY (Day)", the
  reporting date). Any non-degree word in the programme (`offer_parse_um.um_not_degree`) refuses.

English letters print no Malay title (``no_title``); a letter that says PENGESAHAN anywhere on page 1 refuses
(``status_letter``). Later pages: `upsi_later_pages`.
"""
import re

from .offer_parse import _name_ok, house_date
from .offer_parse_um import um_not_degree
from .offer_parse_uum import _LINKERS, _WORD_DATE, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UPSI'
INSTITUTION = 'UNIVERSITI PENDIDIKAN SULTAN IDRIS'
ISSUER = 'Bahagian Hal Ehwal Akademik, Universiti Pendidikan Sultan Idris'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)'
_RIGHT = 60                                     # the right-hand column starts past this
_RUJUKAN = re.compile(r'^Rujukan Kami ?: ?UPSI/\S{1,40}$')
_OFFER_DATE = re.compile(r'^Tarikh ?: ?' + _WORD_DATE + r"(?: ?/ ?\d{1,2} [A-Za-z' -]{3,30} 1\d{3}(?: ?H| ?M)?)?$")
_MATRIC = re.compile(r'^No\. ?Matrik ?: ?[A-Z]\d{11}$')
_INTAKE = re.compile(r'^Semester (\d{1,2}) Sesi (20\d{2})/(20\d{2})$')
_DAY = r'(?:Isnin|Selasa|Rabu|Khamis|Jumaat|Sabtu|Ahad|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
_REPORT_VALUE = re.compile(r'^(' + _WORD_DATE + r')(?: \(' + _DAY + r'\))?$')
_CODED = re.compile(r'^([A-Z]{2}\d{2}) - (\S.*)$')
_PROGRAMME_LABEL = 'Program'
_NEXT_LABEL = 'Fakulti'
_INTAKE_LABEL = 'Sesi Akademik'
_REPORT_LABEL = 'Tarikh Mendaftar'
_PENGESAHAN = re.compile(r'PENGESAHAN')
#: A later page must be one of UPSI's own; any other page goes to the AI.
_UPSI_PAGE = re.compile(r'Universiti\s{1,3}Pendidikan\s{1,3}Sultan\s{1,3}Idris|upsi\.edu\.my|\bUPSI\b', re.IGNORECASE)
_LATER_CODE = re.compile(r'(?<![A-Za-z0-9])([A-Z]{2}\d{2}) ?- ?(?:Ijazah|Sarjana|IJAZAH|SARJANA)')
_LATER_DATE = re.compile(r'Tarikh\s{0,3}Mendaftar[^:\n]{0,20}:\s{0,3}(' + _WORD_DATE + r')', re.IGNORECASE)
_DEGREE_KEY = 'SARJANAMUDA'
#: A lower-case web address (page 2's form link carries "sarjanamuda" in its path): read past by the programme
#: comparison only. An address with a capital letter in it is not taken out, so it still counts.
_URL = re.compile(r"(?:https?://|www\.)[a-z0-9._~:/?#@!$&'*+,;=%-]+")
#: The one conditional cancellation every genuine UPSI letter prints (owner phrase 8 opens it; measured: 12 of the 13
#: titled sample letters). Taken out before the withdrawal check, whose "MENARIK BALIK" after a line break would refuse
#: every genuine letter; any other cancellation wording still refuses.
_NOTE_WORDS = ('Sekiranya saudara/i didapati memberi maklumat salah/tidak benar/memanipulasi maklumat dan tidak '
               'memenuhi syarat kemasukan, pihak Universiti berhak menarik balik tawaran kemasukan saudara/i dengan '
               'serta-merta')
_UPSI_NOTE = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _NOTE_WORDS.split()), re.IGNORECASE)


def is_upsi(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UPSI admissions letter: the university and its academic
    affairs department (Malay or English). Which of them is a degree offer `read_upsi` decides."""
    return 'UNIVERSITI PENDIDIKAN SULTAN IDRIS' in up and ('HAL EHWAL AKADEMIK' in up or 'ACADEMIC AFFAIRS' in up)


def _upsi_title_at(lines) -> int:
    """The title line's index: the title alone on its line, once, at the left margin; else -1."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).startswith(_TITLE)]
    if len(hits) != 1 or _indent(lines[hits[0]]) > 4 or _one_space(lines[hits[0]]) != _TITLE:
        return -1
    return hits[0]


def _upsi_values(lines, label: str) -> list:
    """(index, value) of every "Label : Value" line whose label is ``label``: the label at the left margin, the
    value one column (no 3-space gap in it)."""
    pat = re.compile(r'^\s{0,4}' + re.escape(label) + r'\s{1,40}:\s{0,40}(\S.*)$')
    out = []
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m and len(_cols(m.group(1))) == 1:
            out.append((i, _one_space(m.group(1))))
    return out


def _upsi_one(lines, label: str, at) -> tuple:
    """(index, value, reason) of the ONE "Label : Value" line, after the title; reason 'no_<label>' or
    'twice_<label>'."""
    hits = _upsi_values(lines, label)
    tag = label.split()[-1].lower()
    if len(hits) != 1 or hits[0][0] <= at:
        return -1, '', ('no_' if not hits else 'twice_') + tag
    return hits[0][0], hits[0][1], ''


def _upsi_head(lines, at):
    """(name, offer_date, reason) from the lines before the title: ONE "Rujukan Kami : UPSI/..." line in the right-hand
    column, the "Tarikh" line after it (the offer date: its Gregorian part), ONE "No. Matrik" line after that, the
    name alone straight after it, "Saudara/i," later. The matric is read past, never kept."""
    ref = [i for i, ln in enumerate(lines[:at]) if _indent(ln) >= _RIGHT and _RUJUKAN.match(_one_space(ln))]
    mat = [i for i, ln in enumerate(lines[:at]) if _indent(ln) >= _RIGHT and _MATRIC.match(_one_space(ln))]
    if len(ref) != 1 or len(mat) != 1 or not ref[0] < mat[0] < at - 1:
        return '', '', 'no_head'
    dated = [i for i in range(ref[0] + 1, mat[0]) if _indent(lines[i]) >= _RIGHT
             and _OFFER_DATE.match(_one_space(lines[i]))]
    offer_date = ''
    if len(dated) == 1:
        offer_date = ' '.join(_OFFER_DATE.match(_one_space(lines[dated[0]])).groups())
    ln = lines[mat[0] + 1]
    name = _one_space(ln)
    if _indent(ln) > 4 or len(_cols(ln)) != 1 or not _name_ok(name) or _LINKERS.search(name):
        return '', offer_date, 'name_shape'       # an unread or wrapped name ("... BINTI")
    if not any(_one_space(x) == 'Saudara/i,' for x in lines[mat[0] + 2:at]):
        return '', offer_date, 'no_head'
    return name, offer_date, ''


def _upsi_programme(lines, at):
    """(programme, code, reason): the one "Program : XXNN - ..." line after the title, the "Fakulti" line next (a
    UPSI programme never wraps). The programme must be a plain degree."""
    i, value, why = _upsi_one(lines, _PROGRAMME_LABEL, at)
    if why:
        return '', '', 'no_programme' if why.startswith('no_') else 'programme_twice'
    m = _CODED.match(value)
    if not m:
        return '', '', 'programme_shape'
    nxt = _upsi_values(lines[i + 1:i + 2], _NEXT_LABEL)
    if not nxt:
        return '', '', 'programme_shape'
    code, programme = m.group(1), m.group(2).strip()
    return programme, code, ('not_degree' if um_not_degree(programme.upper()) else '')


def _upsi_report(lines, at) -> str:
    """The reporting date as printed ("DD Month YYYY", the day name dropped); '' when it cannot be read."""
    _i, value, why = _upsi_one(lines, _REPORT_LABEL, at)
    m = _REPORT_VALUE.match(value) if not why else None
    return m.group(1) if m else ''


def upsi_printed_date(page1_layout: str) -> str:
    """The reporting date exactly as page 1 prints it ("DD Month YYYY"), '' when it cannot be read."""
    lines = _uum_lines(page1_layout)
    at = _upsi_title_at(lines)
    return _upsi_report(lines, at) if at >= 0 else ''


def _upsi_dates_sane(intake: str, printed: str, offer_date: str) -> bool:
    """The session's years run on; the reporting date is a real date inside them; the offer date (when read) is a
    real date not after it."""
    m, report = _INTAKE.match(intake or ''), _ymd(printed)
    if not m or report is None or int(m.group(3)) != int(m.group(2)) + 1:
        return False
    if not int(m.group(2)) <= report.year <= int(m.group(3)):
        return False
    offered = _ymd(offer_date) if offer_date else None
    return not offer_date or (offered is not None and offered <= report)


def read_upsi(source: str):
    """``(fields, reason)`` for a UPSI letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock. The IC is always blank."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or _PENGESAHAN.search(_SQUEEZE_OUT.sub('', folded.upper())):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at = _upsi_title_at(lines)
    if at < 0:
        return None, 'no_title'
    if ic_printed(source):
        return None, 'ic_printed'
    name, offer_date, why_head = _upsi_head(lines, at)
    programme, code, why_prog = _upsi_programme(lines, at)
    _i, intake, why_intake = _upsi_one(lines, _INTAKE_LABEL, at)
    intake = intake if _INTAKE.match(intake) else ''
    printed = _upsi_report(lines, at)
    fields = {
        'candidate_name': name, 'candidate_nric': '', 'candidate_nric_source': 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if _ymd(printed) else '',
        'reporting_date_label': _REPORT_LABEL, 'reporting_venue': '', 'offer_date': offer_date, 'issuer': ISSUER,
    }
    for why in (why_head, why_prog, why_intake):
        if why:
            return fields, why
    empty = [k for k in ('candidate_name', 'programme', 'programme_code', 'intake', 'reporting_date')
             if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _upsi_dates_sane(intake, printed, offer_date):
        return fields, 'dates_not_sane'
    return fields, ''


def upsi_letter_refusal(text: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'ic_printed', 'not_an_offer'
    (`offer_ums_refusal._withdrawn_one` with the genuine note `_UPSI_NOTE` taken out, the head being the lines up to
    the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    if ic_printed(text):
        return 'ic_printed'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper() == _TITLE), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(_UPSI_NOTE.sub(' ', one), hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def _second_programme(flat: str, want: str, code: str) -> bool:
    """True when a later page names a programme that is not page 1's: a "SARJANA MUDA" the page-1 programme does not
    start at the same place (compared with every non-letter taken out, so a wrapped repeat still matches), another
    programme code, or a non-degree word. A lower-case web address (`_URL`) is read past for the first only."""
    key = _SQUEEZE_OUT.sub('', _URL.sub(' ', flat).upper())
    tail = want[want.find(_DEGREE_KEY):] if _DEGREE_KEY in want else want
    for m in re.finditer(_DEGREE_KEY, key):
        if not tail or not key[m.start():].startswith(tail):
            return True
    if any(c != code for c in _LATER_CODE.findall(flat)):
        return True
    up = flat.upper()
    return any(re.search(r'(?<![A-Z])' + w + r'(?![A-Z])', up) for w in ('DIPLOMA', 'ASASI', 'PERSEDIAAN'))


def upsi_later_pages(pages, programme: str, code: str, printed_date: str) -> str:
    """Why a later page (page 2 on) refuses the lock: 'unknown_page' (no UPSI name or web address on it),
    'ic_printed' (any IC-like number), 'second_programme' (`_second_programme`), 'second_date' (a word date labelled
    "Tarikh Mendaftar" that differs from page 1's); '' when none. Each page is checked raw and look-alike folded."""
    want = _SQUEEZE_OUT.sub('', (programme or '').upper())
    for page in pages or ():
        for one in (page or '', fold_lookalikes(page or '')):
            if not _UPSI_PAGE.search(one):
                return 'unknown_page'
            if ic_printed(one):
                return 'ic_printed'
            flat = _one_space(one)
            if _second_programme(flat, want, code):
                return 'second_programme'
            for m in _LATER_DATE.finditer(flat):
                if _ymd(_one_space(m.group(1))) != _ymd(printed_date):
                    return 'second_date'
    return ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1. No IC: UPSI prints
#: none, and the matric is never a value.
INK_LABELS = {'candidate_name': 'v:name', 'programme': 'v:programme', 'programme_code': 'v:code',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Read from the page but optional: ink-checked only when read.
INK_OPTIONAL = ('offer_date',)
#: The fields `read_upsi` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric', 'candidate_nric_source', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def upsi_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UPSI lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the reporting date as printed). A required value
    left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    printed = {**{k: f.get(k) or '' for k in INK_LABELS}, 'reporting_date': upsi_printed_date(page1_layout)}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, printed)
