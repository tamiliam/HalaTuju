"""The UM rules lane (OCR-13 phase 4): a DIGITAL Universiti Malaya degree offer letter read from its page-1 LAYOUT
text.

Only a text-layer PDF can lock: a scan gives no layout, so it refuses (``no_layout``, in `offer_parse_lanes`). The
reader refuses on any doubt; every refusal sends the letter to the AI as before. The lane is OFF unless
OCR_FIRST_LANES holds ``ua:UM`` (`offer_exact.ocr_first_lanes`). UM prints the IC ("Nombor K/P"), so the IC guard
applies as on every other lane: a UM letter with no IC never locks.

Page 1, as measured on the corpus and the owner's samples (masked shapes only):

* the first line holds "No Pendaftaran : NNNNNNNN" (the registration number: never stored) and, in a right-hand
  column, "Tarikh : D Month YYYY" (the offer date);
* the next line is "Nombor K/P : IC" (12 digits), then the name alone at the left margin, then the address and
  "Saudara/i,";
* the title "TAWARAN KEMASUKAN KE UNIVERSITI MALAYA" alone on its line, once;
* labelled lines "LABEL : VALUE": "SESI KEMASUKAN" ("SEMESTER N, SESI AKADEMIK YYYY/YYYY", the intake, stored as
  printed), "PROGRAM PENGAJIAN" (the programme; at most two wrapped lines before "FAKULTI"), "TARIKH LAPOR DIRI DI
  KOLEJ" (the reporting date; every measured letter prints "RUJUK LAMPIRAN", so it is read only when a date is
  printed there). The programme must read "(IJAZAH )SARJANA MUDA ..." with no non-degree word in it
  (`offer_parse_uum.not_degree`): Asasi, Diploma and the rest go to the AI.

English letters print no Malay title (``no_title``). Later pages: `um_later_pages`.
"""
import re

from .offer_parse import _IC, _IC_END, _name_ok, _norm_nric, house_date
from .offer_parse_uitm import NOT_DEGREE, _PRA, name_ended
from .offer_parse_uum import _LINKERS, _WORD_DATE, _cols, _indent, _one_space, _uum_lines, _ymd
from .offer_ums_refusal import _SQUEEZE_OUT, _withdrawn_one, fold_lookalikes, status_said

LANE = 'ua:UM'
INSTITUTION = 'UNIVERSITI MALAYA'
ISSUER = 'Jabatan Perkhidmatan Akademik, Universiti Malaya'

#: Page 1 is short; past these no rule runs (the UMS bounds).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS

_TITLE = 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYA'
_REG = re.compile(r'^No\.? Pendaftaran ?: ?\d{6,10}$')
_OFFER_DATE = re.compile(r'^Tarikh ?: ?' + _WORD_DATE + r'$')
_IC_LABEL = 'Nombor K/P'
_IC_VALUE = re.compile(r'^' + _IC + _IC_END + r'$')
_IC_ANY = re.compile(r'(?<!\d)' + _IC + _IC_END)
_DIGIT_RUN = re.compile(r'\d{12,}')
_INTAKE = re.compile(r'^SEMESTER (?:[0-9]{1,2}|[IV]{1,3}), SESI AKADEMIK (20\d{2})/(20\d{2})$')
_DATE_VALUE = re.compile(r'^' + _WORD_DATE + r'$')
_INTAKE_LABEL = 'SESI KEMASUKAN'
_PROGRAMME_LABEL = 'PROGRAM PENGAJIAN'
_NEXT_LABEL = 'FAKULTI'
_REPORT_LABEL = 'TARIKH LAPOR DIRI DI KOLEJ'
_NOT_PRINTED_YET = 'RUJUK LAMPIRAN'
#: "LABEL : VALUE" at the left margin (the colon 2+ spaces after the label).
_LABEL_LINE = re.compile(r'^\s{0,10}([A-Z][A-Z /]{2,40}?)\s{2,}:\s+(\S.*)$')
_DEGREE = re.compile(r"^(?:IJAZAH )?SARJANA MUDA(?: \(?[A-Z][A-Z&,'/.()\-]*)+$")
#: A later page must be one of UM's own; any other page goes to the AI.
_UM_PAGE = re.compile(r'Universiti\s{1,3}Malaya(?![A-Za-z])|um\s?\.edu\.my', re.IGNORECASE)
_LATER_DEGREE = re.compile(r"(?:IJAZAH )?SARJANA MUDA(?: \(?[A-Z][A-Z&,'/.()\-]*)+")
_LATER_DATE = re.compile(r'(?:LAPOR\s{0,3}DIRI|PENDAFTARAN)[^:\n]{0,40}:\s{0,3}(' + _WORD_DATE + r')', re.IGNORECASE)


