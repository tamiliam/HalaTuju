"""The three family readers of the Exact offer read — STPM, matriculation, polytechnic (offer exact-read S5).

Moved VERBATIM out of `offer_parse.py` (2026-11-03, a moves-only step: that file reached its 560-line
budget). The shared machinery — the block reader, the shapes, the date and name rules, the exit guards —
stays in `offer_parse`; `offer_parse.diagnose` reads `_FAMILY` from here.
"""
from __future__ import annotations

import re

from .offer_parse import (_IC, _NOT_WRAP, _STREAM_SHAPE, _TITLE, _date_shape, _first_ic_anywhere, _has,
                          _label, _name_ok, _norm_nric, _read_block, _starts, first_date)


# ── STPM ─────────────────────────────────────────────────────────────────────────────────────
# Section 2 prints SIX numbered labels (2.1-2.6: Bidang, Pusat Tingkatan Enam, Tarikh Lapor Diri,
# Masa Lapor Diri, Dokumen diperlukan, Pakaian). 1.3.0 knew three, so the value block started one
# label too early and "2.4." / "Masa Lapor Diri" landed in stream / institution (class A, S5).
_STPM_BLOCK = [
    ('stream', _label(r'Bidang'), _STREAM_SHAPE),
    ('institution', _label(r'Pusat\s+Tingkatan\s+Enam'),
     _starts(r'KOLEJ|SEKOLAH|SMK|SMJK|SMKA|SM|SEK\.?|MAKTAB|PUSAT\s+TINGKATAN')),
    ('reporting', _label(r'Tarikh\s+(?:Me)?lapor\s+Diri'), _date_shape),       # "Melapor" on some
    ('time', _label(r'Masa\s+(?:Me)?lapor\s+Diri'), _has(r'^\s*\d{1,2}\s*[:.]\s*\d{2}')),
]
_STPM_FILLERS = [_label(r'Dokumen\s+diperlukan'), _label(r'\(?Asal\s+dan\s+salinan\)?'), _label(r'Pakaian')]
_STPM_GLUE = [r'No\.?\s*Kad\s*Pengenalan',
              r'\d\.\d\.?\s*(?:Bidang|Pusat\s+Tingkatan|Tarikh\s+(?:Me)?lapor|Masa\s+(?:Me)?lapor|Dokumen|Pakaian)\b']


def _identity_stpm(lines):
    name = ''
    for i, ln in enumerate(lines):
        m = re.match(r'\s*Nama\s*:?\s*(.*)', ln, re.IGNORECASE)
        if m:
            name = m.group(1).strip(' :') or next((x.strip() for x in lines[i + 1:] if x.strip()), '')
            break
    for ln in lines:
        m = re.match(r'\s*No\.?\s{0,3}Kad\s{0,3}Pengenalan[ \t]{0,3}:?[ \t]{0,3}' + _IC + r'(?!\d)', ln, re.IGNORECASE)
        if m:
            return name, _norm_nric(m.group(1)), 'label'
    return name, _first_ic_anywhere(lines), 'other'


def _parse_stpm(lines, up):
    m = re.search(r'TINGKATAN\s+ENAM\s+SEMESTER\s+(\d)\s+TAHUN\s+(20\d{2})', up)
    block = _read_block(lines, _STPM_BLOCK, _STPM_FILLERS, wraps=('institution',))
    reporting = first_date(block.get('reporting', ''))
    return {
        'programme': f'Tingkatan Enam Semester {m.group(1)}' if m else '',
        'institution': block.get('institution', ''), 'stream': block.get('stream', ''),
        'intake': f'SEMESTER {m.group(1)} TAHUN {m.group(2)}' if m else '',
        'reporting_date': reporting, 'reporting_date_label': 'Tarikh Lapor Diri' if reporting else '',
        'issuer': 'Sektor Operasi Sekolah, Kementerian Pendidikan Malaysia',
    }


