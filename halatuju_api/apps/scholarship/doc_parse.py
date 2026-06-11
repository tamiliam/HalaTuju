"""Deterministic label-anchored field capture for standardised-issuer documents.

Malaysian fixed-format documents — MySTR/STR, TNB electricity, KWSP EPF, JPN birth
certificate, government offer letters — print their fields at FIXED LABELS. This module
reads those fields off the OCR text / PDF text-layer DETERMINISTICALLY, returning the SAME
field keys as ``vision._FIELD_SCHEMAS[doc_type]``, OR ``None`` when the text doesn't match
the expected layout — so ``vision.run_field_extraction_for_document`` falls back to Gemini.

Deterministic-first, Gemini-fallback: the auditable + free path for the standardised tail;
Gemini stays the fallback for the unstandardised one (university offers, odd utilities,
mis-slotted uploads). This mirrors the results-slip pattern (``_extract_slip_deterministic``).

Contract for every parser:
  * pure ``(text: str) -> dict | None``; NEVER raises (the dispatcher also guards).
  * be CONSERVATIVE — return ``None`` unless the text clearly IS this document and the key
    fields are present, so an unrecognised layout degrades to exactly today's Gemini read.
  * MUST be validated against REAL documents before its path is trusted in prod, not just
    the synthetic fixtures in tests (lessons.md S15 / L86 — that miss cost 3 deploys once).
"""
from __future__ import annotations

import re
from typing import Callable, Optional

# ── text + label helpers ──────────────────────────────────────────────────────


def _lines(text: str) -> list:
    """OCR text → trimmed lines (newline-normalised)."""
    norm = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    return [ln.strip() for ln in norm.split('\n')]


def find_value(text: str, label: str) -> str:
    """The value printed after ``label`` (a regex, case-insensitive). Tries the remainder
    of the label's own line (after an optional ``: = -`` separator); if that's blank, the
    next non-empty line. ``''`` when the label isn't present.

    Label-anchored, not position-anchored, so it survives a label sitting on its own line
    (mobile screenshots) or inline with its value (desktop/PDF)."""
    pat = re.compile(label, re.IGNORECASE)
    lines = _lines(text)
    for i, ln in enumerate(lines):
        m = pat.search(ln)
        if not m:
            continue
        rest = ln[m.end():].lstrip(' \t:=-').strip()
        if rest:
            return rest
        for nxt in lines[i + 1:]:
            if nxt:
                return nxt
        return ''
    return ''


def has(text: str, *patterns: str) -> bool:
    """True iff any regex pattern is present (case-insensitive). Used for surface markers."""
    blob = text or ''
    return any(re.search(p, blob, re.IGNORECASE) for p in patterns)


_NRIC_RE = re.compile(r'\b(\d{6})[-\s]?(\d{2})[-\s]?(\d{4})\b')


def first_nric(text: str) -> str:
    """The first Malaysian NRIC in the text, normalised to ``######-##-####``. '' if none."""
    m = _NRIC_RE.search(text or '')
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''


