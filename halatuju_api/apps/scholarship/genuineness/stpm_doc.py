"""STPM results documents (Majlis Peperiksaan Malaysia) — slip and certificate (corpus-gaps C3,
MODEL_VERSION 1.9.0).

Before 1.9.0 an STPM result was scored against the SPM lists only and read as a bad SPM slip
(suspect 0.39–0.52 — mostly from substrings: SPM's 'SEKOLAH' sits inside "PERSEKOLAHAN", and the SPM
disclaimer is a prefix of STPM's), which dropped the Academic card one or two bands. STPM has one
national issuer and a uniform layout, so it is fingerprinted exactly like SPM: two fixed-wording
lists, scored beside the SPM pair in `results_doc._RESULTS_LISTS`, best fit wins and names the type
(`stpm_slip` / `stpm_certificate`). The SPM lists are untouched and come FIRST, so a tie goes to SPM
(the highest STPM score on any of 96 cached SPM documents is 0.12; the lowest SPM score is 0.26).

The wording comes from ten real STPM documents (roadmap C0; PII-free). The slip carries only the MPM
logo (no Jata Negara), so it is text-only; the certificate carries the crest. QR not confirmed on
either, so not listed. Owner rulings (2026-10-26):
  1A. a screenshot / print of the ONLINE results-checker page (no issuer, no signature, no
      disclaimer) is NOT a result document: it scores below the suspect floor on both lists and reads
      `not_<type>`, so the reviewer asks for the real slip or certificate;
  2A. a CERTIFIED photocopy with a clear stamp IS accepted: it scores like a certificate (its text is
      the certificate's; only the crest does not show).
STPM exact-read S3 (1.11.0) scores the higher-results slot too, and adds the 1A page check the
signatures cannot make (one checker page in the corpus prints the slip's wording) — see below.
"""
import re

STPM_SLIP_SIGNATURES = [
    ('MAJLIS PEPERIKSAAN MALAYSIA',  ['MAJLIS PEPERIKSAAN MALAYSIA'],            3, 'text'),
    ('SIJIL TINGGI PERSEKOLAHAN MALAYSIA', ['SIJIL TINGGI PERSEKOLAHAN MALAYSIA',
                                            'TINGGI PERSEKOLAHAN'],               1, 'text'),
    ('Slip Keputusan Peperiksaan STPM', ['SLIP KEPUTUSAN PEPERIKSAAN STPM'],     2, 'text'),
    ('No. Kad Pengenalan',           ['KAD PENGENALAN'],                         1, 'text'),
    ('Angka Giliran',                ['ANGKA GILIRAN'],                          1, 'text'),
    ('No. Siri',                     ['NO SIRI'],                                1, 'text'),
    ('Bil. Mata Pelajaran Didaftarkan', ['MATA PELAJARAN DIDAFTARKAN'],          2, 'text'),
    ('PNGK',                         ['PNGK', 'PURATA NILAI GRED KESELURUHAN'],  2, 'text'),
    ('Wajaran (%)',                  ['WAJARAN'],                                1, 'text'),
    ('Gred Kertas',                  ['GRED KERTAS'],                            1, 'text'),
    ('Nilai Gred Mata Pelajaran',    ['NILAI GRED MATA'],                        1, 'text'),
    ('best-paper note',              ['KEPUTUSAN GRED KERTAS YANG DICATATKAN'],  2, 'text'),
    ('disclaimer (bukan sijil STPM)', ['BUKAN SIJIL STPM'],                      3, 'text'),
    ('grade legend',                 ['PENCAPAIAN GRED KERTAS DIBERIKAN GRED A HINGGA F',
                                      'LULUS SEBAHAGIAN DIBERIKAN GRED'],        2, 'text'),
    ('Ketua Eksekutif',              ['KETUA EKSEKUTIF'],                        2, 'text'),
    ('Tarikh Keputusan Dikeluarkan', ['TARIKH KEPUTUSAN DIKELUARKAN'],           1, 'text'),
]   # total weight 26

