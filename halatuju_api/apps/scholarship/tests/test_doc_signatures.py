"""Unit tests for the probabilistic signature genuineness (apps.scholarship.doc_signatures).

Pure + deterministic — no DB, no AI, no network. Synthetic OCR text stands in for the
Cloud Vision read; the real-corpus calibration lives in eval/calibrate_signatures.py.
"""
from apps.scholarship.doc_signatures import (
    score_signatures, signature_genuineness, band_for, GENUINE_MIN, SUSPECT_MAX,
)

# A faithful genuine SPM results-slip OCR (every textual signature present).
GENUINE_SLIP = """KEMENTERIAN PENDIDIKAN
LEMBAGA PEPERIKSAAN
SIJIL PELAJARAN MALAYSIA TAHUN 2025
NAMA : SHANTHINI A/P RAJU
NO. PENGENALAN DIRI : 080101-10-1234
ANGKA GILIRAN : BA013A001
SEKOLAH : SMK CONVENT
JUMLAH MATA PELAJARAN : SEPULUH
KOD NAMA MATA PELAJARAN GRED
1103 BAHASA MELAYU A
1119 BAHASA INGGERIS A+
LAYAK MENDAPAT SIJIL
UJIAN LISAN BAHASA MELAYU: CEMERLANG
Slip keputusan ini bukan sijil/pernyataan.
PENGARAH PEPERIKSAAN
"""

# A genuine SPM certificate (bilingual furniture).
GENUINE_CERT = """KEMENTERIAN PENDIDIKAN MALAYSIA
MINISTRY OF EDUCATION MALAYSIA
LEMBAGA PEPERIKSAAN
EXAMINATIONS SYNDICATE
Calon yang namanya tercatat di bawah telah menduduki peperiksaan
SIJIL PELAJARAN MALAYSIA
Mata Pelajaran Gred
Subject Grade
UJIAN LISAN BAHASA MELAYU: KEPUJIAN
JUMLAH MATA PELAJARAN : SEPULUH
PEPERIKSAAN TAHUN 2024
Director of Examinations
"""

# A genuine slip photographed with the bottom cut off (no disclaimer / PENGARAH / QR).
CROPPED_SLIP = """KEMENTERIAN PENDIDIKAN
LEMBAGA PEPERIKSAAN
SIJIL PELAJARAN MALAYSIA TAHUN 2025
NO. PENGENALAN DIRI : 080202-10-5678
ANGKA GILIRAN : BA013A002
SEKOLAH : SMK TAMAN
JUMLAH MATA PELAJARAN : SEMBILAN
KOD NAMA MATA PELAJARAN GRED
1103 BAHASA MELAYU A
"""

# A typed/fabricated "slip" — plain text, none of the official furniture.
TYPED_FAKE = """Sijil Pelajaran Malaysia Tahun 2025
Elanjelian A/L Venugopal
710829-02-5709
Bahasa Melayu A
Biologi B
"""


def test_genuine_slip_scores_high_and_types_as_slip():
    r = score_signatures(GENUINE_SLIP)
    assert r['type'] == 'results_slip'
    assert r['probability'] >= GENUINE_MIN
    assert band_for(r['probability']) == 'genuine'


def test_genuine_cert_types_as_certificate():
    r = score_signatures(GENUINE_CERT)
    assert r['type'] == 'certificate'
    assert r['probability'] >= GENUINE_MIN


def test_typed_fake_is_not_type():
    # A typed reproduction scores <0.35 → not recognisably that document → not_<type>.
    g = signature_genuineness(TYPED_FAKE)
    assert g['status'].startswith('not_')
    assert g['probability'] < SUSPECT_MAX


def test_cropped_genuine_is_suspect_not_genuine():
    g = signature_genuineness(CROPPED_SLIP)
    assert g['status'] == 'suspect'             # incomplete → suspect (re-upload), never genuine
    assert SUSPECT_MAX <= g['probability'] < GENUINE_MIN


def test_visual_signals_lift_a_cropped_doc_to_genuine():
    """Crediting the QR + crest (the two visual signatures) recovers a cropped genuine."""
    low = signature_genuineness(CROPPED_SLIP)
    high = signature_genuineness(CROPPED_SLIP, has_qr=True, has_crest=True)
    assert high['probability'] > low['probability']
    assert high['status'] in ('genuine', 'suspect')


