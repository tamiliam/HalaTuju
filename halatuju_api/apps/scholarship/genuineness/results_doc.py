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

# Version of the deterministic document-recognition model — the signature FAMILIES + weights +
# identity gates + bands in THIS module. **Bump on ANY calibration change** (a new family, a
# weight/anchor/threshold tweak) so a stored genuineness result can be traced to the model that
# produced it and performance compared across versions. It travels on every result as
# ``model_version`` (and is persisted in ``vision_fields['authenticity']``).
# History:
#   1.0 (2026-06-27) — first full Layer-1 set held-out-validated on unseen prod docs:
#       results_slip + certificate, birth_certificate (text-only, visual signatures dropped),
#       epf (+ wrong-type backstop), offer_letter families (stpm / matriculation / polytechnic /
#       pismp / ua_offer, identity-anchor gated), STR (letter / dashboard / semakan, identity gated).
#   1.1 (2026-06-27) — ua_offer offer-line now requires the OFFICIAL offer wording ("Tawaran
#       Kemasukan" / "Surat Tawaran") only; a "Pemakluman Kemasukan" admission notification
#       (UM SATU / UPU-rayuan pre-offer, #31) no longer matches → floors at suspect. Owner policy:
#       official offer letters only. (Only a31 used the dropped 'PEMAKLUMAN KEMASUKAN' anchor.)
#   1.2 (2026-06-29) — STR-proof model rework (docs/scholarship/str-proof-spec.md): structured STR
#       currency states (wrong_type / rejected / unreadable / stale / unconfirmed / current); a
#       non-STR in the STR slot (SALINAN / SARA / payslip) is wrong_type (→ RED, not "unconfirmed");
#       a dateless approved STR is no longer "current" (→ unconfirmed/BLUE); extraction reads the
#       status VALUE not the "Status Permohonan STR" label, dates only from letter/payment (not nav
#       chrome), and sharper dashboard-vs-semakan classification. No signature-family/weight change
#       here, but the STR verdict pipeline it feeds changed → bump for traceability.
#   1.2.1 (2026-07-01) — STR-proof refinement (docs/scholarship/str-proof-spec.md): (a) a positive
#       PAID amount ("Jumlah … STR RM…") now corroborates approval, rescuing a doc whose "Lulus"
#       token was misread as the "STR" label (payment is EXTRA — "Lulus" alone still suffices, a
#       zero/absent amount never downgrades); (b) the STR band matrix — Lulus+dated→Certain,
#       Lulus+no-date→Probable, Lulus+prior-year(stale)/approval-unread→Unsure, Ditolak/non-STR→Fail
#       (salary route the net beneath); (c) the officer Status/Current chips split cleanly (Status =
#       approval, Current = date-only, dateless → "we don't know" grey). No signature-family/weight
#       change; the STR currency/verdict logic it feeds changed → bump for traceability.
MODEL_VERSION = '1.2.1'

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
# NOTE: the BC genuineness path is scored TEXT-ONLY (no image read is wired for the BC, unlike
# the results-slip). So the visual signatures (JATA NEGARA crest + barcode) could never be
# credited — they only ever dragged a genuine plain BC toward 'suspect' (3/13 unseen BCs dipped
# to 0.63–0.67 in held-out testing) while catching zero fakes. They are DROPPED here so the
# text signatures alone score the doc honestly. (To escalate to a visual read later — "option b"
# — re-add `('JATA NEGARA', ['__crest__'], 2, 'visual')` + `('barcode', ['__barcode__'], 3,
# 'visual')` AND fetch `results_visual_markers` for the BC in vision.run_field_extraction.)
BC_SIGNATURES = [
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

# Asasi / UA-Diploma / Degree — ONE generic family for the FIXED set of 20 public universities
# (UA; halatuju-web src/data/publicUniversities.ts == courses UNIV-001..020). Their letterheads
# diverge, but every UA offer names the university, so the NAME (any of the 20) is the
# forge-resistant ANCHOR — this covers all 20 incl. ones not yet in the corpus, with no per-uni
# code. The office / finality-clause / offer-line wordings are UNION-matched across institutions,
# so a specific letter still scores on its own variant (specificity kept). TEXT-ONLY (institution
# logos aren't reliably detectable). A university NOT in this list (private / IPTS, e.g. Swinburne)
# matches no anchor → unrecognised → holistic. Validated out-of-sample 2026-06-20.
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
    ('public university (UA) name', list(_UA_NAMES),                               3, 'text'),
    # ONLY the official offer HEADER "Tawaran Kemasukan". A "Pemakluman Kemasukan" (admission
    # NOTIFICATION — e.g. the UM SATU/UPU-rayuan pre-offer, #31) is NOT the official offer, so it
    # must not match here → it floors at suspect → reviewer requests the real offer. (NB: do NOT add
    # 'SURAT TAWARAN' — a pemakluman MENTIONS "surat tawaran rasmi (akan menyusul)", which would
    # wrongly match.) Owner policy: official offer letters only.
    ('offer/admission line',        ['TAWARAN KEMASUKAN'],                        3, 'text'),
    ('academic office',             ['PEJABAT PENGURUSAN AKADEMIK', 'PUSAT PENGURUSAN AKADEMIK',
                                     'BAHAGIAN HAL EHWAL AKADEMIK', 'PEJABAT PENDAFTAR',
                                     'PUSAT PEMASARAN DAN KEMASUKAN'],             1, 'text'),
    ('finality / no-change clause', ['PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN',
                                     'SEBARANG PERTUKARAN', 'TIDAK DIBENARKAN MENUKAR PROGRAM',
                                     'TAWARAN AKAN DITARIK BALIK', 'ADALAH MUKTAMAD'], 1, 'text'),
    ('Program / Kod Program',       ['PROGRAM PENGAJIAN', 'PROGRAM KOD'],          1, 'text'),
    ('registration date',           ['TARIKH PENDAFTARAN', 'TARIKH MENDAFTAR',
                                     'TARIKH LAPOR DIRI'],                         1, 'text'),
]

