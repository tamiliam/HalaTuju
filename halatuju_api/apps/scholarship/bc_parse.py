"""Deterministic, geometry-based birth-certificate reader.

Mirrors the results-slip approach (``academic_engine.parse_spm_slip``): read Google-Vision
WORD BOXES (not flattened text), re-linearise them by position into clean rows, **classify the
version** (bilingual vs monolingual), then read each field from the gap between its KNOWN adjacent
labels. Reading by position is what beats the flattened-OCR cross-wire (#10): the child's ``Nama``
and the father's ``Nama`` land far apart on the form, but in row order each value sits cleanly
between its own pair of label anchors.

A field whose section header isn't present — a cropped upload (#27) — comes back EMPTY, never
inferred. So a partial/forged doc yields blanks, which the genuineness gate + the re-upload nudge
then handle; the parser itself can't hallucinate a person who isn't on the page.

Returns ``{bc_child_name, bc_child_nric, bc_father_name, bc_father_nric, bc_mother_name,
bc_mother_nric, bc_number, _bc_version}`` or ``None`` to defer to the Gemini-image fallback (not a
BC, or too little structure to read deterministically). PII-free unit tests build synthetic word
lists; real certs are validated locally.
"""
import re
from typing import Optional

# NRIC: 12 digits, JPN-spaced ("821001-14 - 6094", "670107-04-5077", "080514-14-0354").
_NRIC_RE = re.compile(r'(\d{6})\s*-?\s*(\d{2})\s*-?\s*(\d{4})')
# JPN register number ("No. Daftar"): 1-2 letters + 4-6 digits (BZ 46718, BS33797, CA 52457).
_REG_RE = re.compile(r'\b([A-Z]{1,2})\s?(\d{4,6})\b')

# All-caps tokens that are NEVER part of a person's name (chrome that can fall inside a band if a
# bracket over-runs). Name VALUES are all-caps and labels are Title-case, so within a tight bracket
# this set is mostly a safety net.
_STOP_CAPS = {
    'KERAJAAN', 'MALAYSIA', 'SIJIL', 'KELAHIRAN', 'GOVERNMENT', 'BIRTH', 'CERTIFICATE',
    'KANAK', 'KANAK-KANAK', 'BAPA', 'IBU', 'CHILD', 'FATHER', 'MOTHER', 'PEMAKLUM', 'INFORMANT',
    'WARGANEGARA', 'BUKAN', 'INDIA', 'MELAYU', 'CINA', 'HINDU', 'ISLAM', 'BUDDHA', 'KRISTIAN',
    'PEREMPUAN', 'LELAKI', 'TAHUN', 'MAKLUMAT', 'TIDAK', 'BERKENAAN', 'JPN', 'UPN',
    'HOSPITAL', 'KLINIK', 'PUSAT', 'KESIHATAN',  # place-of-birth words can edge a name band
}
_PATRONYMIC = {'A', 'L', 'P', 'S', 'O', 'D', 'BIN', 'BINTI', 'N.', 'A/L', 'A/P', 'S/O', 'D/O'}


def _rows(words):
    """Group word boxes into visual rows (by cy proximity), each sorted left→right, rows top→bottom.
    Returns [{'cy', 'tokens': [str], 'text': str}]."""
    ws = sorted((w for w in words if (w.get('text') or '').strip()), key=lambda w: (w['cy'], w['cx']))
    rows, cur, last = [], [], None
    for w in ws:
        h = w.get('h') or 20
        if last is None or abs(w['cy'] - last) <= max(12, h * 0.6):
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
        last = w['cy']
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        r = sorted(r, key=lambda w: w['cx'])
        toks = [w['text'] for w in r]
        out.append({'cy': sum(w['cy'] for w in r) / len(r), 'tokens': toks, 'text': ' '.join(toks)})
    return out


def _norm(s):
    return re.sub(r'[^A-Z]', '', (s or '').upper())


def _find(rows, *needles, start=0, end=None):
    """First row index in [start, end) whose normalised text contains any needle (also normalised)."""
    end = len(rows) if end is None else end
    needles = [_norm(n) for n in needles]
    for i in range(start, end):
        t = _norm(rows[i]['text'])
        if any(n in t for n in needles):
            return i
    return -1


def _is_name_tok(t):
    if t == '/':
        return True
    if not re.match(r'^[A-Z][A-Z.]*$', t):     # all-caps (values); Title-case labels are dropped
        return False
    return t in _PATRONYMIC or t not in _STOP_CAPS


def _name_in_span(rows, start_i, end_i):
    """The personal name in rows (start_i, end_i): the all-caps tokens, patronymic joined."""
    toks = []
    for r in rows[start_i + 1:end_i]:
        toks += [t for t in r['tokens'] if _is_name_tok(t)]
    name = ' '.join(toks)
    name = re.sub(r'\bA\s*/\s*([LP])\b', r'A/\1', name)        # A / L → A/L
    name = re.sub(r'\b([SD])\s*/\s*O\b', r'\1/O', name)        # S / O → S/O
    name = re.sub(r'\s*/\s*', '/', name) if '/' in name and 'A/' not in name and 'S/' not in name and 'D/' not in name else name
    return re.sub(r'\s+', ' ', name).strip(' /')


