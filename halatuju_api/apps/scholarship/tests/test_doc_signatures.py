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
