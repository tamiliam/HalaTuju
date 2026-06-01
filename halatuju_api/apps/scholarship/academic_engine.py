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


def _norm(name: str) -> str:
    """Lowercase, collapse runs of non-alphanumerics to single spaces, strip."""
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


def _norm_grade(g: str) -> str:
    """Spaces out, uppercase. 'A -' / ' a-' → 'A-'."""
    return re.sub(r'\s+', '', (g or '')).upper()


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
    results = fields.get('results')
    if isinstance(results, list) and results:
        for r in results:
            if isinstance(r, dict):
                s = (r.get('subject') or '').strip()
                g = (r.get('grade') or '').strip()
                if s:
                    names.append(s)
                    if g:
                        grades[_norm(s)] = g
    else:
        subs = fields.get('subjects')
        if isinstance(subs, list):
            names = [s.strip() for s in subs if isinstance(s, str) and s.strip()]
    return {'names': names, 'grades': grades}


def compare_academics(profile_grades, slip) -> dict:
    """Compare the slip's subjects/grades against what the student typed.

    Returns ``{slip_count, missing: [readable names], mismatched: [{subject,
    typed, slip}], have_grades: bool, complete: bool, accurate: bool}``."""
    prof_by_name = {}
    for key, grade in (profile_grades or {}).items():
        nm = _SUBJECT_BM.get(key)
        if nm and grade:
            prof_by_name[_norm(nm)] = grade

    slip_norm = {}  # normname → first readable form
    for n in slip['names']:
        slip_norm.setdefault(_norm(n), n)

    missing = sorted(orig for nn, orig in slip_norm.items() if nn not in prof_by_name)
    mismatched = []
    for nn, slip_g in slip['grades'].items():
        typed = prof_by_name.get(nn)
        if typed and _norm_grade(typed) != _norm_grade(slip_g):
            mismatched.append({'subject': slip_norm.get(nn, nn),
                               'typed': typed, 'slip': slip_g})
    return {
        'slip_count': len(slip_norm),
        'missing': missing,
        'mismatched': mismatched,
        'have_grades': bool(slip['grades']),
        'complete': len(slip_norm) > 0 and not missing,
        'accurate': not mismatched,
    }