# Tolerate an intervening ``)``/space — Malaysian bills print the amount as a column under
# an ``(RM)`` header (TNB: "Jumlah Bil Anda (RM) 76.65") as well as inline ("RM700").
_RM_RE = re.compile(r'RM\s*\)?\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE)


def first_amount(text: str) -> str:
    """The first ``RM…`` amount in the text (digits + optional decimals), normalised to
    ``RM<n>``. '' if none."""
    m = _RM_RE.search(text or '')
    return f'RM{m.group(1).replace(",", "")}' if m else ''


# ── registry + dispatcher ─────────────────────────────────────────────────────

_PARSERS: dict = {}


def register(doc_type: str) -> Callable:
    """Register a deterministic parser for ``doc_type``. Parsers are added one per phase
    (STR → TNB elec → KWSP EPF → JPN BC → govt offer → water)."""
    def deco(fn):
        _PARSERS[doc_type] = fn
        return fn
    return deco


def parse_by_labels(doc_type: str, text: str) -> Optional[dict]:
    """Deterministic field capture for ``doc_type`` from ``text``; ``None`` → the caller
    uses Gemini. Never raises — any parser trouble degrades to the Gemini fallback."""
    fn = _PARSERS.get(doc_type)
    if fn is None or not (text or '').strip():
        return None
    try:
        result = fn(text)
    except Exception:
        return None
    # A parser must return the full field dict or None — never a partial/garbage value.
    return result if isinstance(result, dict) and result else None


# ── P1: STR / MySTR (Sumbangan Tunai Rahmah) ──────────────────────────────────
# Surfaces (→ source_type), each grounded in REAL uploads (L86):
#   * 'letter'         — KEMENTERIAN KEWANGAN approval letter. Names BOTH STR + SARA;
#                        the "layak STR <year> dengan jumlah RM<x>" entitlement line is
#                        what makes it an STR proof (and gives the STR-specific amount,
#                        distinct from the combined STR+SARA total and the SARA figure).
#   * 'semakan_status' — MySTR portal "Semakan Status" page ("Status Permohonan Semasa",
#                        "Jumlah Bayaran Keseluruhan STR"). Mobile OCR lists labels then
#                        values in separate columns → name/NRIC read layout-independently.
#   * 'dashboard'      — MySTR app dashboard ("Papan Pemuka").
#   * 'unknown'        — recognised but NOT an STR proof: a SARA-only Perdana Menteri
#                        letter ("bantuan SARA", no STR entitlement), or a SALINAN
#                        application record with no approval. This GATES income_engine.
#                        _str_currency to 'unconfirmed' — deterministically retiring the
#                        AI inference that mis-passed app #63's SARA letter.

_STR_MARKERS = (r'sumbangan\s+tunai\s+rahmah', r'\bMySTR\b', r'jumlah bayaran keseluruhan str',
                r'status\s+permohonan', r'layak\s+str', r'\bSTR\b')
_SARA_MARKERS = (r'sumbangan\s+asas\s+rahmah', r'bantuan\s+sara', r'perdana\s+menteri', r'\bSARA\b')
_STR_APPROVED = (r'diluluskan', r'\blulus\b', r'\bberjaya\b')

# A MyKad-style name line: all-caps with a patronymic/parentage connector. Layout-robust —
# survives the mobile "labels column then values column" OCR order that breaks label anchors.
_NAME_LINE = re.compile(r'^[A-Z][A-Z .@/]*\b(?:A\s*/\s*[LP]|BIN|BINTI|S\s*/\s*O|D\s*/\s*O)\b[A-Z .@/]*$')
_YEAR_RE = re.compile(r'\b(20(?:2[3-9]|3\d))\b')          # a plausible STR year (2023–2039)
_LAYAK_STR_RE = re.compile(r'layak\s+str.*?RM\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE | re.DOTALL)
_ALL_AMOUNTS_RE = re.compile(r'RM\s*\)?\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE)


def _patronymic_name(text: str) -> str:
    """First all-caps name line carrying a parentage connector (the recipient sits near the
    top, before any spouse/child names in the body). '' when there's no such line."""
    for ln in _lines(text):
        if 6 <= len(ln) <= 60 and _NAME_LINE.match(ln):
            return ln
    return ''


def _largest_amount(text: str) -> str:
    """The largest RM amount in the text → the STR keseluruhan total (≥ the amount paid so
    far) on a semakan-status page, where the label is split across OCR columns. '' if none."""
    vals = []
    for m in _ALL_AMOUNTS_RE.finditer(text or ''):
        try:
            vals.append(float(m.group(1).replace(',', '')))
        except ValueError:
            continue
    if not vals:
        return ''
    top = max(vals)
    return f'RM{int(top)}' if top.is_integer() else f'RM{top:.2f}'


def _str_surface(text: str) -> Optional[str]:
    """The STR surface → source_type; 'unknown' for a non-proof; None if not STR/SARA."""
    has_str = has(text, *_STR_MARKERS)
    if not has_str:
        return 'unknown' if has(text, *_SARA_MARKERS) else None
    if has(text, r'\bsalinan\b'):
        return 'unknown'    # a MySTR application-record COPY — NOT proof of approval
    if has(text, r'kementerian\s+kewangan', r'nama\s+penerima', r'telah\s+diluluskan'):
        return 'letter'
    if has(text, r'semakan\s+status', r'status\s+permohonan'):
        return 'semakan_status'
    if has(text, r'papan\s+pemuka', r'\bdashboard\b'):
        return 'dashboard'
    return 'semakan_status'    # STR-marked portal screen we can't sub-classify


@register('str')
def _parse_str(text: str) -> Optional[dict]:
    source_type = _str_surface(text)
    if source_type is None:
        return None                          # not an STR/SARA doc → Gemini

    name = _patronymic_name(text) or find_value(text, r'nama\s+penerima') or find_value(text, r'\bnama\b')
    nric = first_nric(text)
    # A genuine STR surface must yield at least a name or an NRIC; otherwise we don't trust
    # the deterministic read and hand off to Gemini (the SARA-only 'unknown' is exempt — it
    # is a deliberate "not a proof" verdict that needs no recipient fields).
    if source_type != 'unknown' and not (name or nric):
        return None

    status = find_value(text, r'status\s+permohonan(?:\s+semasa)?')
    if not re.search(r'[A-Za-z]{3}', status or ''):   # junk (a stray "i", blank) → use body
        status = ''
    if not status:
        m = next((re.search(p, text, re.IGNORECASE) for p in _STR_APPROVED
                  if re.search(p, text, re.IGNORECASE)), None)
        status = m.group(0) if m else ''

    ym = _YEAR_RE.search(text or '')
    year = ym.group(1) if ym else ''

    if source_type == 'letter':
        lm = _LAYAK_STR_RE.search(text or '')
        amount = f'RM{lm.group(1).replace(",", "")}' if lm else ''
    elif source_type == 'semakan_status':
        amount = _largest_amount(text)
    else:
        amount = ''

    return {'recipient_name': name, 'recipient_nric': nric, 'status': status,
            'year': year, 'amount': amount, 'source_type': source_type}


# ── P2: TNB electricity bill ──────────────────────────────────────────────────
# Tenaga Nasional "Bil Elektrik Anda" — one national issuer (West Malaysia; Sabah=SESB /
# Sarawak=SEB differ → None → Gemini). Highly standardised, label then value on the next
# OCR line:
#   ALAMAT POS → <name> then the address block (until TARIKH BIL)
#   TEMPOH BIL → billing period · Caj Semasa (RM) → the month's charge · Baki Terdahulu
#   (RM) → arrears. amount = Caj Semasa (+ arrears = Jumlah Bil Anda) and unpaid_balance =
#   Baki Terdahulu — matches the convention the income_engine utility_check already reads.


def _money(v: str) -> str:
    """First currency figure in ``v`` → ``RM<n>`` (commas stripped). '' if none."""
    m = re.search(r'([\d,]+(?:\.\d{2})?)', v or '')
    return f'RM{m.group(1).replace(",", "")}' if m else ''


@register('electricity_bill')
def _parse_electricity(text: str) -> Optional[dict]:
    if not has(text, r'bil\s+elektrik') or not has(text, r'tenaga\s+nasional', r'alamat\s+pos', r'no\.?\s*akaun'):
        return None                          # not a TNB bill → Gemini
    lines = _lines(text)
    name, address_lines = '', []
    # The ALAMAT POS block: first line is the account holder, the rest is the address,
    # ending at TARIKH BIL.
    idx = next((k for k, ln in enumerate(lines) if re.search(r'alamat\s+pos', ln, re.IGNORECASE)), -1)
    if idx >= 0:
        end = next((k for k in range(idx + 1, len(lines))
                    if re.search(r'tarikh\s+bil', lines[k], re.IGNORECASE)), len(lines))
        block = [ln for ln in lines[idx + 1:end] if ln]
        if block:
            name, address_lines = block[0], block[1:]
    period = find_value(text, r'tempoh\s+bil')
    amount = _money(find_value(text, r'caj\s+semasa\s*\(?\s*rm\s*\)?'))
    unpaid = _money(find_value(text, r'baki\s+terdahulu\s*\(?\s*rm\s*\)?'))
    if not (name or amount):                 # didn't lock onto the bill → Gemini
        return None
    return {'name': name, 'address': ', '.join(address_lines), 'amount': amount,
            'unpaid_balance': unpaid, 'billing_period': period}


# ── P3: KWSP EPF statement ────────────────────────────────────────────────────
# The KWSP "Penyata Ahli" — fixed labels: name after SULIT DAN PERSENDIRIAN, PENYATA AHLI
# TAHUN <year>, No. Kad Pengenalan, No. Majikan, JUMLAH SIMPANAN: RM<x>, and the CARUMAN
# SEMASA monthly rows (latest month's total = monthly_contribution). A mis-slotted Borang
# EC / payslip carries NONE of these → None → Gemini (free mis-slot detection).

_CARUMAN_RE = re.compile(
    r'^(?:jan|feb|mac|apr|mei|jun|jul|ogos|ogo|sep|okt|nov|dis)-\d{2}\b.*?([\d,]+\.\d{2})\s*$',
    re.IGNORECASE)


def _last_caruman(text: str) -> str:
    """The total of the LAST (most recent) monthly contribution row → ``RM<n>``. ''
    if the CARUMAN table didn't parse."""
    last = ''
    for ln in _lines(text):
        m = _CARUMAN_RE.match(ln)
        if m:
            last = m.group(1)
    return f'RM{last.replace(",", "")}' if last else ''


@register('epf')
def _parse_epf(text: str) -> Optional[dict]:
    if not has(text, r'penyata\s+ahli') or not has(text, r'ahli\s+kwsp', r'jumlah\s+simpanan', r'\bKWSP\b'):
        return None                          # not a KWSP Penyata Ahli (e.g. a Borang EC) → Gemini
    lines = _lines(text)
    si = next((k for k, ln in enumerate(lines)
               if re.search(r'sulit\s+dan\s+persendirian', ln, re.IGNORECASE)), -1)
    name = next((ln for ln in lines[si + 1:] if ln), '') if si >= 0 else ''
    nric = first_nric(find_value(text, r'no\.?\s*kad\s+pengenalan')) or first_nric(text)
    # The KWSP employer number is a digit code — extract the digit-run so a label/value
    # adjacency broken by image OCR yields '' rather than junk ("RINGKASAN", ":").
    em = re.search(r'\d{6,}', find_value(text, r'no\.?\s*majikan'))
    employer = em.group(0) if em else ''
    balance = _money(find_value(text, r'jumlah\s+simpanan'))
    ym = re.search(r'penyata\s+ahli\s+tahun\s+(20\d{2})', text, re.IGNORECASE)
    year = ym.group(1) if ym else ''
    if not (name or nric or balance):
        return None
    return {'name': name, 'nric': nric, 'employer': employer, 'latest_balance': balance,
            'last_contribution': '', 'monthly_contribution': _last_caruman(text), 'year': year}


# ── P4: JPN birth certificate (Sijil Kelahiran) ───────────────────────────────
# JPN forms (LM15 / LM05) — scanned, so the parser reads VISION OCR of a sectioned table.
# The section markers (KANAK-KANAK / BAPA / IBU) land UNRELIABLY in the OCR stream, but two
# anchors hold across forms + states:
#   * the CHILD's IC sits under "No. Daftar" / PKSN — NOT "No. Kad Pengenalan";
#   * the two "No. Kad Pengenalan" NRICs are the FATHER then the MOTHER (reading order),
#     each paired with the nearest preceding name.
# Unlocks the #55 mononym father-link (read father name+IC off the BAPA section). CONSERVATIVE
# — None (→ Gemini, which reads BCs well) unless BOTH parents resolve with an NRIC.

# Tolerant NRIC — JPN OCR spaces the groups ("770909 - 04 - 5229", "820507 02-6239").
_BC_NRIC_RE = re.compile(r'(\d{6})[\s-]{0,3}(\d{2})[\s-]{0,3}(\d{4})')


def _bc_nric(s: str) -> str:
    m = _BC_NRIC_RE.search(s or '')
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''


def _bc_name(line: str) -> str:
    """A name off a BC line: 'Nama[Penuh] <NAME>' → NAME, or a bare patronymic name line.
    '' for label/section/place lines."""
    m = re.match(r'^nama(?:\s+penuh)?\s+(.+)$', line, re.IGNORECASE)
    cand = (m.group(1) if m else line).strip()
    return cand if _NAME_LINE.match(cand) else ''


# Form labels/sections that an all-caps child-name scan must skip (the English "Name" /
# "Full Name" labels, the section headers, "Maklumat…" placeholders).
_BC_STOP = {'name', 'full name', 'nama', 'nama penuh', 'kanak-kanak', 'bapa', 'ibu',
            'child', 'father', 'mother', 'kanak-kanak / child', 'bapa/father', 'ibu/mother'}


def _is_bc_person(s: str) -> bool:
    """An all-caps personal name (mononym OK), not a form label/section header."""
    s = (s or '').strip()
    if not (3 <= len(s) <= 50) or any(c.isdigit() for c in s):
        return False
    if s.lower() in _BC_STOP or not re.match(r'^[A-Z][A-Z .@/]*$', s):
        return False
    return sum(c.isalpha() for c in s) >= 3


def _bc_child(lines: list) -> str:
    """Child name: anchor on the first Nama/Nama Penuh, then the first following all-caps
    person line (skipping the English 'Name'/'Full Name' labels). Accepts a mononym."""
    for i, ln in enumerate(lines):
        if not re.match(r'^nama(\s+penuh)?\b', ln.strip(), re.IGNORECASE):
            continue
        m = re.match(r'^nama(?:\s+penuh)?\s+(.+)$', ln.strip(), re.IGNORECASE)
        if m and _is_bc_person(m.group(1)):
            return m.group(1).strip()
        nxt = next((x.strip() for x in lines[i + 1:i + 5] if _is_bc_person(x)), '')
        if nxt:
            return nxt
    return ''


@register('birth_certificate')
def _parse_bc(text: str) -> Optional[dict]:
    if not has(text, r'sijil\s+kelahiran', r'birth\s+certificate'):
        return None                          # not a BC (e.g. a mis-slotted IC) → Gemini
    if not has(text, r'kad\s+pengenalan'):
        return None
    lines = _lines(text)
    child = _bc_child(lines)    # mononym-tolerant, skips the 'Name'/'Full Name' labels
    # parents: each "No. Kad Pengenalan" NRIC + the nearest preceding name (≠ child).
    parents = []
    for i, ln in enumerate(lines):
        if not re.search(r'kad\s+pengenalan', ln, re.IGNORECASE):
            continue
        nric = next((_bc_nric(lines[j]) for j in range(i, min(i + 3, len(lines))) if _bc_nric(lines[j])), '')
        if not nric:
            continue
        nm = next((_bc_name(lines[k]) for k in range(i - 1, max(-1, i - 9), -1)
                   if _bc_name(lines[k]) and _bc_name(lines[k]) != child), '')
        parents.append((nm, nric))
    if len(parents) < 2:                     # couldn't isolate both parents → Gemini
        return None
    (fn, fr), (mn, mr) = parents[0], parents[1]
    reg = re.search(r'\b([A-Z]{2}\s?\d{4,6})\b', text or '')   # JPN register no (CA17451, BV 46144)
    return {'bc_child_name': child or '', 'bc_child_nric': '',
            'bc_father_name': fn, 'bc_father_nric': fr,
            'bc_mother_name': mn, 'bc_mother_nric': mr,
            'bc_number': reg.group(1) if reg else ''}


# ── P5: offer letter — GOVERNMENT templates only ──────────────────────────────
# Offers span ~10 issuers with divergent programme/institution labels, so this parser is
# deliberately NARROW: it reads only the three standardised GOVERNMENT templates (where
# identity + issuer + programme are all label-anchored), and returns None for universities
# and anything else → Gemini (the unstructured tail it handles well, audit rec 2). The
# strong win is the deterministic identity (candidate name + 12-digit IC = the gate matched
# against the profile NRIC); programme/institution come along for free on these templates.

_OFFER_MARKERS = (r'surat\s+tawaran', r'tawaran\s+kemasukan', r'pemakluman\s+kemasukan',
                  r'ditawarkan')
_IC12_RE = re.compile(r'(?<!\d)(\d{12})(?!\d)')   # 12-digit IC; tolerates a mashed "…2306NO"


def _offer_name(text: str) -> str:
    """The candidate's name across the government addressee formats: 'NAME (12-digit)' /
    'NAME K/P : …' (often OCR-mashed, "ELANGOVANK/P") / 'Nama: NAME No. Kad Pengenalan: …'.
    Validated as a patronymic name (a mononym candidate defers to Gemini). '' if none."""
    for pat in (r'([A-Z][A-Z .@/]{4,}?)\s*\(\d{12}\)',                       # NAME (IC)
                r'[Nn]ama\s*[:.]?\s*([A-Z][A-Z .@/]{4,}?)\s*(?:[Nn]o\.?\s*[Kk]ad|[Kk]\s*/\s*[Pp])',
                r'([A-Z][A-Z .@/]{4,}?)\s*[Kk]\s*/\s*[Pp]\s*[:.]'):         # NAME K/P :
        m = re.search(pat, text or '')
        if m and _NAME_LINE.match(m.group(1).strip()):
            return m.group(1).strip()
    return _patronymic_name(text)


def _clean_short(v: str) -> str:
    """A field value only if it's a clean short token — guards against a value that swallowed
    the rest of a mashed single-line PDF ("PERAKAUNANTempoh Pengajian: …Kolej: …")."""
    v = (v or '').strip()
    if not v or len(v) > 55 or re.search(
            r'tempoh|kolej|yuran|pendaftaran|tarikh|institusi|no\.?\s|:', v, re.IGNORECASE):
        return ''
    return v


def _offer_template(text: str):
    """(issuer, programme) for a recognised GOVERNMENT template, or (None, None). The
    programme is constructed from the issuer type (always clean) + a clean specific token
    when one parses; a mashed/unsplittable value degrades to just the issuer-type programme."""
    if has(text, r'politeknik\s+dan\s+kolej\s+komuniti', r'\bpoliteknik\b'):
        return 'Jabatan Pendidikan Politeknik dan Kolej Komuniti', _clean_short(find_value(text, r'program\s*:'))
    if has(text, r'matrikulasi'):
        jur = _clean_short(find_value(text, r'jurusan\s*:'))
        return 'Bahagian Matrikulasi KPM', (f'Program Matrikulasi ({jur})' if jur else 'Program Matrikulasi')
    if has(text, r'sektor\s+operasi\s+sekolah', r'tingkatan\s+enam', r'pengurusan\s+sekolah\s+harian'):
        bid = _clean_short(find_value(text, r'bidang\s*:?'))
        return 'Sektor Operasi Sekolah', (f'Tingkatan Enam Semester 1 ({bid})' if bid else 'Tingkatan Enam Semester 1')
    if has(text, r'institut\s+pendidikan\s+guru', r'\bPISMP\b'):
        return 'Institut Pendidikan Guru Malaysia', 'PISMP'
    return None, None


@register('offer_letter')
def _parse_offer(text: str) -> Optional[dict]:
    if not has(text, *_OFFER_MARKERS):
        return None
    issuer, programme = _offer_template(text)
    if issuer is None:                       # university / unrecognised → Gemini
        return None
    m = _IC12_RE.search(text or '')
    nric = m.group(1) if m else ''
    name = _offer_name(text)
    # Emit only with the full identity AND a programme — for JPPKK that means a clean
    # "Program :" was read (a messy image with no clean label → None → Gemini, no degrade);
    # Form6/Matrik/IPG carry a programme constructed from the issuer type, robust on images.
    if not (name and nric and programme):
        return None
    return {'candidate_name': name, 'candidate_nric': nric, 'programme': programme or '',
            'institution': '', 'issuer': issuer,
            'offer_date': find_value(text, r'tarikh\s*:'), 'intake': '', 'candidate_address': ''}
