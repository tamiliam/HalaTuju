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

# A MySTR Semakan in the mobile LABELS-then-VALUES OCR order (#104): "Status Permohonan Semasa" is
# followed by the NEXT LABEL ("Fasa Bayaran"), not its value — the value "Lulus" sits in the values
# column further down. The status read must NOT leak "Fasa Bayaran"; it body-scans to "Lulus".
_SEMAKAN_COLUMNS = """Semakan Status
Maklumat Pemohon
Nama
No. MyKad
Status Pedalaman
Status Permohonan Semasa
Fasa Bayaran
YOGESWARY A/P TESTAMMA
880311085266
Tidak
Lulus
Fasa 1 Fasa 2 Fasa 3 Fasa 4
150 200 0 0
Jumlah Telah Dibayar
RM 350
Jumlah Bayaran Keseluruhan STR
RM 700
"""

# A MySTR app DASHBOARD (the #23 shape): heading "Status Permohonan STR" with the value "Lulus"
# on the next line; the Jumlah tiles are surface signatures, not decision variables. No date.
_DASHBOARD = """Dashboard
NALINI A/P TESTAMMA
800723145840
Profil
Status Permohonan STR
Lulus
Jumlah Telah Dibayar
RM 850.00
Jumlah Bayaran Keseluruhan STR
RM 1,200.00
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

    def test_semakan_labels_then_values_reads_lulus_not_fasa_bayaran(self):
        # #104: the label-anchored read grabs the next LABEL ("Fasa Bayaran"); the parser rejects a
        # non-status word and body-scans to the actual status "Lulus" (else it read 'unreadable' → 🟡).
        r = parse_by_labels('str', _SEMAKAN_COLUMNS)
        self.assertEqual(r['source_type'], 'semakan_status')
        self.assertEqual(r['status'], 'Lulus')
        self.assertEqual(r['recipient_name'], 'YOGESWARY A/P TESTAMMA')
        self.assertEqual(r['recipient_nric'], '880311-08-5266')

    def test_dashboard_classified_and_status_reads_lulus_not_str(self):
        # #23: the dashboard heading "Status Permohonan STR" must NOT (a) mis-tag the surface as
        # semakan_status, nor (b) leak the trailing "STR" as the status. Reads dashboard + Lulus.
        r = parse_by_labels('str', _DASHBOARD)
        self.assertEqual(r['source_type'], 'dashboard')
        self.assertEqual(r['recipient_name'], 'NALINI A/P TESTAMMA')
        self.assertEqual(r['recipient_nric'], '800723-14-5840')
        self.assertEqual(r['status'], 'Lulus')          # the VALUE, not the "STR" heading leak
        self.assertEqual(r['amount'], '')               # dashboard amounts are signatures, not variables

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

    def test_mytnb_express_payment_screenshot(self):
        # Students often submit the myTNB "Express Payment / Verify Your Account" screen
        # instead of the full bill — account + address + a single AMOUNT DUE, no name/arrears.
        txt = ("myTNB\nExpress Payment\nPay your electricity bill conveniently here\n"
               "1. Verify Your Account\n220716208404\n"
               "2, JLN JASA TIGA 25/27C, TMN SRI MUDA, 40400,\nSHAH ALAM, Selangor.\n"
               "MY AMOUNT DUE\n212.05\nDue Date 14-May-2026\n"
               "I AM PAYING (RM)\n0.00\nNote: You may pay up to RM 250.00")
        r = parse_by_labels('electricity_bill', txt)
        self.assertEqual(r['amount'], 'RM212.05')         # MY AMOUNT DUE, not the "0.00" paying field
        self.assertEqual(r['name'], '')                   # not shown on the Express Payment page
        self.assertEqual(r['unpaid_balance'], '')
        self.assertEqual(r['address'],
                         '2, JLN JASA TIGA 25/27C, TMN SRI MUDA, 40400, SHAH ALAM, Selangor.')


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
        # NEW: the AVERAGE over both months (408 + 460) / 2 = 434, with the count + status,
        # plus the statement date + a best-effort address block.
        self.assertEqual(r['avg_monthly_contribution'], 'RM434.00')
        self.assertEqual(r['months_counted'], '2')
        self.assertEqual(r['contribution_status'], 'has')
        self.assertEqual(r['statement_date'], '10/06/2026')
        self.assertIn('40000 SHAH ALAM', r['address'])
        self.assertEqual(r['year'], '2026')

    def test_zero_contribution_is_a_signal_not_unreadable(self):
        # "Tiada Transaksi" → a GENUINE zero (no formal salary), distinct from an unreadable table.
        zero = _KWSP.replace(
            'Jan-26 Caruman - IWS 16/01/2026 221.00 187.00 408.00\n'
            'Feb-26 Caruman - IWS 20/02/2026 250.00 210.00 460.00\n',
            'Tiada Transaksi\n')
        r = parse_by_labels('epf', zero)
        self.assertEqual(r['contribution_status'], 'zero')
        self.assertEqual(r['avg_monthly_contribution'], 'RM0.00')

    def test_unreadable_caruman_is_unknown_not_zero(self):
        # The Penyata is recognised but the CARUMAN table didn't parse → 'unknown', NOT 'zero'
        # (#72: a parse miss must never be read as "no income").
        no_rows = _KWSP.replace(
            'Jan-26 Caruman - IWS 16/01/2026 221.00 187.00 408.00\n'
            'Feb-26 Caruman - IWS 20/02/2026 250.00 210.00 460.00\n', '')
        r = parse_by_labels('epf', no_rows)
        self.assertEqual(r['contribution_status'], 'unknown')
        self.assertEqual(r['avg_monthly_contribution'], '')

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


# A JPN LM15 BC as Vision reads it — sections interleaved, English "Name" labels present,
# the child's IC under "No. Daftar" (NOT captured as a parent), parents under "No. Kad
# Pengenalan" (father then mother), one NRIC spaced as JPN OCR renders it.
_BC = """JPN. LM15
KERAJAAN MALAYSIA
SIJIL KELAHIRAN
BIRTH CERTIFICATE
080808-10-1234
No. Daftar
Register No
CA99999
Nama Penuh TESTCHILD A/P TESTFATHER
Full Name
KANAK-KANAK / CHILD
Tarikh dan Waktu Kelahiran 08 OGOS 2008
Nama TESTFATHER A/L TESTGRANDF
Name
No. Kad Pengenalan 750101-10-1111
BAPA/FATHER
IBU / MOTHER
Nama
Name
TESTMOTHER A/P TESTGRANDM
No. Kad Pengenalan 800202 - 14 - 2222
"""

# LM05 with a MONONYM child (the #55 / JAYASHREE shape).
_BC_MONONYM = """JPN. LM05
SIJIL KELAHIRAN
Nama
TESTKID
KANAK-KANAK
Nama
TESTDAD A/L GRANDPA
No. Kad Pengenalan
750101-10-1111
Nama
TESTMUM A/P GRANDMA
No. Kad Pengenalan
800202-14-2222
"""


class TestBcParser(SimpleTestCase):
    def test_lm15_child_and_both_parents_with_spaced_nric(self):
        r = parse_by_labels('birth_certificate', _BC)
        self.assertEqual(r['bc_child_name'], 'TESTCHILD A/P TESTFATHER')   # not the "Name" label
        self.assertEqual(r['bc_child_nric'], '')                          # No.Daftar IC not a parent
        self.assertEqual(r['bc_father_name'], 'TESTFATHER A/L TESTGRANDF')
        self.assertEqual(r['bc_father_nric'], '750101-10-1111')
        self.assertEqual(r['bc_mother_name'], 'TESTMOTHER A/P TESTGRANDM')
        self.assertEqual(r['bc_mother_nric'], '800202-14-2222')           # normalised from spaced

    def test_lm05_mononym_child(self):
        r = parse_by_labels('birth_certificate', _BC_MONONYM)
        self.assertEqual(r['bc_child_name'], 'TESTKID')                   # mononym, not a parent
        self.assertEqual(r['bc_father_name'], 'TESTDAD A/L GRANDPA')
        self.assertEqual(r['bc_father_nric'], '750101-10-1111')
        self.assertEqual(r['bc_mother_name'], 'TESTMUM A/P GRANDMA')

    def test_letterhead_not_taken_as_child(self):
        # app #10: OCR put "KERAJAAN MALAYSIA" right where the child name is scanned (after a
        # bare 'Nama' label) — the parser must skip the letterhead and find the real child.
        bc = """SIJIL KELAHIRAN
