"""Probabilistic genuineness for SPM results documents (slip + certificate) via SIGNATURE
presence. Moved here from apps/scholarship/doc_signatures.py (which is now a back-compat shim).

Unlike the IC / supporting-doc checks (which ask a model a holistic question), almost every
distinctive feature of an SPM slip/cert is a fixed PRINTED STRING, so we detect it
deterministically in the OCR text — no model guess, fully auditable, identical every run.
Only two signatures are visual (the JATA NEGARA crest and the QR code), passed in as flags.

We score against TWO lists — a results SLIP and a CERTIFICATE — and take the better fit, which
also tells us WHICH one it is. The score is a PROBABILITY (weighted fraction of expected
signatures present), not a yes/no: a student may photograph a slip with the bottom cut off, so
a genuine document can be missing its trailing signatures (QR / PENGARAH / disclaimer) and must
still score as likely-genuine on everything else. Forge-hard signatures carry more weight, so
their PRESENCE lifts confidence while their ABSENCE alone never condemns a complete document.

SOFT signal only; the reviewer is the authority.
"""
import re
import unicodedata

from .bands import GENUINE_MIN, SUSPECT_MAX, band_for  # noqa: F401  (re-exported for callers)

# Each signature: (label, [match patterns], weight, kind). kind 'text' is matched against the
# OCR text; kind 'visual' is satisfied by a passed-in flag (crest / QR). Weights: 1 = ordinary
# label, 2 = distinctive, 3 = forge-hard / near-unique to the genuine document.
SLIP_SIGNATURES = [
    ('JATA NEGARA',                  ['__crest__'],                          2, 'visual'),
    ('KEMENTERIAN PENDIDIKAN',       ['KEMENTERIAN PENDIDIKAN'],             1, 'text'),
    ('LEMBAGA PEPERIKSAAN',          ['LEMBAGA PEPERIKSAAN'],                2, 'text'),
    ('SIJIL PELAJARAN MALAYSIA',     ['SIJIL PELAJARAN MALAYSIA'],           1, 'text'),
    ('NO. PENGENALAN DIRI',          ['PENGENALAN DIRI'],                    1, 'text'),
    ('ANGKA GILIRAN',                ['ANGKA GILIRAN'],                      2, 'text'),
    ('SEKOLAH',                      ['SEKOLAH'],                            1, 'text'),
    ('JUMLAH MATA PELAJARAN',        ['JUMLAH MATA PELAJARAN'],              1, 'text'),
    ('KOD',                          ['KOD'],                                1, 'text'),
    ('NAMA MATA PELAJARAN',          ['NAMA MATA PELAJARAN'],                1, 'text'),
    ('GRED',                         ['GRED'],                               1, 'text'),
    ('LAYAK MENDAPAT SIJIL',         ['LAYAK MENDAPAT SIJIL'],               2, 'text'),
    ('UJIAN LISAN BAHASA MELAYU',    ['UJIAN LISAN BAHASA MELAYU'],          1, 'text'),
    ('disclaimer (bukan sijil)',     ['SLIP KEPUTUSAN INI BUKAN SIJIL',
                                      'BUKAN SIJIL/PERNYATAAN',
                                      'BUKAN SIJIL PERNYATAAN'],             3, 'text'),
    ('QR CODE',                      ['__qr__'],                             3, 'visual'),
    ('PENGARAH PEPERIKSAAN',         ['PENGARAH PEPERIKSAAN'],               2, 'text'),
]

