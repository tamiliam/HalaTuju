"""Genuineness of a Matriculation transcript and a polytechnic Diploma transcript in the HIGHER-RESULTS
slot (Matric/Diploma exact-read M4, MODEL_VERSION 1.21.0).

Before M4 every Matriculation / Diploma upload in that slot was unscored — "not checked", held at
Probable by the TD-114 floor. Each family below has ONE national issuer and a fixed layout, so it is
fingerprinted the way `stpm_doc` fingerprints STPM: a fixed-wording list, text only (the crest
would need a new Gemini call; the transcripts clear 0.70 without it), scored by
`results_doc._score_list` and banded by `bands.band_for`.

GENUINE OR NOTHING, BOTH FAMILIES (review, 2026-10-29). A page that passes a family's gates and
scores ≥ 0.70 is stored "genuine"; anything else stays unscored — "not checked", exactly as before
M4 — EXCEPT the pages the owner ruled on (M4b, below): a NON-FINAL page (a semester result slip, the
polytechnic portal screen, a transcript with no completion status) stored NOT_CHECKED with its
`doc_seen` — read as "the final results are not yet uploaded" — and a Matriculation offer letter
stored `not_matric_result`. A transcript is genuine only when FINAL (its completion status printed). No suspect is ever stored (owner ruling 4, 2026-10-29), because no band is calibrated: a genuine 2-year
transcript seen page 1 only scores 0.68, a cropped photo 0.64, a noisy scan 0.61. A suspect would
tell a student with a real transcript that it "does not look genuine" — so until multi-page and
cropped samples calibrate a suspect band, the floor (Probable at best) is the cautious answer.

THE GATES (a page must pass every one before it is scored):
  * Matriculation — `results_kind.detect` reads it as Matriculation; it carries the transcript
    title ("Transkrip Akademik" / "Academic Transcript", never inside the slip's "bukan transkrip
    akademik"), at least one transcript-only grid label (Mata Nilaian / Value Point / PNGS), and
    BOTH a "Semester I" and a "Semester II" block (a semester result slip shows one semester); and
    no slip-only wording at all (`_MATRIC_SLIP`, several phrases, so a mangled or cut-off
    disclaimer still excludes it).
  * Polytechnic — read as Diploma, a polytechnic's own name printed (`prints_polytechnic`), no
    Kolej Komuniti anywhere once the JPPKK department's name is removed (OCR "KOMUNlTI" too), the
    transcript title (never inside "not an academic transcript"), the transcript's own grid
    (CODE COURSE CREDIT GRADE + the cumulative-GPA label), and no result-slip wording.
Calibrated on the corpus OCR as production reads it (page 1 of a scan): the 6 KPM transcripts (2
certified copies — ruling 2A) at 0.96–1.00 and the one polytechnic transcript at 1.00 pass and score
genuine; every control (95 offer letters, 98 SPM slips, 39 STPM pages, the Matriculation and
polytechnic result slips, the portal screen, UiTM, fakes) fails a gate or scores ≤ 0.29.
UiTM, private-college / Kolej Komuniti diplomas and Asasi are never scored here. Ruling 1A (an online
checker page) has no Matriculation / polytechnic example in the corpus; such a page is not scored.
"""
import re

from apps.scholarship.results_kind import detect, prints_polytechnic

from .bands import GENUINE_MIN, NOT_CHECKED, NOT_FINAL_SEEN, band_for

