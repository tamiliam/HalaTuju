"""The five public-issuer OFFER-LETTER signature families (+ the 20 UA names) — moved verbatim out of
``results_doc`` (offer exact-read S6, 2026-11-03, a moves-only split: ``results_doc.py`` stood at the
600-line standard). Pure data, no imports. ``results_doc`` re-exports every name, so
``from .results_doc import _UA_NAMES`` / ``UA_OFFER_SIGNATURES`` keep working; ``results_doc``'s
``_OFFER_LISTS`` still assembles them, and ``results_doc.MODEL_VERSION`` still versions them. 1.26.0 (request
#66) adds IIUM's ENGLISH reading of the UA family (``UA_OFFER_SIGNATURES_EN``, ``english_ua_lists``; no imports).
"""


# Offer letters — five standard public-issuer families, scored together, best fit wins (and names
# the pathway). TEXT-ONLY: the issuer fingerprints are conclusive and the crest is generic. Since
# 1.4.0 an offer matching no family is banded by its best score (there is no holistic deferral any
# more); since 1.8.0 a known public TVET issuer reads NOT CHECKED instead (`offer_issuers`).

# STPM / Tingkatan Enam — MOE, Sektor Operasi Sekolah (the school varies, the issuer is constant).
# Owner-specified set (2026-06-17): the Jata Negara crest + the issuer line + the letter's standard
# body sections (Bidang / Pusat Tingkatan Enam / Tarikh Lapor Diri / Dokumen) + two near-unique
# boilerplate sentences. Deliberately NOT the signatory name or HQ address — those change with
# personnel / relocation, whereas these structural signatures are durable. The text signatures
# alone clear 0.70 on every genuine corpus letter, so the crest (a generic government marker, not
# STPM-specific) is bonus-only — its absence never sinks a real letter.
STPM_OFFER_SIGNATURES = [
    ('Jata Negara crest',          ['__crest__'],                              2, 'visual'),
    ('Sektor Operasi Sekolah',     ['SEKTOR OPERASI SEKOLAH'],                  3, 'text'),
    ('Tawaran ke Tingkatan Enam',  ['TAWARAN KEMASUKAN KE TINGKATAN ENAM',
                                     'TINGKATAN ENAM'],                          2, 'text'),
    ('Pusat Tingkatan Enam',       ['PUSAT TINGKATAN ENAM'],                    2, 'text'),
    ('Tarikh Lapor Diri',          ['TARIKH LAPOR DIRI'],                       1, 'text'),
    ('Dokumen diperlukan',         ['DOKUMEN DIPERLUKAN', 'DOKUMEN YANG DIPERLUKAN'], 1, 'text'),
    ('Keputusan muktamad (T.Enam)', ['KEPUTUSAN INI ADALAH MUKTAMAD BERDASARKAN '
                                      'SYARAT KEMASUKAN KE TINGKATAN ENAM'],     2, 'text'),
    ('Tawaran terbatal (murid)',   ['TERBATAL SERTA MERTA JIKA MURID'],         1, 'text'),
    ('Bidang',                     ['BIDANG'],                                  1, 'text'),
]

# Matriculation — Bahagian Matrikulasi KPM (the most uniform of the three; online-generated).
# Owner-specified set (2026-06-17): crest + issuer + body sections (Jurusan / Kolej / Tarikh
# Kemasukan) + two near-unique boilerplate sentences. Every text signature is matric-exclusive
# except the generic 'KOLEJ' (also in "Kolej Komuniti" / college names) → weight 1.
MATRIC_OFFER_SIGNATURES = [
    ('Jata Negara crest',          ['__crest__'],                              2, 'visual'),
    ('Bahagian Matrikulasi',       ['BAHAGIAN MATRIKULASI'],                    3, 'text'),
    ('Tawaran Program Matrikulasi KPM', ['TAWARAN KEMASUKAN PROGRAM MATRIKULASI '
                                         'KEMENTERIAN PENDIDIKAN'],             2, 'text'),
    ('Jurusan',                    ['JURUSAN'],                                 2, 'text'),
    ('Tarikh Kemasukan ke kolej',  ['TARIKH KEMASUKAN KE KOLEJ'],               1, 'text'),
    ('Mendaftar pada tarikh kolej', ['PERLU MENDAFTAR PADA TARIKH YANG DITETAPKAN '
                                      'OLEH PIHAK KOLEJ'],                       2, 'text'),
    ('Tawaran terbatal (saudara)', ['TERBATAL SERTA MERTA JIKA SAUDARA'],       1, 'text'),
    ('Kolej',                      ['KOLEJ'],                                   1, 'text'),
]