CERT_SIGNATURES = [
    ('JATA NEGARA',                  ['__crest__'],                          2, 'visual'),
    ('KEMENTERIAN PENDIDIKAN MALAYSIA', ['KEMENTERIAN PENDIDIKAN MALAYSIA',
                                         'KEMENTERIAN PENDIDIKAN'],          1, 'text'),
    ('MINISTRY OF EDUCATION MALAYSIA', ['MINISTRY OF EDUCATION'],            2, 'text'),
    ('LEMBAGA PEPERIKSAAN',          ['LEMBAGA PEPERIKSAAN'],                1, 'text'),
    ('EXAMINATIONS SYNDICATE',       ['EXAMINATIONS SYNDICATE'],             2, 'text'),
    ('Calon yang namanya',           ['CALON YANG NAMANYA'],                 2, 'text'),
    ('SIJIL PELAJARAN MALAYSIA',     ['SIJIL PELAJARAN MALAYSIA'],           1, 'text'),
    ('Mata Pelajaran',               ['MATA PELAJARAN'],                     1, 'text'),
    ('Gred',                         ['GRED'],                               1, 'text'),
    ('Subject',                      ['SUBJECT'],                            1, 'text'),
    ('Grade',                        ['GRADE'],                              1, 'text'),
    ('UJIAN LISAN BAHASA MELAYU',    ['UJIAN LISAN BAHASA MELAYU'],          1, 'text'),
    ('JUMLAH MATA PELAJARAN',        ['JUMLAH MATA PELAJARAN'],              1, 'text'),
    ('PEPERIKSAAN TAHUN',            ['PEPERIKSAAN TAHUN'],                   1, 'text'),
    ('QR CODE',                      ['__qr__'],                             3, 'visual'),
    ('Director of Examinations',     ['DIRECTOR OF EXAMINATIONS'],           2, 'text'),
]

# Birth certificate (JPN Sijil Kelahiran) — standard document, so same signature approach.
# Mostly fixed printed strings; the JATA NEGARA crest + the barcode (which encodes the child's
# IC) are the two visual markers (the barcode is the BC's machine token, ~ the slip's QR).
BC_SIGNATURES = [
    ('JATA NEGARA',                   ['__crest__'],                                    2, 'visual'),
    ('KERAJAAN MALAYSIA',             ['KERAJAAN MALAYSIA'],                            1, 'text'),
    ('SIJIL KELAHIRAN',               ['SIJIL KELAHIRAN'],                              2, 'text'),
    ('Akta Pendaftaran 1957',         ['PENDAFTARAN KELAHIRAN DAN KEMATIAN'],           3, 'text'),
    ('KANAK-KANAK',                   ['KANAK KANAK'],                                  2, 'text'),
    ('BAPA',                          ['BAPA'],                                         1, 'text'),
    ('IBU',                           ['IBU'],                                          1, 'text'),
    ('No. Kad Pengenalan',            ['KAD PENGENALAN'],                               1, 'text'),
    ('Taraf Kewarganegaraan',         ['KEWARGANEGARAAN', 'WARGANEGARA'],               1, 'text'),
    ('Kawasan Pendaftaran',           ['KAWASAN PENDAFTARAN'],                          2, 'text'),
    ('Tempat Kelahiran',              ['TEMPAT KELAHIRAN'],                             1, 'text'),
    ('No. Daftar',                    ['NO DAFTAR'],                                    2, 'text'),
    ('certification line',            ['DISAHKAN BAHAWA MAKLUMAT'],                     2, 'text'),
    ('PENDAFTAR BESAR',               ['PENDAFTAR BESAR'],                              2, 'text'),
    ('Kelahiran & Kematian Malaysia', ['KELAHIRAN DAN KEMATIAN MALAYSIA',
                                       'KELAHIRAN KEMATIAN MALAYSIA'],                  1, 'text'),
    ('barcode',                       ['__barcode__'],                                  3, 'visual'),
]