STPM_CERT_SIGNATURES = [
    ('JATA NEGARA',                  ['__crest__'],                              2, 'visual'),
    ('MAJLIS PEPERIKSAAN MALAYSIA',  ['MAJLIS PEPERIKSAAN MALAYSIA'],            2, 'text'),
    ('MALAYSIAN EXAMINATIONS COUNCIL', ['MALAYSIAN EXAMINATIONS COUNCIL'],       3, 'text'),
    ('SIJIL TINGGI PERSEKOLAHAN MALAYSIA', ['SIJIL TINGGI PERSEKOLAHAN MALAYSIA',
                                            'TINGGI PERSEKOLAHAN'],               1, 'text'),
    ('MALAYSIA HIGHER SCHOOL CERTIFICATE', ['HIGHER SCHOOL CERTIFICATE'],        2, 'text'),
    ('Dengan ini disahkan bahawa',   ['DENGAN INI DISAHKAN BAHAWA',
                                      'THIS IS TO CERTIFY THAT'],                2, 'text'),
    ('telah menduduki peperiksaan',  ['TELAH MENDUDUKI PEPERIKSAAN', 'SAT FOR THE'], 1, 'text'),
    ('subjects shown below',         ['MATA PELAJARAN YANG DITUNJUKKAN DI BAWAH',
                                      'FOR THE SUBJECTS SHOWN BELOW'],           2, 'text'),
    ('Angka Giliran (Index No.)',    ['ANGKA GILIRAN', 'INDEX NO'],              1, 'text'),
    ('Tahun Peperiksaan',            ['TAHUN PEPERIKSAAN', 'YEAR OF EXAMINATION'], 1, 'text'),
    ('LULUS PENUH (FULL PASS)',      ['LULUS PENUH', 'FULL PASS'],               1, 'text'),
    ('Bilangan Mata Pelajaran Lulus', ['BILANGAN MATA PELAJARAN LULUS',
                                       'NUMBER OF SUBJECTS PASSED'],             1, 'text'),
    ('Purata Nilai Gred (CGPA)',     ['CUMULATIVE GRADE POINT AVERAGE',
                                      'PURATA NILAI GRED'],                      2, 'text'),
    ('Pengerusi (Chairman)',         ['PENGERUSI', 'CHAIRMAN'],                  1, 'text'),
    ('Ketua Eksekutif (Chief Executive)', ['KETUA EKSEKUTIF', 'CHIEF EXECUTIVE'], 2, 'text'),
    ('Results released on',          ['TARIKH KEPUTUSAN DIUMUMKAN', 'RESULTS RELEASED ON'], 1, 'text'),
]   # total weight 25

STPM_LISTS = {'stpm_slip': STPM_SLIP_SIGNATURES, 'stpm_certificate': STPM_CERT_SIGNATURES}
#: The result types the STPM family names — readers that ask "is this a results document?" accept them
#: beside SPM's `results_slip` / `certificate`.
STPM_TYPES = frozenset(STPM_LISTS)
#: The issuer anchors no SPM document carries (C0, 96 cached SPM docs). A SEMESTER-result slot holds
#: many things (university / polytechnic slips have no family), so it is scored against STPM only when
#: one of these is on the page — anything else in that slot stays unscored, as before.
_STPM_ANCHORS = ('MAJLIS PEPERIKSAAN MALAYSIA', 'MALAYSIAN EXAMINATIONS COUNCIL', 'TINGGI PERSEKOLAHAN')


def stpm_semester_genuineness(ocr_text: str) -> dict:
    """The genuineness of a SEMESTER-result upload that is an STPM document — `signature_genuineness`
    over the STPM lists only — or `{}` (no signal) when no STPM issuer anchor is on the page. Pure."""
    from .results_doc import _norm_fold_upper_alnum, signature_genuineness
    tn = _norm_fold_upper_alnum(ocr_text)
    if not any(a in tn for a in _STPM_ANCHORS):
        return {}
    return signature_genuineness(ocr_text, doc_type='stpm_result')


