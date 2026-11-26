"""The UNIMAS rules lane (OCR-14 phase 2): a DIGITAL Universiti Malaysia Sarawak degree offer letter read from its
page-1 LAYOUT text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UNIMAS`` (`offer_exact.ocr_first_lanes`).

UNIMAS PRINTS NO IC (owner, 26 Nov: "Same as UUM"). The head prints the matric number ("No Matrik : " and 6 digits,
in the right-hand column): it is NOT the IC and is never stored, matched or ink-checked. A UNIMAS lock stores the IC
blank (source 'none'; `offer_exact.ISSUER_PRINTS_NO_IC`). ANY 12-digit IC-like number on any page refuses
(``ic_printed``): a letter that prints one is not the template this lane was measured on.

Page 1 of the 2026/27 layout, as measured on the corpus and the owner's samples (masked shapes only):

* the first line is "Pejabat Timbalan Naib Canselor" (the 2023/24 "Pejabat Pendaftar" layout refuses:
  ``old_layout``); the offer date ("DD Month YYYY") alone at the left margin, then the name alone on the next line,
  then the address (`offer_parse_uitm.name_ended` must prove the name ended); its last line carries "No Matrik"
  in the right-hand column; then "Saudara/Saudari";
* the title "Tawaran Kemasukan Ke Universiti Malaysia Sarawak" alone at the left margin, once, with the session
  ("Semester N Sesi YYYY/YYYY", the intake, as printed) after it on the same line;
* "Program : Sarjana Muda ... - XX9999999" (the UPU code goes to ``programme_code``, the rest is the programme as
  printed; it may wrap onto at most two lines under its value), then "Fakulti". Any non-degree word refuses
  (`offer_parse_um.um_not_degree`), and so does a second UPU code anywhere on the page (``second_code``).

UNIMAS prints no reporting date (owner: none printed): it is left blank and never guessed. "Lokasi Pendaftaran" is
a place, or a note to check a web page by a date; it is never read. A UNIMAS letter is one page (measured: every
corpus and sample letter): any later page refuses (``later_page``).
"""
import re

from .offer_parse import _name_ok
from .offer_parse_uitm import name_ended
from .offer_parse_um import um_not_degree
from .offer_parse_uum import _LINKERS, _WORD_DATE, _cols, _indent, _one_space, _uum_lines, _ymd, ic_printed
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UNIMAS'
INSTITUTION = 'UNIVERSITI MALAYSIA SARAWAK'
ISSUER = 'Pusat Pengajian Prasiswazah, Universiti Malaysia Sarawak'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_FIRST_LINE = 'Pejabat Timbalan Naib Canselor'
_TITLE = 'Tawaran Kemasukan Ke Universiti Malaysia Sarawak'
_TITLE_LINE = re.compile(r'^' + _TITLE + r' (Semester \d{1,2} Sesi 20\d{2}/20\d{2})$')
_INTAKE = re.compile(r'^Semester (\d{1,2}) Sesi (20\d{2})/(20\d{2})$')
_DATE_LINE = re.compile(r'^' + _WORD_DATE + r'$')
_MATRIC = re.compile(r'^No Matrik ?: ?\d{6}$')
_SALUTATION = 'Saudara/Saudari'
_RIGHT = 60                                     # the right-hand column starts past this
_PROGRAMME = re.compile(r'^\s{0,8}Program\s{1,40}:\s{0,40}(\S.*)$')
_FACULTY = re.compile(r'^\s{0,8}Fakulti\s{1,40}:\s{0,40}(\S.*)$')
_WRAP_AT = (30, 50)                             # a wrapped programme line starts under its value
_MAX_WRAPS = 2
_CODED = re.compile(r'^(Sarjana Muda \S.*\S) - ([A-Z]{2}\d{7})$')
_ANY_CODE = re.compile(r'(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![0-9])')
#: The sentence every UNIMAS offer opens its body with (owner phrase 3 and the words after it; measured: every
#: corpus and sample letter of this layout). Its "Tahniah!" is a portal tell (`offer_parse._PORTAL_TELL`), so the
#: portal check reads past this exact sentence, once (`unimas_portal`); any other tell still refuses.
_GREETING_WORDS = ('Tahniah! Saudara/saudari adalah ditawarkan tempat untuk mengikuti pengajian Ijazah Sarjana Muda '
                   'di Universiti Malaysia Sarawak')