def is_um(up: str) -> bool:
    """``up`` (upper-cased, spaces folded) reads as a UM admissions letter: the university and its academic services
    department. Which of them is a degree offer `read_um` decides."""
    return bool(re.search(r'UNIVERSITI MALAYA(?![A-Z])', up)) and 'PERKHIDMATAN AKADEMIK' in up


def _um_title_at(lines) -> int:
    """The title line's index: the title alone on its line, once, at the left margin; else -1."""
    hits = [i for i, ln in enumerate(lines) if _one_space(ln).startswith(_TITLE)]
    if len(hits) != 1 or _indent(lines[hits[0]]) > 10 or _one_space(lines[hits[0]]) != _TITLE:
        return -1
    return hits[0]


def _um_label_values(lines, label: str) -> list:
    """(index, value) of every "LABEL : VALUE" line whose label is ``label``."""
    out = []
    for i, ln in enumerate(lines):
        m = _LABEL_LINE.match(ln)
        if m and _one_space(m.group(1)) == label:
            out.append((i, _one_space(m.group(2))))
    return out


def _um_head(lines, at):
    """(name, nric, printed_ic, offer_date, reason) from the lines before the title: "No Pendaftaran" first (the
    offer date in its right-hand column), "Nombor K/P : IC" next, the name alone after it (the line after it must prove
    the name ended: `offer_parse_uitm.name_ended`), "Saudara/i," later."""
    if at < 4:
        return '', '', '', '', 'no_head'
    first = _cols(lines[0])
    if _indent(lines[0]) > 10 or len(first) != 2 or not _REG.match(_one_space(first[0])):
        return '', '', '', '', 'no_head'
    m = _OFFER_DATE.match(_one_space(first[1]))
    offer_date = ' '.join(m.groups()) if m else ''
    ic_cols = _cols(lines[1])
    if _indent(lines[1]) > 10 or len(ic_cols) != 2 or ic_cols[0] != _IC_LABEL or not ic_cols[1].startswith(':'):
        return '', '', '', offer_date, 'no_ic_line'
    printed_ic = _one_space(ic_cols[1][1:])
    nric = _norm_nric(printed_ic) if _IC_VALUE.match(printed_ic) else ''
    ln = lines[2]
    name = _one_space(ln)
    if _indent(ln) > 10 or len(_cols(ln)) != 1 or not _name_ok(name) or _LINKERS.search(name):
        return '', nric, printed_ic, offer_date, 'name_shape'   # an unread or wrapped name ("... BINTI")
    if not name_ended(lines[3]):
        return '', nric, printed_ic, offer_date, 'name_not_ended'   # the rest of the name may be on the next line
    if not any(_one_space(x) == 'Saudara/i,' for x in lines[3:at]):
        return name, nric, printed_ic, offer_date, 'no_head'
    return name, nric, printed_ic, offer_date, ''


def um_not_degree(programme: str) -> bool:
    """True when the programme is not a plain degree: a non-degree word (`NOT_DEGREE`, PRA as a word), raw or
    look-alike folded, spaced or dotted, or a name that is not "(IJAZAH )SARJANA MUDA ..." in plain capitals."""
    folded = fold_lookalikes(programme or '').upper()
    key = _SQUEEZE_OUT.sub('', folded)
    return (any(w in key for w in NOT_DEGREE) or bool(_PRA.search(folded)) or bool(_PRA.search(key[:3]))
            or not _DEGREE.match(programme or ''))