# EPF (KWSP Penyata Ahli) — standard statement. No Jata Negara crest / no QR; the visual anchor
# is the KWSP logo, and the distinctive "computer print, no signature" line + kwsp.gov.my play the
# machine-token role. Covers both the 2-account (older) and 3-account (2024+) formats.
EPF_SIGNATURES = [
    ('KWSP logo',                  ['__crest__'],                                         2, 'visual'),
    ('KWSP / EPF',                 ['KWSP', 'KUMPULAN WANG SIMPANAN PEKERJA'],            2, 'text'),
    ('SULIT DAN PERSENDIRIAN',     ['SULIT DAN PERSENDIRIAN'],                            2, 'text'),
    ('PENYATA AHLI',               ['PENYATA AHLI'],                                      3, 'text'),
    ('No. Ahli KWSP',              ['NO AHLI KWSP', 'AHLI KWSP'],                         2, 'text'),
    ('No. Kad Pengenalan',         ['KAD PENGENALAN'],                                    1, 'text'),
    ('No. Majikan',                ['NO MAJIKAN', 'MAJIKAN'],                             1, 'text'),
    ('RINGKASAN AKAUN',            ['RINGKASAN AKAUN'],                                   2, 'text'),
    ('Akaun',                      ['JENIS AKAUN', 'AKAUN PERSARAAN', 'AKAUN 1'],         1, 'text'),
    ('CARUMAN',                    ['CARUMAN'],                                           1, 'text'),
    ('JUMLAH SIMPANAN',            ['JUMLAH SIMPANAN'],                                   2, 'text'),
    ('CARUMAN SEMASA',             ['CARUMAN SEMASA'],                                    1, 'text'),
    ('computer-print disclaimer',  ['CETAKAN KOMPUTER DAN TIDAK MEMERLUKAN TANDATANGAN'], 3, 'text'),
    ('kwsp.gov.my',                ['KWSP GOV MY'],                                       2, 'text'),
    ('Cetakan myEPF',              ['CETAKAN MYEPF', 'MYEPF'],                            1, 'text'),
    ('KWSP address',               ['MENARA KWSP', 'JALAN SULTAN'],                       1, 'text'),
]

# Offer letters — unlike the slip/cert (single issuer), the post-SPM offer comes from THREE
# standard government issuers, each with a fixed machine-generated letterhead. We score against
# all three and take the best fit (which also names the pathway). TEXT-ONLY: the issuer
# fingerprints are conclusive on their own, and the Jata Negara crest is generic boilerplate
# across every government letter (a weak, easily-forged discriminator) — so no visual signature,
# which also keeps the scorer fully deterministic + free. The heterogeneous tail (universities,
# IPG, private foundations) matches NO family and is deferred to the holistic check (see the
# identity gate in ``signature_genuineness``), so a legitimate university offer is never flagged.

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