# ── Matriculation ────────────────────────────────────────────────────────────────────────────
# ⚠ THE JURUSAN KEY IS 'stream', NOT 'programme'. The Gemini schema (vision.py) states it plainly:
# *"stream" = the Form-Six "Bidang" ... OR the matriculation "Jurusan"*. This parser used to file
# the Jurusan under 'programme' and return NO 'stream' key at all, so a matriculation letter read
# HERE reached the pathway check with its stream axis empty, while the same letter read by Gemini
# reached it populated. Measured on production 2026-09-10: 26/26 Gemini-read matric letters carried
# a stream; 0/4 parser-read ones did. One letter, two readers, two different homes for one fact.
_MATRIC_BLOCK = [
    ('stream', _label(r'Jurusan'), _STREAM_SHAPE),
    # The engineering matriculation letter adds "Aliran: KEJURUTERAAN AWAM" under the Jurusan.
    ('aliran', _label(r'Aliran'), _has(r'^[A-Z][A-Z &]+$')),
    ('duration', _label(r'Tempoh\s+Pengajian'), _has(r'\bSEMESTER\b|\bBULAN\b|\bTAHUN\b')),
    ('institution', _label(r'Kolej'), _starts(r'KOLEJ\s+MATRIKULASI')),
    ('online_reg', _label(r'Pendaftaran\s+dalam\s+talian'), _date_shape),
    ('reporting', _label(r'Tarikh\s+Kemasukan\s+ke\s+kolej'), _date_shape),
    ('fee', _label(r'Yuran\s+Pendaftaran'), _starts(r'RM')),
]
#: The glued text layer (class B): break before each label, the IC label and the matric number.
_MATRIC_GLUE = [r'K\s*/\s*P\s*:', r'NO\.?\s*MATRIK\b', r'Jurusan\s*:', r'Aliran\s*:', r'Tempoh\s+Pengajian\s*:',
                r'(?<![Kk]e )Kolej\s*:', r'Pendaftaran\s+dalam\s+talian\s*:', r'Tarikh\s+Kemasukan\s+ke\s+kolej\s*:',
                r'Yuran\s+Pendaftaran\s*:', r'Tarikh\s*:', r'Rujukan\s+Kami', r'TAWARAN\s+KEMASUKAN', r'Saudara']


#: A word that sits above "K/P:" on a letter but is never a name: a state, a stamp, an office (review M3).
_NOT_NAME_LINE = re.compile(r'^(?:SEGERA|SULIT|RAHSIA|TERHAD|KPM|PERSENDIRIAN|PERINGATAN|MAKLUMAN)$')
#: A name line that ends on its parentage marker continues on the next line ("…HAKIM BIN" / "ABDULLAH").
_ENDS_MARKER = re.compile(r'\b(?:BIN|BINTI|BT|BTE|A\s*/\s*[LP]|ANAK|AK)$', re.IGNORECASE)


def _identity_matric(lines):
    """The IC from the "K/P:" line; the name is the line DIRECTLY above it, in the strict name shape
    (no parentage marker needed: a one-word, Chinese or East-Malaysian name has none — class C).
    Review M3: a state / stamp word there is no name; a name wrapped after its parentage marker is
    joined ("…HAKIM BIN" + "ABDULLAH"); a name line that itself ENDS on the marker (its tail lost) is
    no name. A wrong name is a false wrong-person red, so every doubt reads no name (→ no lock)."""
    for i, ln in enumerate(lines):
        m = re.match(r'\s*K\s{0,3}/\s{0,3}P[ \t]{0,3}:?[ \t]{0,3}' + _IC + r'(?!\d)', ln, re.IGNORECASE)
        if m:
            above = [x.strip() for x in lines[:i] if x.strip()][-2:]
            name = above[-1] if above else ''
            if len(above) == 2 and _ENDS_MARKER.search(above[0]) and _name_ok(above[0]):
                name = f'{above[0]} {name}'
            ok = (_name_ok(name) and not _ENDS_MARKER.search(name)
                  and not all(_NOT_WRAP.match(w) or _NOT_NAME_LINE.match(w) for w in name.upper().split()))
            return (name if ok else ''), _norm_nric(m.group(1)), 'label'
    return '', _first_ic_anywhere(lines), 'other'


def _parse_matric(lines, up):
    sm = re.search(r'SESI\s{0,3}(20\d{2})\s{0,3}/\s{0,3}(20\d{2})', up)
    block = _read_block(lines, _MATRIC_BLOCK)
    jurusan = block.get('stream', '')
    # ⚠ THE BRACKET IS OURS, NOT THE LETTER'S. No KPM matriculation letter prints "Program
    # Matrikulasi (SAINS)" — this f-string builds it, and the pathway check then reads whatever is
    # inside the bracket as part of the programme NAME. It is kept because FIVE call sites derive
    # the matric track from this string (`offer_pathway.parse_matric_track`, via services.py:1549 +
    # :1846, offer_pathway.py:562 and the backfill command). The Jurusan is ALSO emitted as
    # `stream` above, which is its proper home; retiring the bracket is a separate, measurable
    # change and must not be done here as a tidy-up (decision 2026-09-10, kept in S5).
    reporting = first_date(block.get('reporting', ''))
    return {
        'programme': f'Program Matrikulasi ({jurusan})' if jurusan else '',
        'institution': block.get('institution', ''), 'stream': jurusan,
        'intake': f'SESI {sm.group(1)}/{sm.group(2)}' if sm else '',
        'reporting_date': reporting, 'reporting_date_label': 'Tarikh Kemasukan ke kolej' if reporting else '',
        'issuer': 'Bahagian Matrikulasi, Kementerian Pendidikan Malaysia',
    }


