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

import math
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
    # Islamic studies (extended) — code-health S1 #4: these blocks had drifted out of
    # sync with subjects.ts (64 keys the grades form offers were unknown here, so a
    # student's entered grade was dropped AND the slip row bounced — a permanent
    # "missing subject" loop). test_subject_drift.py now pins the mirror.
    'tasawwur_islam': 'Tasawwur Islam', 'usul_aldin': 'Usul Al-Din',
    'al_syariah': 'Al-Syariah', 'manahij': 'Manahij', 'lughah_arabiah': 'Lughah Arabiah',
    'adab_balaghah': 'Adab & Balaghah', 'hifz_alquran': 'Hifz Al-Quran',
    'maharat_alquran': 'Maharat Al-Quran', 'turath_islamiah': 'Turath Islamiah',
    'turath_quran_sunnah': 'Turath Quran & Sunnah', 'turath_bahasa_arab': 'Turath Bahasa Arab',
    # Arts & performance
    'reka_bentuk_grafik': 'Reka Bentuk Grafik', 'reka_bentuk_industri': 'Reka Bentuk Industri',
    'reka_bentuk_kraf': 'Reka Bentuk Kraf', 'multimedia_kreatif': 'Multimedia Kreatif',
    'produksi_reka_tanda': 'Produksi Reka Tanda', 'produksi_multimedia': 'Produksi Multimedia',
    'produksi_seni': 'Produksi Seni Persembahan', 'seni_halus_2d': 'Seni Halus 2D',
    'seni_halus_3d': 'Seni Halus 3D', 'aural_teori_muzik': 'Aural & Teori Muzik',
    'alat_muzik': 'Alat Muzik Utama', 'muzik_komputer': 'Muzik Komputer',
    'tarian': 'Tarian', 'koreografi': 'Koreografi Tari', 'apresiasi_tari': 'Apresiasi Tari',
    'lakonan': 'Lakonan', 'sinografi': 'Sinografi', 'penulisan_skrip': 'Penulisan Skrip',
    # Vocational / MPV
    'hiasan_dalaman': 'Hiasan Dalaman', 'kerja_paip': 'Kerja Paip',
    'pembinaan_domestik': 'Pembinaan Domestik', 'pembuatan_perabot': 'Pembuatan Perabot',
    'katering': 'Katering', 'pemprosesan_makanan': 'Pemprosesan Makanan',
    'rekaan_jahitan': 'Rekaan & Jahitan', 'penjagaan_muka': 'Penjagaan Muka & Badan',
    'asuhan_kanak': 'Asuhan Kanak-Kanak', 'gerontologi': 'Gerontologi',
    'pendawaian_domestik': 'Pendawaian Domestik', 'menservis_automobil': 'Menservis Automobil',
    'kimpalan': 'Kimpalan', 'menservis_motosikal': 'Menservis Motosikal',
    'penyejukan': 'Penyejukan & Penyamanan Udara', 'landskap_nurseri': 'Landskap & Nurseri',
    'tanaman_makanan': 'Tanaman Makanan', 'akuakultur': 'Akuakultur',
    'menservis_elektrik': 'Menservis Peralatan Elektrik',
    'voc_food': 'Vokasional Makanan', 'voc_landscape': 'Vokasional Landskap',
    'voc_construct': 'MPV Binaan Bangunan', 'voc_weld': 'MPV Kimpalan & Fabrikasi',
    'voc_auto': 'MPV Automotif', 'voc_elec_serv': 'MPV Elektrik & Elektronik',
    'voc_catering': 'MPV Katering & Penyajian', 'voc_tailoring': 'MPV Jahitan & Pakaian',
    # Technical / vocational (SPM_CODE_MAP targets)
    'teknologi_kej': 'Teknologi Kejuruteraan',
    'prinsip_elektrik': 'Prinsip Elektrik & Elektronik',
    'aplikasi_elektrik': 'Aplikasi Elektrik & Elektronik',
    'pemesinan_berkomputer': 'Pemesinan Berkomputer',
    'aplikasi_komputer': 'Aplikasi Komputer dlm Perniagaan',
    'komunikasi_visual': 'Komunikasi Visual', 'bahan_binaan': 'Bahan Binaan',
    'teknologi_binaan': 'Teknologi Binaan',
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


