"""Deterministic parse of the STANDARDISED government offer letters (STPM / Matrikulasi /
Polytechnic) from OCR text — the 'Exact read' path for offers, replacing the Gemini image read
for these fixed-format issuers.

Background: an earlier text-based offer parser (doc_parse P5) was retired 2026-06-18 because the
offer's 2-D label/value layout doesn't survive flattened OCR. This retry is narrower + issuer-aware:
the IDENTITY (name/NRIC) and PATHWAY/INTAKE sit on same lines or in the title (easy), and the
info-block fields (institution, reporting date) are recovered per issuer — index-paired for the
clean single-line blocks (Matrikulasi/Polytechnic) or by targeted label search (STPM's multi-line
block). CONSERVATIVE: returns None (→ Gemini) unless it locks a coherent read incl. the fields the
verdict needs. University (ua_offer) offers vary and stay on Gemini. PISMP deferred (new format).

Output mirrors the Gemini offer schema fields read by pathway_engine.student_offer_check:
  candidate_name, candidate_nric, programme, institution, intake, reporting_date,
  reporting_date_label, offer_date, issuer.
Pure + deterministic; never raises.
"""
from __future__ import annotations

import re

_NRIC_RE = re.compile(r'\b(\d{6}[- ]?\d{2}[- ]?\d{4})\b')
_MALAY_MONTH = (r'(?:JAN\w*|FEB\w*|MAC\w*|APR\w*|MEI|JUN\w*|JUL\w*|OGOS?|OKT\w*|NOV\w*|DIS\w*|'
                r'MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPT?\w*|OCTOBER|DECEMBER)')
_DMY_RE = re.compile(r'(\d{1,2}\s+' + _MALAY_MONTH + r'\s+20\d{2})', re.IGNORECASE)
_NAME_MARKER = re.compile(r'\b(A\s*/\s*[LP]|BIN|BINTI)\b', re.IGNORECASE)


def _digits(s: str) -> str:
    return re.sub(r'\D', '', s or '')


def _norm_nric(raw: str) -> str:
    d = _digits(raw)
    return f'{d[:6]}-{d[6:8]}-{d[8:12]}' if len(d) == 12 else ''


def _offer_date(lines):
    for ln in lines:
        m = re.match(r'\s*Tarikh\s*:?\s*(.+)', ln, re.IGNORECASE)
        if m and 'CETAK' not in ln.upper() and _DMY_RE.search(m.group(1) or ''):
            return _DMY_RE.search(m.group(1)).group(1).strip()
    return ''


def _first_nric(text: str) -> str:
    m = _NRIC_RE.search(text or '')
    return _norm_nric(m.group(1)) if m else ''


def _detect(up: str):
    if 'TINGKATAN ENAM' in up and ('SEKTOR OPERASI SEKOLAH' in up or 'KEMASUKAN KE TINGKATAN ENAM' in up):
        return 'stpm'
    if 'PROGRAM MATRIKULASI' in up or 'BAHAGIAN MATRIKULASI' in up:
        return 'matriculation'
    if 'POLITEKNIK' in up and ('JABATAN PENDIDIKAN POLITEKNIK' in up or 'SURAT TAWARAN PENGAJIAN' in up):
        return 'polytechnic'
    return ''


def _value_after_label(lines, label_re):
    """Same-line value after a 'Label: value' line, else the next non-empty line."""
    for i, ln in enumerate(lines):
        m = label_re.match(ln)
        if m:
            tail = (m.group(1) or '').strip(' :').strip()
            if tail:
                return tail
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return nxt.strip(' :').strip()
    return ''


