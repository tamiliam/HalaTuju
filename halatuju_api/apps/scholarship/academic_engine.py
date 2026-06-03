"""
Academic verification (Sprint 2 of the verification-verdict roadmap).

Two checks the officer otherwise does by eye, against the results slip:
  - **Completeness** — is every subject ON the slip entered in the system?
    (Theresa entered 8 of her 10 — missing Moral + Tamil Literature.)
  - **Accuracy** — for the subjects entered, do the TYPED grades match the
    grades printed on the slip? Typed and OCR'd are two independent readings;
    agreement is strong verification, disagreement pinpoints the one cell.

Comparison is by **normalised subject name**, not grade key — this sidesteps the
``b_tamil`` / ``bahasa_tamil`` (and similar) key collisions in the subject table,
and lets the OCR'd Malay name match the profile's subject regardless of which
internal key the profile happens to use.

``_SUBJECT_BM`` mirrors the Bahasa-Melayu names in
``halatuju-web/src/lib/subjects.ts`` (``SUBJECT_NAMES``). Keep the two in sync —
they are the only two copies of this mapping (see lessons #88/#93). Pure +
deterministic; the grades themselves are extracted by Gemini in ``vision.py`` and
this module only DECIDES from them, so a hallucinated grade can never become a
silent 'verified'.
"""
from __future__ import annotations

import re

# grade key → Bahasa-Melayu subject name (mirror of subjects.ts SUBJECT_NAMES).
_SUBJECT_BM = {
    'bm': 'Bahasa Melayu', 'eng': 'Bahasa Inggeris', 'math': 'Matematik',
    'addmath': 'Matematik Tambahan', 'hist': 'Sejarah', 'sci': 'Sains',
    'addsci': 'Sains Tambahan', 'islam': 'Pendidikan Islam', 'moral': 'Pendidikan Moral',
    'phy': 'Fizik', 'chem': 'Kimia', 'bio': 'Biologi',
    'geo': 'Geografi', 'ekonomi': 'Ekonomi', 'poa': 'Prinsip Perakaunan',
    'business': 'Perniagaan', 'keusahawanan': 'Pengajian Keusahawanan',
    'psv': 'Pendidikan Seni Visual', 'music': 'Pendidikan Muzik', 'sports_sci': 'Sains Sukan',
    'eng_civil': 'Kejuruteraan Awam', 'eng_mech': 'Kejuruteraan Mekanikal',
    'eng_elec': 'Kejuruteraan Elektrik', 'eng_draw': 'Lukisan Kejuruteraan',
    'lukisan_kejuruteraan': 'Lukisan Kejuruteraan', 'gkt': 'Grafik Komunikasi Teknikal',
    'kelestarian': 'Asas Kelestarian', 'reka_cipta': 'Reka Cipta',
    'srt': 'Sains Rumah Tangga', 'pertanian': 'Pertanian',
    'comp_sci': 'Sains Komputer', 'multimedia': 'Multimedia', 'digital_gfx': 'Grafik Digital',
    'lit_bm': 'Kesusasteraan Melayu Komunikatif', 'lit_eng': 'Kesusasteraan Inggeris',
    'lit_cina': 'Kesusasteraan Cina', 'lit_tamil': 'Kesusasteraan Tamil',
    'lukisan': 'Lukisan', 'sejarah_seni': 'Sejarah dan Pengurusan Seni',
    'bahasa_arab': 'Bahasa Arab', 'bahasa_arab_tinggi': 'Bahasa Arab Tinggi',
    'bahasa_cina': 'Bahasa Cina', 'bahasa_tamil': 'Bahasa Tamil', 'bahasa_iban': 'Bahasa Iban',
    'bahasa_kadazandusun': 'Bahasa Kadazandusun', 'bahasa_semai': 'Bahasa Semai',
    'bahasa_punjabi': 'Bahasa Punjabi', 'bible_knowledge': 'Pengetahuan Bible',
    'bahasa_perancis': 'Bahasa Perancis', 'bahasa_jepun': 'Bahasa Jepun',
    'bahasa_jerman': 'Bahasa Jerman', 'b_cina': 'Bahasa Cina', 'b_tamil': 'Bahasa Tamil',
    'pqs': 'Pendidikan Al-Quran & Al-Sunnah', 'psi': 'Pendidikan Syariah Islamiah',
}


