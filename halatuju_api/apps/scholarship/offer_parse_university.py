"""Deterministic read of the Universiti Malaysia Sabah (UMS) offer letter — OCR-first S1 (2026-11-19).

The first UNIVERSITY family of the Exact read (`offer_parse.diagnose` hands a UMS letter here). The
UMS letter is one fixed template ("TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH, SESI ..."), seen
two ways:

* a digital PDF: read from page 1's LAYOUT text (`pdf_pages.pdf_page1_layout`), where each label and
  its value share a line and the name stands alone under the offer date. The plain text layer glues
  the IC, the student number, the name and the address into one run, so a name read from it could
  swallow an address word: a text-layer letter WITHOUT its layout text never locks here;
* a scanned letter (Vision OCR): one item per line, the blocks often out of order — so every field
  below is read by a rule that does not depend on the order of the label block.

CONSERVATIVE (owner rule: "the visible page always judges"; a wrong fact is worse than the AI):
every field has ONE source, and any doubt returns no lock, so the letter goes to the AI as before.

* institution — the title only, never a hostel line; the hostel / venue goes to ``reporting_venue``.
* intake — "SESI ..." from the title.
* IC — ONLY from the "No. Kad Pengenalan" label (same line, or the next lines that hold nothing but
  the student number / a colon); never the first IC anywhere; any other IC on the page refuses.
* name — the line straight after the offer-date line ("Tarikh : 15 Ogos 2026"), by the strict
  shared name rules; a certifier's stamp line is never a name.
* programme — the sentence "... untuk mendapat <programme> dan sebanyak ..." must AGREE, letter for
  letter, with the programme as printed on its own line ("Program : ..."), and start "Sarjana Muda" /
  "Ijazah Sarjana Muda" / "Diploma". The UPU code ("UH0000001") is extra evidence only, read with a
  glued-safe pattern (``offer_course_match.COURSE_CODE_RE`` misses a glued code).
* reporting date — the first date after "Tarikh Lapor Diri"; sane against the intake and offer date.
* campus — only a value in the closed list of UMS campuses.

Status letters ("SURAT PENGESAHAN PELAJAR") never lock. Pure; never raises on text input.
"""
from __future__ import annotations

import re

from .offer_parse import _IC, _IC_END, _MALAY_MONTH, _decimal_digits, _name_ok, _norm_nric, first_date
from .offer_parse_families import _ENDS_MARKER, _blocked

#: Recorded on a rules read (`rules_lane`) — the lane switch (`offer_exact.ocr_first_lanes`) names it.
LANE = 'ua:UMS'
INSTITUTION = 'Universiti Malaysia Sabah'
ISSUER = INSTITUTION                      # the letterhead's university (the answers' own convention)
#: The campuses a UMS letter prints ("Kampus : Kota Kinabalu"). A value outside this list is not read.
CAMPUSES = ('Kota Kinabalu', 'Antarabangsa Labuan', 'Labuan', 'Sandakan')

_TITLE_WORDS = r'TAWARAN\s{1,3}KEMASUKAN\s{1,3}KE\s{1,3}UNIVERSITI\s{1,3}MALAYSIA\s{1,3}SABAH'
_DETECT = re.compile(_TITLE_WORDS, re.IGNORECASE)
_TITLE = re.compile(_TITLE_WORDS + r'\s{0,3},?\s{0,3}(SESI\s{1,3}[0-9IV]{1,3}\s{0,2}-\s{0,2}20\d{2}\s{0,2}/\s{0,2}20\d{2})'
                    r'\s*$', re.IGNORECASE)
