"""Deterministic capture scaffold — label helpers + dispatcher (apps.scholarship.doc_parse).

Per-doc-type parsers (STR, TNB, KWSP, …) get their own real-file-validated tests as they
land; this covers the shared infrastructure they all build on."""
from django.test import SimpleTestCase

from apps.scholarship import doc_parse
from apps.scholarship.doc_parse import (find_value, has, first_nric, first_amount,
                                        parse_by_labels, register)


class TestFindValue(SimpleTestCase):
    def test_same_line_after_separator(self):
        self.assertEqual(find_value('No. Kad Pengenalan : 800817-07-5636', r'no\.?\s*kad pengenalan'),
                         '800817-07-5636')

    def test_falls_to_next_non_empty_line_when_label_alone(self):
        text = 'Nama\n\nRUSHAINDRA KUMARI A/P JAYARAM\n'
        self.assertEqual(find_value(text, r'nama'), 'RUSHAINDRA KUMARI A/P JAYARAM')

    def test_case_insensitive_and_trims(self):
        self.assertEqual(find_value('STATUS:   Berjaya  ', r'status'), 'Berjaya')

    def test_missing_label_returns_blank(self):
        self.assertEqual(find_value('nothing here', r'jumlah'), '')

    def test_first_match_wins(self):
        self.assertEqual(find_value('Nama: A\nNama: B', r'nama'), 'A')


class TestMarkersAndScalars(SimpleTestCase):
    def test_has_any_pattern(self):
        self.assertTrue(has('… Semakan Status …', r'semakan status'))
        self.assertTrue(has('MySTR portal', r'\bMySTR\b'))
        self.assertFalse(has('plain text', r'dashboard'))

    def test_first_nric_normalises_spacing_and_dashes(self):
        self.assertEqual(first_nric('No 800817 07 5636 here'), '800817-07-5636')
        self.assertEqual(first_nric('800817-07-5636'), '800817-07-5636')
        self.assertEqual(first_nric('no ic at all'), '')

    def test_first_amount_strips_commas(self):
        self.assertEqual(first_amount('Jumlah Bil Anda (RM) 1,234.50'), 'RM1234.50')
        self.assertEqual(first_amount('RM700'), 'RM700')
        self.assertEqual(first_amount('no money'), '')


class TestDispatcher(SimpleTestCase):
    def test_unregistered_doc_type_returns_none(self):
        self.assertIsNone(parse_by_labels('totally_unknown_type', 'some text'))

    def test_blank_text_returns_none(self):
        self.assertIsNone(parse_by_labels('str', '   '))

    def test_a_raising_parser_degrades_to_none(self):
        @register('_test_boom')
        def _boom(_text):
            raise ValueError('kaboom')
        try:
            self.assertIsNone(parse_by_labels('_test_boom', 'x'))
        finally:
            doc_parse._PARSERS.pop('_test_boom', None)

    def test_a_parser_returning_empty_or_nondict_is_none(self):
        @register('_test_empty')
        def _empty(_text):
            return {}
        @register('_test_str')
        def _str(_text):
            return 'not a dict'
        try:
            self.assertIsNone(parse_by_labels('_test_empty', 'x'))
            self.assertIsNone(parse_by_labels('_test_str', 'x'))
        finally:
            doc_parse._PARSERS.pop('_test_empty', None)
            doc_parse._PARSERS.pop('_test_str', None)

    def test_a_valid_parser_result_passes_through(self):
        @register('_test_ok')
        def _ok(_text):
            return {'recipient_name': 'A', 'source_type': 'letter'}
        try:
            self.assertEqual(parse_by_labels('_test_ok', 'x'),
                             {'recipient_name': 'A', 'source_type': 'letter'})
        finally:
            doc_parse._PARSERS.pop('_test_ok', None)


# ── STR parser (P1) — synthetic fixtures mirror the REAL OCR structures validated
# against live uploads (letters #29/#61, semakan #62/#51, SALINAN #23, SARA #63). Fake
# names/NRICs only — no PII in the repo (lessons.md). ───────────────────────────────────

# A Kementerian Kewangan approval LETTER: approves STR **and** SARA; the "layak STR …
# dengan jumlah RM<x>" line is the STR-specific entitlement (≠ combined ≠ SARA figure).
_LETTER = """KEMENTERIAN KEWANGAN MALAYSIA
No. Rujukan : STR-01(A)(i)
No Pengenalan : 900101015555
Tarikh : 09/01/2026
AHMAD BIN TESTABU
12 JALAN UJIAN, 50000 KUALA LUMPUR
SUMBANGAN TUNAI RAHMAH (STR) DAN SUMBANGAN ASAS RAHMAH (SARA) TAHUN 2026
2. permohonan STR dan SARA 2026 tuan/puan telah diluluskan dengan jumlah keseluruhan
kelayakan STR dan SARA sebanyak RM2,400. Tuan/Puan layak STR 2026 dengan jumlah RM1,200
setahun manakala kelayakan SARA 2026 tuan/puan sebanyak RM1,200 setahun.
Nama Penerima : AHMAD BIN TESTABU
"""