# Polytechnic — JPPKK, Kementerian Pendidikan Tinggi (from ambilan.mypolycc.edu.my).
# Owner-specified set (2026-06-17): TWO visual marks (Jata Negara crest + the round blue JPPKK
# seal by the signatory) + issuer + ministry + title + body sections (Program / Institusi /
# Tarikh dan Masa Daftar) + two near-unique boilerplate clauses. 'PROGRAM'/'INSTITUSI' are
# generic → weight 1. Text signatures alone clear 0.70, so the two visuals are bonus.
POLY_OFFER_SIGNATURES = [
    ('Jata Negara crest',          ['__crest__'],                              2, 'visual'),
    ('JPPKK round seal',           ['__seal__'],                               2, 'visual'),
    ('Jabatan Pend. Politeknik & KK', ['JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI'], 3, 'text'),
    ('Kementerian Pendidikan Tinggi', ['KEMENTERIAN PENDIDIKAN TINGGI'],        2, 'text'),
    ('Surat Tawaran Pengajian',     ['SURAT TAWARAN PENGAJIAN'],                2, 'text'),
    ('Tarikh dan Masa Daftar',      ['TARIKH DAN MASA DAFTAR'],                 1, 'text'),
    ('Tawaran muktamad/terbatal',   ['MUKTAMAD DAN TERBATAL SEKIRANYA ANDA TIDAK '
                                     'MENDAFTAR DI INSTITUSI'],                  2, 'text'),
    ('Tertakluk kesahihan maklumat', ['TERTAKLUK KEPADA KESAHIHAN MAKLUMAT DALAM '
                                      'BORANG PERMOHONAN'],                      2, 'text'),
    ('Program',                     ['PROGRAM'],                                1, 'text'),
    ('Institusi',                   ['INSTITUSI'],                              1, 'text'),
]

# PISMP — Institut Pendidikan Guru (IPG), KPM. Single central issuer. Owner-specified set
# (2026-06-17): issuer + the PISMP offer title + the registration/placement body fields + the
# three offer-defining clauses (Perjanjian Pendidikan Guru / cancellation / finality). Those
# clauses are what separate a genuine OFFER from a PISMP *announcement* (a43, which carries the
# identity strings but none of the offer-specific signatures → scores suspect). Calibrated on
# n=1 genuine offer (a80) — weights conservative, flagged for re-tuning when more arrive.
PISMP_OFFER_SIGNATURES = [
    ('Institut Pendidikan Guru',    ['INSTITUT PENDIDIKAN GURU'],               3, 'text'),
    ('Tawaran IJSM Perguruan (PISMP)', ['TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN',
                                        'IJAZAH SARJANA MUDA PERGURUAN'],        3, 'text'),
    ('Kementerian Pendidikan Malaysia', ['KEMENTERIAN PENDIDIKAN MALAYSIA'],     1, 'text'),
    ('Bidang Pengkhususan',         ['BIDANG PENGKHUSUSAN'],                     1, 'text'),
    ('Aliran Sekolah',              ['ALIRAN SEKOLAH'],                          1, 'text'),
    ('Tarikh Pendaftaran',          ['TARIKH PENDAFTARAN'],                      1, 'text'),
    ('Tempat Pengajian',            ['TEMPAT PENGAJIAN'],                        1, 'text'),
    ('Perjanjian Pendidikan Guru',  ['PERJANJIAN PENDIDIKAN GURU'],             2, 'text'),
    ('Tawaran terbatal sendirinya', ['TERBATAL DENGAN SENDIRINYA JIKA'],         2, 'text'),
    ('Penetapan bidang muktamad',   ['PENETAPAN BIDANG DAN TEMPAT PENGAJIAN ADALAH MUKTAMAD'], 2, 'text'),
]