def test_never_raises_on_empty():
    g = signature_genuineness('')
    assert g['status'].startswith('not_') and g['probability'] == 0.0


def test_signature_genuineness_reports_evidence():
    g = signature_genuineness(GENUINE_SLIP)
    assert 'LAYAK MENDAPAT SIJIL' in g['present']
    assert isinstance(g['missing'], list)
    assert 'signatures present' in g['reason']


# ── Birth certificate (same approach + band as the slip) ──────────────────────
GENUINE_BC = """KERAJAAN MALAYSIA
SIJIL KELAHIRAN
Akta Pendaftaran Kelahiran dan Kematian, 1957
Kawasan Pendaftaran : SELANGOR DAN WILAYAH PERSEKUTUAN
KANAK-KANAK
Nama : TAANUSIYA
Tarikh Kelahiran : 14 MEI 2008
Tempat Kelahiran : HOSPITAL BERSALIN KUALA LUMPUR
Taraf Kewarganegaraan : WARGANEGARA
BAPA
Nama : MUGINDRAN A/L ATHIAH
No. Kad Pengenalan : 800419-14-5221
IBU
Nama : THAVAMALAR A/P VIJAYAN
No. Kad Pengenalan : 821001-14-6094
No. Daftar : BZ 46718
Disahkan bahawa maklumat di atas adalah seperti yang dicatat dalam Daftar Kelahiran
PENDAFTAR BESAR KELAHIRAN DAN KEMATIAN MALAYSIA
"""
# A typed fake BC — names + NRICs + Ibu/Bapa labels only, no official furniture (the a16 pattern).
TYPED_FAKE_BC = "Elanjelian A/L Venugopal\nGUNAMANI A/P P. Ganeson\n480805-02-0505\nIbu\nVenugopal A/L Sankaranaidu\n440216-02-0909\nBapa\n"
# Only the lower third in frame (cropped/zoomed — the a27 pattern): IBU section + certification.
CROPPED_BC = "IBU\nNama : THAMARAI A/P VEERASINGAM\nNo. Kad Pengenalan : 860419-43-5610\nTaraf Kewarganegaraan : WARGANEGARA\nDisahkan bahawa maklumat\n"


def test_genuine_bc_scores_genuine_and_types_as_bc():
    r = score_signatures(GENUINE_BC, doc_type='birth_certificate')
    assert r['type'] == 'birth_certificate'
    assert r['probability'] >= GENUINE_MIN
    assert band_for(r['probability']) == 'genuine'


def test_typed_fake_bc_is_not_type():
    g = signature_genuineness(TYPED_FAKE_BC, doc_type='birth_certificate')
    assert g['status'] == 'not_birth_certificate'   # <0.35 → not recognisably a BC
    assert g['probability'] < SUSPECT_MAX


def test_cropped_bc_is_flagged_not_genuine():
    # A zoomed-in / partial BC missing its top (title, crest, child/father) must NOT pass.
    g = signature_genuineness(CROPPED_BC, doc_type='birth_certificate')
    assert g['status'] != 'genuine'        # suspect or not_birth_certificate (by how much is in frame)
    assert g['probability'] < GENUINE_MIN


# ── EPF (KWSP Penyata Ahli) — same approach + band; catches wrong-type mis-slots ──
GENUINE_EPF = """KWSP EPF
SULIT DAN PERSENDIRIAN
NADARAJ A/L MUTHU
NO 3 SOLOK 11, 42000 PELABUHAN KLANG, Selangor
PENYATA AHLI TAHUN 2026
No. Ahli KWSP : 5174701   Tarikh Penyata : 13/06/2026
No. Kad Pengenalan : 620601105949
No. Majikan : 000000000
JUMLAH SIMPANAN: RM47,522.80
RINGKASAN AKAUN
Jenis Akaun  Baki Pembuka  Masuk  Caruman
Akaun Persaraan (Akaun 1) 43198.37
CARUMAN SEMASA
Penyata ini adalah cetakan komputer dan tidak memerlukan tandatangan.
Menara KWSP No 1, Jalan Sultan. www.kwsp.gov.my  Cetakan myEPF  Muka Surat 1
"""
# A KWSP WITHDRAWAL form (the a53 pattern) — genuine KWSP doc, WRONG kind for income proof.
WRONG_TYPE_EPF = "KWSP EPF\nPENGESAHAN PERMOHONAN PENGELUARAN\nMAKLUMAT AHLI\nUMUR 55 TAHUN\nwww.kwsp.gov.my\n"