BIRTH CERTIFICATE
Nama
KERAJAAN MALAYSIA
TAANUSIYA A/P TESTFATHER
KANAK-KANAK
Nama
TESTDAD A/L GRANDPA
No. Kad Pengenalan 750101-10-1111
Nama
TESTMUM A/P GRANDMA
No. Kad Pengenalan 800202-14-2222
"""
        r = parse_by_labels('birth_certificate', bc)
        self.assertEqual(r['bc_child_name'], 'TAANUSIYA A/P TESTFATHER')   # not "KERAJAAN MALAYSIA"

    def test_only_letterhead_no_real_child_falls_to_gemini(self):
        # If the only "name-like" line is a letterhead, defer to Gemini rather than return it.
        bc = """SIJIL KELAHIRAN
Nama
KERAJAAN MALAYSIA
No. Kad Pengenalan 750101-10-1111
No. Kad Pengenalan 800202-14-2222
"""
        self.assertIsNone(parse_by_labels('birth_certificate', bc))

    def test_misslotted_ic_in_bc_slot_returns_none(self):
        # A MyKad uploaded into the BC slot (the "mother ic.png" case) → not a BC → Gemini.
        self.assertIsNone(parse_by_labels('birth_certificate',
                          'KAD PENGENALAN\nMYKAD\nNAMA SESEORANG BIN ALI\n800101-10-1234'))

    def test_partial_bc_one_parent_falls_to_gemini(self):
        partial = """SIJIL KELAHIRAN