# Asasi / UA-Diploma / Degree — ONE generic family for the FIXED 20 public universities (UA; web
# src/data/publicUniversities.ts == courses UNIV-001..020). Every UA offer names the university, so the
# NAME (any of the 20) is the forge-resistant ANCHOR, covering all 20 with no per-uni code; office /
# finality / offer-line wordings are UNION-matched across institutions. TEXT-ONLY. A university NOT in
# this list (private / IPTS, e.g. Swinburne) is banded by score with a "private college" reason (1.8.0).
# Validated out-of-sample 2026-06-20.
_UA_NAMES = [
    'UNIVERSITI MALAYA', 'UNIVERSITI SAINS MALAYSIA', 'UNIVERSITI KEBANGSAAN MALAYSIA',
    'UNIVERSITI PUTRA MALAYSIA', 'UNIVERSITI TEKNOLOGI MALAYSIA', 'UNIVERSITI TEKNOLOGI MARA',
    'UNIVERSITI ISLAM ANTARABANGSA MALAYSIA', 'UNIVERSITI UTARA MALAYSIA',
    'UNIVERSITI MALAYSIA SARAWAK', 'UNIVERSITI MALAYSIA SABAH', 'UNIVERSITI PENDIDIKAN SULTAN IDRIS',
    'UNIVERSITI SAINS ISLAM MALAYSIA', 'UNIVERSITI TEKNIKAL MALAYSIA MELAKA',
    'UNIVERSITI MALAYSIA PAHANG', 'UNIVERSITI MALAYSIA PERLIS', 'UNIVERSITI TUN HUSSEIN ONN MALAYSIA',
    'UNIVERSITI MALAYSIA TERENGGANU', 'UNIVERSITI MALAYSIA KELANTAN',
    'UNIVERSITI PERTAHANAN NASIONAL MALAYSIA', 'UNIVERSITI SULTAN ZAINAL ABIDIN',
]
# UA-name + offer-line are present in EVERY genuine UA offer (and dominate the score so a doc
# that merely *mentions* a university without an admission offer can't reach genuine); the
# office / clause / program / date wordings vary by institution → union-matched, weight 1 each.
UA_OFFER_SIGNATURES = [
    # 1.8.2: UiTM's own clauses name it on a letterhead-less PDF text layer — never its offer line (copied).
    ('public university (UA) name', list(_UA_NAMES) + ['PELAJAR UITM SETELAH MEMBUAT PENDAFTARAN',
                                                       'UITM BERHAK MENUKARKAN CALON'], 3, 'text'),
    # ONLY the official offer line: "Tawaran Kemasukan", or UiTM's own (1.8.1 — it never prints that
    # header). A "Pemakluman Kemasukan" (admission NOTIFICATION, the UM SATU pre-offer #31) must not
    # match → floors at suspect. NB never 'SURAT TAWARAN' (a pemakluman mentions "surat tawaran rasmi"),
    # and UiTM's line keeps "PROGRAM DI UITM": bare "ditawarkan tempat untuk mengikuti" is on a31 too.
    ('offer/admission line',        ['TAWARAN KEMASUKAN',
                                     'ANDA DITAWARKAN TEMPAT UNTUK MENGIKUTI PROGRAM DI UITM'], 3, 'text'),
    ('academic office',             ['PEJABAT PENGURUSAN AKADEMIK', 'PUSAT PENGURUSAN AKADEMIK',
                                     'BAHAGIAN HAL EHWAL AKADEMIK', 'PEJABAT PENDAFTAR',
                                     'PUSAT PEMASARAN DAN KEMASUKAN', 'BAHAGIAN PENGAMBILAN PELAJAR'], 1, 'text'),
    ('finality / no-change clause', ['PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN',
                                     'SEBARANG PERTUKARAN', 'TIDAK DIBENARKAN MENUKAR PROGRAM',
                                     'TAWARAN AKAN DITARIK BALIK', 'ADALAH MUKTAMAD'], 1, 'text'),
    ('Program / Kod Program',       ['PROGRAM PENGAJIAN', 'PROGRAM KOD'],          1, 'text'),
    ('registration date',           ['TARIKH PENDAFTARAN', 'TARIKH MENDAFTAR', 'TARIKH LAPOR DIRI',
                                     'HADIR MENDAFTAR PADA TARIKH'],               1, 'text'),
]