def test_genuine_epf_scores_genuine_and_types_as_epf():
    r = score_signatures(GENUINE_EPF, doc_type='epf')
    assert r['type'] == 'epf'
    assert r['probability'] >= GENUINE_MIN


def test_wrong_type_kwsp_doc_is_not_epf():
    # A withdrawal form / tax form / STR mis-filed as an EPF statement → not_epf (TD-117 backstop).
    g = signature_genuineness(WRONG_TYPE_EPF, doc_type='epf')
    assert g['status'] == 'not_epf'
    assert g['probability'] < SUSPECT_MAX


# ── Offer letters — THREE standard issuers, scored by best fit; the heterogeneous tail
#    (universities / IPG / private) is unrecognised → deferred to the holistic check. ──
GENUINE_STPM_OFFER = """SURAT TAWARAN CETAKAN KOMPUTER
PEJABAT TIMBALAN KETUA PENGARAH PENDIDIKAN MALAYSIA
SEKTOR OPERASI SEKOLAH
KEMENTERIAN PENDIDIKAN
TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026
2.1. BIDANG : SAINS
2.2. PUSAT TINGKATAN ENAM : SMK CONTOH
2.3. TARIKH LAPOR DIRI : 08 JUN 2026
2.5. DOKUMEN DIPERLUKAN
Keputusan ini adalah muktamad berdasarkan syarat kemasukan ke tingkatan enam.
Tawaran ini terbatal serta-merta jika murid berstatus bukan warganegara Malaysia.
Surat ini adalah cetakan komputer dan tidak ditandatangani.
"""

GENUINE_MATRIC_OFFER = """KEMENTERIAN PENDIDIKAN
BAHAGIAN MATRIKULASI
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2026/2027
JURUSAN : SAINS
KOLEJ : KOLEJ MATRIKULASI CONTOH
TARIKH KEMASUKAN KE KOLEJ : 8 JUN 2026
Saudara/ Saudari perlu mendaftar pada tarikh yang ditetapkan oleh pihak kolej.
Tawaran ini terbatal serta-merta jika saudara/ saudari berstatus bukan warganegara Malaysia atau maklumat permohonan tidak benar.
PENGARAH BAHAGIAN MATRIKULASI KPM
"""

GENUINE_POLY_OFFER = """JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
KEMENTERIAN PENDIDIKAN TINGGI
SURAT TAWARAN PENGAJIAN SESI I : 2026/2027
Program : DIPLOMA PERAKAUNAN
Institusi : POLITEKNIK CONTOH
Tarikh dan Masa Daftar : 21 JUN 2026
Tawaran ini adalah MUKTAMAD dan TERBATAL sekiranya anda tidak mendaftar di institusi berkenaan pada tarikh dan masa yang ditetapkan.
Tawaran ini adalah tertakluk kepada kesahihan maklumat dalam borang permohonan dengan dokumen asal yang dikemukakan.
PENGARAH BAHAGIAN AMBILAN DAN PEMBANGUNAN PELAJAR
"""

# A cropped STPM offer — issuer anchor (Tingkatan Enam) survives, the rest is cut off.
CROPPED_STPM_OFFER = """TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026
Saudara/Saudari,
2.1. BIDANG : SAINS
2.2. PUSAT TINGKATAN ENAM
"""

# A genuine UNIVERSITY offer — a legitimate offer letter, but NOT one of the three standard
# issuers, so the signature scorer must NOT flag it; it defers to the holistic check.
UNIVERSITY_OFFER = """UNIVERSITI MALAYA
TAWARAN KEMASUKAN PROGRAM ASASI SAINS SOSIAL
Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.
Pendaftaran akan dibuat secara dalam talian.
"""


def test_genuine_stpm_offer_scores_genuine_and_types_as_stpm():
    g = signature_genuineness(GENUINE_STPM_OFFER, doc_type='offer_letter')
    assert g['type'] == 'stpm'
    assert g['status'] == 'genuine'
    assert g['probability'] >= GENUINE_MIN


