"""Deterministic ("Exact") reader for STPM results documents — STPM exact-read roadmap S2.

An STPM certificate, results slip or MPM transcript prints the same facts — name, IC, index
number, exam year, PNGK and one grade per subject — under fixed printed labels. This module reads
them from the OCR text (a digital PDF's text layer) or, for a scan / photo, from the Vision WORD
BOXES re-linearised into visual rows (`academic_engine._group_rows`, the SPM slip's row builder).

(A certificate whose text layer is stored column by column is paired in `stpm_columns`, 1.1.0; its
merged-line form under pypdf 5.9.0, 1.3.0.)
It first recognises the LAYOUT from a SET of printed anchors (never one exact phrase), because the
certificate and the slip print the facts in different places. ⚠ The layout is a READER-ONLY routing
step (owner ruling 2026-10-27): it is never returned, stored or shown, and no rule reads it. A
checker page (the online "Halaman Keputusan"), a cropped table with no title, or any variant we do
not recognise returns None, and the caller falls back to today's Gemini read.

CONSERVATIVE — a wrong Exact value is far worse than an AI read. Every hit has passed:
  * a name, an exam year from the TITLE / "Tahun Peperiksaan" (never from the release date: STPM
    2025 is released in 2026, and some slips misprint the date), and at least one subject;
  * every subject named from the known STPM vocabulary and graded on the STPM scale;
  * every subject row's grade letter and grade point agreeing on the fixed STPM scale (owner's
    rule, 2026-10-27, `_settle_grade`): both read clearly and matching → accepted; one unclear
    or missing (a point first snapped to the valid value within 0.05: 3.66, 3.7, 367, 3,67) →
    completed from the scale ONLY when the value that was read matches the grade the STUDENT
    ENTERED for that subject; otherwise (or with no entry, or neither read, or a disagreement)
    → None, and Gemini reads it so the reviewer sees any mismatch as today;
  * the printed subject count (slip: registered; certificate: passed) matching the rows read — a
    certificate's count may be ABSENT (label, no number: 1.2.0), never mis-read;
  * the printed PNGK equal to the PNGK recomputed from the rows (Pengajian Am + the best three
    other subjects, MPM's rule, half-up to two places). One misread grade breaks the sum.
Owner ruling B (2026-10-28): a bare base letter whose point is that letter WITH a sign (A + 3.67) lost
its sign in print → the signed grade, on a PNGK-counted row only, recorded in `_rows_sign_from_point`.
Grade X (absent) is kept as printed, with no grade point.

Output mirrors the Gemini higher-results schema (`higher_results.SCHEMA`) so the comparison
downstream is unchanged: candidate_name, exam, cgpa, cgpa_label, institution, results
[{subject, grade}] (subject NAME only, no code), plus exam_year, nric and index_no. The caller
stores `PARSER_VERSION` beside `capture`, outside the fields. Pure + deterministic; never raises. PII-free unit tests use synthetic twins
(`tests/test_stpm_parse.py`); the real corpus is scored locally by `eval/stpm_parse_check.py`.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

# Parser version — bump on ANY change to the deterministic capture (doc-recognition versioning
# rule, the `offer_parse` precedent) so a stored read says which reader made it.
# 1.0.0 (2026-10-27): S2 — certificate (2023/24 + 2025), results slip (2022-2025), transcript.
# 1.1.0 (2026-10-28): a certificate's COLUMN-ordered text layer (names, then letters, then points).
# 1.2.0 (2026-10-28): a certificate's passed count may be ABSENT (label, no number) when the rows equal the
#   subjects the student entered (no entry: text layer only); never mis-read.
# 1.3.0 (2026-10-28): the column-ordered certificate as pypdf 5.9.0 (production's locked library) lays it
#   out: merged lines (names run together, letters on the "Gred (Grade)" line, every point on one line).
PARSER_VERSION = '1.3.0'

#: The STPM subject grade scale and its printed grade points (the slip's "Nilai Gred").
GRADE_POINTS = {'A': '4.00', 'A-': '3.67', 'B+': '3.33', 'B': '3.00', 'B-': '2.67', 'C+': '2.33',
                'C': '2.00', 'C-': '1.67', 'D+': '1.33', 'D': '1.00', 'F': '0.00'}
STPM_SCALE = frozenset(GRADE_POINTS) | {'X'}       # X = absent, printed with no grade point

#: Known STPM subjects, Malay and English, as printed (a name outside this list → None). The
#: displayed form is the printed one; matching ignores spacing and punctuation.
_SUBJECTS = (
    'PENGAJIAN AM', 'GENERAL STUDIES', 'BAHASA MELAYU', 'MALAY', 'BAHASA CINA', 'CHINESE LANGUAGE',
    'BAHASA TAMIL', 'TAMIL LANGUAGE', 'BAHASA ARAB', 'ARABIC LANGUAGE', 'LITERATURE IN ENGLISH',
    'KESUSASTERAAN MELAYU KOMUNIKATIF', 'COMMUNICATIVE MALAY LITERATURE', 'SYARIAH', 'USULUDDIN',
    'TAHFIZ AL-QURAN', 'SEJARAH', 'HISTORY', 'GEOGRAFI', 'GEOGRAPHY', 'EKONOMI', 'ECONOMICS',
    'PENGAJIAN PERNIAGAAN', 'BUSINESS STUDIES', 'PERAKAUNAN', 'ACCOUNTING', 'MATEMATIK (M)',
    'MATHEMATICS (M)', 'MATEMATIK (T)', 'MATHEMATICS (T)', 'MATEMATIK LANJUTAN (T)',
    'FURTHER MATHEMATICS (T)', 'SAINS KOMPUTER', 'INFORMATION AND COMMUNICATIONS TECHNOLOGY',
    'FIZIK', 'PHYSICS', 'KIMIA', 'CHEMISTRY', 'BIOLOGI', 'BIOLOGY', 'SAINS SUKAN', 'SPORTS SCIENCE',
    'SENI VISUAL', 'VISUAL ARTS', 'MUZIK', 'MUSIC',
)
_GENERAL_STUDIES = frozenset({'PENGAJIANAM', 'GENERALSTUDIES'})


def _letters(s) -> str:
    """Upper-case letters and digits only — the anchor / vocabulary match form."""
    return re.sub(r'[^A-Z0-9]', '', str(s or '').upper())


_SUBJECT_BY_KEY = {_letters(s): s for s in _SUBJECTS}

_GP_RE = re.compile(r'^[0-4]\.\d{2}$')
#: A grade-point-shaped token as OCR may print it: 3.67, 3,67, 3.7, 4.0, 3.670, or 367 (lost dot).
_POINT_TOKEN = re.compile(r'^(\d)[.,](\d{1,3})$|^(\d)(\d{2})$')
_SNAP = Decimal('0.05')
OFF_SCALE = 'off-scale'


def _point_of(token):
    """A grade-point token → the valid printed value it is (snapped within 0.05), OFF_SCALE when
    it is a number near no valid value, or None when the token is not point-shaped."""
    m = _POINT_TOKEN.match(token or '')
    if not m:
        return None
    value = Decimal(f'{m[1]}.{m[2]}' if m[1] is not None else f'{m[3]}.{m[4]}')
    near = min(GRADE_POINTS.values(), key=lambda v: abs(Decimal(v) - value))
    return near if abs(Decimal(near) - value) <= _SNAP else OFF_SCALE
_CODE_RE = re.compile(r'^(9\d\d)\W*$')
_NRIC_RE = re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{2})\s*-?\s*(\d{2})\s*-?\s*(\d{4})(?!\d)')
_INDEX_RE = re.compile(r'\b([A-Z]{2}\d{4})\s*/\s*(\d{4})\b')
_NAME_TOKEN = re.compile(r"^[A-Z][A-Z'.\-]*$|^[@/]$|^A/[LP]$|^[SD]/O$")
_NOT_A_NAME = frozenset({'MAJLIS', 'PEPERIKSAAN', 'MALAYSIA', 'SIJIL', 'TINGGI', 'PERSEKOLAHAN',
                         'STPM', 'NAMA', 'KAD', 'PENGENALAN', 'THIS', 'CERTIFY', 'IDENTITY'})
#: School, stamp and watermark words that sit near the name line (a school row, a certified-copy
#: stamp). A name is never read Exact if one would be part of it — None, never a trimmed name.
_NOT_IN_A_NAME = frozenset({
    'SMK', 'SMJK', 'SMKA', 'SJK', 'SK', 'SMA', 'SBP', 'SEKOLAH', 'KOLEJ', 'MAKTAB', 'TINGKATAN',
    'MENENGAH', 'KEBANGSAAN', 'SALINAN', 'COPY', 'CERTIFIED', 'TRUE', 'SAH', 'DISAHKAN', 'DIAKUI',
    'BENAR', 'SPECIMEN', 'SPESIMEN', 'CONTOH', 'SAMPLE', 'PENGETUA', 'PRINCIPAL', 'CAP', 'COP',
    'MPM', 'ASAL', 'ORIGINAL', 'TANDATANGAN',
})
_DASHES = {'-', '−', '–', '—'}
#: Greek / Cyrillic CAPITALS that Vision sometimes returns for the identical-looking Latin letter
#: ("ΕΚΟΝΟΜΙ" for EKONOMI). Mapped back so the vocabulary and anchors still match.
_HOMOGLYPHS = str.maketrans('ΑΒΕΖΗΙΚΜΝΟΡΤΥΧАВЕКМНОРСТУХ', 'ABEZHIKMNOPTYXABEKMHOPCTYX')

# ── The layout anchors (a SET, with tolerance — any variant missing too many → None) ────────────
#: A checker page, or a TERM (penggal / semester) result — never a final STPM result document.
_CHECKER = ('HALAMANKEPUTUSAN', 'KEMBALIKECARIAN', 'SEMAKANKEPUTUSAN', 'PENGGAL', 'SEMESTER')
_SLIP_MARKS = ('BUKANSIJILSTPM', 'MATAPELAJARANDIDAFTARKAN', 'GREDKERTAS', 'WAJARAN', 'PNGK',
               'ANGKAGILIRAN')
_CERT_MARKS = ('DISAHKANBAHAWA', 'HIGHERSCHOOLCERTIFICATE', 'TAHUNPEPERIKSAAN',
               'BILANGANMATAPELAJARANLULUS', 'NILAIGRED', 'THISISTOCERTIFY', 'ANGKAGILIRAN')
_TRANSCRIPT_MARKS = ('MATAPELAJARANDIDAFTARKAN', 'PNGK', 'ANGKAGILIRAN', 'GREDKERTAS', 'NOSIRI')


def _title_year(rows, pattern):
    """The year printed IN the title row itself (never a number from a neighbouring row)."""
    for r in rows:
        m = re.search(pattern, _letters(''.join(r)))
        if m:
            return m
    return None


def _layout(flat: str, rows):
    """('slip' | 'certificate' | 'transcript', exam_year) or None. INTERNAL routing only."""
    if 'MAJLISPEPERIKSAANMALAYSIA' not in flat or any(m in flat for m in _CHECKER):
        return None
    slip = _title_year(rows, r'SLIPKEPUTUSANPEPERIKSAANSTPM(20\d\d)$')
    transcript = _title_year(rows, r'^TRANSKRIP(20\d\d)$')
    found = []
    if slip and sum(m in flat for m in _SLIP_MARKS) >= 4:
        found.append(('slip', int(slip.group(1))))
    if transcript and not slip and sum(m in flat for m in _TRANSCRIPT_MARKS) >= 4:
        found.append(('transcript', int(transcript.group(1))))
    if ('SIJILTINGGIPERSEKOLAHANMALAYSIA' in flat and 'SLIPKEPUTUSAN' not in flat
            and not transcript and sum(m in flat for m in _CERT_MARKS) >= 5):
        found.append(('certificate', None))
    return found[0] if len(found) == 1 else None


# ── Rows ─────────────────────────────────────────────────────────────────────────────────────


def _join_signs(tokens):
    """['B', '+'] → ['B+'] (Vision splits a grade's sign into its own word box)."""
    out = []
    for t in tokens:
        t = t.strip().translate(_HOMOGLYPHS)
        if not t:
            continue
        if out and (t == '+' or t in _DASHES) and out[-1] in ('A', 'B', 'C', 'D'):
            out[-1] += '+' if t == '+' else '-'
            continue
        out.append(t.replace('−', '-').replace('–', '-'))
    return out


def _rows_of(text, words):
    """Visual rows as token lists: from the word boxes when given (a scan), else the text lines."""
    if words:
        from .academic_engine import _group_rows
        rows = [[w.get('text') or '' for w in r] for r in _group_rows(words)]
    else:
        rows = [ln.split() for ln in (text or '').splitlines()]
    return [r for r in (_join_signs(r) for r in rows) if r]


def _find(rows, *keys, start=0):
    """Index of the first row (from `start`) whose letters contain every key, or -1."""
    for i in range(start, len(rows)):
        flat = _letters(''.join(rows[i]))
        if all(k in flat for k in keys):
            return i
    return -1


def _after(row, label_key):
    """The tokens after the label: after the first ':' if one follows the label, else after the
    token that completes the label's letters."""
    acc = ''
    for i, t in enumerate(row):
        acc += _letters(t)
        if label_key in acc:
            rest = row[i + 1:]
            if t.endswith(':') or (':' in t and not t.endswith(':')):
                tail = t.split(':', 1)[1]
                rest = ([tail] if tail else []) + rest
            elif rest and rest[0].startswith(':'):
                rest = ([rest[0][1:]] if rest[0][1:] else []) + rest[1:]
            return [x for x in rest if x]
    return []


def _clean_name(tokens):
    """The candidate name from its value tokens, or '' when they do not read as a name."""
    if not tokens or not all(_NAME_TOKEN.match(t) for t in tokens):
        return ''
    if any(t in _NOT_A_NAME or t.strip('.,:;') in _NOT_IN_A_NAME for t in tokens):
        return ''
    name = ' '.join(tokens)
    name = re.sub(r'\bA\s*/\s*([LP])\b', r'A/\1', name)
    name = re.sub(r'\b([SD])\s*/\s*O\b', r'\1/O', name)
    name = re.sub(r'\s*@\s*', ' @ ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name if len(_letters(name)) >= 4 and ' ' in name else ''


def _nric(rows, i):
    m = _NRIC_RE.search(' '.join(rows[i])) if i >= 0 else None
    if not m:
        return ''
    _yy, mm, dd = (int(x) for x in m.groups()[:3])
    return ''.join(m.groups()) if 1 <= mm <= 12 and 1 <= dd <= 31 else ''


def _index_no(rows, i):
    m = _INDEX_RE.search(' '.join(rows[i])) if i >= 0 else None
    return f'{m.group(1)}/{m.group(2)}' if m else ''


# ── Subject rows ─────────────────────────────────────────────────────────────────────────────


def _split_subject(tokens):
    """(subject, grade | None, point | None) from a subject row's tokens AFTER its code, or None.
    Read from the right: [grade point] then [grade], the rest is the name. One trailing token of
    one or two characters that is neither (OCR debris where the letter was) is dropped: the
    letter is then unclear (None) and only `_settle_grade`'s rule 2 can complete it."""
    rest = list(tokens)
    point = _point_of(rest.pop()) if rest and _point_of(rest[-1]) else None
    grade = rest.pop() if rest and rest[-1] in STPM_SCALE else None
    if grade is None and len(rest) > 1 and len(rest[-1]) <= 2 and _letters(''.join(rest)) not in _SUBJECT_BY_KEY:
        rest.pop()
    subject = _SUBJECT_BY_KEY.get(_letters(''.join(rest)))
    return (subject, grade, point) if subject else None


def _sign_from_point(letter, point):
    """Owner ruling B (2026-10-28): a bare base letter (A B C D) whose clearly read point is that SAME
    letter WITH a sign (A + 3.67 → A-; B + 3.33 → B+) lost its sign in the print → the signed grade.
    Any other pairing (B + 3.67) is a disagreement → None. Counted rows only (the caller checks)."""
    if letter not in ('A', 'B', 'C', 'D'):
        return None
    hits = [g for g in (letter + '+', letter + '-') if GRADE_POINTS.get(g) == point]
    return hits[0] if len(hits) == 1 else None


def _settle_grade(rows_read, entered):
    """The owner's grade rule, per row. ``entered(subject)`` is the grade the student entered for
    that subject, or None (no profile / no entry → rule 1 only).
      1. Letter and (snapped) point both read and agreeing on the scale → accepted.
      2. One unclear or missing → completed from the scale ONLY when the value that WAS read equals
         the student's entry for that subject.
      3. Otherwise — the read value differs from the entry, no entry, neither read, or letter and
         point disagree → None. A point read clearly but OFF the scale (3.50) is a disagreement.
    X (absent) is accepted as printed with no point. The student's grade is never written into the
    read except through rule 2, and a rule-2 row is marked `from_entry`: the caller accepts it only
    when the row COUNTS towards the PNGK, so the PNGK check guards it. List / None."""
    by_point = {v: k for k, v in GRADE_POINTS.items()}
    for r in rows_read:
        g, p = r['grade'], r['point']
        if p == OFF_SCALE:
            return None
        clear_p = p
        if g == 'X':
            if p is not None:
                return None
            continue
        if g is not None and clear_p is not None:
            if GRADE_POINTS[g] != clear_p:
                signed = _sign_from_point(g, clear_p)        # owner ruling B (2026-10-28)
                if signed is None:
                    return None
                r['grade'], r['sign_from_point'], r['base'] = signed, True, g
            continue
        read = g if g is not None else by_point.get(clear_p)
        mine = entered(r['subject']) if read and entered else None     # normalised by the caller
        if not read or not mine or mine != read:
            return None
        r['grade'], r['point'], r['from_entry'] = read, GRADE_POINTS[read], True
    return rows_read


def _pngk(rows_read):
    """(PNGK string, set of counted row indexes): Pengajian Am + the best three others (all
    subjects when no Pengajian Am is printed: the best four), half-up to two places."""
    graded = [(i, Decimal(r['point'])) for i, r in enumerate(rows_read) if r['grade'] != 'X']
    ga = [x for x in graded if _letters(rows_read[x[0]]['subject']) in _GENERAL_STUDIES][:1]
    others = sorted((x for x in graded if x not in ga), key=lambda x: -x[1])
    counted = ga + others[:4 - len(ga)]
    if not counted:
        return None, set()
    mean = sum(p for _, p in counted) / len(counted)
    return str(mean.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), {i for i, _ in counted}


def _completions_proven(rows_read, counted, printed_pngk):
    """Does the PNGK PROVE every completed row (rule 2 `from_entry`, ruling B `sign_from_point`)?
      * the row counts towards the PNGK, and ties with no uncounted row (else which of two equal
        points was counted is arbitrary, and the sum cannot tell them apart);
      * ruling B: with the row's ALTERNATIVE value — the bare letter as read (A → 4.00) — the
        PNGK, re-ranked, no longer adds up (else the sum fits both readings and proves neither).
    A rule-2 row has no alternative: only ONE value was read and the completion IS that value (the
    other was missing or unreadable), so only the first check applies; the student's entry and the
    sum both corroborate the value read."""
    for i, r in enumerate(rows_read):
        if not (r.get('from_entry') or r.get('sign_from_point')):
            continue
        ranked = _letters(r['subject']) not in _GENERAL_STUDIES      # PA counts by name, not rank
        if i not in counted or ranked and any(j not in counted and rows_read[j]['grade'] != 'X'
                                   and Decimal(rows_read[j]['point']) == Decimal(r['point'])
                                   for j in range(len(rows_read))):
            return False
        if r.get('sign_from_point'):
            alt = [dict(x) for x in rows_read]
            alt[i]['point'] = GRADE_POINTS[r['base']]
            if _pngk(alt)[0] == printed_pngk:
                return False
    return True


def _checked_results(rows_read, printed_pngk, printed_count, count_kind, entered=None):
    """The results list after every sanity gate, or None."""
    if not rows_read or not printed_pngk or not _GP_RE.match(printed_pngk):
        return None
    if len({_letters(r['subject']) for r in rows_read}) != len(rows_read):
        return None                                   # one subject read twice
    rows_read = _settle_grade(rows_read, entered)
    if rows_read is None:
        return None
    if printed_count is not None:
        n = (len(rows_read) if count_kind == 'registered'
             else sum(1 for r in rows_read if r['grade'] not in ('F', 'X')))
        if n != printed_count:
            return None
    computed, counted = _pngk(rows_read)
    if computed != printed_pngk or not _completions_proven(rows_read, counted, printed_pngk):
        return None
    return [{'subject': r['subject'], 'grade': r['grade'], 'from_entry': bool(r.get('from_entry')),
             'sign_from_point': bool(r.get('sign_from_point'))} for r in rows_read]


def _count_after(rows, i, label_key):
    """The integer printed after a count label; 'missing' when the label row is there but its
    number is not; None when the label is not printed at all."""
    if i < 0:
        return None
    for t in _after(rows[i], label_key):
        if t.isdigit():
            return int(t)
        if _letters(t) and not t.startswith('('):
            break
    return 'missing'


def _count_absent(rows, i):
    """The passed-count label is printed with NO number in its place: nothing follows it, or the
    next printed text does ("Purata Nilai Gred …", the "(Number of Subjects Passed)" subtitle). A
    stray token where the number belongs ('S', 'l', '4.') is a MIS-read, and a bracketed digit ('(4)')
    is a printed count — neither is an absence → False."""
    toks = [t for t in _after(rows[i], 'LULUS') if _letters(t)]
    if toks and any(c.isdigit() for c in toks[0]):
        return False
    return not toks or toks[0].startswith('(') or _letters(toks[0]) == 'PURATA'


def _point_after(rows, i, label_key):
    if i < 0:
        return None
    for t in _after(rows[i], label_key):
        if _GP_RE.match(t):
            return t
    return None


# ── The slip (and transcript) ────────────────────────────────────────────────────────────────


def _slip_subjects(rows, start, words_given):
    """Subject rows between the KOD header and the notes: a row led by a 9xx code opens a subject;
    its grade + grade point sit on that row (a scan) or, on a text layer, alone on the last line
    of the block. Paper rows (no code) are never subjects."""
    end = len(rows)
    for key in ('NOTA', 'NOTE', 'KETUAEKSEKUTIF', 'CHIEFEXECUTIVE'):
        j = _find(rows, key, start=start)
        end = min(end, j) if j >= 0 else end
    blocks, cur = [], None
    for row in rows[start:end]:
        if _CODE_RE.match(row[0]):
            cur = {'head': row[1:], 'body': []}
            blocks.append(cur)
        elif cur is not None:
            cur['body'].append(row)
    read = []
    for b in blocks:
        split = _split_subject(b['head'])
        if split is None:
            return None
        subject, grade, point = split
        if grade is None and point is None and not words_given:
            pairs = [r for r in b['body'] if len(r) == 2 and r[0] in GRADE_POINTS and _point_of(r[1])]
            if len(pairs) != 1 or b['body'][-1] is not pairs[0]:
                return None                  # the subject's grade + point close its block
            grade, point = pairs[0][0], _point_of(pairs[0][1])
        read.append({'subject': subject, 'grade': grade, 'point': point})
    return read


def _parse_slip(rows, words_given, entered=None):
    namas = [i for i, r in enumerate(rows) if _letters(r[0]).startswith('NAMA')]
    if len(namas) != 1:                      # none, or two documents in one upload
        return None
    nama = namas[0]
    rows = rows[nama:]                       # a transcript's English page comes first: skip it
    tokens = _after(rows[0], 'NAMA')
    ic = _find(rows, 'KADPENGENALAN')
    if ic not in (1, 2):                     # the IC row must follow, or follow ONE wrapped row
        return None
    if ic == 2:                              # a name wrapped onto the ONE row before the IC
        tokens += rows[1]
    name = _clean_name(tokens)
    kod = _find(rows, 'KOD', 'MATAPELAJARAN')
    ic_value = ''.join(_after(rows[ic], 'PENGENALAN')) if ic > 0 else ''
    if not name or kod < 0 or not _NRIC_RE.fullmatch(ic_value):
        return None                          # anything else on the IC row: a name ran onto it
    pngk_row = _find(rows, 'PNGK')
    count_row = _find(rows, 'MATAPELAJARANDIDAFTARKAN')
    count = _count_after(rows, count_row, 'DIDAFTARKAN')
    if count == 'missing':
        return None
    subjects = _slip_subjects(rows, kod + 1, words_given)
    results = _checked_results(subjects, _point_after(rows, pngk_row, 'PNGK'), count, 'registered',
                               entered)
    if results is None:
        return None
    return {'candidate_name': name, 'nric': _nric(rows, ic),
            'index_no': _index_no(rows, _find(rows, 'ANGKAGILIRAN')),
            'cgpa': _point_after(rows, pngk_row, 'PNGK'), 'results': results}


# ── The certificate ──────────────────────────────────────────────────────────────────────────

_STATUS = ('LULUS', 'GAGAL', 'FULL', 'PARTIAL', 'FAIL')


def _cert_subjects(rows, start, end):
    """Each row between the subject header and "Bilangan Mata Pelajaran Lulus": NAME [grade]
    point (LULUS PENUH). English subtitle rows open with '(' and are skipped; anything else that
    does not read as a subject row → None (a skewed photo whose grades sit between rows)."""
    read = []
    for row in rows[start:end]:
        if row[0].startswith('('):
            continue
        cut = next((k for k, t in enumerate(row) if t.startswith('(')), len(row))
        tail = _letters(''.join(row[cut:]))
        if tail and not any(tail.startswith(s) for s in _STATUS):
            return None
        split = _split_subject(row[:cut])
        if split is None:
            return None
        subject, grade, point = split
        read.append({'subject': subject, 'grade': grade, 'point': point})
    return read


def _cert_year(rows):
    i = _find(rows, 'TAHUNPEPERIKSAAN')
    if i < 0:
        return None
    m = re.search(r'PEPERIKSAAN\s*:?\s*(20\d\d)\b', ' '.join(rows[i]).upper())
    return int(m.group(1)) if m else None


def _cert_name_wraps(rows, who):
    """Does a capitalised word sit between the name row and the IC row (a long name wrapped onto
    the next line, which a same-row read would truncate)? Then the name is not read Exact."""
    ic = _find(rows, 'KADPENGENALAN', start=who)
    for r in rows[who + 1:ic if ic > who else who + 2]:
        words = [t for t in r if t not in ('(This', 'This', 'is', 'to', 'certify', 'that', '(', ')')
                 and t not in _NOT_A_NAME]          # the title's own words are never a name
        if any(re.fullmatch(r"[A-Z][A-Z'@/.\-]+", t) for t in words):
            return True
    return False


def _name_tokens(row):
    """The name after "disahkan bahawa", minus the English subtitle when a text layer prints it on
    the same line — and only that exact phrase ("(This is to certify that"); anything else stays."""
    tokens = _after(row, 'BAHAWA')
    cut = next((k for k, t in enumerate(tokens) if t.startswith('(')), None)
    if cut is not None and _letters(''.join(tokens[cut:])) == 'THISISTOCERTIFYTHAT':
        tokens = tokens[:cut]
    return tokens


def _parse_cert(rows, entered=None, words_given=False):
    whos = [i for i, r in enumerate(rows) if 'DISAHKANBAHAWA' in _letters(''.join(r))]
    if len(whos) != 1 or _cert_name_wraps(rows, whos[0]):
        return None
    name = _clean_name(_name_tokens(rows[whos[0]]))
    head = next((i for i, r in enumerate(rows) if _letters(''.join(r)).startswith('MATAPELAJARAN')), -1)
    lulus = _find(rows, 'BILANGANMATAPELAJARANLULUS')
    purata = _find(rows, 'PURATANILAIGRED')
    if not name or head < 0 or lulus <= head:
        return None
    count = _count_after(rows, lulus, 'LULUS')
    label = 'KESELURUHAN' if _find(rows, 'PURATANILAIGREDKESELURUHAN') >= 0 else 'KUMULATIF'
    pngk = _point_after(rows, purata, label)
    read, year = _cert_subjects(rows, head + 1, lulus), _cert_year(rows)
    if read is None and not words_given and count == 'missing':   # a column-ordered text layer
        from .stpm_columns import cert_columns
        columns = cert_columns(rows, head, lulus, purata)
        if columns is not None:
            read, pngk, year, count = columns
    if count == 'missing':      # absent → no count gate; the PNGK must still equal the recomputed one
        # ... and the rows read must equal the subjects the student entered; with no entry, only a
        # digital text layer (never a scan) may go without its count (review, 2026-10-28).
        entered_n = getattr(entered, 'count', None)
        if not _count_absent(rows, lulus) or read is None or (
                len(read) != entered_n if entered_n else words_given):
            return None
        count = None
    results = _checked_results(read, pngk, count, 'passed', entered)
    if results is None or year is None:
        return None
    return {'candidate_name': name, 'nric': _nric(rows, _find(rows, 'KADPENGENALAN')),
            'index_no': _index_no(rows, _find(rows, 'ANGKAGILIRAN')), 'cgpa': pngk,
            'results': results, 'exam_year': year}


# ── The entry point ──────────────────────────────────────────────────────────────────────────


def parse(text, words=None, entered=None):
    """STPM results OCR text (+ Vision word boxes for a scan) → the higher-results field dict, or
    None to defer to Gemini. ``entered(subject) -> grade | None`` is the student's own entry for a
    printed subject, already normalised (`higher_results.entered_grade_value`) — rule 2 of
    `_settle_grade`; without it only cleanly read rows pass. The result carries `_rows_from_entry`
    (subjects completed by rule 2) and `_rows_sign_from_point` (ruling B) for the caller to store OUTSIDE the fields. Never raises."""
    try:
        return _parse(text, words, entered)
    except Exception:          # a reader bug must fall back to AI, never break a read
        return None


def _parse(text, words, entered):
    rows = _rows_of(text, words)
    flat = _letters(''.join(''.join(r) for r in rows))
    found = _layout(flat, rows)
    if found is None:
        return None
    layout, year = found
    fields = (_parse_cert(rows, entered, bool(words)) if layout == 'certificate'
              else _parse_slip(rows, bool(words), entered))
    if fields is None or not fields['nric']:
        return None
    ics = {''.join(m.groups()) for r in rows for m in _NRIC_RE.finditer(' '.join(r))}
    if ics != {fields['nric']}:              # another person's IC on the page
        return None
    year = fields.pop('exam_year', None) or year
    if not year or not 2000 <= year <= 2100:
        return None
    return {
        'candidate_name': fields['candidate_name'],
        'exam': f'SIJIL TINGGI PERSEKOLAHAN MALAYSIA {year}',   # one title for every layout
        'exam_year': str(year), 'nric': fields['nric'], 'index_no': fields['index_no'],
        'cgpa': fields['cgpa'], 'cgpa_label': 'PNGK',          # STPM's PNGK is cumulative
        'institution': '',
        'results': [{'subject': r['subject'], 'grade': r['grade']} for r in fields['results']],
        # Audit only: the caller moves this out of the fields, beside `capture` (never a field).
        '_rows_from_entry': [r['subject'] for r in fields['results'] if r['from_entry']],
        '_rows_sign_from_point': [r['subject'] for r in fields['results'] if r['sign_from_point']],
    }