#: The KPM academic transcript's fixed wording (every corpus transcript prints all of it). The
#: heaviest weights sit on what ONLY a transcript prints (value-point column, semester GPA, the
#: average-grade box, the completion status) — an offer letter from the same division shares the
#: header and the college, so those weigh least.
MATRIC_TRANSCRIPT_SIGNATURES = [
    ('KEMENTERIAN PENDIDIKAN MALAYSIA', ['KEMENTERIAN PENDIDIKAN MALAYSIA', 'MINISTRY OF EDUCATION MALAYSIA'], 1, 'text'),
    ('BAHAGIAN MATRIKULASI',          ['BAHAGIAN MATRIKULASI'],                     2, 'text'),
    ('MATRICULATION DIVISION',        ['MATRICULATION DIVISION'],                   2, 'text'),
    ('Putrajaya address',             ['PUSAT PENTADBIRAN KERAJAAN PERSEKUTUAN', '62604 PUTRAJAYA'], 1, 'text'),
    ('www.moe.gov.my',                ['WWW MOE GOV MY'],                           1, 'text'),
    ('TRANSKRIP AKADEMIK',            ['TRANSKRIP AKADEMIK'],                       2, 'text'),
    ('ACADEMIC TRANSCRIPT',           ['ACADEMIC TRANSCRIPT'],                      1, 'text'),
    ('No. Matrik',                    ['NO MATRIK', 'MATRIC NO'],                   1, 'text'),
    ('Kolej Matrikulasi',             ['KOLEJ MATRIKULASI', 'MATRICULATION COLLEGE'], 1, 'text'),
    ('Mata Nilaian (Value Point)',    ['MATA NILAIAN', 'VALUE POINT'],              3, 'text'),
    ('PNGS (semester GPA)',           ['PNGS'],                                     3, 'text'),
    ('PNGK / CGPA',                   ['PNGK', 'CGPA'],                             1, 'text'),
    ('average-grade box',             ['PURATA GRED BAGI KURSUS TERAS', 'AVERAGE GRADE FOR CORE COURSES'], 2, 'text'),
    ('Lulus dan Tamat',               ['LULUS DAN TAMAT PROGRAM MATRIKULASI',
                                       'PASS AND COMPLETED MATRICULATION PROGRAMME'], 3, 'text'),
    ('Pengarah (Director)',           ['PENGARAH', 'DIRECTOR'],                     1, 'text'),
    ('Pengajian Am Matrikulasi',      ['PENGAJIAN AM MATRIKULASI', 'MATRICULATION GENERAL STUDIES'], 1, 'text'),
    ('Jurusan (Major)',               ['JURUSAN'],                                  1, 'text'),
    ('Jantina (Gender)',              ['JANTINA'],                                  1, 'text'),
]   # total weight 28

#: The JPPKK polytechnic transcript's fixed wording (the one corpus transcript prints all of it).
POLY_TRANSCRIPT_SIGNATURES = [
    ('JPPKK',                         ['JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI'], 2, 'text'),
    ('ACADEMIC TRANSCRIPT',           ['ACADEMIC TRANSCRIPT'],                      1, 'text'),
    ('REG.NO',                        ['REG NO'],                                   1, 'text'),
    ('MEDIUM OF INSTRUCTION',         ['MEDIUM OF INSTRUCTION'],                    1, 'text'),
    ('INTAKE SESSION',                ['INTAKE SESSION'],                           1, 'text'),
    ('column header',                 ['CODE COURSE CREDIT GRADE REMARK'],          2, 'text'),
    ('Grade Point Average (GPA)',     ['GRADE POINT AVERAGE GPA'],                  1, 'text'),
    ('Cumulative GPA (CGPA)',         ['CUMULATIVE GRADE POINT AVERAGE CGPA'],      2, 'text'),
    ('Credit Earned / Total Credits', ['CREDIT EARNED', 'TOTAL CREDITS'],           1, 'text'),
    ('End of results',                ['END OF RESULTS'],                           2, 'text'),
    ('no alteration',                 ['NO ALTERATION OR ADDITION IS HEREBY AUTHORIZED'], 2, 'text'),
    ('computer generated',            ['COMPUTER GENERATED AND NO AUTHORIZED SIGNATURE IS REQUIRED'], 2, 'text'),
    ('Polytechnic Board',             ['POLYTECHNIC BOARD OF EXAMINATION'],         2, 'text'),
    ('abbreviation legend',           ['COURSE EXEMPTION', 'CREDIT TRANSFER VERTICAL', 'REPEAT TO IMPROVE GRADE'], 1, 'text'),
]   # total weight 21