def _um_programme(lines, at):
    """(programme, reason): the one "PROGRAM PENGAJIAN : VALUE" line after the title, plus up to two wrapped lines
    (indented 30+, one column), then the "FAKULTI" line."""
    hits = _um_label_values(lines, _PROGRAMME_LABEL)
    if len(hits) != 1 or hits[0][0] <= at:
        return '', 'no_programme' if not hits else 'programme_twice'
    i, first = hits[0]
    parts, j = [first], i + 1
    while j < len(lines) and j <= i + 3 and not _LABEL_LINE.match(lines[j]):
        if _indent(lines[j]) < 30 or len(_cols(lines[j])) != 1:
            return '', 'programme_shape'
        parts.append(_one_space(lines[j]))
        j += 1
    nxt = _LABEL_LINE.match(lines[j]) if j < len(lines) else None
    if not nxt or _one_space(nxt.group(1)) != _NEXT_LABEL or len(parts) > 3:
        return '', 'programme_shape'
    programme = ' '.join(parts)
    return programme, ('not_degree' if um_not_degree(programme) else '')


def _um_one(lines, label, at) -> tuple:
    """(value, reason) of the ONE "LABEL : VALUE" line after the title; reason 'no_<label>' or 'twice_<label>'."""
    hits = _um_label_values(lines, label)
    tag = label.split()[0].lower()
    if len(hits) != 1 or hits[0][0] <= at:
        return '', ('no_' if not hits else 'twice_') + tag
    return hits[0][1], ''


def um_printed_date(page1_layout: str) -> str:
    """The reporting date exactly as page 1 prints it ("D Month YYYY"); '' when none is printed or unread."""
    lines = _uum_lines(page1_layout)
    at = _um_title_at(lines)
    if at < 0:
        return ''
    value, why = _um_one(lines, _REPORT_LABEL, at)
    return value if not why and _DATE_VALUE.match(value) else ''


def _um_dates_sane(intake: str, printed: str, offer_date: str) -> bool:
    """The session's years run on; the offer date (when read) is a real date no earlier than the year before the
    session; the reporting date (when printed) is a real date inside the session's two years, not before the offer."""
    m = _INTAKE.match(intake or '')
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        return False
    y1, y2 = int(m.group(1)), int(m.group(2))
    offered = _ymd(offer_date) if offer_date else None
    if offer_date and (offered is None or not y1 - 1 <= offered.year <= y2):
        return False
    if not printed:
        return True
    report = _ymd(printed)
    return report is not None and y1 <= report.year <= y2 and (offered is None or offered <= report)


def read_um(source: str):
    """``(fields, reason)`` for a UM letter's page-1 layout: ``fields`` None before the title holds; ``reason``
    '' when every required field is read and sane, else why it must not lock."""
    source = source or ''
    if len(source) > MAX_CHARS or len(source.splitlines()) > MAX_LINES:
        return None, 'too_long'
    if status_said(source) or status_said(fold_lookalikes(source)):
        return None, 'status_letter'
    lines = _uum_lines(source)
    at = _um_title_at(lines)
    if at < 0:
        return None, 'no_title'
    name, nric, _printed_ic, offer_date, why_head = _um_head(lines, at)
    programme, why_prog = _um_programme(lines, at)
    intake, why_intake = _um_one(lines, _INTAKE_LABEL, at)
    intake = intake if _INTAKE.match(intake) else ''
    report, why_report = _um_one(lines, _REPORT_LABEL, at)
    printed = report if _DATE_VALUE.match(report) else ''
    if not why_report and not printed and report != _NOT_PRINTED_YET:
        why_report = 'reporting_shape'           # neither a date nor "RUJUK LAMPIRAN": not the measured template
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': programme, 'programme_code': '', 'institution': INSTITUTION, 'campus': '',
        'stream': '', 'intake': intake, 'reporting_date': house_date(printed) if _ymd(printed) else '',
        'reporting_date_label': _REPORT_LABEL if printed else '', 'reporting_venue': '', 'offer_date': offer_date,
        'issuer': ISSUER,
    }
    for why in (why_head, why_prog, why_intake, why_report):
        if why:
            return fields, why
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake') if not fields[k]]
    if printed and not fields['reporting_date']:
        empty.append('reporting_date')
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _um_dates_sane(intake, printed, offer_date):
        return fields, 'dates_not_sane'
    return fields, ''


