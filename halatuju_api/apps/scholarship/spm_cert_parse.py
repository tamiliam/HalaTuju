"""Deterministic ("Exact") reader for the SPM CERTIFICATE (sijil), from word boxes in visual rows.

Replaces `academic_engine.parse_spm_cert` (2026-10-28, MODEL_VERSION 1.14.0). That reader paired a
SUBJECT block with a GRADE block by their order in the flattened OCR text. On scans it returned None
(a grade letter read "A." or "B." dropped one grade; a school named "... SAINS ..." added a subject),
and on a scanner's OCR text layer whose lines are stored out of order it paired subjects with the
WRONG grades. This reader pairs each subject with the grade on its OWN visual row instead:

* a scan or photo is read from the Vision word boxes (`academic_engine._group_rows`, the SPM slip's
  and the STPM reader's row builder, which also de-rotates a sideways photo);
* a digital PDF is read from its text layer's own character boxes (page 1, `_pdf_words`);
* text with no positions → None (the caller falls back to the Gemini read, as before).

CONSERVATIVE — a wrong Exact value is far worse than an AI read. Every hit has passed:
  * the certificate markers ("layak dianugerahi" + "Sijil Pelajaran Malaysia");
  * exactly one name row between the title and the IC row, and one IC on the whole page;
  * a subject table bounded by its "Mata Pelajaran / Gred" header and the oral / CEFR / total
    lines below it; every line in the subject column is a KNOWN SPM subject, word for word;
  * every grade on the SPM scale, its letter agreeing with its printed band ("A- (CEMERLANG)").
    The band is the reliable part (a word); a letter whose sign is unreadable ("A.", "B." or an
    off-scale "B-") is taken from the band only when the base letter agrees and the band is
    complete. A clear letter that disagrees with the band → None;
  * a subject and its grade on the same visual row (a subject-only row and a grade-only row next
    to each other are joined only when they sit within 0.8 of a word height);
  * the printed "JUMLAH MATA PELAJARAN <word>" equal to the rows read, where printed (a label whose
    number is unreadable → None).
Output: ``{candidate_name, nric, exam, results: [{subject, grade, band}]}`` — the old schema.
Pure + deterministic; never raises. Tests: synthetic twins (`tests/test_certificate_parser.py`);
the real corpus is scored locally by `eval/spm_cert_check.py`.
"""
from __future__ import annotations

import math
import re
import statistics

from .academic_engine import (
    _BAND_TO_GRADE, _GRADE_TO_BAND, _SUBJECT_BM, _dominant_angle, _group_rows, _norm_lower_alnum,
    _spm_exam_year, ensure_exam_year,
)

__all__ = ['parse_spm_cert', 'ensure_exam_year']     # vision.py imports both from here

#: Known SPM subjects as their exact word sequence (a line must BE one of these, not contain it).
_SUBJECT_SEQ = {tuple(_norm_lower_alnum(n).split()): n for n in set(_SUBJECT_BM.values())}
_MAX_SUBJECT_WORDS = max(len(k) for k in _SUBJECT_SEQ)
_SPM_SCALE = frozenset({'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G'})
#: "A- (CEMERLANG)", "B . ( KEPUJIAN TINGGD", "C + (KEPUJIAN ATAS)" — the grade cell, as one string.
_GRADE_CELL = re.compile(r'([A-G])\s*([+\-.,]?)\s*\(?\s*(CEMERLANG|KEPUJIAN|LULUS|GAGAL)'
                         r'(?:\s+(TERTINGG\w*|TINGG\w*|ATAS))?\s*(\)?)')
_BAND_HEAD = re.compile(r'\(?(CEMERLANG|KEPUJIAN|LULUS|GAGAL)\b')
_LONE_LETTER = re.compile(r'[A-G][+\-.,]?')
_IC = re.compile(r'(?<!\d)(\d{6})-?(\d{2})-?(\d{4})(?!\d)')
_TABLE_END = re.compile(r'LISAN|CEFR|MLAH\s+MATA\s+PELAJARAN|PERIKSAAN\s+TAHUN')
_COUNT_WORDS = {'TIGA': 3, 'EMPAT': 4, 'LIMA': 5, 'ENAM': 6, 'TUJUH': 7, 'LAPAN': 8, 'DELAPAN': 8,
                'SEMBILAN': 9, 'SEPULUH': 10, 'SEBELAS': 11}
_NAME_CHARS = re.compile(r"[A-Z][A-Z@/'.\- ]*")