# SPM grade-BANDS. Every subject row on an SPM slip prints the grade twice — as a
# Malay word-band AND as a letter — e.g. "MATEMATIK ... CEMERLANG TINGGI ... A".
# Gemini sometimes glues the band words onto the subject ("MATEMATIK CEMERLANG
# TINGGI"), which then fails to match the profile's "Matematik" → every subject
# reads as "missing". So we STRIP a trailing band phrase from the subject name, and
# keep the band→letter map as a fallback when the letter grade itself is unreadable.
_BAND_TO_GRADE = {
    'cemerlang tertinggi': 'A+', 'cemerlang tinggi': 'A', 'cemerlang': 'A-',
    'kepujian tertinggi': 'B+', 'kepujian tinggi': 'B', 'kepujian atas': 'C+',
    'kepujian': 'C', 'lulus atas': 'D', 'lulus': 'E', 'gagal': 'G',
    'tidak hadir': 'TH',
}
# Trailing band phrase: a band word (cemerlang/kepujian/lulus/gagal) optionally
# followed by a modifier (tertinggi/tinggi/atas). Anchored at the END so a real
# subject like "Bahasa Arab Tinggi" is untouched (no band word precedes "Tinggi").
_BAND_RE = re.compile(
    r'\s+(cemerlang|kepujian|lulus|gagal)(?:\s+(tertinggi|tinggi|atas))?\s*$',
    re.IGNORECASE,
)


def _split_band(name: str):
    """Split a slip subject into ``(clean_subject, band_grade)``. ``band_grade`` is the
    letter implied by the stripped band phrase ('' if none), used only as a fallback
    when the OCR'd letter grade is missing."""
    s = (name or '').strip()
    m = _BAND_RE.search(s)
    if not m:
        return s, ''
    phrase = ' '.join(p for p in (m.group(1), m.group(2)) if p).lower()
    return s[:m.start()].strip(), _BAND_TO_GRADE.get(phrase, '')


def _band_to_grade(phrase: str) -> str:
    """The letter grade implied by a full Malay band phrase (the slip's redundant
    second encoding of the grade), or '' if unrecognised. 'Cemerlang Tertinggi' → 'A+'."""
    return _BAND_TO_GRADE.get(' '.join((phrase or '').lower().split()), '')


def _norm(name: str) -> str:
    """Lowercase, collapse runs of non-alphanumerics to single spaces, strip."""
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


def _norm_grade(g: str) -> str:
    """Spaces out, uppercase. 'A -' / ' a-' → 'A-'."""
    return re.sub(r'\s+', '', (g or '')).upper()


def _base_letter(g: str) -> str:
    """The SPM grade WITHOUT its +/- modifier: 'A+' / 'A-' → 'A'. The +/- is the
    OCR-unreliable bit (a faint '+', a 'Ter-' prefix on the band), so a mismatch
    that differs ONLY by the modifier is treated as uncertain, not asserted."""
    return _norm_grade(g).rstrip('+-')


# ── Deterministic positional parse of an SPM results slip (OCR-first) ──────────
# SPM slips are STANDARDISED: a two-column table of subject names and grades, each
# grade printed twice — a letter (A-) AND a Malay word-band (Cemerlang). The reliable
# way to read them is POSITIONALLY: group the OCR words into rows by their Y-coordinate
# so each subject pairs with the grade ON ITS OWN ROW. This is immune to the row
# transposition that free-form vision extraction suffers on a watermarked slip (where
# it pairs a subject with a neighbouring row's grade — the live "PERTANIAN reads B"
# bug). The band word is the authoritative, OCR-reliable grade signal; the letter
# confirms it. ``parse_spm_slip`` returns None to fall back to Gemini when the image
# doesn't parse as an SPM slip. Pure (takes a word list) → unit-testable, no live calls.

_SLIP_NAME_MARKER = re.compile(r'\b(a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti)\b', re.IGNORECASE)
_GRADE_TOKENS = frozenset({'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G', 'TH'})
_BAND_HEADS = frozenset({'cemerlang', 'kepujian', 'lulus', 'gagal'})
_BAND_MODS = frozenset({'tertinggi', 'tinggi', 'atas'})