#: Wording ONLY a Matriculation semester RESULT SLIP prints (its title, its disclaimer in both
#: languages, in parts so a mangled or cut-off line still matches) — such a page is never scored.
_MATRIC_SLIP = ('SLIP KEPUTUSAN', 'RESULT SLIP', 'BUKAN TRANSKRIP', 'NOT AN ACADEMIC TRANSCRIPT',
                'TRANSKRIP AKADEMIK SEBENAR', 'ACTUAL ACADEMIC TRANSCRIPT', 'BERHAK MEMINDA',
                'RESERVES THE RIGHT TO AMEND')
#: A polytechnic semester result slip / the portal screen, never a transcript.
_POLY_SLIP = ('KEPUTUSAN PENILAIAN AKHIR', 'SLIP KEPUTUSAN', 'RESULT SLIP', 'NOT AN ACADEMIC TRANSCRIPT',
              'BUKAN TRANSKRIP', 'SEMAKAN BUTIRAN PELAJAR', 'KELAS SEMASA')
#: Negated titles — removed before the title gate reads the page.
_NEGATED_TITLE = re.compile(r'\b(?:BUKAN|NOT AN|NOT)\s+(?:TRANSKRIP AKADEMIK|ACADEMIC TRANSCRIPT)\b')
_MATRIC_TITLE = re.compile(r'\b(?:TRANSKRIP AKADEMIK|ACADEMIC TRANSCRIPT)\b')
_MATRIC_GRID = re.compile(r'\b(?:MATA NILAIAN|VALUE POINT|PNGS)\b')
_SEM_I, _SEM_II = re.compile(r'\bSEMESTER I\b'), re.compile(r'\bSEMESTER II\b')
_KOLEJ_KOMUNITI = re.compile(r'\bKOLEJ KOMUN[IL1]TI\b')
_POLY_GRID = ('CODE COURSE CREDIT GRADE', 'CUMULATIVE GRADE POINT AVERAGE')


def _scored(ocr_text, signatures, family):
    from .results_doc import MODEL_VERSION, _norm_fold_upper_alnum, _score_list
    tn = _norm_fold_upper_alnum(ocr_text)
    r = _score_list(signatures, tn, False, False)
    p = r['probability']
    status = band_for(p)
    if status == 'not_type':
        status = 'not_' + family
    n_have, n_all = len(r['present']), len(r['present']) + len(r['missing'])
    reason = (f"{n_have}/{n_all} {family.replace('_', ' ')} signatures present (p={p:.2f}); "
              f"missing: {', '.join(r['missing'][:4]) or 'none'}")
    return {'status': status, 'probability': p, 'type': family, 'present': r['present'],
            'missing': r['missing'], 'reason': reason[:300], 'model_version': MODEL_VERSION}


def _matric_gates(tn):
    """Is this normalised page a Matriculation TRANSCRIPT (not a slip, not a letter)?"""
    if any(m in tn for m in _MATRIC_SLIP):
        return False
    titled = _NEGATED_TITLE.sub(' ', tn)
    return bool(_MATRIC_TITLE.search(titled) and _MATRIC_GRID.search(tn) and _SEM_I.search(tn)
                and _SEM_II.search(tn))


def _poly_gates(ocr_text, tn):
    """Is this normalised page a polytechnic's own TRANSCRIPT (not a slip, the portal, a Kolej Komuniti)?"""
    from apps.scholarship.results_kind import _NOT_ISSUERS
    if not prints_polytechnic(ocr_text) or _KOLEJ_KOMUNITI.search(_NOT_ISSUERS.sub(' ', tn)):
        return False
    if any(m in tn for m in _POLY_SLIP):
        return False
    return bool('ACADEMIC TRANSCRIPT' in _NEGATED_TITLE.sub(' ', tn) and all(g in tn for g in _POLY_GRID))


