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

* title — "TAWARAN KEMASUKAN ..." at a LINE START; a cancellation, deferral, rejection, withdrawal,
  appeal or reply word (PEMBATALAN, PENANGGUHAN, PENOLAKAN, TARIK BALIK, RAYUAN, MAKLUMBALAS) at or
  above the title refuses (``not_an_offer``).
* institution — the title only, never a hostel line; the hostel / venue goes to ``reporting_venue``.
* intake — "SESI ..." from the title.
* IC — ONLY from the "No. Kad Pengenalan" label (same line, or the next lines that hold nothing but
  the student number / a colon); never the first IC anywhere; any other IC on the page refuses.
* name — the line straight after the ONE offer-date line ("Tarikh : 15 Ogos 2026"; two such lines
  above the title — a stamp's date — read no name), by the strict shared name rules; a certifier's or
  officer's line (PENDAFTAR, CANSELOR, NAIB, TIMBALAN, PEJABAT ...) is never a name, and a name-like
  next line that is not an address line (no address word) may be a wrapped name: no name.
* programme — from the label block between the title and the sentence: the "Program : ..." line (or,
  in a scan, the degree line after a bare "Program" label; a value may wrap onto ONE next line). It
  must AGREE, letter for letter, with the sentence "... untuk mendapat <programme> dan sebanyak ...";
  any value there that disagrees, or no label at all, reads no programme. It starts "Sarjana Muda" /
  "Ijazah Sarjana Muda" / "Diploma". The UPU code ("UH0000001") is extra evidence only, read with a
  glued-safe pattern bounded on the left (``offer_course_match.COURSE_CODE_RE`` misses a glued code).
* reporting date — the first date after "Tarikh Lapor Diri"; a range ("28 - 29 September", "28
  September - 1 Oktober 2031", "... hingga ...") gives its FIRST day, with its own month or the end's,
  the year borrowed from the end; a range that cannot be placed reads no date. Sane against the
  intake and the offer date.
* campus — only from the "Kampus" label (same line, or the line after a bare label) below the title,
  and only a value in the closed list of UMS campuses.

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
#: The title STARTS its line (whitespace normalised): "PEMBATALAN TAWARAN KEMASUKAN ..." is not an offer.
_TITLE = re.compile(r'^' + _TITLE_WORDS + r'\s{0,3},?\s{0,3}(SESI\s{1,3}[0-9IV]{1,3}\s{0,2}-\s{0,2}20\d{2}\s{0,2}/\s{0,2}20\d{2})'
                    r'\s*$', re.IGNORECASE)
_STATUS = re.compile(r'SURAT\s{1,3}PENGESAHAN', re.IGNORECASE)
#: A letter that withdraws, defers, refuses or answers an offer (review round 1): any of these words above
#: the body (the head and the title line) means it is not the offer itself, so it never locks.
_NOT_AN_OFFER = re.compile(r'\b(?:PEMBATALAN|PENANGGUHAN|PENOLAKAN|TARIK\s{1,3}BALIK|RAYUAN|MAKLUM\s{0,3}BALAS)\b',
                           re.IGNORECASE)
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
#: A UPU programme code, glued-safe ("Program UH0000001Fakulti", "Fakulti:UH0000001Bayaran"): U + a letter
#: + seven digits, no 8th, and no digit or capital letter just before it ("1UH0000001", "XUH0000001": no code).
_UPU_ANY = re.compile(r'U[A-Z]\d{7}(?!\d)')
_UPU_CODE = re.compile(r'(?<![0-9A-Z])U[A-Z]\d{7}(?!\d)')
#: Layout text pads words with long space runs; each run is bounded (no polynomial backtracking).
_SENTENCE = re.compile(r'untuk\s{1,80}mendapat\s{1,80}(\S.{4,400}?)\s{1,80}dan\s{1,80}sebanyak', re.IGNORECASE | re.DOTALL)
_DEGREE = re.compile(r'^(?:IJAZAH\s)?SARJANA\sMUDA\s.+\sDENGAN\sKEPUJIAN(?:\s\(.+\))?$|^DIPLOMA\s', re.IGNORECASE)
#: The programme's own label line ("Program : X"; a scanned letter prints "Program" alone, the value elsewhere).
_PROGRAM_LINE = re.compile(r'^Program\s{0,3}(?::\s{0,3}(.*))?$', re.IGNORECASE)
#: A line that starts a programme name (a scanned letter's programme value line).
_DEGREE_START = re.compile(r'^(?:IJAZAH\s)?SARJANA\sMUDA\b|^DIPLOMA\b', re.IGNORECASE)
#: A range separator between two date parts: a dash or "(se)hingga" with a digit after it.
_RANGE_SEP = re.compile(r'[0-9A-Za-z]\s{0,3}(?:[-–]|\b(?:SE)?HINGGA\b)\s{0,3}\d', re.IGNORECASE)
#: "28-29 September 2024", "28 September - 1 Oktober 2031", "30 Disember 2031 hingga 2 Januari 2032".
_DAY_RANGE = re.compile(r'(?<!\d)(\d{1,2})(?:\s{1,3}(' + _MALAY_MONTH + r'))?(?:\s{1,3}(20\d{2}))?\s{0,3}'
                        r'(?:[-–]|(?:SE)?HINGGA)\s{0,3}(\d{1,2})\s{1,3}(' + _MALAY_MONTH + r')\s{1,3}(20\d{2})',
                        re.IGNORECASE)
_REPORT_LABEL = re.compile(r'Tarikh\s{1,3}Lapor\s{1,3}Diri', re.IGNORECASE)
_VENUE = re.compile(r'^Tempat(?:\s{0,3}/\s{0,3}Kolej|\s{1,3}Lapor\s{1,3}Diri)?\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_CAMPUS = re.compile(r'^Kampus\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_CAMPUS_LABEL = re.compile(r'^Kampus\s{0,3}:?$', re.IGNORECASE)
_SESI_YEARS = re.compile(r'(20\d{2})\s{0,2}/\s{0,2}(20\d{2})')
#: An address word: a line holding one is the address under the name, never the name's wrapped tail.
_ADDRESS_WORD = re.compile(r'\b(?:KG|KAMPUNG|JALAN|JLN|LORONG|LRG|TAMAN|TMN|LOT|BATU|KOTA|BANDAR|PEKAN|RUMAH|BLOK|'
                           r'PETI|SURAT|PERUMAHAN|LADANG|ESTET|SABAH|SARAWAK|LABUAN|JOHOR|KEDAH|KELANTAN|MELAKA|'
                           r'PAHANG|PERAK|PERLIS|PULAU|PINANG|SELANGOR|TERENGGANU|SEMBILAN|KUALA|LUMPUR|PUTRAJAYA)\b',
                           re.IGNORECASE)
#: Two columns on one layout line (the name must stand alone).
_GAP = re.compile(r'\S\s{3,}\S')
#: A certifier's stamp ("SALINAN DISAHKAN BENAR", with its OCR misreads) or an officer's title / office
#: ("PENDAFTAR", "TIMBALAN NAIB CANSELOR", "PEJABAT ...") — never a name.
_STAMP = re.compile(r'\b(?:SALINAN|DISAHKAN|DISALKAN|BENAR|BEHAR|SEBENAR|COP|PEGAWAI|PENGETUA|SAH|PENDAFTAR|'
                    r'CANSELOR|NAIB|TIMBALAN|PEJABAT)\b', re.IGNORECASE)


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
    """(offer date, name) from the head above the title: the name is the line right after the date. Both
    '' when the head prints more than one "Tarikh" line (a stamp's own date: which one is the offer's?).
    The name is '' when the line after it is name-like too (a wrapped name) and not the IC label."""
    dated = [ln for ln in lines[:title_at] if _OFFER_DATE.match(_one_space(ln)) or _OFFER_LABEL.match(_one_space(ln))]
    if len(dated) > 1:
        return '', ''
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
        after = _one_space(lines[at + 1]) if at + 1 < title_at else ''
        if (_GAP.search(raw) or _blocked(name) or _STAMP.search(name) or not _name_ok(name)
                or _ENDS_MARKER.search(name) or (_name_ok(after) and not _ADDRESS_WORD.search(after))):
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


def _tidy(s: str) -> str:
    return re.sub(r'\s+([)-])', r'\1', re.sub(r'([(-])\s+', r'\1', s))


def _ums_programme(lines, title_at):
    """The programme from its LABEL block (review round 1): the "Program : X" value (X may wrap onto the
    next line), or, in a scanned letter whose "Program" label stands alone, the line(s) that start a
    programme name ("Sarjana Muda ...", "Diploma ...") between the title and the sentence. It must AGREE,
    letter for letter, with the "untuk mendapat <programme> dan sebanyak" sentence, whose own lines are
    never a source. '' when there is no Program label, no value, or ANY value line that disagrees."""
    joined = '\n'.join(lines)
    found = list(_SENTENCE.finditer(joined))
    said = {_alnum_key(m.group(1)) for m in found}
    if len(said) != 1 or not next(iter(said)):
        return ''
    want = next(iter(said))
    stop = min(joined.count('\n', 0, m.start()) for m in found)     # the label block ends where the sentence starts
    labelled, values = False, set()
    for i in range(title_at + 1, stop):
        one = _one_space(lines[i])
        lab = _PROGRAM_LINE.match(one)
        labelled = labelled or bool(lab)
        value = _one_space(lab.group(1) or '') if lab else (one if _DEGREE_START.match(one) else '')
        if not value:
            continue
        nxt = _one_space(lines[i + 1]) if i + 1 < stop else ''
        hit = [c for c in (value, f'{value} {nxt}' if nxt else '') if c and _alnum_key(c) == want]
        if not hit:
            return ''                            # a Program value that is not the sentence's programme
        values.add(_tidy(hit[0]))
    values = {v for v in values if _DEGREE.match(v)}
    return next(iter(values)) if labelled and len(values) == 1 else ''


def _range_start(part: str) -> str:
    """A date range's FIRST day ("28-29 September 2024", "28 September - 1 Oktober 2031" -> 28 September
    2031): its own month, or the end's when it prints only a day; the end's year when it prints none.
    '' unless that first day reads and is not after the end (a borrowed month or year that does not fit)."""
    from .offer_parse import house_date
    from .pathway_engine import parse_reporting_date
    m = _DAY_RANGE.search(part)
    if not m or (m.group(3) and not m.group(2)):
        return ''
    first = f'{m.group(1)} {m.group(2) or m.group(5)} {m.group(3) or m.group(6)}'
    a = parse_reporting_date(house_date(first))
    b = parse_reporting_date(house_date(f'{m.group(4)} {m.group(5)} {m.group(6)}'))
    return first if (a is not None and b is not None and a <= b) else ''


def _reporting_date(lines):
    """The first date in the six lines after the "Tarikh Lapor Diri" label (label, colon and venue lines
    sit between them in a scanned letter); '' when the label is absent or printed twice. A dash or
    "hingga" between two dates is a range: its first day (`_range_start`), or no date at all."""
    at = [i for i, ln in enumerate(lines) if _REPORT_LABEL.search(ln)]
    if len(at) != 1:
        return ''
    i = at[0]
    tail = _REPORT_LABEL.split(lines[i], maxsplit=1)[1]
    for part in [tail] + lines[i + 1:i + 7]:
        got = first_date(part)
        if not got:
            continue
        return _range_start(part) if _RANGE_SEP.search(part) else got
    return ''


def _same_line(pattern, lines):
    vals = {_one_space(m.group(1)) for ln in lines for m in [pattern.match(_one_space(ln))] if m}
    return next(iter(vals)) if len(vals) == 1 else ''


def _campus(lines, title_at):
    """The campus from the "Kampus" label below the title: "Kampus : X", or X on the line after a bare
    "Kampus" label (a scanned letter), when X is exactly one UMS campus. Never a line elsewhere (an address
    line "Labuan" is not the campus); '' when the label is absent or names two values."""
    vals = set()
    for i in range(title_at + 1, len(lines)):
        one = _one_space(lines[i])
        m = _CAMPUS.match(one)
        if m:
            vals.add(_one_space(m.group(1)).lower())
        elif _CAMPUS_LABEL.match(one) and i + 1 < len(lines):
            vals.add(_one_space(lines[i + 1]).lower())
    named = {c for c in CAMPUSES for v in vals if v == c.lower()}
    return next(iter(named)) if len(vals) == 1 and len(named) == 1 else ''


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
    if any(_NOT_AN_OFFER.search(ln) for ln in lines[:title_at + 1]):
        return None, 'not_an_offer'
    offer_date, name = _offer_date_and_name(lines, title_at)
    nric = _ic(lines, title_at)
    codes, bounded = _UPU_ANY.findall(source), _UPU_CODE.findall(source)
    code = codes[0] if len(set(codes)) == 1 and len(bounded) == len(codes) else ''   # any unbounded one: none
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': _ums_programme(lines, title_at), 'programme_code': code,
        'institution': INSTITUTION, 'campus': _campus(lines, title_at), 'stream': '', 'intake': intake,
        'reporting_date': house_date(_reporting_date(lines)), 'reporting_date_label': 'Tarikh Lapor Diri',
        'reporting_venue': _same_line(_VENUE, lines), 'offer_date': offer_date, 'issuer': ISSUER,
    }
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _sane(fields):
        return fields, 'dates_not_sane'
    return fields, ''