def _dominant_angle(words) -> float:
    """The slip's overall text-baseline angle (degrees), or 0.0 when near-upright.
    Median over the per-word ``angle`` (robust to a few outliers — diagonal watermarks,
    Jawi marks). Gated: a result within ±25° of horizontal is treated as upright (0.0)
    so a clean, upright slip is NEVER rotated by OCR angle-noise (the earlier regression).
    Only a clearly-rotated slip (~±90°) crosses the gate and gets de-rotated."""
    angs = sorted(w['angle'] for w in words if w.get('angle') is not None)
    if not angs:
        return 0.0
    med = angs[len(angs) // 2]
    return med if abs(med) >= 25.0 else 0.0


def _row_tol(axis_sorted) -> float:
    """Row-merge tolerance for the de-rotated row axis — half the typical between-row
    pitch (the median of the larger gaps), clamped to a sane band. Derived from the data
    so it adapts to the slip's resolution (a phone photo can be 4000px tall)."""
    gaps = sorted(b - a for a, b in zip(axis_sorted, axis_sorted[1:]) if b - a > 1.5)
    if not gaps:
        return 12.0
    upper = gaps[len(gaps) // 2:]            # the larger gaps ≈ between-row pitch
    pitch = upper[len(upper) // 2]
    return max(min(pitch * 0.5, 40.0), 10.0)


def _group_rows(words, *, y_tol_frac=0.6):
    """Cluster OCR words into visual ROWS — words at the same row position are one row,
    returned in reading order; rows top-to-bottom. Each word is a dict
    ``{text, cx, cy, h, angle?}``. This is what makes the parse transposition-proof:
    pairing is by geometry, not by the model's reading order.

    Orientation-robust: an upright slip groups by raw Y (unchanged). A clearly-rotated
    slip (phone photo turned sideways, ~±90°, possibly with keystone) is first DE-ROTATED
    by its dominant text angle — the row axis ``y' = -cx·sinθ + cy·cosθ`` becomes
    horizontal again, so each subject still pairs with the grade on its own row. Without
    this, a rotated slip clusters by raw cy into nonsense and the whole parse is abandoned
    to Gemini, which transposes grades on a watermark."""
    usable = [w for w in (words or []) if (w.get('text') or '').strip()]
    if not usable:
        return []
    theta = _dominant_angle(usable)
    if theta == 0.0:
        # Upright: group by raw Y, order by raw X (original behaviour — unchanged).
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
    # Rotated: de-rotate every centroid by the dominant angle, cluster on the row axis,
    # read along the text axis. Single-linkage along the sorted row axis tolerates a
    # row's internal spread (a keystone leaves the subject and its grade slightly offset)
    # while still splitting cleanly at the larger between-row gap.
    rad = math.radians(theta)
    cos, sin = math.cos(rad), math.sin(rad)
    proj = [(-w['cx'] * sin + w['cy'] * cos,    # row axis (top→bottom of the slip)
             w['cx'] * cos + w['cy'] * sin,     # text axis (reading order within a row)
             w) for w in usable]
    proj.sort(key=lambda p: p[0])
    tol = _row_tol([p[0] for p in proj])
    rows_r = [[proj[0]]]
    for prev, cur in zip(proj, proj[1:]):
        (rows_r[-1].append(cur) if cur[0] - prev[0] <= tol else rows_r.append([cur]))
    return [[w for _, _, w in sorted(r, key=lambda p: p[1])] for r in rows_r]


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
    # i.e. before the band word — not a stray letter inside the subject name. OCR often
    # splits "A+"/"A-" into "A" then "+"/"-" → reassemble.
    letter = ''
    if grade_idx is not None and grade_idx < band_idx:
        letter = norm[grade_idx]
        if len(letter) == 1 and grade_idx + 1 < band_idx and norm[grade_idx + 1] in ('+', '-'):
            letter += norm[grade_idx + 1]
    # The Malay word-BAND is the AUTHORITATIVE grade. It's distinctive text OCR reads
    # reliably ("Cemerlang Tertinggi"), whereas the letter's +/- is a tiny mark that
    # gets split, dropped, or spilled onto another line — so the letter alone reads
    # "A" where the slip plainly says "A+ · Cemerlang Tertinggi". The letter is only a
    # fallback when the band is somehow unrecognised.
    grade = _band_to_grade(band) or letter
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


# Malay cardinals for the slip's own declared subject total ("JUMLAH MATA PELAJARAN :
# SEPULUH" = 10). Used to detect an under-read and bounce to Gemini.
_MALAY_NUM = {'ENAM': 6, 'TUJUH': 7, 'LAPAN': 8, 'DELAPAN': 8, 'SEMBILAN': 9,
              'SEPULUH': 10, 'SEBELAS': 11}


def _declared_subject_count(full_upper: str):
    """The subject total the slip prints in 'JUMLAH MATA PELAJARAN <word>', or None.
    SPM slips state it as a Malay cardinal (e.g. SEPULUH = 10)."""
    m = re.search(r'JUMLAH MATA PELAJARAN\s*:?\s*(.{0,30})', full_upper)
    if not m:
        return None
    tail = m.group(1)
    if 'DUA BELAS' in tail:
        return 12
    for word, n in _MALAY_NUM.items():
        if re.search(r'\b' + word + r'\b', tail):
            return n
    return None


def parse_spm_slip(words):
    """Deterministic positional parse of SPM-slip OCR words →
    ``{candidate_name, exam, results: [{subject, grade, band}]}``, or **None** to fall
    back to Gemini (not an SPM slip, fewer than 3 subject rows recognised, or fewer rows
    than the slip's own declared subject total — an under-read)."""
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
    # The slip declares its own subject total — recovering fewer means the positional parse
    # UNDER-read. The classic cause is a 2-column slip whose GRED column is a separate block,
    # so flattened OCR splits each grade from its subject (dropping subjects AND mis-pairing
    # the ones it keeps with a neighbour's grade). A partial/mis-aligned read is worse than no
    # read, so discard it → the Gemini IMAGE reader handles the 2-D table. (#66/doc912:
    # declared SEPULUH=10, positional parse recovered only 4, 3 of them mis-graded.)
    declared = _declared_subject_count(full)
    if declared and len(results) < declared:
        return None
    # The slip's measured tilt (0.0 when upright; ~±90 for a sideways photo). Surfaced so the
    # help coach can give POINTED advice — "your slip was at an angle, retake it flat" — but
    # ONLY when the skew actually coincides with a doubtful read (a cleanly-read rotated slip
    # like Pavalaharasi's must not be nagged). The verdict layer decides; this just reports it.
    usable = [w for w in (words or []) if (w.get('text') or '').strip()]
    skew = round(_dominant_angle(usable), 1)
    # _debug_rows: the raw grouped OCR lines (top-to-bottom) — a temporary diagnostic so
    # a misparsed grade row can be inspected from the stored record. Ignored downstream.
    debug = [' '.join(w['text'] for w in row) for row in rows]
    return {'candidate_name': _slip_name(rows), 'exam': _slip_exam(rows),
            'results': results, 'skew_angle': skew, '_debug_rows': debug}


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
                # The Malay band is AUTHORITATIVE — it's distinctive text OCR reads
                # reliably, whereas the letter's +/- is a tiny, easily-dropped mark. So
                # the band's grade wins; the printed letter is only the fallback. (Applies
                # to BOTH the deterministic parse and the Gemini fallback read.)
                g = band_grade or (r.get('grade') or '').strip()
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
    # Currency vs the application's cohort: the expected SPM for an intake-year cohort was sat the
    # YEAR BEFORE (cohort − 1). 'current' → green, 'off' → amber, '' → no signal (no year / no cohort).
    _cy = getattr(getattr(getattr(doc, 'application', None), 'cohort', None), 'year', None)
    exam_year_status = ('current' if exam_year == str(_cy - 1) else 'off') if (exam_year and _cy) else ''
    skew = f.get('skew_angle')                        # the photo's measured tilt (deterministic read only)
    was_skewed = isinstance(skew, (int, float)) and abs(skew) >= 25.0

    if not data['names']:
        # No subject rows. Distinguish "extraction hasn't run / was skipped" (genuinely
        # PENDING) from "Gemini ran but couldn't read the subject table" (UNREADABLE — the
        # student should re-upload a clearer copy). A bare candidate-name with empty results
        # is the latter.
        pending = (not sv) or sv == 'review_manually'
        s = 'pending' if pending else 'unreadable'
        return {'name': name, 'subjects': s, 'results': s,
                'candidate_name': candidate_name, 'exam': exam, 'exam_year': exam_year,
                'exam_year_status': exam_year_status, 'was_skewed': was_skewed,
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
        'exam_year_status': exam_year_status, 'was_skewed': was_skewed,
        'missing': cmp['missing'], 'mismatched': cmp['mismatched'],
        'uncertain': cmp['uncertain'], 'slip_count': cmp['slip_count'],
    }


def semester_check(doc) -> dict:
    """A post-SPM SEMESTER-result slip, read for just three things (owner 2026-07-05): the
    student's NAME + NRIC (cross-checked against the student's own profile) and the CGPA.
    Returns ``{name, nric, cgpa, name_status, nric_status}`` — name_status 'match'/'partial'/
    'mismatch'/'no_ref', nric_status 'match'/'mismatch'/'no_ref'. None until the slip has been
    read (the row then shows 'Unread'). CGPA is a plain value (optional — a single-semester slip
    has none). Reads only the student's own document + profile."""
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    if not vf.get('student_verdict'):
        return None
    from . import vision
    f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
    name = (f.get('name') or '').strip()
    nric = (f.get('nric') or '').strip()
    cgpa = (f.get('cgpa') or '').strip()
    profile = getattr(getattr(doc, 'application', None), 'profile', None)
    sname = (getattr(profile, 'name', '') or '').strip()
    snric = (getattr(profile, 'nric', '') or '').strip()
    name_status = vision.name_match(name, sname) if (name and sname) else 'no_ref'
    if not nric or not snric:
        nric_status = 'no_ref'
    else:
        nric_status = 'match' if vision.nric_match(nric, snric) else 'mismatch'
    return {'name': name, 'nric': nric, 'cgpa': cgpa,
            'name_status': name_status, 'nric_status': nric_status}