# ── The owner's rulings (2026-10-29, M4b; ruling B replaced the slip / portal part the same day) ──
# A. The higher-results upload is for the FINAL result only — the final academic transcript for
#    Matriculation and Diploma. "Only the final version counts."
# B. A NON-FINAL document — a Matriculation or polytechnic semester RESULT SLIP, the polytechnic
#    student-PORTAL screen, or a transcript with no completion status — does not count: it is read
#    as if the final results are NOT YET UPLOADED (no genuineness signal, never the −2 step; the
#    Academic card is capped at Probable and the final transcript is asked for —
#    `higher_results.final_owed`, `higher_owed`). Stored as `bands.NOT_CHECKED` with a `doc_seen`
#    from `bands.NOT_FINAL_SEEN`.
# C. A PROVISIONAL transcript that prints the completion status and the final CGPA counts as final
#    ("it is equivalent to SPM or STPM slips as opposed to certs").
# D. A Matriculation OFFER LETTER in the results card is not a results document — the step STPM's
#    1A page takes (`not_matric_result`). No suspect band (ruling 4 of the morning, unchanged).
# Each page is recognised from fixed wording only, calibrated on the corpus (page-1 input): every
# marker set is printed on every corpus page of its kind and on no final transcript. Anything the
# markers do not settle stays "not checked".
#: Matriculation slip: its title and its disclaimer, both languages (3 corpus slips print all 6;
#: transcripts 0). Two needed, so one mangled phrase still recognises it.
_MATRIC_SLIP_MARKS = ('SLIP KEPUTUSAN PEPERIKSAAN', 'EXAMINATION RESULT SLIP', 'BUKAN TRANSKRIP AKADEMIK',
                      'NOT AN ACADEMIC TRANSCRIPT', 'TRANSKRIP AKADEMIK SEBENAR', 'ACTUAL ACADEMIC TRANSCRIPT')
#: Polytechnic slip: the slip's title AND two of its own column / summary labels (2 corpus slips).
_POLY_SLIP_TITLE = 'KEPUTUSAN PENILAIAN AKHIR'
_POLY_SLIP_MARKS = ('HPNM', 'JAM KREDIT', 'KELAS SEMASA', 'NILAI MATA', 'MATA KREDIT')
#: The polytechnic student portal's own furniture (the corpus screenshot prints all 6; nothing else any).
_PORTAL_MARKS = ('SEMAKAN BUTIRAN PELAJAR', 'STATUS PENDAFTARAN HAL EHWAL PELAJAR', 'DAFTAR HHP',
                 'STATUS DAFTAR LATIHAN INDUSTRI', 'KEPUTUSAN PEPERIKSAAN MENGIKUT SEMESTER', 'KEPUTUSAN ASASI TVET')
#: A Matriculation offer letter's own wording (the 22 Bahagian Matrikulasi offers print 3-4; 0 on
#: every transcript and slip).
_OFFER_MARKS = ('TAWARAN', 'LAPOR DIRI', 'SURAT TAWARAN', 'KEMASUKAN', 'TARIKH PENDAFTARAN', 'TAHNIAH',
                'DITAWARKAN', 'OFFER')
#: The completion status a FINAL transcript prints (ruling A / C): every corpus transcript, the
#: provisional polytechnic one included.
_MATRIC_FINAL = ('LULUS DAN TAMAT', 'PASS AND COMPLETED')
_POLY_FINAL = ('STATUS COMPLETED',)
#: The END of a transcript is on the page (so a missing status is really missing, not cut off by a
#: page-1-only read): the Matriculation average box / PNGK; the polytechnic "End of results".
_MATRIC_END = ('PURATA GRED BAGI KURSUS TERAS', 'AVERAGE GRADE FOR CORE COURSES', 'PNGK CGPA')
_POLY_END = ('END OF RESULTS',)
#: What `doc_seen` says for each ruling (the reviewer's line, the student's note).
MATRIC_SLIP, POLY_SLIP, POLY_PORTAL, MATRIC_OFFER = (
    'matric_result_slip', 'poly_result_slip', 'poly_portal_page', 'matric_offer_letter')