# STR (Sumbangan Tunai Rahmah) — THREE genuine approval artefacts (owner-specified 2026-06-27),
# each scored as its own form; score_signatures takes the best fit. The IDENTITY anchor for each
# is its DISTINCTIVE PAGE MARKER, deliberately NOT the shared "Maklumat Pemohon" / "Sumbangan
# Tunai Rahmah" strings — because those also appear on an LHDN **SALINAN** application copy (a8,
# a23) and must NOT be mistaken for an approval. A **SARA** letter (a63, Perdana Menteri) carries
# none of these markers. So: SALINAN + SARA fall to 'unrecognised' → holistic, never genuine STR.
# (Approval vs not — diluluskan / Lulus — is the extraction `status` field, a separate axis.)
STR_LETTER_SIGNATURES = [          # MOF approval letter (Kementerian Kewangan)
    ('Kementerian Kewangan Malaysia', ['KEMENTERIAN KEWANGAN MALAYSIA'],         3, 'text'),
    ('Sumbangan Tunai Rahmah (STR)',  ['SUMBANGAN TUNAI RAHMAH'],                 2, 'text'),
    ('STR application approved body', ['SUKACITA DIMAKLUMKAN BAHAWA PERMOHONAN STR'], 2, 'text'),
    ('MOF Putrajaya address',         ['62592 PUTRAJAYA', 'PERSIARAN PERDANA'],   1, 'text'),
    ('mof.gov.my',                    ['MOF GOV MY'],                             1, 'text'),
    ('No. Rujukan',                   ['NO RUJUKAN'],                             1, 'text'),
    ('kelayakan STR enquiry clause',  ['BERHUBUNG KELAYAKAN STR', 'PERTANYAAN LANJUT'], 1, 'text'),
]
STR_DASHBOARD_SIGNATURES = [       # MySTR app dashboard
    ('Status Permohonan STR',         ['STATUS PERMOHONAN STR'],                  3, 'text'),
    ('Dashboard',                     ['DASHBOARD'],                              2, 'text'),
    ('Profil',                        ['PROFIL'],                                 1, 'text'),
    ('Jumlah Telah Dibayar',          ['JUMLAH TELAH DIBAYAR'],                   1, 'text'),
    ('Jumlah Bayaran Keseluruhan',    ['JUMLAH BAYARAN KESELURUHAN'],             1, 'text'),
]
STR_SEMAKAN_SIGNATURES = [         # MySTR Semakan Status check page
    # 'Status Permohonan Semasa' (the approval status field) outweighs the 'Semakan Status'
    # page title — real Semakan screenshots are commonly cropped to start at 'Maklumat
    # Pemohon', dropping the title, so the status field is the more reliable anchor (and it's
    # ABSENT on an LHDN SALINAN application copy, which carries Umur/Jantina/Pekerjaan instead).
    ('Status Permohonan Semasa',      ['STATUS PERMOHONAN SEMASA'],               3, 'text'),
    ('Semakan Status',                ['SEMAKAN STATUS'],                         2, 'text'),
    ('Maklumat Pemohon',              ['MAKLUMAT PEMOHON'],                       1, 'text'),
    ('No. MyKad',                     ['NO MYKAD'],                               1, 'text'),
    ('Fasa Bayaran',                  ['FASA BAYARAN'],                           1, 'text'),
    # The MySTR Semakan co-displays the SARA sub-section "Sumbangan Asas Rahmah" (SARA, the
    # sibling scheme). A weight-1 corroborating signal only — NOT an identity anchor, so a
    # SARA-only doc (no Semakan Status / Status Permohonan Semasa) still can't pass as STR.
    ('Sumbangan Asas Rahmah',         ['SUMBANGAN ASAS RAHMAH'],                  1, 'text'),
    ('Status Pedalaman',              ['STATUS PEDALAMAN'],                       1, 'text'),
]

