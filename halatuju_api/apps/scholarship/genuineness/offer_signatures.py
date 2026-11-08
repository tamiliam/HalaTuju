"""The five public-issuer OFFER-LETTER signature families (+ the 20 UA names) — moved verbatim out of
``results_doc`` (offer exact-read S6, 2026-11-03, a moves-only split: ``results_doc.py`` stood at the
600-line standard). Pure data, no imports. ``results_doc`` re-exports every name, so
``from .results_doc import _UA_NAMES`` / ``UA_OFFER_SIGNATURES`` keep working; ``results_doc``'s
``_OFFER_LISTS`` still assembles them, and ``results_doc.MODEL_VERSION`` still versions them. 1.26.0 (request
#66) adds IIUM's ENGLISH reading of the UA family (``UA_OFFER_SIGNATURES_EN``, ``english_ua_lists``; its one
import, the letterhead reader, is lazy).
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
# IIUM (UNIV-006) writes its offers in English. Doc 5105, a genuine one, read not_offer_letter. Its REAL
# layout (its stored text layer, read by review rounds 1-2): the letterhead is an IMAGE, so the text has no
# letterhead at all — four lines (reference, date, the candidate's name and address), "Dear …", then the
# offer SENTENCE "We are pleased to inform you that the International Islamic University Malaysia (IIUM) has
# accepted and approved your application for the following programme in Semester 1, 2024/2025:"; the office
# "Academic Management and Admission Division" only in the signature block and the acceptance form; "This
# offer is valid for one (1) year only from the date of issuance"; "Registration Date". No title.
# The English reading is the SAME UA family — the same six rows and weights, each Malay row with only those
# real English twins added — and it opens ONLY on IIUM's own offer, anchored on its ISSUER, the sentence's
# subject (`english_ua_lists`):
#   1. the sentence with IIUM as its SUBJECT ("… THAT THE INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA (IIUM) HAS
#      ACCEPTED AND APPROVED …"): "Mercu Academy, a partner of the International Islamic University Malaysia
#      (IIUM), has accepted …" is not it;
#   2. the office anywhere on the page;
#   3. NOTHING before the sentence names another organisation — no organisation noun at all outside IIUM's
#      name and office (`offer_reading._outside_orgs`; a company is one; a CAMPUS too, "MERCU CAMPUS"): a
#      private college's own letterhead, an "affiliated college", "IIUM Holdings Berhad" sit above it; and
#      no partner / tie-up word ANYWHERE on the page (`_PARTNER`, `_TIE_UP`, "validated", "in association"):
#      "… the following programme at Mercu College, our teaching partner campus" (final review). The
#      organisation check is NOT page-wide: a genuine letter names banks, kulliyyahs and mahallahs below;
#   4. no CONDITIONAL / PROVISIONAL / "NOTIFICATION OF ADMISSION" (whole words; "UNCONDITIONAL" is not one)
#      from the top of the page to the end of the sentence's line — a title or the sentence itself; a genuine
#      letter's terms further down may say "conditional upon" (the owner's rule: an unconditional official
#      offer only, decisions.md 2026-06-27);
#   5. the SIGNATURE block (from "Yours sincerely" to the office line, at most six lines) names no other
#      organisation: "Registrar / MERCU UNIVERSITY COLLEGE" signing under IIUM's sentence.
# Accepted residuals (final review): a private body named only by an acronym above "Dear"; a private name
# only in a FOOTER below the signature (no safe rule: a genuine letter's lower pages name banks and campuses);
# a candidate addressed at a residential college ("Kolej Kediaman …") keeps the 1.25.0 call; one template
# sentence anchors the reading (a second IIUM template needs adding here).
# Every other page, and every other UA letter, is scored by `UA_OFFER_SIGNATURES` exactly as under 1.25.0.
# The acronyms "IIUM" / "UIAM" are never an anchor (`offer_issuers._UA_SHORT` keeps them for its reason).
# `_UA_NAMES` (and so every block and reason that reads it) is untouched: adding the English name to the
# BLOCK's public names would let a company line BELOW it ("IIUM HOLDINGS BERHAD") escape the block.
_IIUM_EN = 'INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA'
_IIUM_OFFICE = 'ACADEMIC MANAGEMENT AND ADMISSION DIVISION'
#: The offer sentence (UiTM's own sentence is the Malay row's precedent). Never "offer of admission": on
#: IIUM's pages it sits in "rejection of offer of admission", "I accept the offer of admission", "your
#: application for offer of admission … was unsuccessful" and the booklet's "this offer of admission".
_IIUM_OFFER_SENTENCE = 'HAS ACCEPTED AND APPROVED YOUR APPLICATION FOR THE FOLLOWING PROGRAMME'
#: ... with IIUM as its subject (rule 1), folded: "(IIUM)" is a word.
_IIUM_SUBJECT = f' THAT THE {_IIUM_EN} IIUM {_IIUM_OFFER_SENTENCE} '
#: Rule 3: tie-up words beyond `offer_reading._PARTNER` / `_TIE_UP`.
_TIE_UP_EXTRA = (' VALIDATED ', ' VALIDATION ', ' IN ASSOCIATION ', ' TIE UP ')
#: Rule 4: whole words that make a page not yet an unconditional offer.
_NOT_YET = (' CONDITIONAL ', ' PROVISIONAL ', ' NOTIFICATION OF ADMISSION ')
_ENGLISH_TWINS = {
    'public university (UA) name': [_IIUM_EN],
    'offer/admission line': [_IIUM_OFFER_SENTENCE],
    'academic office': [_IIUM_OFFICE],                       # "Bahagian … Akademik"
    'finality / no-change clause': ['THIS OFFER IS VALID FOR'],
    'Program / Kod Program': [],                             # "PROGRAMME :" folds to a bare word: no twin
    'registration date': ['REGISTRATION DATE'],
}
UA_OFFER_SIGNATURES_EN = [(label, patterns + _ENGLISH_TWINS[label], weight, kind)
                          for label, patterns, weight, kind in UA_OFFER_SIGNATURES]


def english_ua_lists(lists: dict, text_norm: str, ocr_text: str = ''):
    """``(lists, text_norm)`` for an offer: unchanged, unless the page is IIUM's own English offer (the five
    rules above) — then the UA family reads its English twins (`UA_OFFER_SIGNATURES_EN`)."""
    if _IIUM_SUBJECT not in f' {text_norm} ' or _IIUM_OFFICE not in text_norm or not _issued_by_iium(ocr_text):
        return lists, text_norm
    return {**lists, 'ua_offer': UA_OFFER_SIGNATURES_EN}, text_norm


def _issued_by_iium(ocr_text: str) -> bool:
    """Rules 3-5 (rule 4 up to the end of the sentence's line)."""
    from .offer_reading import _PARTNER, _TIE_UP, _folded_lines, _page
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    at = page.find(_IIUM_SUBJECT)
    if at < 0:
        return False
    end = page.find(' ', at + len(_IIUM_SUBJECT))
    line_end = next((pos + len(ln.strip()) for pos, ln in _starts(lines) if pos + len(ln.strip()) >= end), len(page))
    if any(w in f'{page[:line_end]} ' for w in _NOT_YET):
        return False                                          # rule 4
    if any(w in page for w in _PARTNER + _TIE_UP + _TIE_UP_EXTRA):
        return False                                          # rule 3: tie-up wording, ANYWHERE on the page
    for pos, ln in _starts(lines):
        if pos >= at:
            break
        if _names_another(f' {page[pos:min(pos + len(ln.strip()), at)].strip()} ', campus=True):
            return False                                      # rule 3: another organisation named first
    return not any(_names_another(ln) for ln in _signature_block(lines))      # rule 5


def _names_another(ln: str, campus: bool = False) -> bool:
    """The folded line names an organisation other than IIUM and its office (`offer_reading._outside_orgs`; a
    company is one). Above the sentence a CAMPUS counts too ("MERCU CAMPUS")."""
    from .offer_reading import _allowed_spans, _decontact, _outside_orgs, _unstreeted
    ln = _unstreeted(_decontact(ln))
    allowed = (f' {_IIUM_EN} ', f' {_IIUM_OFFICE} ')
    return bool(_outside_orgs(ln, _allowed_spans(ln, allowed))) or (campus and ' CAMPUS ' in ln)


#: Rule 5: the signature block — from the closing to IIUM's office line, at most this many lines.
_CLOSINGS = (' YOURS SINCERELY ', ' YOURS FAITHFULLY ', ' YOURS TRULY ')
_SIGNATURE_LINES = 6


def _signature_block(lines):
    """The lines from the first closing ("Yours sincerely") to the office line inclusive (at most
    `_SIGNATURE_LINES`); none when the page has no closing."""
    at = next((i for i, ln in enumerate(lines) if any(c in ln for c in _CLOSINGS)), None)
    if at is None:
        return []
    block = []
    for ln in lines[at:at + _SIGNATURE_LINES]:
        block.append(ln)
        if f' {_IIUM_OFFICE} ' in ln:
            break
    return block


def _starts(lines):
    """(where each folded line starts in `offer_reading._page(lines)`, the line)."""
    pos = 1
    for ln in lines:
        yield pos, ln
        pos += len(ln.strip()) + 1