_STATUS = re.compile(r'SURAT\s{1,3}PENGESAHAN', re.IGNORECASE)
_DATE = r'\d{1,2}\s{1,3}' + _MALAY_MONTH + r'\s{1,3}20\d{2}'
#: The offer-date line ("Tarikh : 15 Ogos 2026"; Vision reads "Tankh"), or the label alone with the
#: date on the next line (":08 September 2025").
_OFFER_DATE = re.compile(r'^Ta[rn][il1]?[kc]h\s{0,3}:?\s{0,3}(' + _DATE + r')$', re.IGNORECASE)
_OFFER_LABEL = re.compile(r'^Ta[rn][il1]?[kc]h\s{0,3}:?$', re.IGNORECASE)
_DATE_ONLY = re.compile(r'^:?\s{0,3}(' + _DATE + r')$', re.IGNORECASE)
_IC_LABEL = re.compile(r'No\.?\s{0,3}Kad\s{1,3}Pengenalan\s{0,3}:?\s{0,3}(.*)$', re.IGNORECASE)
_IC_RE = re.compile(r'(?<!\d)' + _IC + _IC_END)
_STUDENT_NO = re.compile(r'^:?\s{0,3}[A-Z][A-Z0-9]\d{8}$')     # "BK00000001" (OCR may read a letter as a digit)
#: The label's own remainder when it is ONLY the IC, which the layout text may split ("01   0203145678").
_IC_ONLY = re.compile(r'^:?[\d 	-]{12,40}$')
#: A UPU programme code, glued-safe ("Program UH0000001Fakulti"): U + a letter + seven digits, no 8th.
_UPU_CODE = re.compile(r'U[A-Z]\d{7}(?!\d)')
#: Layout text pads words with long space runs; each run is bounded (no polynomial backtracking).
_SENTENCE = re.compile(r'untuk\s{1,80}mendapat\s{1,80}(\S.{4,400}?)\s{1,80}dan\s{1,80}sebanyak', re.IGNORECASE | re.DOTALL)
_DEGREE = re.compile(r'^(?:IJAZAH\s)?SARJANA\sMUDA\s.+\sDENGAN\sKEPUJIAN(?:\s\(.+\))?$|^DIPLOMA\s', re.IGNORECASE)
_PROGRAM_LABEL = re.compile(r'^Program\s{0,3}:\s{0,3}', re.IGNORECASE)
_DASH = re.compile(r'\d\s{0,2}[-–]\s{0,2}\d')
_DASH_RANGE = re.compile(r'(?<!\d)(\d{1,2})\s{0,2}[-–]\s{0,2}\d{1,2}\s{1,3}(' + _MALAY_MONTH + r')\s{1,3}(20\d{2})', re.IGNORECASE)
_FULL_RANGE = re.compile(r'(' + _DATE + r')\s{0,3}[-–]\s{0,3}' + _DATE, re.IGNORECASE)
_REPORT_LABEL = re.compile(r'Tarikh\s{1,3}Lapor\s{1,3}Diri', re.IGNORECASE)
_VENUE = re.compile(r'^Tempat(?:\s{0,3}/\s{0,3}Kolej|\s{1,3}Lapor\s{1,3}Diri)?\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_CAMPUS = re.compile(r'^Kampus\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_SESI_YEARS = re.compile(r'(20\d{2})\s{0,2}/\s{0,2}(20\d{2})')
#: Two columns on one layout line (the name must stand alone).
_GAP = re.compile(r'\S\s{3,}\S')
#: A certifier's stamp ("SALINAN DISAHKAN BENAR", with its OCR misreads) — never a name.
_STAMP = re.compile(r'\b(?:SALINAN|DISAHKAN|DISALKAN|BENAR|BEHAR|SEBENAR|COP|PEGAWAI|PENGETUA|SAH)\b', re.IGNORECASE)


def is_ums(up: str) -> bool:
    """The UMS offer title anywhere in the (upper-cased) text — `offer_parse._detect`'s fourth family."""
    return bool(_DETECT.search(up or ''))


def _text_lines(text: str) -> list:
    return [ln.strip() for ln in (text or '').splitlines() if ln.strip()]


def _one_space(s: str) -> str:
    return ' '.join((s or '').split())


def _alnum_key(s: str) -> str:
    return re.sub(r'[^A-Z0-9()]', '', (s or '').upper())


def _title(lines):
    """(index, intake) of the one title line; (-1, '') when absent or printed twice differently."""
    hits = [(i, _one_space(m.group(1)).upper()) for i, ln in enumerate(lines) for m in [_TITLE.search(_one_space(ln))] if m]
    intakes = {re.sub(r'\s', '', v) for _i, v in hits}
    if len(intakes) != 1:
        return -1, ''
    i, intake = hits[0]
    return i, re.sub(r'\s{0,2}-\s{0,2}', '-', re.sub(r'\s{0,2}/\s{0,2}', '/', intake))


def _offer_date_and_name(lines, title_at):
    """(offer date, name) from the head above the title: the name is the line right after the date."""
    for i, ln in enumerate(lines[:title_at]):
        one = _one_space(ln)
        m = _OFFER_DATE.match(one)
        at = i + 1
        if not m and _OFFER_LABEL.match(one) and at < title_at:
            m = _DATE_ONLY.match(_one_space(lines[at]))
            at += 1
        if not m:
            continue
        raw = lines[at] if at < title_at else ''
        name = _one_space(raw)
        if (_GAP.search(raw) or _blocked(name) or _STAMP.search(name) or not _name_ok(name)
                or _ENDS_MARKER.search(name)):
            name = ''
        return _one_space(m.group(1)), name
    return '', ''


def _ic(lines, title_at):
    """The IC printed by the "No. Kad Pengenalan" label (same line, or the next lines holding only a
    colon / the student number). '' unless exactly one, and no OTHER IC in the letter's head (above
    the title; a certifier's stamp lower down may carry the certifier's own IC — never read)."""
    found = set()
    for i, ln in enumerate(lines[:title_at]):
        m = _IC_LABEL.search(ln)
        if not m:
            continue
        rest = m.group(1).strip()
        if _IC_ONLY.match(rest) and len(_decimal_digits(rest)) == 12:
            found.add(_norm_nric(_decimal_digits(rest)))
            continue
        for part in [rest] + lines[i + 1:min(i + 4, title_at)]:
            part = part.strip()
            hit = _IC_RE.search(part)
            if hit:
                found.add(_norm_nric(hit.group(1)))
                break
            if part and part != ':' and not _STUDENT_NO.match(part):
                break
    head = {_decimal_digits(m.group(1)) for ln in lines[:title_at] for m in _IC_RE.finditer(ln)}
    if len(found) != 1 or not head <= {_decimal_digits(next(iter(found)))}:
        return ''
    return next(iter(found))


def _ums_programme(lines, text):
    """The programme as printed on its own line, only when the "untuk mendapat" sentence names the
    same programme letter for letter (it may wrap onto the next line)."""
    said = [_alnum_key(m.group(1)) for m in _SENTENCE.finditer(text)]
    if len(set(said)) != 1 or not said[0]:
        return ''
    want, hits = said[0], set()
    for i, ln in enumerate(lines):
        first = _one_space(_PROGRAM_LABEL.sub('', _one_space(ln)))
        for cand in (first, f'{first} {_one_space(lines[i + 1])}' if i + 1 < len(lines) else ''):
            if cand and _alnum_key(cand) == want and 'untuk mendapat' not in cand.lower():
                hits.add(re.sub(r'\s+([)-])', r'\1', re.sub(r'([(-])\s+', r'\1', cand)))
    hits = {h for h in hits if _DEGREE.match(h)}
    return next(iter(hits)) if len(hits) == 1 else ''


def _reporting_date(lines):
    """The first date in the six lines after the "Tarikh Lapor Diri" label (label, colon and venue lines
    sit between them in a scanned letter); '' when the label is absent or printed twice."""
    at = [i for i, ln in enumerate(lines) if _REPORT_LABEL.search(ln)]
    if len(at) != 1:
        return ''
    i = at[0]
    tail = _REPORT_LABEL.split(lines[i], maxsplit=1)[1]
    for part in [tail] + lines[i + 1:i + 7]:
        got = first_date(part)
        if not got:
            continue
        if not _DASH.search(part):
            return got
        whole = _FULL_RANGE.search(part)         # "12 September 2026 - 13 September 2026" -> the first
        if whole:
            return _one_space(whole.group(1))
        days = _DASH_RANGE.search(part)          # "28-29 September 2024" -> its FIRST day
        return f'{days.group(1)} {days.group(2)} {days.group(3)}' if days else ''   # any other range: no lock
    return ''


def _same_line(pattern, lines):
    vals = {_one_space(m.group(1)) for ln in lines for m in [pattern.match(_one_space(ln))] if m}
    return next(iter(vals)) if len(vals) == 1 else ''


def _campus(lines):
    """The campus from "Kampus : X" when X is a UMS campus; in a scanned letter (label and value on
    separate lines) a line that is exactly one campus name, when only one such campus is printed."""
    value = _same_line(_CAMPUS, lines)
    named = {c for c in CAMPUSES if value.lower() == c.lower()}
    if not value:
        named = {c for c in CAMPUSES for ln in lines if _one_space(ln).lower() == c.lower()}
    return next(iter(named)) if len(named) == 1 else ''


def _sane(fields) -> bool:
    """The reporting date falls in the intake's years, and the offer date is not after it."""
    from .pathway_engine import parse_reporting_date
    years = _SESI_YEARS.search(fields['intake'])
    report = parse_reporting_date(fields['reporting_date'])
    if not years or report is None or not (int(years.group(1)) <= report.year <= int(years.group(2))):
        return False
    offered = parse_reporting_date(fields['offer_date']) if fields['offer_date'] else None
    return offered is None or offered <= report


def read_ums(source: str):
    """``(fields, reason)`` for one UMS letter's text: ``fields`` is the read (None before the title
    holds), ``reason`` '' when every required field is read and sane, else why it must not lock."""
    from .offer_parse import house_date
    if _STATUS.search(source or ''):
        return None, 'status_letter'
    lines = _text_lines(source)
    title_at, intake = _title(lines)
    if title_at < 0:
        return None, 'no_title'
    offer_date, name = _offer_date_and_name(lines, title_at)
    nric = _ic(lines, title_at)
    codes = set(_UPU_CODE.findall(source))
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': _ums_programme(lines, source), 'programme_code': next(iter(codes)) if len(codes) == 1 else '',
        'institution': INSTITUTION, 'campus': _campus(lines), 'stream': '', 'intake': intake,
        'reporting_date': house_date(_reporting_date(lines)), 'reporting_date_label': 'Tarikh Lapor Diri',
        'reporting_venue': _same_line(_VENUE, lines), 'offer_date': offer_date, 'issuer': ISSUER,
    }
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _sane(fields):
        return fields, 'dates_not_sane'
    return fields, ''