# A doc_type is scored against its FAMILY of candidate lists (best fit wins + names the type).
# results_slip + certificate are scored together (auto-detect); birth_certificate is its own.
_RESULTS_LISTS = {'results_slip': SLIP_SIGNATURES, 'certificate': CERT_SIGNATURES}
_STR_LISTS = {'str_letter': STR_LETTER_SIGNATURES, 'str_dashboard': STR_DASHBOARD_SIGNATURES,
              'str_semakan': STR_SEMAKAN_SIGNATURES}
_OFFER_LISTS = {'stpm': STPM_OFFER_SIGNATURES, 'matriculation': MATRIC_OFFER_SIGNATURES,
                'polytechnic': POLY_OFFER_SIGNATURES, 'pismp': PISMP_OFFER_SIGNATURES,
                'ua_offer': UA_OFFER_SIGNATURES}
_FAMILIES = {'results_slip': _RESULTS_LISTS, 'certificate': _RESULTS_LISTS,
             'birth_certificate': {'birth_certificate': BC_SIGNATURES},
             'epf': {'epf': EPF_SIGNATURES},
             'offer_letter': _OFFER_LISTS,
             'str': _STR_LISTS}
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
    # Asasi / UA-Diploma / Degree — recognised iff the letter names one of the fixed 20 UAs.
    'ua_offer':      list(_UA_NAMES),
}, 'str': {
    # The DISTINCTIVE page marker per STR approval form (NOT the shared "Maklumat Pemohon" /
    # "Sumbangan Tunai Rahmah" — those also sit on an LHDN SALINAN copy). A doc matching none
    # (a SALINAN, a SARA letter) is 'unrecognised' → holistic, never a genuine STR.
    'str_letter':    ['KEMENTERIAN KEWANGAN MALAYSIA'],
    'str_dashboard': ['STATUS PERMOHONAN STR'],
    # Any of three anchors recognises a genuine Semakan — robust to crop AND OCR layout noise:
    #  • 'Semakan Status' (page title) — lost when cropped above it;
    #  • 'Status Permohonan Semasa' (status field) — can be OCR-split on the desktop layout, where
    #    the label wraps and the value lands between ("Status Permohonan" / Lulus / "Semasa", a51);
    #  • 'Status Pedalaman' (rural-status field) — present on EVERY Semakan (mobile + desktop),
    #    absent on the letter / dashboard / SALINAN / SARA, and OCR-stable. The backstop anchor.
    'str_semakan':   ['SEMAKAN STATUS', 'STATUS PERMOHONAN SEMASA', 'STATUS PEDALAMAN'],
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
                               f"(p={r['probability']:.2f}) — defer to holistic check")[:300],
                    'model_version': MODEL_VERSION}
        status = 'genuine' if r['probability'] >= GENUINE_MIN else 'suspect'
        reason = (f"{n_have}/{n_all} {r['type']} offer signatures present "
                  f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
        return {'status': status, 'probability': r['probability'], 'type': r['type'],
                'present': r['present'], 'missing': r['missing'], 'reason': reason[:300],
                'model_version': MODEL_VERSION}

    status = band_for(r['probability'])
    if status == 'not_type':                       # <0.35 → not recognisably that document
        status = 'not_' + (doc_type or r['type'])
    reason = (f"{n_have}/{n_all} {r['type'].replace('_', ' ')} signatures present "
              f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
    return {'status': status, 'probability': r['probability'], 'type': r['type'],
            'present': r['present'], 'missing': r['missing'], 'reason': reason[:300],
            'model_version': MODEL_VERSION}