def test_genuine_matric_offer_types_as_matriculation():
    g = signature_genuineness(GENUINE_MATRIC_OFFER, doc_type='offer_letter')
    assert g['type'] == 'matriculation'
    assert g['status'] == 'genuine'


def test_genuine_poly_offer_types_as_polytechnic():
    g = signature_genuineness(GENUINE_POLY_OFFER, doc_type='offer_letter')
    assert g['type'] == 'polytechnic'
    assert g['status'] == 'genuine'


def test_cropped_offer_is_suspect_never_not_offer_letter():
    # Recognised as STPM (anchor present) but incomplete → suspect (re-upload), NOT not_offer_letter.
    g = signature_genuineness(CROPPED_STPM_OFFER, doc_type='offer_letter')
    assert g['type'] == 'stpm'
    assert g['status'] == 'suspect'


def test_university_offer_is_unrecognised_and_defers_to_holistic():
    # A legitimate non-standard issuer must never be flagged by the signature scorer.
    g = signature_genuineness(UNIVERSITY_OFFER, doc_type='offer_letter')
    assert g['status'] == 'unrecognised'


def test_assess_routes_offer_letter_to_signatures_when_recognised():
    from apps.scholarship.genuineness import assess
    g = assess('offer_letter', ocr_text=GENUINE_POLY_OFFER)
    assert g['type'] == 'polytechnic' and g['status'] == 'genuine'


def test_poly_text_alone_is_genuine_and_visuals_are_bonus():
    # Text signatures clear 0.70 with NO visuals; the crest + JPPKK seal only lift confidence.
    text_only = signature_genuineness(GENUINE_POLY_OFFER, doc_type='offer_letter')
    with_visuals = signature_genuineness(GENUINE_POLY_OFFER, doc_type='offer_letter',
                                         has_crest=True, has_seal=True)
    assert text_only['status'] == 'genuine'
    assert with_visuals['probability'] > text_only['probability']


# PISMP — Institut Pendidikan Guru (IPG), KPM. The offer-specific clauses separate a genuine
# offer from a mere ANNOUNCEMENT (which carries only the identity strings).
GENUINE_PISMP_OFFER = """INSTITUT PENDIDIKAN GURU MALAYSIA
KEMENTERIAN PENDIDIKAN MALAYSIA
NAMA: TAVANISAH A/P CONTOH
NO. KAD PENGENALAN: 060328100916
Tarikh : 13 Ogos 2024
TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP) KEMENTERIAN PENDIDIKAN MALAYSIA
BIDANG PENGKHUSUSAN : BAHASA TAMIL PENDIDIKAN RENDAH
ELEKTIF : PENDIDIKAN JASMANI
ALIRAN SEKOLAH : SEKOLAH JENIS KEBANGSAAN TAMIL (SJKT)
TARIKH PENDAFTARAN : 26 OGOS 2024
TEMPAT PENGAJIAN : INSTITUT PENDIDIKAN GURU KAMPUS IPOH
Surat tawaran ini hendaklah dibaca bersama-sama Perjanjian Pendidikan Guru.
Tawaran ini akan TERBATAL dengan sendirinya jika gagal memenuhi syarat.
Penetapan bidang dan tempat pengajian adalah muktamad.
"""

# A PISMP ANNOUNCEMENT (a43 pattern): identity strings present, but NONE of the offer-specific
# clauses → recognised as PISMP but scores below genuine → suspect (not a real offer letter).
PISMP_ANNOUNCEMENT = """INSTITUT PENDIDIKAN GURU MALAYSIA
TAWARAN MENGIKUTI PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)
BIDANG PENGKHUSUSAN : BAHASA TAMIL PENDIDIKAN RENDAH
ALIRAN SEKOLAH : SJKT
Sila semak status permohonan anda di portal.
"""


def test_genuine_pismp_offer_types_as_pismp_and_genuine():
    g = signature_genuineness(GENUINE_PISMP_OFFER, doc_type='offer_letter')
    assert g['type'] == 'pismp'
    assert g['status'] == 'genuine'


def test_pismp_announcement_is_suspect_not_genuine():
    # Recognised as PISMP (identity present) but missing every offer-specific clause → suspect.
    g = signature_genuineness(PISMP_ANNOUNCEMENT, doc_type='offer_letter')
    assert g['type'] == 'pismp'
    assert g['status'] == 'suspect'