# ── Polytechnic ──────────────────────────────────────────────────────────────────────────────
_POLY_PROGRAMME_SHAPE = (lambda v: bool(re.search(r'[A-Za-z]{3}', v or '')) and not _date_shape(v)
                         and not re.match(r'\s*(?:POLITEKNIK|KOLEJ|RM\b|\d+\s+SEMESTER|SEPENUH|SEPARUH)', v, re.I))
_POLY_BLOCK = [
    ('programme', _label(r'Program'), _POLY_PROGRAMME_SHAPE),
    ('mode', _label(r'Mod\s+Pengajian'), _has(r'\bMASA\b')),
    ('institution', _label(r'Institusi'), _starts(r'POLITEKNIK|KOLEJ\s+KOMUNITI')),
    ('duration', _label(r'Tempoh\s+Pengajian'), _has(r'\bSEMESTER\b|\bBULAN\b|\bTAHUN\b')),
    ('session', _label(r'Sesi'), _has(r'20\d{2}\s*/\s*20\d{2}')),
    # "Tarikh dan Masa Daftar" (1.3.0 knew no other wording) / "Tarikh Daftar" / "Tarikh dan Masa
    # Pendaftaran", or "Tarikh dan Masa" with "Daftar" on the next line — class E: an unknown wording
    # shifted the block. Never a bare "Tarikh" (that is the issue date).
    ('reporting', _label(r'Tarikh\s+dan\s+Masa(?:\s+(?:Daftar|Pendaftaran))?|Tarikh\s+(?:Daftar|Pendaftaran)'),
     _date_shape),
]
_POLY_FILLERS = [_label(r'Daftar')]
#: A polytechnic programme printed with its code in front ("DKA - DIPLOMA KEJURUTERAAN AWAM") → the
#: code goes to `programme_code` (S4's shape; `offer_course_match.programme_line` reads it back). A
#: photo's OCR can drop the dash ("DKK DIPLOMA …"): a code then still counts before a programme word.
_POLY_CODE = re.compile(r'^\s*([A-Z][A-Z0-9]{1,5})(?:\s*[-–]\s*(?=[A-Z(])|\s+(?=(?:DIPLOMA|SIJIL|ASASI|IJAZAH)\b))')
#: "SESI I : 2026/2027", "SESII: …", "SESI 1:2026/2027" (a photo's OCR reads the Roman I as 1 — the
#: letters print Roman, class D) → "SESI I : 2026/2027". No numeral → "SESI 2026/2027".
#: An OCR'd "l" for the Roman I ("SESIl") reads as I too.
_POLY_SESSION = re.compile(r'SESI\s{0,3}([IL1]{1,3}|2|3)?\s{0,3}:?\s{0,3}(20\d{2})\s{0,3}/\s{0,3}(20\d{2})')


def _identity_poly(lines):
    """'NAME (IC)' — the line above the title, in the strict name shape (no marker needed, class C)."""
    for ln in lines:
        if _TITLE['polytechnic'].search(ln.upper()):
            break
        m = re.match(r'\s*(\S.*?)[ \t]{0,3}\([ \t]{0,3}' + _IC + r'[ \t]{0,3}\)\s*$', ln)
        if m and _name_ok(m.group(1)):
            return m.group(1).strip(), _norm_nric(m.group(2)), 'label'
    return '', _first_ic_anywhere(lines), 'other'


def _parse_poly(lines, up):
    sm = _POLY_SESSION.search(up)
    num = (sm.group(1) or '') if sm else ''
    roman = {'2': 'II', '3': 'III'}.get(num, 'I' * len(num))
    years = f'{sm.group(2)}/{sm.group(3)}' if sm else ''
    intake = (f'SESI {roman} : {years}' if roman else f'SESI {years}') if sm else ''
    block = _read_block(lines, _POLY_BLOCK, _POLY_FILLERS, wraps=('programme',))
    programme, code = block.get('programme', ''), ''
    cm = _POLY_CODE.match(programme)
    if cm:
        code, programme = cm.group(1), programme[cm.end():].strip()
    reporting = first_date(block.get('reporting', ''))
    return {
        'programme': programme, 'programme_code': code,
        'institution': block.get('institution', ''), 'intake': intake,
        'reporting_date': reporting, 'reporting_date_label': 'Tarikh dan Masa Daftar' if reporting else '',
        'issuer': 'Jabatan Pendidikan Politeknik dan Kolej Komuniti',
    }


_FAMILY = {
    'stpm': (_parse_stpm, _identity_stpm, _STPM_GLUE),
    'matriculation': (_parse_matric, _identity_matric, _MATRIC_GLUE),
    'polytechnic': (_parse_poly, _identity_poly, ()),
}