# MySTR mobile "Semakan Status": labels in one OCR column, values in another; a stray info
# icon "i" bleeds onto the status label; the keseluruhan total ≥ the amount paid so far.
_SEMAKAN = """Semakan Status
Maklumat Pemohon
Nama
No. MyKad
SITI A/P TESTAMMA
950202025656
Status Pedalaman
Status Permohonan Semasa i
Lulus
Jumlah Telah Dibayar
RM 600
Jumlah Bayaran
RM 1,200
Keseluruhan STR
"""

# A MySTR application-record COPY — STR-marked but stamped SALINAN, no approval status.
_SALINAN = """KERAJAAN MALAYSIA
SUMBANGAN TUNAI RAHMAH (STR)
SALINAN
MAKLUMAT PEMOHON
Nama :
RAJA A/L TESTAN
No. MyKad
800808085858
"""

# A SARA-only Perdana Menteri letter (the #63 shape) — no STR entitlement, no NRIC.
_SARA_ONLY = """PERDANA MENTERI MALAYSIA
SELVI A/P TESTAH
03 Januari 2026
Saya bersyukur kerana saudara/saudari adalah salah seorang yang terpilih untuk terus
menerima bantuan SARA.
ANWAR IBRAHIM
MALAYSIA MADANI
"""


class TestStrParser(SimpleTestCase):
    def test_letter_reads_str_specific_amount_not_combined_or_sara(self):
        r = parse_by_labels('str', _LETTER)
        self.assertEqual(r['source_type'], 'letter')
        self.assertEqual(r['recipient_name'], 'AHMAD BIN TESTABU')
        self.assertEqual(r['recipient_nric'], '900101-01-5555')
        self.assertEqual(r['status'], 'diluluskan')
        self.assertEqual(r['year'], '2026')
        self.assertEqual(r['amount'], 'RM1200')      # the STR line, NOT RM2,400 / the SARA RM1,200

    def test_semakan_layout_independent_name_nric_status_total(self):
        r = parse_by_labels('str', _SEMAKAN)
        self.assertEqual(r['source_type'], 'semakan_status')
        self.assertEqual(r['recipient_name'], 'SITI A/P TESTAMMA')   # read despite labels-then-values
        self.assertEqual(r['recipient_nric'], '950202-02-5656')
        self.assertEqual(r['status'], 'Lulus')        # the stray "i" was rejected → body word
        self.assertEqual(r['year'], '')               # no year on the page → current (#5)
        self.assertEqual(r['amount'], 'RM1200')       # keseluruhan total, not the RM600 paid

    def test_salinan_is_unknown_not_a_proof(self):
        r = parse_by_labels('str', _SALINAN)
        self.assertEqual(r['source_type'], 'unknown')   # application copy → gated to unconfirmed

    def test_sara_only_letter_is_unknown_the_deterministic_gate(self):
        r = parse_by_labels('str', _SARA_ONLY)
        self.assertEqual(r['source_type'], 'unknown')   # retires the #63 AI-inference mis-pass
        self.assertEqual(r['recipient_name'], 'SELVI A/P TESTAH')

    def test_non_str_document_returns_none(self):
        self.assertIsNone(parse_by_labels('str', 'PENYATA GAJI PEKERJA\nMajikan: ACME\nGaji Pokok 3000'))

    def test_str_marked_but_no_recipient_falls_to_gemini(self):
        # An STR mention with no name + no NRIC → don't trust a deterministic read.
        self.assertIsNone(parse_by_labels('str', 'Sumbangan Tunai Rahmah STR 2026 portal'))


# A TNB "Bil Elektrik Anda" — label then value on the next line; amount = Caj Semasa (the
# month's charge that + Baki Terdahulu arrears = Jumlah Bil Anda). Mirrors the real layout
# validated against 8 live bills. (Sabah=SESB / Sarawak=SEB differ → fall to Gemini.)
_TNB = """Bil Elektrik Anda
ALAMAT POS
AHMAD BIN TESTABU
12 JALAN UJIAN
TAMAN TEST
50000 KUALA LUMPUR
WP KUALA LUMPUR
TARIKH BIL
05.05.2026
TEMPOH BIL
04.04.2026 - 03.05.2026
(30 Hari)
NO. AKAUN
220000000000
TARIF
Domestik Am
BAYARAN BAGI TEMPOH
04.04.2026 - 03.05.2026
RM72.15
Jumlah Bil Anda (RM)
576.65
Baki Terdahulu (RM)
268.45
Caj Semasa (RM)
308.22
Tenaga Nasional Berhad 199001009294 (200866-W)
"""