def _parse_stpm(lines, up):
    name = _value_after_label(lines, re.compile(r'\s*Nama\s*:?\s*(.*)', re.IGNORECASE))
    nric = _value_after_label(lines, re.compile(r'\s*No\.?\s*Kad\s*Pengenalan\s*:?\s*(.*)', re.IGNORECASE))
    nric = _norm_nric(nric) or _first_nric('\n'.join(lines))
    m = re.search(r'TINGKATAN ENAM SEMESTER\s+(\d)\s+TAHUN\s+(20\d{2})', up)
    programme = f'Tingkatan Enam Semester {m.group(1)}' if m else 'Tingkatan Enam'
    intake = m.group(2) if m else (re.search(r'TAHUN\s+(20\d{2})', up).group(1)
                                   if re.search(r'TAHUN\s+(20\d{2})', up) else '')
    # Pusat Tingkatan Enam = the school; the value block starts after the numbered labels.
    institution = next((ln.strip() for ln in lines
                        if re.match(r'\s*(SEKOLAH|SMK|KOLEJ|MAKTAB)\b', ln, re.IGNORECASE)), '')
    # Tarikh Lapor Diri: the reporting date is the first DD-Mon-YYYY that is NOT the offer/print date.
    offer_dt = _offer_date(lines)
    reporting = ''
    for ln in lines:
        if 'CETAK' in ln.upper():
            continue
        mm = _DMY_RE.search(ln)
        if mm and mm.group(1).strip() != offer_dt and 'TARIKH' not in ln.upper():
            reporting = mm.group(1).strip()
            break
    return {
        'candidate_name': name, 'candidate_nric': nric, 'programme': programme,
        'institution': institution, 'intake': intake,
        'reporting_date': reporting, 'reporting_date_label': 'Tarikh Lapor Diri' if reporting else '',
        'offer_date': offer_dt, 'issuer': 'Sektor Operasi Sekolah, Kementerian Pendidikan Malaysia',
    }


def _info_block_pairs(lines, label_names):
    """Pair a block of KNOWN labels with the value lines that follow it (Matrikulasi/Polytechnic:
    single-line values). Returns {label_key: value}. Labels + values are contiguous blocks."""
    labels_seen, first_label_i = [], None
    for i, ln in enumerate(lines):
        key = next((k for k, pat in label_names if pat.match(ln)), None)
        if key:
            labels_seen.append((i, key))
            if first_label_i is None:
                first_label_i = i
    if not labels_seen:
        return {}
    last_label_i = labels_seen[-1][0]
    values = [ln.strip() for ln in lines[last_label_i + 1:] if ln.strip()]
    out = {}
    for (_, key), val in zip(labels_seen, values):
        out[key] = re.sub(r'^\s*:\s*', '', val).strip()
    return out


# Anchored to a LABEL-ONLY line (block layout: labels alone, values in the block below) so a value
# like 'KOLEJ MATRIKULASI PAHANG' can't re-match the 'Kolej:' label and corrupt the pairing.
_MATRIC_LABELS = [
    ('programme', re.compile(r'^\s*Jurusan\s*:?\s*$', re.IGNORECASE)),
    ('duration', re.compile(r'^\s*Tempoh\s+Pengajian\s*:?\s*$', re.IGNORECASE)),
    ('institution', re.compile(r'^\s*Kolej\s*:?\s*$', re.IGNORECASE)),
    ('online_reg', re.compile(r'^\s*Pendaftaran\s+dalam\s+talian\s*:?\s*$', re.IGNORECASE)),
    ('reporting', re.compile(r'^\s*Tarikh\s+Kemasukan\s+ke\s+kolej\s*:?\s*$', re.IGNORECASE)),
    ('fee', re.compile(r'^\s*Yuran\s+Pendaftaran\s*:?\s*$', re.IGNORECASE)),
]