BIRTH CERTIFICATE
Nama Penuh ANAK A/P BAPA
Nama IBU A/P DATUK
No. Kad Pengenalan 800202-14-2222
"""
        self.assertIsNone(parse_by_labels('birth_certificate', partial))



# Water bills — shared Malay labels (Bil Semasa = current, Baki Terdahulu / Tunggakan = arrears).
_WATER_AIRSGR = """INVOIS
BIL AIR
KANDASAMY A/L TESTSAMY
NO 2 JLN 25/27C TMN SRI MUDA
40400 SHAH ALAM
Wilayah
Tarikh
: 12/05/2026
RINGKASAN BIL
Baki Terdahulu RM 39.85
Bayaran Sehingga Kini (Bayaran Terakhir 08/04/2026)
Bil Semasa (Bayar Sebelum 15/06/2026) RM 13.00
Jumlah Perlu Dibayar RM 52.85
No. Akaun :3482012000
"""

# a80-style OCR interleaving: the header label/value pairs get shuffled, so the "Tarikh" date sits a
# line or two below the label (with the Wilayah value spliced between).
_WATER_INTERLEAVED = """INVOIS
BIL AIR
LETCHUMY A/P TESTAMMAL
41200 KLANG SELANGOR
Tarikh
: Hulu Selangor
: 26/05/2026
Baki Terdahulu RM 20.00
Bil Semasa (Bayar Sebelum 25/06/2026) RM 30.00
Jumlah Perlu Dibayar RM 50.00
No. Akaun :8659871000
"""

_WATER_MASKED = """INVOIS
BIL AIR
L*****G
42200 KAPAR SELANGOR
Baki Terdahulu RM 25.70
Bil Semasa (Bayar Sebelum 11/06/2026) RM 25.95
Jumlah Perlu Dibayar RM 51.65
No. Akaun :6400040000
"""


class TestWaterParser(SimpleTestCase):
    def test_air_selangor_amount_and_arrears(self):
        r = parse_by_labels('water_bill', _WATER_AIRSGR)
        self.assertEqual(r['name'], 'KANDASAMY A/L TESTSAMY')
        self.assertEqual(r['amount'], 'RM13.00')          # Bil Semasa (after the inline date clause)
        self.assertEqual(r['unpaid_balance'], 'RM39.85')  # Baki Terdahulu
        # The bill is dated from the "Tarikh" header (so recency works) — NOT the due date
        # (15/06/2026) or the last-payment date (08/04/2026).
        self.assertEqual(r['bill_date'], '12/05/2026')
        # #117 fix: the address is now read (postcode-anchored: street line + postcode line), never
        # the hardcoded '' that made _bill_needs_upload re-ask forever.
        self.assertEqual(r['address'], 'NO 2 JLN 25/27C TMN SRI MUDA 40400 SHAH ALAM')

    def test_no_readable_address_bails_to_gemini(self):
        # THE #117 load-bearing rule: a recognised water bill whose address can't be read must
        # return None (→ Gemini), never a dict with a blank address (which looped #36/#66).
        no_addr = ("BIL AIR\nSOME HOLDER\nBaki Terdahulu RM 5.00\n"
                   "Bil Semasa RM 20.00\nJumlah Perlu Dibayar RM 25.00\nNo. Akaun :1\n")
        self.assertIsNone(parse_by_labels('water_bill', no_addr))

    def test_bill_date_survives_ocr_interleaving(self):
        # a80-style: the "Tarikh" date sits two lines below the label (Wilayah value spliced in).
        r = parse_by_labels('water_bill', _WATER_INTERLEAVED)
        self.assertEqual(r['bill_date'], '26/05/2026')    # not the due date 25/06/2026

    def test_masked_name_still_reads_amounts(self):
        r = parse_by_labels('water_bill', _WATER_MASKED)
        self.assertEqual(r['name'], '')                   # company masked it → soft, fine
        self.assertEqual(r['amount'], 'RM25.95')
        self.assertEqual(r['unpaid_balance'], 'RM25.70')
        # No "Tarikh" header (only a "Bayar Sebelum" due date) → bill_date empty, NOT the due date.
        self.assertEqual(r['bill_date'], '')

    def test_tunggakan_arrears_variant(self):
        txt = ("BIL AIR\nTESTNAME A/P RAJU\n8 LORONG TEST\n41000 KLANG\n"
               "Tunggakan RM 10.00\nBil Semasa RM 27.22\nNo. Akaun 123\n")
        r = parse_by_labels('water_bill', txt)
        self.assertEqual(r['amount'], 'RM27.22')
        self.assertEqual(r['unpaid_balance'], 'RM10.00')  # via the Tunggakan alternate
        self.assertEqual(r['address'], '8 LORONG TEST 41000 KLANG')

    def test_non_water_or_unrecognised_defers(self):
        self.assertIsNone(parse_by_labels('water_bill', 'CamScanner'))
        self.assertIsNone(parse_by_labels('water_bill', 'SYARIKAT XYZ\nsome bill\nRM50'))