# ── IIUM in ENGLISH (1.26.0, request #66) ──────────────────────────────────────────────────
# IIUM (UNIV-006) writes its offers in English: "International Islamic University Malaysia", "Academic
# Management and Admission Division (AMAD)", "Offer of Admission …". Doc 5105, a genuine one, read
# not_offer_letter. The English reading is the SAME UA family — the same six rows and weights, each Malay
# row with its English twins added — and it applies ONLY to a page carrying BOTH IIUM's English name and
# its own admission office (`english_ua_lists`). Every other page, and every other UA letter, is scored by
# `UA_OFFER_SIGNATURES` exactly as under 1.25.0. Why gated: private colleges write English, so English
# offer wording scored on every page would lift a private letter from not_offer_letter to suspect; and a
# private letter that cites "validated by International Islamic University Malaysia" carries no AMAD.
# The full name only, never "IIUM" / "UIAM" (`offer_issuers._UA_SHORT` keeps those for its reason): a
# partner's letter cites the acronym far more often than the full name. `_UA_NAMES` (and so every block
# and reason that reads it) is untouched.
_IIUM_EN = 'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'
_IIUM_OFFICE = 'ACADEMIC MANAGEMENT AND ADMISSION DIVISION'
#: The offer TITLE, by the Malay rules' care: never bare "OFFER OF ADMISSION" nor "OFFER LETTER" — IIUM's own
#: admission booklet says "this offer of admission will be revoked" and "print the offer letter" three and
#: ten times — only the title running into what is offered (folded: "OFFER OF ADMISSION TO THE …",
#: "OFFER OF ADMISSION / BACHELOR OF …"). A notification ("Notification of Admission") never matches.
_ENGLISH_OFFER_TAILS = ('TO', 'INTO', 'FOR', 'BACHELOR', 'DIPLOMA', 'FOUNDATION', 'UNDERGRADUATE', 'SEMESTER')
#: A conditional / provisional offer is read without its "OFFER" (`english_ua_lists`), so it never reads as
#: the title: the owner's rule is an unconditional official offer only (decisions.md 2026-06-27).
_ENGLISH_NOT_YET = ('CONDITIONAL', 'PROVISIONAL')
_ENGLISH_TWINS = {
    'public university (UA) name': [_IIUM_EN],
    'offer/admission line': [f'OFFER OF ADMISSION {w}' for w in _ENGLISH_OFFER_TAILS],
    'academic office': [_IIUM_OFFICE],                                   # "Bahagian … Akademik"
    'finality / no-change clause': ['THIS OFFER IS VALID FOR', 'CHANGE OF PROGRAMME IS NOT ALLOWED',
                                    'OFFER WILL BE WITHDRAWN'],          # never "REVOKED": the booklet's
    'Program / Kod Program': ['PROGRAMME CODE', 'PROGRAMME OF STUDY'],
    'registration date': ['REGISTRATION DATE', 'DATE OF REGISTRATION'],
}
UA_OFFER_SIGNATURES_EN = [(label, patterns + _ENGLISH_TWINS[label], weight, kind)
                          for label, patterns, weight, kind in UA_OFFER_SIGNATURES]
#: ... and the same with the bare title, for a page that prints "OFFER OF ADMISSION" as a line of its OWN
#: (the booklet's three are inside sentences).
_TITLE_LINE = 'OFFER OF ADMISSION'
UA_OFFER_SIGNATURES_EN_TITLED = [(label, patterns + ([_TITLE_LINE] if label == 'offer/admission line' else []),
                                  weight, kind) for label, patterns, weight, kind in UA_OFFER_SIGNATURES_EN]


def english_ua_lists(lists: dict, text_norm: str, folded_lines=()):
    """``(lists, text_norm)`` for an offer: unchanged, unless the folded page names IIUM in English AND its
    admission office (AMAD) — then the UA family reads its English twins (`UA_OFFER_SIGNATURES_EN`; with the
    bare title when one of `folded_lines` is exactly "OFFER OF ADMISSION") and a "CONDITIONAL / PROVISIONAL
    OFFER" is read without its "OFFER"."""
    if _IIUM_EN not in text_norm or _IIUM_OFFICE not in text_norm:
        return lists, text_norm
    for w in _ENGLISH_NOT_YET:
        text_norm = text_norm.replace(f'{w} OFFER', w)
    titled = _TITLE_LINE in set(folded_lines)
    return {**lists, 'ua_offer': UA_OFFER_SIGNATURES_EN_TITLED if titled else UA_OFFER_SIGNATURES_EN}, text_norm