def um_letter_refusal(text: str) -> str:
    """The whole letter (every page): 'too_long', 'status_letter', 'not_an_offer' (`offer_ums_refusal._withdrawn_one`,
    the head being the lines up to the title), or ''."""
    text = text or ''
    folded = fold_lookalikes(text)
    if len(text) > MAX_LETTER_CHARS or len(folded) > MAX_LETTER_CHARS:
        return 'too_long'
    if status_said(text) or status_said(folded):
        return 'status_letter'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    at = next((i for i, ln in enumerate(lines) if _one_space(ln).upper() == _TITLE), -1)
    head = lines[:at + 1] if at >= 0 else []
    return 'not_an_offer' if any(_withdrawn_one(one, hd) for one, hd in
                                 ((text, head), (folded, [fold_lookalikes(h) for h in head]))) else ''


def um_later_pages(pages, nric: str, programme: str, printed_date: str) -> str:
    """Why a later page (page 2 on) refuses the lock: 'unknown_page' (no UM name or web address on it),
    'second_ic' (a 12-digit IC, or a longer digit run, that is not the letter's IC), 'second_programme' (a
    "SARJANA MUDA" programme that is not page 1's, or a non-degree word), 'second_date' (a word date labelled as a
    reporting or registration date that differs from page 1's, or any such date when page 1 prints none); '' when
    none. Each page is checked raw and look-alike folded. Footer and notes words never refuse."""
    want_ic = _norm_nric(nric)
    want = _SQUEEZE_OUT.sub('', (programme or '').upper())
    for page in pages or ():
        for one in (page or '', fold_lookalikes(page or '')):
            if not _UM_PAGE.search(one):
                return 'unknown_page'
            if any(_norm_nric(m.group(1)) != want_ic for m in _IC_ANY.finditer(one)):
                return 'second_ic'
            if any(r != want_ic.replace('-', '') for r in _DIGIT_RUN.findall(one)):
                return 'second_ic'
            flat = _one_space(one)
            if any(_SQUEEZE_OUT.sub('', m.group(0)) not in want for m in _LATER_DEGREE.finditer(flat)):
                return 'second_programme'
            key = _SQUEEZE_OUT.sub('', flat.upper())
            if any(w in key for w in NOT_DEGREE) or _PRA.search(flat.upper()):
                return 'second_programme'
            for m in _LATER_DATE.finditer(flat):
                if _ymd(_one_space(m.group(1))) is None or _ymd(_one_space(m.group(1))) != _ymd(printed_date):
                    return 'second_date'
    return ''


#: S-visible 2 (`pdf_ink.ink_missing`): the field -> ink label for every value read off page 1.
INK_LABELS = {'candidate_name': 'v:name', 'candidate_nric': 'v:nric', 'programme': 'v:programme',
              'intake': 'v:intake', 'reporting_date': 'v:date', 'offer_date': 'v:offer_date'}
#: Read from the page but optional: ink-checked only when read (UM prints "RUJUK LAMPIRAN" for the date).
INK_OPTIONAL = ('reporting_date', 'offer_date')
#: The fields `read_um` returns that are not read off the page (constants and the reader's own labels).
NOT_PRINTED = ('candidate_nric_source', 'programme_code', 'institution', 'campus', 'issuer', 'stream',
               'reporting_date_label', 'reporting_venue')


def um_ink_targets(fields, page1_layout) -> tuple:
    """(phrases, values) a UM lock relied on, as (label, text) pairs: the owner phrases page 1's layout shows
    (``p<n>``) and every field read off the page (`INK_LABELS`; the IC and the reporting date as printed). A
    required value left blank stays in, so the ink check refuses it."""
    from .offer_owner_words import owner_ink_targets
    f = fields if isinstance(fields, dict) else {}
    lines = _uum_lines(page1_layout)
    at = _um_title_at(lines)
    printed_ic = _um_head(lines, at)[2] if at >= 0 else ''
    printed = {**{k: f.get(k) or '' for k in INK_LABELS}, 'candidate_nric': printed_ic,
               'reporting_date': um_printed_date(page1_layout)}
    return owner_ink_targets(LANE, page1_layout, INK_LABELS, INK_OPTIONAL, printed)
