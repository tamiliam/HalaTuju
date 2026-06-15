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
    assert band_for(r['probability']) == 'likely_genuine'


def test_genuine_cert_types_as_certificate():
    r = score_signatures(GENUINE_CERT)
    assert r['type'] == 'certificate'
    assert r['probability'] >= GENUINE_MIN


def test_typed_fake_is_suspect():
    g = signature_genuineness(TYPED_FAKE)
    assert g['status'] == 'suspect'
    assert g['probability'] < SUSPECT_MAX


def test_cropped_genuine_lands_in_review_not_suspect():
    g = signature_genuineness(CROPPED_SLIP)
    assert g['status'] == 'low_confidence'      # review, never suspect
    assert SUSPECT_MAX <= g['probability'] < GENUINE_MIN


def test_visual_signals_lift_a_cropped_doc_to_genuine():
    """Crediting the QR + crest (the two visual signatures) recovers a cropped genuine."""
    low = signature_genuineness(CROPPED_SLIP)
    high = signature_genuineness(CROPPED_SLIP, has_qr=True, has_crest=True)
    assert high['probability'] > low['probability']
    assert high['status'] in ('likely_genuine', 'low_confidence')


def test_never_raises_on_empty():
    g = signature_genuineness('')
    assert g['status'] == 'suspect' and g['probability'] == 0.0


def test_signature_genuineness_reports_evidence():
    g = signature_genuineness(GENUINE_SLIP)
    assert 'LAYAK MENDAPAT SIJIL' in g['present']
    assert isinstance(g['missing'], list)
    assert 'signatures present' in g['reason']