# Per-INSTITUTION offer families (owner-specified 2026-06-20). Asasi + UA-Diploma offers come from
# many universities with divergent letterheads, so each enumerated institution is its own family
# (the university NAME line is the forge-resistant anchor). TEXT-ONLY: institution logos can't be
# reliably detected per-logo, and the printed university name is conclusive. Any university NOT
# enumerated here stays unrecognised → holistic. Calibrated on 1–2 corpus docs each (thin — weights
# conservative); a cropped capture (e.g. a75) hits only the anchor → suspect, as intended.
ASASI_UPNM_SIGNATURES = [
    ('UPNM (Univ Pertahanan Nasional)', ['UNIVERSITI PERTAHANAN NASIONAL MALAYSIA'],   3, 'text'),
    ('Pusat Pengurusan Akademik & Pengijazahan', ['PUSAT PENGURUSAN AKADEMIK DAN PENGIJAZAHAN'], 2, 'text'),
    ('Tawaran kemasukan ke UPNM',    ['TAWARAN KEMASUKAN KE UNIVERSITI PERTAHANAN NASIONAL MALAYSIA'], 2, 'text'),
    ('pertukaran tidak dibenarkan',  ['SEBARANG PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN'], 2, 'text'),
    ('Program Pengajian',            ['PROGRAM PENGAJIAN'],                          1, 'text'),
    ('Tarikh Pendaftaran',           ['TARIKH PENDAFTARAN'],                         1, 'text'),
]
ASASIPINTAR_UKM_SIGNATURES = [
    ('ASASIpintar UKM',              ['TAWARAN KEMASUKAN PROGRAM ASASIPINTAR'],      3, 'text'),
    ('Univ Kebangsaan Malaysia',     ['UNIVERSITI KEBANGSAAN MALAYSIA'],             2, 'text'),
    ('Tawaran muktamad (asasipintar)', ['TAWARAN YANG DIBERIKAN ADALAH MUKTAMAD'],   2, 'text'),
    ('Pusat Pengurusan Akademik',    ['PUSAT PENGURUSAN AKADEMIK'],                  1, 'text'),
    ('Program Pengajian',            ['PROGRAM PENGAJIAN'],                          1, 'text'),
    ('Tarikh Lapor Diri',            ['TARIKH LAPOR DIRI'],                          1, 'text'),
]
UTHM_DIPLOMA_SIGNATURES = [
    ('UTHM (Univ Tun Hussein Onn)',  ['UNIVERSITI TUN HUSSEIN ONN MALAYSIA'],        3, 'text'),
    ('Pejabat Pengurusan Akademik',  ['PEJABAT PENGURUSAN AKADEMIK'],                2, 'text'),
    ('Tawaran kemasukan ke UTHM',    ['TAWARAN KEMASUKAN KE UNIVERSITI TUN HUSSEIN ONN MALAYSIA'], 2, 'text'),
    ('Tahniah diucapkan',            ['TAHNIAH DIUCAPKAN'],                          1, 'text'),
    ('Program & Kod',                ['PROGRAM KOD'],                                1, 'text'),
]
UPSI_DIPLOMA_SIGNATURES = [
    ('UPSI (Univ Pendidikan Sultan Idris)', ['UNIVERSITI PENDIDIKAN SULTAN IDRIS'],  3, 'text'),
    ('Bahagian Hal Ehwal Akademik',  ['BAHAGIAN HAL EHWAL AKADEMIK'],                2, 'text'),
    ('Tawaran kemasukan ke UPSI',    ['TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS'], 2, 'text'),
    ('tidak dibenarkan menukar program', ['TIDAK DIBENARKAN MENUKAR PROGRAM PENGAJIAN'], 2, 'text'),
    ('Sultan Idris Education University', ['SULTAN IDRIS EDUCATION UNIVERSITY'],      1, 'text'),
    ('Tarikh Mendaftar',             ['TARIKH MENDAFTAR'],                           1, 'text'),
]
UTEM_DIPLOMA_SIGNATURES = [
    ('UTeM (Univ Teknikal Malaysia Melaka)', ['UNIVERSITI TEKNIKAL MALAYSIA MELAKA'], 3, 'text'),
    ('Pejabat Pendaftar',            ['PEJABAT PENDAFTAR'],                          2, 'text'),
    ('Tawaran kemasukan ke UTeM',    ['TAWARAN KEMASUKAN KE UNIVERSITI TEKNIKAL MALAYSIA'], 2, 'text'),
    ('ditarik balik (UTeM clause)',  ['TAWARAN AKAN DITARIK BALIK SEKIRANYA UTEM'],  2, 'text'),
    ('Program Pengajian',            ['PROGRAM PENGAJIAN'],                          1, 'text'),
]
UMP_DIPLOMA_SIGNATURES = [
    ('UMP (Univ Malaysia Pahang)',   ['UNIVERSITI MALAYSIA PAHANG'],                 3, 'text'),
    ('Pusat Pemasaran dan Kemasukan', ['PUSAT PEMASARAN DAN KEMASUKAN'],             2, 'text'),
    ('Tawaran kemasukan ke Diploma UMP', ['TAWARAN KEMASUKAN KE PROGRAM DIPLOMA UNIVERSITI MALAYSIA PAHANG'], 2, 'text'),
    ('pertukaran program tidak dibenarkan', ['PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN'], 2, 'text'),
    ('Program Pengajian',            ['PROGRAM PENGAJIAN'],                          1, 'text'),
    ('Tarikh Pendaftaran',           ['TARIKH PENDAFTARAN'],                         1, 'text'),
]

# A doc_type is scored against its FAMILY of candidate lists (best fit wins + names the type).
# results_slip + certificate are scored together (auto-detect); birth_certificate is its own.
_RESULTS_LISTS = {'results_slip': SLIP_SIGNATURES, 'certificate': CERT_SIGNATURES}
_OFFER_LISTS = {'stpm': STPM_OFFER_SIGNATURES, 'matriculation': MATRIC_OFFER_SIGNATURES,
                'polytechnic': POLY_OFFER_SIGNATURES, 'pismp': PISMP_OFFER_SIGNATURES,
                'asasi_upnm': ASASI_UPNM_SIGNATURES, 'asasipintar_ukm': ASASIPINTAR_UKM_SIGNATURES,
                'uthm_diploma': UTHM_DIPLOMA_SIGNATURES, 'upsi_diploma': UPSI_DIPLOMA_SIGNATURES,
                'utem_diploma': UTEM_DIPLOMA_SIGNATURES, 'ump_diploma': UMP_DIPLOMA_SIGNATURES}