class TestElectricityParser(SimpleTestCase):
    def test_tnb_bill_full_read(self):
        r = parse_by_labels('electricity_bill', _TNB)
        self.assertEqual(r['name'], 'AHMAD BIN TESTABU')
        self.assertEqual(r['address'], '12 JALAN UJIAN, TAMAN TEST, 50000 KUALA LUMPUR, WP KUALA LUMPUR')
        self.assertEqual(r['amount'], 'RM308.22')          # Caj Semasa, NOT Jumlah Bil (576.65)
        self.assertEqual(r['unpaid_balance'], 'RM268.45')  # Baki Terdahulu (arrears)
        self.assertEqual(r['billing_period'], '04.04.2026 - 03.05.2026')

    def test_rm_label_value_on_next_line_not_the_unit(self):
        # "Caj Semasa (RM)" then "308.22" — must read the value line, not the "(RM)" unit.
        self.assertEqual(parse_by_labels('electricity_bill', _TNB)['amount'], 'RM308.22')

    def test_non_tnb_utility_falls_to_gemini(self):
        # A Sarawak Energy / water bill etc. lacks the TNB markers → Gemini.
        self.assertIsNone(parse_by_labels('electricity_bill',
                          'SARAWAK ENERGY BERHAD\nBil Elektrik\nJumlah RM50'))
        self.assertIsNone(parse_by_labels('electricity_bill', 'SYARIKAT AIR MELAKA\nBIL AIR\nRM27'))

    def test_no_text_layer_falls_to_gemini(self):
        self.assertIsNone(parse_by_labels('electricity_bill', 'CamScanner'))


# A KWSP "Penyata Ahli": name after SULIT…, fixed labels, CARUMAN rows (latest = monthly).
_KWSP = """SULIT DAN PERSENDIRIAN

AHMAD BIN TESTABU
NO 5 JALAN TEST
40000 SHAH ALAM
Selangor
PENYATA AHLI TAHUN 2026
RINGKASAN AKAUN
No. Ahli KWSP : 12345678 Tarikh Penyata : 10/06/2026
No. Kad Pengenalan : 800101015555
No. Majikan : 001307002
JUMLAH SIMPANAN: RM150,000.50
Akaun Persaraan (Akaun 1) 140,000.00 9,000.00 0.00 0.00 149,000.00
JUMLAH (RM) 150,000.50
CARUMAN SEMASA
Jan-26 Caruman - IWS 16/01/2026 221.00 187.00 408.00
Feb-26 Caruman - IWS 20/02/2026 250.00 210.00 460.00
"""

# A Borang EC (income statement) mis-slotted into the EPF slot — none of the KWSP labels.
_BORANG_EC = """Jab Akauntan Negara Msia
Penyata Gaji Pekerja AGENSI KERAJAAN EC
PENYATA SARAAN DARIPADA PENGGAJIAN
BORANG EC INI PERLU DISEDIAKAN UNTUK DISERAHKAN KEPADA PEKERJA
A BUTIRAN PEKERJA
1. Nama Penuh Pekerja/Pesara
"""


class TestEpfParser(SimpleTestCase):
    def test_kwsp_penyata_full_read(self):
        r = parse_by_labels('epf', _KWSP)
        self.assertEqual(r['name'], 'AHMAD BIN TESTABU')
        self.assertEqual(r['nric'], '800101-01-5555')
        self.assertEqual(r['employer'], '001307002')
        self.assertEqual(r['latest_balance'], 'RM150000.50')
        self.assertEqual(r['monthly_contribution'], 'RM460.00')   # the LAST (most recent) row
        self.assertEqual(r['year'], '2026')

    def test_borang_ec_in_epf_slot_returns_none_misslot_detection(self):
        # The deterministic parser refuses a non-KWSP doc → Gemini reads it (and the
        # mis-slot is visible because no KWSP fields were captured).
        self.assertIsNone(parse_by_labels('epf', _BORANG_EC))

    def test_employer_blanks_when_label_value_adjacency_breaks(self):
        # Image OCR can put a non-numeric line after "No. Majikan" → employer must blank,
        # not capture "RINGKASAN" / ":".
        broken = _KWSP.replace('No. Majikan : 001307002', 'No. Majikan\nRINGKASAN AKAUN')
        self.assertEqual(parse_by_labels('epf', broken)['employer'], '')

    def test_non_kwsp_text_returns_none(self):
        self.assertIsNone(parse_by_labels('epf', 'just some random text with no kwsp markers'))