_GREETING = re.compile(r'\s{1,40}'.join(re.escape(w) for w in _GREETING_WORDS.split()))


def is_unimas(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UNIMAS admissions letter: the university and its academic
    office or undergraduate centre. Which of them is a degree offer `read_unimas` decides."""
    return 'UNIVERSITI MALAYSIA SARAWAK' in up and ('PEJABAT TIMBALAN NAIB CANSELOR' in up
                                                     or 'PUSAT PENGAJIAN PRASISWAZAH' in up)


def unimas_portal(text: str) -> bool:
    """True when ``text`` (the whole letter) carries a portal tell (`offer_parse._PORTAL_TELL`) once the greeting
    (`_GREETING`) is taken out; a letter that prints the greeting more than once counts as a portal page."""
    from .offer_parse import _PORTAL_TELL
    rest, n = _GREETING.subn(' ', text or '')
    return n > 1 or bool(_PORTAL_TELL.search(rest))


def _unimas_title_at(lines) -> tuple:
    """(index, intake) of the title line: the title once, at the left margin, one column, the session after it;
    (-1, '') else."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith(_TITLE.upper())]
    if len(hits) != 1 or _indent(lines[hits[0]]) > 4 or len(_cols(lines[hits[0]])) != 1:
        return -1, ''
    m = _TITLE_LINE.match(_one_space(lines[hits[0]]))
    return (hits[0], m.group(1)) if m else (-1, '')


def _unimas_head(lines, at):
    """(name, offer_date, reason) from the lines before the title: the first line "Pejabat Timbalan Naib Canselor";
    ONE date alone at the left margin (the offer date); the name alone on the line straight after it (the line
    after the name must prove it ended: `name_ended`); ONE "No Matrik" in the right-hand column after the name,
    read past and never kept; "Saudara/Saudari" the line before the title."""
    if not lines or _indent(lines[0]) > 4 or _one_space(lines[0]) != _FIRST_LINE:
        return '', '', 'old_layout'
    dated = [i for i, ln in enumerate(lines[:at]) if _indent(ln) <= 4 and len(_cols(ln)) == 1
             and _DATE_LINE.match(_one_space(ln))]
    if len(dated) != 1 or dated[0] + 2 >= at:
        return '', '', 'no_head'
    offer_date, n = _one_space(lines[dated[0]]), dated[0] + 1
    name = _one_space(lines[n])
    if (_indent(lines[n]) > 4 or len(_cols(lines[n])) != 1 or not _name_ok(name) or name != name.upper()
            or _LINKERS.search(name)):
        return '', offer_date, 'name_shape'       # an unread or wrapped name ("... BINTI")
    if not name_ended(lines[n + 1]):
        return '', offer_date, 'name_not_ended'   # the rest of the name may be on the next line
    mat = [i for i, ln in enumerate(lines[:at]) if 'MATRIK' in ln.upper()]
    if (len(mat) != 1 or not n < mat[0] < at - 1 or len(_cols(lines[mat[0]])) < 2
            or lines[mat[0]].find('No Matrik') < _RIGHT or not _MATRIC.match(_one_space(_cols(lines[mat[0]])[-1]))):
        return '', offer_date, 'no_head'
    if _one_space(lines[at - 1]) != _SALUTATION:
        return '', offer_date, 'no_head'
    return name, offer_date, ''


def _unimas_programme(lines, at, source: str):
    """(programme, code, reason): the one "Program : Sarjana Muda ... - XX9999999" line after the title, wrapped
    onto at most `_MAX_WRAPS` lines under its value, then the "Fakulti" line. The programme must be a plain degree;
    the page may print no other UPU code."""
    hits = [i for i, ln in enumerate(lines) if _PROGRAMME.match(ln)]
    if len(hits) != 1 or hits[0] <= at:
        return '', '', 'no_programme' if not hits else 'programme_twice'
    i = hits[0]
    value = _PROGRAMME.match(lines[i]).group(1)
    parts, j = [value] if len(_cols(value)) == 1 else [], i + 1
    while parts and j < len(lines) and not _FACULTY.match(lines[j]) and len(parts) <= _MAX_WRAPS:
        if not _WRAP_AT[0] <= _indent(lines[j]) <= _WRAP_AT[1] or len(_cols(lines[j])) != 1:
            break
        parts.append(lines[j])
        j += 1
    faculty = _FACULTY.match(lines[j]) if parts and j < len(lines) else None
    if not faculty or len(_cols(faculty.group(1))) != 1:
        return '', '', 'programme_shape'
    m = _CODED.match(_one_space(' '.join(parts)))
    if not m:
        return '', '', 'programme_shape'
    programme, code = m.group(1), m.group(2)
    if any(c != code for c in _ANY_CODE.findall(source)):
        return '', '', 'second_code'
    return programme, code, ('not_degree' if um_not_degree(programme.upper()) else '')


def _unimas_dates_sane(intake: str, offer_date: str) -> bool:
    """The session's years run on; the offer date is a real date in the year before the session or its first."""
    m, offered = _INTAKE.match(intake or ''), _ymd(offer_date)
    if not m or offered is None or int(m.group(3)) != int(m.group(2)) + 1:
        return False
    return int(m.group(2)) - 1 <= offered.year <= int(m.group(2))


def read_unimas(source: str):
    """``(fields, reason)`` for a UNIMAS letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock. The IC and the reporting date are
    always blank (UNIMAS prints neither)."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    folded = fold_lookalikes(source)
    if status_said(source) or status_said(folded) or 'PENGESAHAN' in _SQUEEZE_OUT.sub('', folded.upper()):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at, intake = _unimas_title_at(lines)
    if at < 0:
        return None, 'no_title'
    if ic_printed(source):
        return None, 'ic_printed'
    name, offer_date, why_head = _unimas_head(lines, at)
    programme, code, why_prog = _unimas_programme(lines, at, source)
    fields = {
        'candidate_name': name, 'candidate_nric': '', 'candidate_nric_source': 'none',
        'programme': programme, 'programme_code': code, 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': '', 'reporting_date_label': '', 'reporting_venue': '',
        'offer_date': offer_date if _ymd(offer_date) else '', 'issuer': ISSUER,
    }
    for why in (why_head, why_prog):
        if why:
            return fields, why
    empty = [k for k in ('candidate_name', 'programme', 'programme_code', 'intake', 'offer_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _unimas_dates_sane(intake, offer_date):
        return fields, 'dates_not_sane'
    return fields, ''


def unimas_letter_refusal(text: str) -> str:
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
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper().startswith(_TITLE.upper())), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def unimas_later_pages(pages) -> str:
    """'later_page' when the letter has any page after page 1 (a UNIMAS letter is one page; any other page may hold
    a second programme, a date or an IC the reader never measured), else ''."""
    return 'later_page' if any((p or '').strip() for p in pages or ()) else ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1. No IC: UNIMAS prints
#: none, and the matric is never a value. No reporting date: UNIMAS prints none.
INK_LABELS = {'candidate_name': 'v:name', 'programme': 'v:programme', 'programme_code': 'v:code',
              'intake': 'v:intake', 'offer_date': 'v:offer_date'}
#: Read from the page but optional: ink-checked only when read (none: every one is required).
INK_OPTIONAL = ()
#: The fields `read_unimas` returns that are not read off the page (constants and blanks).
NOT_PRINTED = ('candidate_nric', 'candidate_nric_source', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date', 'reporting_date_label', 'reporting_venue')


def unimas_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UNIMAS lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`). A required value left blank stays in, so the ink
    check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, {k: f.get(k) or '' for k in INK_LABELS})