_FAMILIES = {'results_slip': _RESULTS_LISTS, 'certificate': _RESULTS_LISTS,
             'birth_certificate': {'birth_certificate': BC_SIGNATURES},
             'epf': {'epf': EPF_SIGNATURES},
             'offer_letter': _OFFER_LISTS}
_LISTS = _RESULTS_LISTS   # back-compat default (slip/cert)

# Issuer "identity" anchors per offer-letter family: presence of ANY means the document IS that
# pathway's offer (so a low overall score = cropped/incomplete → suspect, NOT "not an offer
# letter"). If NO family's anchor matches, the document is not one of the three standard issuers
# (a university / IPG / private offer) and ``signature_genuineness`` defers to the holistic check.
_IDENTITY = {'offer_letter': {
    'stpm':          ['SEKTOR OPERASI SEKOLAH', 'TINGKATAN ENAM', 'PUSAT TINGKATAN ENAM'],
    'matriculation': ['BAHAGIAN MATRIKULASI', 'PROGRAM MATRIKULASI', 'JURUSAN'],
    'polytechnic':   ['JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI',
                      'SURAT TAWARAN PENGAJIAN', 'GALERIA PJH'],
    'pismp':         ['INSTITUT PENDIDIKAN GURU', 'IJAZAH SARJANA MUDA PERGURUAN'],
    # Per-institution Asasi / UA-Diploma — the university NAME is the identity anchor.
    'asasi_upnm':      ['UNIVERSITI PERTAHANAN NASIONAL MALAYSIA'],
    'asasipintar_ukm': ['ASASIPINTAR', 'UNIVERSITI KEBANGSAAN MALAYSIA'],
    'uthm_diploma':    ['UNIVERSITI TUN HUSSEIN ONN MALAYSIA'],
    'upsi_diploma':    ['UNIVERSITI PENDIDIKAN SULTAN IDRIS', 'SULTAN IDRIS EDUCATION UNIVERSITY'],
    'utem_diploma':    ['UNIVERSITI TEKNIKAL MALAYSIA MELAKA'],
    'ump_diploma':     ['UNIVERSITI MALAYSIA PAHANG'],
}}