def parse_spm_cert(text, words=None, pdf=None):
    """SPM certificate → fields, or None (→ Gemini). ``words``: Vision word boxes
    ``{text, cx, cy, h, angle?}`` (page 1); ``pdf``: the upload's bytes, used for a digital PDF's
    text layer when no words were computed. ``text`` alone (no positions) → None."""
    try:
        if words is None and isinstance(pdf, (bytes, bytearray)) and bytes(pdf[:5]) == b'%PDF-':
            words = _pdf_words(bytes(pdf))
        return _read(words, (text or '').upper()) if words else None
    except Exception:          # a reader failure is a fallback to Gemini, never an error
        return None


def _pdf_words(data):
    """Page 1 of a digital PDF as word boxes in the Vision shape (top-left origin, points)."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    try:
        page = pdf[0]
        height, tp = page.get_height(), page.get_textpage()
        out, cur = [], []

        def flush():
            if cur:
                le, bo = min(c[1] for c in cur), min(c[2] for c in cur)
                ri, to = max(c[3] for c in cur), max(c[4] for c in cur)
                out.append({'text': ''.join(c[0] for c in cur), 'cx': (le + ri) / 2,
                            'cy': height - (bo + to) / 2, 'h': to - bo, 'angle': 0.0})
                cur.clear()
        for i in range(tp.count_chars()):
            ch = tp.get_text_range(i, 1)
            if not ch or ch.isspace():
                flush()
                continue
            cur.append((ch, *tp.get_charbox(i)))
        flush()
        return out
    finally:
        pdf.close()


def _row_text(row):
    return ' '.join(w['text'] for w in row)


def _read(words, flat):
    rows = _group_rows(words)
    texts = [_row_text(r).upper() for r in rows]
    full = ' '.join(texts)
    if 'LAYAK DIANUGERAHI' not in full or 'SIJIL PELAJARAN MALAYSIA' not in full:
        return None
    title = next((i for i, t in enumerate(texts) if t.strip() == 'SIJIL PELAJARAN MALAYSIA'), None)
    head = next((i for i, t in enumerate(texts)
                 if title is not None and i > title and 'PELAJARAN' in t and re.search(r'\bGRED\b', t)), None)
    if title is None or head is None:
        return None
    end = next((i for i in range(head + 1, len(rows)) if _TABLE_END.search(texts[i])), None)
    if end is None:
        return None
    ident = _name_and_ic(rows, texts, title, head)
    results = _table(rows[head:end], words)
    if ident is None or results is None or len(results) < 3:
        return None
    # The printed total and the year, from the rows and from the flat OCR text (a row split can
    # move a word): a printed total must be read and equal; two different years → None.
    counts = [c for c in (_declared_count(full), _declared_count(flat)) if c is not None]
    years = {y for y in (_spm_exam_year(full), _spm_exam_year(flat)) if y}
    if (counts and {c for c in counts if c >= 0} != {len(results)}) or len(years) > 1:
        return None
    yr = next(iter(years), '')
    return {'candidate_name': ident[0], 'nric': ident[1],
            'exam': f'SIJIL PELAJARAN MALAYSIA TAHUN {yr}' if yr else 'SIJIL PELAJARAN MALAYSIA',
            'results': results}


def _name_and_ic(rows, texts, title, head):
    """(name, IC) from the block under the title: exactly one IC row, exactly one row above it
    (the name), and no other IC anywhere on the page. None when any of that is not so."""
    ic_rows = [i for i in range(title + 1, head) if _IC.fullmatch(texts[i].replace(' ', ''))]
    if len(ic_rows) != 1 or ic_rows[0] != title + 2:
        return None
    m = _IC.fullmatch(texts[ic_rows[0]].replace(' ', ''))
    ic = '-'.join(m.groups())
    if {''.join(g.groups()) for t in texts for g in _IC.finditer(t.replace(' ', ''))} != {ic.replace('-', '')}:
        return None
    name = ' '.join(_row_text(rows[title + 1]).split())
    if len(name.split()) < 2 or not _NAME_CHARS.fullmatch(name.upper()):
        return None
    return name, ic


def _declared_count(full):
    """The printed subject total, None when the label is absent; -1 when present but unreadable."""
    m = re.search(r'MLAH\s+MATA\s+PELAJARAN\s*:?\s*([A-Z]+(?:\s+BELAS)?)', full)
    if not m:
        return None
    word = m.group(1)
    if word.endswith(' BELAS'):
        base = {'DUA': 2, 'TIGA': 3}.get(word.split()[0])
        return 10 + base if base else -1
    return _COUNT_WORDS.get(word, -1)


def _settle(letter, sign, head, mod, closed):
    """The grade of one cell, or None when letter and band disagree (see the module docstring)."""
    mod = ('tertinggi' if mod.startswith('TERTINGG') else 'tinggi' if mod.startswith('TINGG')
           else mod.lower())
    band = _BAND_TO_GRADE.get(' '.join(p for p in (head.lower(), mod) if p), '')
    if band not in _SPM_SCALE:
        return None
    read = letter + (sign if sign in '+-' else '')
    if sign in '+-' or not sign:
        if read in _SPM_SCALE:
            return band if read == band else None
    # The sign is unreadable ('A.', 'B,', off-scale 'B-'): the band decides ONLY where losing a faint
    # "TER" could not change it. Final mapping, base letter agreeing and the band complete:
    #   CEMERLANG TERTINGGI → A+ · KEPUJIAN TERTINGGI → B+ · KEPUJIAN ATAS → C+ · LULUS ATAS → D
    #   CEMERLANG) → A- · KEPUJIAN) → C · LULUS) → E · GAGAL) → G
    #   CEMERLANG TINGGI (A, or A+ with "TER" lost) · KEPUJIAN TINGGI (B, or B+) → None.
    if mod == 'tinggi':
        return None
    return band if band[0] == letter and (mod or closed) else None


def _split_row(row, subject_edge, h, ax):
    """One table row → (subject or '', grade or '', ok). ``ok`` False = a subject-column line that
    is not a known subject, or a grade cell that does not settle (the whole read is abandoned).
    ``ax(word)``: the word's position along the text line (cx on an upright page)."""
    toks = [w['text'] for w in row]
    subject, n = '', 0
    if ax(row[0]) <= subject_edge:
        norm = [_norm_lower_alnum(t) for t in toks]
        for k in range(min(len(toks), _MAX_SUBJECT_WORDS), 0, -1):
            seq = tuple(t for t in norm[:k] if t)
            if seq in _SUBJECT_SEQ and norm[k - 1]:
                subject, n = _SUBJECT_SEQ[seq], k
                break
        if not subject:
            return '', '', False
    glued = n and n < len(toks) and _gap(ax(row[n - 1]), row[n - 1], ax(row[n]), row[n], h) < 2.0 * h
    # Every band word right of the subject: exactly the one in the grade cell, or none. A second
    # grade (or a second subject + grade further right) abandons the read — never "last cell wins".
    bands = sum(1 for t in toks[n:] if _BAND_HEAD.match(t.upper()))
    for j in range(n, len(toks)):
        m = _GRADE_CELL.fullmatch(' '.join(toks[j:]).upper())
        if m:
            if (j > n and glued) or bands != 1 or any(_LONE_LETTER.fullmatch(t) for t in toks[n:j]):
                return '', '', False                # glued word / two grade cells / a stray letter
            grade = _settle(m.group(1), m.group(2), m.group(3), m.group(4) or '', bool(m.group(5)))
            return subject, grade or '', grade is not None
    return ('', '', False) if glued or bands else (subject, '', True)