MATRIC_NOT_FINAL, POLY_NOT_FINAL = 'matric_transcript_not_final', 'poly_transcript_not_final'
_OWED = ' — not the final result (owner ruling B, 2026-10-29); the final academic transcript is still owed'
_RULINGS = {
    MATRIC_SLIP: (NOT_CHECKED, 'a Matriculation semester result slip' + _OWED),
    POLY_SLIP: (NOT_CHECKED, 'a polytechnic semester result slip' + _OWED),
    POLY_PORTAL: (NOT_CHECKED, 'the polytechnic student-portal page' + _OWED),
    MATRIC_NOT_FINAL: (NOT_CHECKED, 'a Matriculation transcript with no completion status' + _OWED),
    POLY_NOT_FINAL: (NOT_CHECKED, 'a polytechnic transcript with no completion status' + _OWED),
    MATRIC_OFFER: ('not_matric_result', 'a Matriculation offer letter, not a results document '
                   '(owner ruling D, 2026-10-29)'),
}
assert set(_RULINGS) - {MATRIC_OFFER} == NOT_FINAL_SEEN       # one home for the non-final codes


def _count(tn, marks):
    return sum(1 for m in marks if m in tn)


def _ruled_page(ocr_text, tn, kind):
    """The ruling a page is recognised as (`MATRIC_SLIP` …), or ''. A page that passes a
    transcript's own gates is a transcript: only its completion status can rule it (non-final)."""
    if kind == 'matric' and _matric_gates(tn):
        final = any(m in tn for m in _MATRIC_FINAL)
        return '' if final or not any(m in tn for m in _MATRIC_END) else MATRIC_NOT_FINAL
    if kind == 'diploma' and _poly_gates(ocr_text, tn):
        final = any(m in tn for m in _POLY_FINAL)
        return '' if final or not any(m in tn for m in _POLY_END) else POLY_NOT_FINAL
    if _count(tn, _PORTAL_MARKS) >= 3:
        return POLY_PORTAL
    kpm = 'BAHAGIAN MATRIKULASI' in tn or 'MATRICULATION DIVISION' in tn
    if kind == 'matric' and kpm and _count(tn, _MATRIC_SLIP_MARKS) >= 2:
        return MATRIC_SLIP
    if (kind == 'diploma' and prints_polytechnic(ocr_text) and _POLY_SLIP_TITLE in tn
            and _count(tn, _POLY_SLIP_MARKS) >= 2):
        return POLY_SLIP
    if (kind == 'matric' and 'BAHAGIAN MATRIKULASI' in tn and _count(tn, _OFFER_MARKS) >= 2
            and not _MATRIC_GRID.search(tn)):
        return MATRIC_OFFER
    return ''


def _ruling_result(ocr_text, seen):
    from .results_doc import MODEL_VERSION
    status, reason = _RULINGS[seen]
    sg = _scored(ocr_text, POLY_TRANSCRIPT_SIGNATURES if seen.startswith('poly') else
                 MATRIC_TRANSCRIPT_SIGNATURES, seen)
    return {**sg, 'status': status, 'type': seen, 'model_version': MODEL_VERSION,
            'reason': f"{reason}; signatures p={sg['probability']:.2f}"[:300]}


def matric_poly_higher_genuineness(ocr_text: str) -> dict:
    """The genuineness of a Matriculation or polytechnic HIGHER-RESULTS page: "genuine" when it is a
    FINAL transcript (its gates, its completion status) scoring ≥ 0.70; a non-final page (ruling B)
    NOT_CHECKED with its `doc_seen`; a Matriculation offer letter `not_matric_result` (ruling D);
    else `{}` (no signal, "not checked"). Never a suspect. Pure."""
    from .results_doc import _norm_fold_upper_alnum
    tn = _norm_fold_upper_alnum(ocr_text)
    kind = detect(ocr_text)
    seen = _ruled_page(ocr_text, tn, kind)
    if seen:
        return _ruling_result(ocr_text, seen)
    if kind == 'matric' and _matric_gates(tn) and any(m in tn for m in _MATRIC_FINAL):
        sg = _scored(ocr_text, MATRIC_TRANSCRIPT_SIGNATURES, 'matric_transcript')
    elif kind == 'diploma' and _poly_gates(ocr_text, tn) and any(m in tn for m in _POLY_FINAL):
        sg = _scored(ocr_text, POLY_TRANSCRIPT_SIGNATURES, 'poly_transcript')
    else:
        return {}
    return sg if sg['status'] == 'genuine' and sg['probability'] >= GENUINE_MIN else {}