def _norm(s: str) -> str:
    """Upper-case, strip accents, collapse runs of non-alphanumerics to a single space."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^A-Z0-9]+', ' ', s.upper()).strip()


def _score_list(signatures, text_norm, has_qr, has_crest, has_seal=False):
    present, missing, got, total = [], [], 0, 0
    for label, patterns, weight, kind in signatures:
        total += weight
        if kind == 'visual':
            # __crest__ → the crest flag; __seal__ → an official round stamp/seal (e.g. the
            # JPPKK seal on a polytechnic offer); __qr__/__barcode__ → the machine-token flag.
            if patterns == ['__crest__']:
                hit = has_crest
            elif patterns == ['__seal__']:
                hit = has_seal
            else:
                hit = has_qr
        else:
            hit = any(_norm(p) in text_norm for p in patterns)
        (present if hit else missing).append(label)
        if hit:
            got += weight
    return {'weight_got': got, 'weight_total': total,
            'probability': round(got / total, 3) if total else 0.0,
            'present': present, 'missing': missing}


def score_signatures(ocr_text: str, has_qr: bool = False, has_crest: bool = False,
                     doc_type: str = None, has_seal: bool = False) -> dict:
    """Score OCR text against the slip + certificate signature lists. Returns
    ``{type, probability, weight_got, weight_total, present, missing, scores}`` for the
    better-fitting list. Pure + deterministic for the text signatures."""
    tn = _norm(ocr_text)
    lists = _FAMILIES.get(doc_type, _LISTS)
    scores = {name: _score_list(sig, tn, has_qr, has_crest, has_seal) for name, sig in lists.items()}
    best = max(scores, key=lambda k: scores[k]['probability'])
    b = scores[best]
    return {'type': best, 'probability': b['probability'],
            'weight_got': b['weight_got'], 'weight_total': b['weight_total'],
            'present': b['present'], 'missing': b['missing'], 'scores': scores}


# The two NON-text signatures (QR + crest) are visual, so a tiny multimodal read reports
# them — far more robust than decoding the QR (a model sees "a QR is present" even on a blurry
# photo where a decoder fails). Soft: an AI outage / no image → both absent, never a penalty.
_VISUAL_SCHEMA = {'type': 'object', 'properties': {
    'has_qr_code': {'type': 'boolean'}, 'has_jata_negara_crest': {'type': 'boolean'}},
    'required': ['has_qr_code', 'has_jata_negara_crest']}
_VISUAL_PROMPT = (
    'This image was uploaded as a Malaysian SPM results slip or certificate. Ignore the text '
    'and report two VISUAL features: has_qr_code — is a QR code / 2D barcode present anywhere on '
    'the document? has_jata_negara_crest — is the Malaysian national crest (Jata Negara, the '
    'tiger-and-shield coat of arms) present in the header?')


def results_visual_markers(data: bytes, content_type: str = '') -> dict:
    """Soft multimodal read of the two visual signatures → ``{'has_qr', 'has_crest'}``, or
    ``{}`` on no image / AI outage (both then treated as absent — never penalising). The Gemini
    seam is reached via ``vision._call_gemini_json`` (lazy import keeps this module's top pure)."""
    from apps.scholarship import vision
    img, mime = vision._as_image_for_gemini(data, content_type)
    if img is None:
        return {}
    r = vision._call_gemini_json(_VISUAL_PROMPT, _VISUAL_SCHEMA, image=img, mime_type=mime)
    if not isinstance(r, dict) or r.get('_error'):
        return {}
    return {'has_qr': bool(r.get('has_qr_code')), 'has_crest': bool(r.get('has_jata_negara_crest'))}


def signature_genuineness(ocr_text: str, has_qr: bool = False, has_crest: bool = False,
                          doc_type: str = None, has_seal: bool = False) -> dict:
    """The soft genuineness signal for a standard document from its signatures:
    ``{status, probability, type, present, missing, reason}``. ``status`` maps onto the cap
    vocabulary via ``band_for``. ``doc_type`` selects the signature family (slip/cert by default,
    'birth_certificate' for the BC). Pure + deterministic given the inputs; never raises."""
    r = score_signatures(ocr_text, has_qr=has_qr, has_crest=has_crest, doc_type=doc_type,
                         has_seal=has_seal)
    n_have, n_all = len(r['present']), len(r['present']) + len(r['missing'])

    identity = _IDENTITY.get(doc_type)
    if identity:
        # Multi-issuer type (offer letter): only score if we recognise one of the standard
        # issuers; otherwise defer to the holistic check (a legit university/IPG offer is NOT
        # one of these three, and must never be flagged). Recognised-but-incomplete → suspect,
        # never not_<type> (we KNOW it's that pathway's offer — it's just cropped).
        tn = _norm(ocr_text)
        recognised = any(_norm(p) in tn for p in identity.get(r['type'], []))
        if not recognised:
            return {'status': 'unrecognised', 'probability': r['probability'], 'type': r['type'],
                    'present': r['present'], 'missing': r['missing'],
                    'reason': (f"not one of the standard {doc_type.replace('_', ' ')} issuers "
                               f"(p={r['probability']:.2f}) — defer to holistic check")[:300]}
        status = 'genuine' if r['probability'] >= GENUINE_MIN else 'suspect'
        reason = (f"{n_have}/{n_all} {r['type']} offer signatures present "
                  f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
        return {'status': status, 'probability': r['probability'], 'type': r['type'],
                'present': r['present'], 'missing': r['missing'], 'reason': reason[:300]}

    status = band_for(r['probability'])
    if status == 'not_type':                       # <0.35 → not recognisably that document
        status = 'not_' + (doc_type or r['type'])
    reason = (f"{n_have}/{n_all} {r['type'].replace('_', ' ')} signatures present "
              f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
    return {'status': status, 'probability': r['probability'], 'type': r['type'],
            'present': r['present'], 'missing': r['missing'], 'reason': reason[:300]}