def _gap(xa, a, xb, b, h):
    """Estimated blank space between two words on a row, from their centres. A capital is ~0.8 h
    wide on the corpus scans; 0.9 h errs towards "glued", i.e. towards None."""
    return (xb - 0.45 * h * len(b['text'])) - (xa + 0.45 * h * len(a['text']))


def _table(rows, words):
    """[{subject, grade, band}] from the header row + body rows, or None when unsure."""
    theta = math.radians(_dominant_angle([w for w in words if (w.get('text') or '').strip()]))
    cos, sin = math.cos(theta), math.sin(theta)

    def ax(w):                                       # along the text line
        return w['cx'] * cos + w['cy'] * sin

    def ay(w):                                       # down the page
        return -w['cx'] * sin + w['cy'] * cos
    header = rows[0]
    left = min(ax(w) for w in header)
    gred = next((ax(w) for w in header if w['text'].strip('.:').upper() == 'GRED'), None)
    if gred is None or gred <= left:
        return None
    edge = left + 0.25 * (gred - left)
    h = statistics.median(w.get('h') or 0 for w in words) or 12
    cells = []                                       # (subject, grade, row position)
    for row in rows[1:]:
        if all(w['text'].strip('().:').upper() in ('SUBJECT', 'GRADE', '') for w in row):
            continue
        subject, grade, ok = _split_row(row, edge, h, ax)
        if not ok:
            return None
        if subject or grade:
            cells.append([subject, grade, statistics.mean(ay(w) for w in row)])
    pairs, i = [], 0
    while i < len(cells):
        s, g, y = cells[i]
        if not (s and g) and i + 1 < len(cells):
            s2, g2, y2 = cells[i + 1]
            if bool(s) != bool(s2) and bool(g) != bool(g2) and not (s2 and g2) and abs(y2 - y) < 0.8 * h:
                s, g, i = s or s2, g or g2, i + 1
        if not (s and g):
            return None
        pairs.append((s, g, y))
        i += 1
    if len({p[0] for p in pairs}) != len(pairs):
        return None
    return [{'subject': s, 'grade': g, 'band': _GRADE_TO_BAND.get(g, '')} for s, g, _ in pairs]