def _parse_matric(lines, up):
    # Name: the line carrying a parentage marker, above 'K/P:'.
    name = next((ln.strip() for ln in lines[:20]
                 if _NAME_MARKER.search(ln) and not any(c.isdigit() for c in ln)), '')
    nric = _value_after_label(lines, re.compile(r'\s*K\s*/\s*P\s*:?\s*(.*)', re.IGNORECASE))
    nric = _norm_nric(nric) or _first_nric('\n'.join(lines))
    sm = re.search(r'SESI\D{0,8}(20\d{2}(?:\s*/\s*20\d{2})?)', up)
    intake = sm.group(1).replace(' ', '') if sm else ''
    pairs = _info_block_pairs(lines, _MATRIC_LABELS)
    jurusan = pairs.get('programme', '')
    programme = f'Program Matrikulasi ({jurusan})' if jurusan else 'Program Matrikulasi'
    # 'Kolej Matrikulasi <state>' is unmistakable — take it directly (robust to a messy value block).
    institution = next((ln.strip() for ln in lines
                        if re.match(r'\s*KOLEJ\s+MATRIKULASI\b', ln, re.IGNORECASE)), pairs.get('institution', ''))
    reporting = pairs.get('reporting', '')
    rm = _DMY_RE.search(reporting)
    return {
        'candidate_name': name, 'candidate_nric': nric, 'programme': programme,
        'institution': institution, 'intake': intake,
        'reporting_date': rm.group(1).strip() if rm else '',
        'reporting_date_label': 'Tarikh Kemasukan ke kolej' if rm else '',
        'offer_date': _offer_date(lines),
        'issuer': 'Bahagian Matrikulasi, Kementerian Pendidikan Malaysia',
    }


_POLY_LABELS = [
    ('programme', re.compile(r'^\s*Program\s*:?\s*$', re.IGNORECASE)),
    ('mode', re.compile(r'^\s*Mod\s+Pengajian\s*:?\s*$', re.IGNORECASE)),
    ('institution', re.compile(r'^\s*Institusi\s*:?\s*$', re.IGNORECASE)),
    ('duration', re.compile(r'^\s*Tempoh\s+Pengajian\s*:?\s*$', re.IGNORECASE)),
]


def _parse_poly(lines, up):
    # Name + NRIC on one line: 'NAME (NRIC)'.
    name, nric = '', ''
    for ln in lines[:20]:
        m = re.match(r'\s*([A-Z][A-Z /.\'@-]+?)\s*\((\d{6}[- ]?\d{2}[- ]?\d{4})\)\s*$', ln)
        if m and _NAME_MARKER.search(m.group(1)):
            name, nric = m.group(1).strip(), _norm_nric(m.group(2))
            break
    if not nric:
        nric = _first_nric('\n'.join(lines))
    sm = re.search(r'SESI\D{0,8}(20\d{2}(?:\s*/\s*20\d{2})?)', up)   # SESI / SESII / 'SESI I : 2026/2027'
    intake = sm.group(1).replace(' ', '') if sm else ''
    pairs = _info_block_pairs(lines, _POLY_LABELS)
    reporting = _value_after_label(lines, re.compile(r'\s*Tarikh\s*dan\s*Masa\s*Daftar\s*:?\s*(.*)', re.IGNORECASE))
    rm = _DMY_RE.search(reporting) or re.search(r'(\d{1,2}[/-]\d{1,2}[/-]20\d{2})', reporting)
    return {
        'candidate_name': name, 'candidate_nric': nric, 'programme': pairs.get('programme', ''),
        'institution': pairs.get('institution', ''), 'intake': intake,
        'reporting_date': rm.group(1).strip() if rm else '',
        'reporting_date_label': 'Tarikh dan Masa Daftar' if rm else '',
        'offer_date': _offer_date(lines),
        'issuer': 'Jabatan Pendidikan Politeknik dan Kolej Komuniti',
    }


# The verdict-critical fields a lock REQUIRES (so switching off Gemini can't drop them).
_REQUIRED = ('candidate_name', 'candidate_nric', 'programme', 'intake')


def parse_govt_offer(text: str):
    """STPM/Matrikulasi/Polytechnic offer OCR text → the offer field dict, or None to defer to
    Gemini. Conservative: None unless the issuer is recognised AND all of _REQUIRED are read."""
    up = (text or '').upper()
    fam = _detect(up)
    if not fam:
        return None
    lines = [ln.rstrip() for ln in (text or '').splitlines()]
    fields = {'stpm': _parse_stpm, 'matriculation': _parse_matric,
              'polytechnic': _parse_poly}[fam](lines, up)
    if any(not (fields.get(k) or '').strip() for k in _REQUIRED):
        return None
    fields['_family'] = fam
    return fields