# ── The HIGHER-RESULTS slot (STPM exact-read S3, MODEL_VERSION 1.11.0) ───────────────────────────
# Before S3 nothing in the `higher_results` slot was scored ("not checked" on every card). Now an
# upload whose own printed markers say STPM (`results_kind.detect` — the routing reader, so a
# Matriculation / Asasi / Diploma / SPM / MUET page, or one we cannot tell, stays UNSCORED, "not
# checked" as before) is scored on the same two STPM lists as the results slot, text only (the crest
# would need a new Gemini call here, and the certificate clears 0.70 without it). The slip and the
# certificate are judged the same way (owner, 2026-10-27). Ruling 1A on top of the score, because the
# signatures cannot see it — a checker page prints most of the slip's wording (corpus: 0.92): the online
# results-CHECKER page itself, known by its own heading / buttons / section title, → not a results
# document. A PRINTOUT of the MPM results web page is a slip in any form — saved as a PDF, scanned,
# photographed or certified (owner ruling A, 2026-10-27) — and is judged by the signatures alone; a
# photo of a screen with no checker heading or button cannot be told apart from it and is judged the same.
# Ruling 2A needs nothing: a certified copy carries the document's own text and scores like it.
# An MPM TRANSCRIPT ('TRANSKRIP <year>' + MPM's cover letter, one corpus sample) has no list of its own
# yet: on the slip list it reads 0.69 (suspect) for a genuine document, so it stays UNSCORED ("not checked").
#: What `doc_seen` says for a ruling-1A page (the reviewer's "it appears to be" line).
ONLINE_PAGE = 'stpm_online_results_page'
#: The checker page's OWN furniture, each seen only on a checker page in the corpus (its heading, its
#: "back to search" button, the candidate-details section title) — never generic words (Cetak / Semakan).
_CHECKER_PAGE = ('HALAMAN KEPUTUSAN', 'KEMBALI KE CARIAN', 'MAKLUMAT CALON')
#: An MPM transcript: its title, or its cover letter's wording ("transkrip peperiksaan STPM" / "a
#: transcript of"). The slip's title and the certificate's oath are never on one.
_TRANSCRIPT = re.compile(r'\bTRANSKRIP (?:20\d\d|PEPERIKSAAN|STPM)\b|\bTRANSCRIPT OF\b')
_NOT_A_TRANSCRIPT = ('SLIP KEPUTUSAN PEPERIKSAAN STPM', 'DENGAN INI DISAHKAN BAHAWA')


def is_checker_page(ocr_text: str) -> bool:
    """Ruling 1A: is this the online results-CHECKER page (its own heading / buttons)? Pure."""
    from .results_doc import _norm_fold_upper_alnum
    tn = _norm_fold_upper_alnum(ocr_text)
    return any(m in tn for m in _CHECKER_PAGE)


def stpm_higher_genuineness(ocr_text: str) -> dict:
    """The genuineness of a HIGHER-RESULTS upload: `{}` (no signal, "not checked") unless the page
    reads as STPM; else the STPM-list score, with ruling 1A forcing `not_stpm_result`. Same shape as
    `signature_genuineness`."""
    from apps.scholarship.results_kind import detect
    from .results_doc import _norm_fold_upper_alnum, signature_genuineness
    if detect(ocr_text) != 'stpm':
        return {}
    tn = _norm_fold_upper_alnum(ocr_text)
    checker = is_checker_page(ocr_text)
    if not checker and _TRANSCRIPT.search(tn) and not any(m in tn for m in _NOT_A_TRANSCRIPT):
        return {}
    sg = signature_genuineness(ocr_text, doc_type='stpm_result')
    if not checker:
        return sg
    return {**sg, 'status': 'not_stpm_result', 'type': ONLINE_PAGE,
            'reason': ('the online results-checker page, not the results slip or certificate (ruling 1A) — '
                       f'ask for the real document; signatures p={sg["probability"]:.2f}')[:300]}


def stpm_slot_genuineness(doc, ocr_text: str) -> dict:
    """`vision`'s one call for the two slots that score STPM only: the semester result (1.9.0) and
    the higher results (1.11.0). Text only — the upload is never fetched again."""
    if doc.doc_type == 'semester_result':
        return stpm_semester_genuineness(ocr_text)
    return stpm_higher_genuineness(ocr_text)
