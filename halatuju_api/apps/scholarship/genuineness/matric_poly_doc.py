"""Genuineness of a Matriculation transcript and a polytechnic Diploma transcript in the HIGHER-RESULTS
slot (Matric/Diploma exact-read M4, MODEL_VERSION 1.21.0).

Before M4 every Matriculation / Diploma upload in that slot was unscored — "not checked", held at
Probable by the TD-114 floor. Each family below has ONE national issuer and a fixed layout, so it is
fingerprinted the way `stpm_doc` fingerprints STPM: a fixed-wording list, text only (the crest
would need a new Gemini call; the transcripts clear 0.70 without it), scored by
`results_doc._score_list` and banded by `bands.band_for`.

WHICH PAGES ARE SCORED (everything else keeps "not checked", exactly as before):
  * Matriculation — a page `results_kind.detect` reads as Matriculation that is NOT a semester
    RESULT SLIP (its own title "Slip Keputusan Peperiksaan" or its disclaimer "bukan transkrip
    akademik"). Calibrated on the corpus OCR as production reads it (page 1 of a scan): 6 KPM
    transcripts, 2 of them certified copies (ruling 2A: a certified copy carries the document's own
    text and scores like it), at p = 0.96–1.00; every control — 95 offer letters (23 from Bahagian
    Matrikulasi), 98 SPM slips, 39 STPM pages, the UiTM / polytechnic diplomas, fakes — at most
    p = 0.29 on this list, below the 0.35 suspect floor. Genuine (≥ 0.70) and suspect (0.35–0.70)
    are stored; BELOW the floor the page is not recognisably a transcript at all — in the corpus,
    only Matriculation OFFER letters — and whether that should read as a wrong document is an owner
    ruling not yet made, so it stays unscored ("not checked"), never marked fake.
  * Polytechnic — a page read as Diploma that prints a polytechnic's own name
    (`results_kind.prints_polytechnic`) and carries the transcript's own title. ⚠ ONE transcript in
    the corpus, so the band below "genuine" cannot be calibrated: a polytechnic page scores
    GENUINE (p ≥ 0.70) or NOTHING ("not checked", as before) — it is never marked suspect or fake
    on one sample's evidence. The two semester result slips and the student-portal screen in the
    corpus are therefore unscored (owner questions, M4 report).
UiTM, private-college diplomas and Asasi are never scored here.

Ruling 1A (an online results-CHECKER page is not a result document) has no Matriculation or
polytechnic checker page in the corpus to recognise; such a page scores below 0.70 on these lists.
"""
import re

from apps.scholarship.results_kind import detect, prints_polytechnic

from .bands import GENUINE_MIN, band_for

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

#: What a Matriculation semester RESULT SLIP prints and a transcript never does — such a page is
#: not scored (owner question: is a final-semester slip accepted in place of the transcript?).
_MATRIC_SLIP = ('SLIP KEPUTUSAN PEPERIKSAAN', 'BUKAN TRANSKRIP AKADEMIK', 'NOT AN ACADEMIC TRANSCRIPT')
_POLY_TITLE = ('ACADEMIC TRANSCRIPT',)


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


def matric_poly_higher_genuineness(ocr_text: str) -> dict:
    """The genuineness of a Matriculation or polytechnic HIGHER-RESULTS page, or `{}` (no signal,
    "not checked") for every other page — see the module docstring for which. Pure."""
    from .results_doc import _norm_fold_upper_alnum
    tn = _norm_fold_upper_alnum(ocr_text)
    kind = detect(ocr_text)
    if kind == 'matric':
        if any(_norm_fold_upper_alnum(m) in tn for m in _MATRIC_SLIP):
            return {}
        sg = _scored(ocr_text, MATRIC_TRANSCRIPT_SIGNATURES, 'matric_transcript')
        return {} if sg['status'].startswith('not_') else sg      # below the floor: owner question
    kk = re.search(r'(?m)^\s*KOLEJ KOMUNITI\b', (ocr_text or '').upper())    # a Kolej Komuniti's own page
    if kind == 'diploma' and prints_polytechnic(ocr_text) and not kk and any(m in tn for m in _POLY_TITLE):
        sg = _scored(ocr_text, POLY_TRANSCRIPT_SIGNATURES, 'poly_transcript')
        return sg if sg['probability'] >= GENUINE_MIN else {}     # one sample: genuine or nothing
    return {}