def _nric_in_span(rows, start_i, end_i):
    for r in rows[start_i:end_i]:
        m = _NRIC_RE.search(r['text'])
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return ''


def parse_bc(words) -> Optional[dict]:
    rows = _rows(words)
    if not rows:
        return None
    full = _norm(' '.join(r['text'] for r in rows))
    if 'SIJILKELAHIRAN' not in full and 'BIRTHCERTIFICATE' not in full:
        return None                                            # not a BC → Gemini/genuineness

    # ── classify version ──────────────────────────────────────────────────────
    bilingual = any(_norm(n) in full for n in ('CHILD', 'FATHER', 'MOTHER', 'FULL NAME', 'BIRTH CERTIFICATE'))
    version = 'bilingual' if bilingual else 'mono'

    # ── section headers (Malay tokens — present in BOTH versions) ──────────────
    ci = _find(rows, 'KANAK-KANAK', 'KANAK KANAK')
    fi = _find(rows, 'BAPA', start=max(ci, 0))
    mi = _find(rows, 'IBU', start=max(fi, 0))
    # Informant block — the exclusion bound. The header is 'PEMAKLUM' on some certs, 'PEMBERITAHU' on
    # others; both must bound the mother band so the informant (often a parent) never bleeds in.
    pi = _find(rows, 'PEMAKLUM', 'PEMBERITAHU', start=max(mi, 0))
    end = pi if pi != -1 else len(rows)

    # ── child IC: the 12-digit NRIC ABOVE the KANAK-KANAK header (top-right), NOT the
    #    letter-prefixed No. Daftar; born-date encoded, equals the student's own NRIC ──
    child_nric = _nric_in_span(rows, 0, ci) if ci != -1 else ''

    # ── child name: between KANAK-KANAK and "Tarikh dan Waktu Kelahiran" (fallback: BAPA) ──
    child_name = ''
    if ci != -1:
        ti = _find(rows, 'Tarikh dan Waktu', 'Tarikh dan Waktu Kelahiran', start=ci + 1,
                   end=(fi if fi != -1 else len(rows)))
        child_name = _name_in_span(rows, ci, ti if ti != -1 else (fi if fi != -1 else len(rows)))

    # ── father: between BAPA and IBU; name up to "No. Kad Pengenalan"; IC = first NRIC after it
    #    within the band (the value can be on the label row OR the next — so search to the band end,
    #    not a fragile "Umur" bound which sits on the LABEL row while the value is on the next). ──
    father_name = father_nric = ''
    if fi != -1:
        f_end = mi if mi != -1 else end
        # Anchor on the distinctive 'PENGENALAN' token, not 'Kad Pengenalan': the bilingual label
        # interleaves with its English co-label ("No. Identity Kad Card No. Pengenalan"), so the
        # two Malay words aren't contiguous — but 'PENGENALAN' survives and isn't ambiguous.
        f_kp = _find(rows, 'PENGENALAN', start=fi + 1, end=f_end)
        father_name = _name_in_span(rows, fi, f_kp if f_kp != -1 else f_end)
        father_nric = _nric_in_span(rows, f_kp if f_kp != -1 else fi, f_end)

    # ── mother: between IBU and PEMAKLUM (never the informant); same field layout ──
    mother_name = mother_nric = ''
    if mi != -1:
        m_kp = _find(rows, 'PENGENALAN', start=mi + 1, end=end)
        mother_name = _name_in_span(rows, mi, m_kp if m_kp != -1 else end)
        mother_nric = _nric_in_span(rows, m_kp if m_kp != -1 else mi, end)

    # ── register number (No. Daftar) — letter-prefixed (BZ 46718 / BS33797), so distinct from the
    #    all-digit child IC and from any NRIC. It appears once; the first such token is it. ──
    bc_number = ''
    m = _REG_RE.search(' '.join(r['text'] for r in rows))
    if m:
        bc_number = f'{m.group(1)} {m.group(2)}'

    # Deterministic confidence: a real, complete BC resolves the child + both parents. If we can't
    # (cropped / odd layout), return None so the gated Gemini fallback + genuineness take over —
    # rather than emit a partial that looks authoritative.
    if not child_name or not (father_name and father_nric) or not (mother_name and mother_nric):
        return None

    return {'bc_child_name': child_name, 'bc_child_nric': child_nric,
            'bc_father_name': father_name, 'bc_father_nric': father_nric,
            'bc_mother_name': mother_name, 'bc_mother_nric': mother_nric,
            'bc_number': bc_number, '_bc_version': version}