# Every known SPM subject as (canonical_name, token_set), LONGEST first so e.g.
# "Matematik Tambahan" wins over "Matematik" on a subset match.
_KNOWN_SUBJECTS = sorted(
    ((name, frozenset(_norm(name).split())) for name in set(_SUBJECT_BM.values())),
    key=lambda t: -len(t[1]),
)


def _match_known_subject(raw: str) -> str:
    """Resolve an OCR'd slip row to the canonical SPM subject it CONTAINS — instead of
    matching word-for-word. A row reads e.g. "1103 BAHASA MELAYU" or "4541 KIMIA
    Malaysia" (subject code + OCR noise + watermark text); we keep the row iff a known
    subject's words are all present in it, and return that subject's clean name. Strips
    codes/noise for free, and drops non-subject rows (an "Ujian Lisan" oral line, a
    watermark fragment). '' when no known subject matches."""
    tokens = set(_norm(raw).split())
    if not tokens:
        return ''
    for name, kt in _KNOWN_SUBJECTS:
        if kt and kt <= tokens:
            return name
    return ''


def _group_rows(words, *, y_tol_frac=0.6):
    """Cluster OCR words into visual ROWS by Y-coordinate — words at the same vertical
    position are one row, returned left-to-right; rows top-to-bottom. Each word is a
    dict ``{text, cx, cy, h}`` (centre x/y + height). This is what makes the parse
    transposition-proof: pairing is by geometry, not by the model's reading order."""
    usable = [w for w in (words or []) if (w.get('text') or '').strip()]
    if not usable:
        return []
    heights = sorted((w.get('h') or 0) for w in usable)
    med_h = heights[len(heights) // 2] or 12
    tol = max(med_h * y_tol_frac, 6)
    rows: list[dict] = []
    for w in sorted(usable, key=lambda w: w['cy']):
        for row in rows:
            if abs(w['cy'] - row['cy']) <= tol:
                row['ws'].append(w)
                break
        else:
            rows.append({'cy': w['cy'], 'ws': [w]})
    rows.sort(key=lambda r: r['cy'])
    return [sorted(r['ws'], key=lambda w: w['cx']) for r in rows]


def _parse_grade_row(row):
    """One slip row → ``{subject, grade, band}`` or None (not a graded subject row).
    The grade column starts at the first letter-grade OR band word; everything to its
    LEFT is the subject — so subject and grade stay row-aligned."""
    toks = [w['text'] for w in row]
    norm = [t.strip('()[].').strip().upper() for t in toks]
    low = [t.lower() for t in norm]
    grade_idx = next((i for i, t in enumerate(norm) if t in _GRADE_TOKENS), None)
    band_idx = next((i for i, t in enumerate(low) if t in _BAND_HEADS or t == 'tidak'), None)
    # Every SPM grade row prints a Malay word-band — requiring one excludes header /
    # name rows (e.g. an OCR-split "A/P" in a name that looks like an "A" grade).
    if band_idx is None:
        return None
    cut = min(i for i in (grade_idx, band_idx) if i is not None)
    raw_subject = ' '.join(toks[:cut]).strip(' .:-\t')
    # Resolve to the known SPM subject this row IS (ignoring the subject code + OCR
    # noise); drop the row if it isn't a recognised subject (header / oral-test / noise).
    subject = _match_known_subject(raw_subject)
    if not subject:
        return None
    head = low[band_idx]
    if head == 'tidak':
        band = 'tidak hadir'
    else:
        nxt = low[band_idx + 1] if band_idx + 1 < len(low) else ''
        band = (head + ' ' + nxt).strip() if nxt in _BAND_MODS else head
    # The letter grade must sit in the grade column (between the subject and the band),
    # i.e. before the band word — not a stray letter inside the subject name.
    letter = norm[grade_idx] if (grade_idx is not None and grade_idx < band_idx) else ''
    grade = letter or _band_to_grade(band)
    if not grade:
        return None
    return {'subject': subject, 'grade': grade, 'band': band}


def _slip_name(rows):
    """Candidate name — the top-area line carrying a parentage marker (a/p, a/l, bin,
    binti); '' if none (a marker-less name) so the downstream name check is skipped
    rather than fed a wrong value."""
    for row in rows[:12]:
        line = ' '.join(w['text'] for w in row).strip()
        if _SLIP_NAME_MARKER.search(line) and not any(ch.isdigit() for ch in line):
            return line
    return ''


def _slip_exam(rows):
    text = ' '.join(w['text'] for row in rows for w in row)
    if 'SIJIL PELAJARAN MALAYSIA' not in text.upper():
        return ''
    m = re.search(r'\b(20\d{2})\b', text)
    return f'SIJIL PELAJARAN MALAYSIA TAHUN {m.group(1)}' if m else 'SIJIL PELAJARAN MALAYSIA'


def parse_spm_slip(words):
    """Deterministic positional parse of SPM-slip OCR words →
    ``{candidate_name, exam, results: [{subject, grade, band}]}``, or **None** to fall
    back to Gemini (not an SPM slip, or fewer than 3 subject rows recognised)."""
    rows = _group_rows(words)
    if not rows:
        return None
    full = ' '.join(w['text'] for row in rows for w in row).upper()
    if 'SIJIL PELAJARAN MALAYSIA' not in full and 'LEMBAGA PEPERIKSAAN' not in full:
        return None
    results, seen = [], set()
    for row in rows:
        gr = _parse_grade_row(row)
        if not gr:
            continue
        nn = _norm(gr['subject'])
        if nn in seen:
            continue
        seen.add(nn)
        results.append(gr)
    if len(results) < 3:
        return None
    # _debug_rows: the raw grouped OCR lines (top-to-bottom) — a temporary diagnostic so
    # a misparsed grade row can be inspected from the stored record. Ignored downstream.
    debug = [' '.join(w['text'] for w in row) for row in rows]
    return {'candidate_name': _slip_name(rows), 'exam': _slip_exam(rows),
            'results': results, '_debug_rows': debug}


def read_slip(doc) -> dict:
    """Pull subject names + grades out of a results_slip's doc-assist fields.

    Returns ``{names: [str], grades: {normname: grade}}``. Supports the new
    ``results: [{subject, grade}]`` shape (S2) AND the legacy ``subjects: [name]``
    shape (names only, no grades) — so completeness works on already-extracted
    docs without re-OCR; accuracy needs the new shape."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    fields = vf.get('fields', {})
    fields = fields if isinstance(fields, dict) else {}
    names: list[str] = []
    grades: dict[str, str] = {}
    bands: dict[str, str] = {}   # normname → grade implied by the slip's band phrase
    results = fields.get('results')
    if isinstance(results, list) and results:
        for r in results:
            if isinstance(r, dict):
                # Strip any band words Gemini glued onto the subject ("MATEMATIK
                # CEMERLANG TINGGI" → "MATEMATIK"); that leak also yields a band grade.
                s, leaked_band = _split_band(r.get('subject') or '')
                # The explicit band field (the slip's redundant 2nd grade encoding).
                band_grade = _band_to_grade(r.get('band') or '') or leaked_band
                g = (r.get('grade') or '').strip() or band_grade
                if s:
                    names.append(s)
                    nn = _norm(s)
                    if g:
                        grades[nn] = g
                    if band_grade:
                        bands[nn] = band_grade
    else:
        subs = fields.get('subjects')
        if isinstance(subs, list):
            names = [_split_band(s)[0] for s in subs if isinstance(s, str) and s.strip()]
    return {'names': names, 'grades': grades, 'bands': bands}


def compare_academics(profile_grades, slip) -> dict:
    """Compare the slip's subjects/grades against what the student typed.

    Returns ``{slip_count, missing, mismatched: [{subject, typed, slip}],
    uncertain: [{subject, typed, slip, band}], have_grades, complete, accurate}``.

    The slip prints each grade twice — a letter AND a Malay band. When the two
    DISAGREE for a row, the read is unreliable for that subject, so a would-be
    grade mismatch is downgraded to **uncertain** ("please check") rather than
    asserted as a confident mismatch (guards against an OCR row-transposition
    confidently telling the student a wrong grade)."""
    prof_by_name = {}
    for key, grade in (profile_grades or {}).items():
        nm = _SUBJECT_BM.get(key)
        if nm and grade:
            prof_by_name[_norm(nm)] = grade

    slip_norm = {}  # normname → first readable form
    for n in slip['names']:
        slip_norm.setdefault(_norm(n), n)
    bands = slip.get('bands', {})

    missing = sorted(orig for nn, orig in slip_norm.items() if nn not in prof_by_name)
    mismatched, uncertain = [], []
    for nn, slip_g in slip['grades'].items():
        typed = prof_by_name.get(nn)
        if not typed or _norm_grade(typed) == _norm_grade(slip_g):
            continue  # not entered, or the typed grade matches the slip letter
        band_g = bands.get(nn)
        row = {'subject': slip_norm.get(nn, nn), 'typed': typed, 'slip': slip_g}
        band_conflict = bool(band_g) and _norm_grade(band_g) != _norm_grade(slip_g)
        # A difference that is ONLY the +/- modifier (A+ vs A) sits in the OCR's blind
        # spot — even a consistent letter+band misread can't be trusted there.
        pm_only = _base_letter(typed) == _base_letter(slip_g)
        if band_conflict or pm_only:
            uncertain.append({**row, 'band': band_g or ''})
        else:
            mismatched.append(row)
    return {
        'slip_count': len(slip_norm),
        'missing': missing,
        'mismatched': mismatched,
        'uncertain': uncertain,
        'have_grades': bool(slip['grades']),
        'complete': len(slip_norm) > 0 and not missing,
        'accurate': not mismatched and not uncertain,
    }


def _slip_name_status(doc) -> str:
    """Name check for a results slip, from the doc-assist read: 'match' / 'mismatch'
    / 'unreadable' / 'pending' (not yet field-extracted)."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = vf.get('student_verdict')
    if sv == 'name_mismatch':
        return 'mismatch'
    if sv in ('wrong_doc', 'unreadable') or doc.vision_name_match == 'unreadable':
        return 'unreadable'
    if sv == 'ok' or doc.vision_name_match == 'found':
        return 'match'
    if sv == 'review_manually':
        return 'pending'
    return 'pending'


def student_slip_check(doc) -> dict:
    """The clinical three-check read of ONE results slip against the student's own
    profile — the single source the serializer (for the FE checklist) and the help
    coach (to pick its advice) both consume, so they can never disagree.

    Returns ``{name, subjects, results}`` each 'match' / 'mismatch' / 'unreadable'
    / 'pending', plus ``{candidate_name, missing, mismatched, slip_count}`` detail.
    Reads ONLY the student's own document + profile (no admin data)."""
    name = _slip_name_status(doc)
    data = read_slip(doc)
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = vf.get('student_verdict')
    f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
    candidate_name = (f.get('candidate_name') or '')
    exam = (f.get('exam') or '').strip()              # e.g. "SIJIL PELAJARAN MALAYSIA TAHUN 2025"
    em = re.search(r'\b(20\d{2})\b', exam)
    exam_year = em.group(1) if em else ''             # soft data point — surfaced, not gated

    if not data['names']:
        # No subject rows. Distinguish "extraction hasn't run / was skipped" (genuinely
        # PENDING) from "Gemini ran but couldn't read the subject table" (UNREADABLE — the
        # student should re-upload a clearer copy). A bare candidate-name with empty results
        # is the latter.
        pending = (not sv) or sv == 'review_manually'
        s = 'pending' if pending else 'unreadable'
        return {'name': name, 'subjects': s, 'results': s,
                'candidate_name': candidate_name, 'exam': exam, 'exam_year': exam_year,
                'missing': [], 'mismatched': [], 'uncertain': [], 'slip_count': 0}

    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    cmp = compare_academics(getattr(profile, 'grades', None), data)
    subjects = 'mismatch' if cmp['missing'] else 'match'
    if not cmp['have_grades']:
        results = 'pending'
    elif cmp['mismatched']:
        results = 'mismatch'
    elif cmp['uncertain']:
        results = 'uncertain'   # letter↔band disagree → please check, not a confident mismatch
    else:
        results = 'match'
    return {
        'name': name, 'subjects': subjects, 'results': results,
        'candidate_name': candidate_name, 'exam': exam, 'exam_year': exam_year,
        'missing': cmp['missing'], 'mismatched': cmp['mismatched'],
        'uncertain': cmp['uncertain'], 'slip_count': cmp['slip_count'],
    }
