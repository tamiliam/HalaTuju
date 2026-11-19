"""OCR-first S6 (2026-11-19): the TNB photo lane, the relaxed EPF cell read, the lane stamp.

Synthetic text only. Both new lanes sit behind settings switches that are OFF by default; every
refusal here must stay a refusal (None / 'unknown' → the AI read, exactly as before S6).
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import doc_parse_epf
from apps.scholarship.doc_parse import parse_by_labels, rules_parser_version
from apps.scholarship.doc_parse_tnb import parse_tnb_photo

# The full TNB bill as PHOTO OCR prints it: labels on their own lines, a bare "RM" line before
# each figure, no ALAMAT POS. Summary: 268.45 + 308.22 - 0.02 = 576.65.
_PHOTO = """Bil Elektrik Anda
Tenaga Nasional Berhad
Tarikh Bil
05 Mei 2026
Tempoh Bil
04.04.2026 - 03.05.2026
No. Invois
123456789012
AHMAD BIN TESTABU
12 JALAN UJIAN
TAMAN TEST
50000 KUALA LUMPUR
WP KUALA LUMPUR
Jumlah Perlu Dibayar
RM
576.65
Tunggakan
RM
268.45
Caj Semasa
RM
308.22
Penggenapan
RM
-0.02
Jumlah Bil
RM
576.65
Sila Bayar Sebelum
Butiran Caj
Caj Semasa
308.22
"""

_ON = override_settings(OCR_FIRST_TNB_PHOTO_ENABLED=True)


class TestTnbPhotoLane(SimpleTestCase):
    @_ON
    def test_photo_layout_locks_with_the_switch_on(self):
        r = parse_by_labels('electricity_bill', _PHOTO)
        self.assertEqual(r, {'name': 'AHMAD BIN TESTABU',
                             'address': '12 JALAN UJIAN, TAMAN TEST, 50000 KUALA LUMPUR, WP KUALA LUMPUR',
                             'amount': 'RM308.22', 'unpaid_balance': 'RM268.45',
                             'billing_period': '04.04.2026 03.05.2026', 'bill_date': '05 Mei 2026'})

    def test_switch_off_keeps_the_photo_on_ai(self):
        self.assertIsNone(parse_by_labels('electricity_bill', _PHOTO))
        self.assertEqual(rules_parser_version('electricity_bill', _PHOTO), '')

    def test_the_env_var_turns_the_lane_on_when_no_setting_exists(self):
        from apps.scholarship.doc_parse_tnb import PHOTO_SWITCH, lane_on
        with mock.patch.dict('os.environ', {PHOTO_SWITCH: '1'}):
            self.assertTrue(lane_on(PHOTO_SWITCH))
        with mock.patch.dict('os.environ', {PHOTO_SWITCH: '0'}):
            self.assertFalse(lane_on(PHOTO_SWITCH))

    def _refuses(self, text):
        self.assertIsNone(parse_tnb_photo(text))

    def test_a_summary_that_does_not_reconcile_refuses(self):
        self._refuses(_PHOTO.replace('Jumlah Bil\nRM\n576.65', 'Jumlah Bil\nRM\n577.65'))

    def test_swapped_arrears_and_charge_refuse_on_the_itemised_line(self):
        swapped = _PHOTO.replace('Tunggakan\nRM\n268.45\nCaj Semasa\nRM\n308.22',
                                 'Tunggakan\nRM\n308.22\nCaj Semasa\nRM\n268.45')
        self._refuses(swapped)

    def test_a_missing_itemised_charge_refuses(self):
        self._refuses(_PHOTO.replace('Butiran Caj\nCaj Semasa\n308.22\n', ''))

    def test_two_figures_in_one_zone_refuse(self):
        self._refuses(_PHOTO.replace('Caj Semasa\nRM\n308.22', 'Caj Semasa\nRM\n308.22\n12.00'))

    def test_a_large_rounding_refuses(self):
        self._refuses(_PHOTO.replace('-0.02', '-1.02').replace('576.65', '575.65'))

    def test_sabah_and_sarawak_stay_ai(self):
        self._refuses(_PHOTO + 'Sarawak\n')
        self._refuses(_PHOTO.replace('Tenaga Nasional Berhad', 'Tenaga Nasional Berhad\nSESB'))

    def test_a_garbled_or_missing_bill_date_refuses(self):
        self._refuses(_PHOTO.replace('05 Mei 2026', '05 Mei 2O26'))
        self._refuses(_PHOTO.replace('05 Mei 2026', '05 Mei 2016'))
        self._refuses(_PHOTO.replace('Tarikh Bil\n05 Mei 2026\n', ''))

    def test_a_stray_number_in_the_address_refuses(self):
        self._refuses(_PHOTO.replace('TAMAN TEST', 'TAMAN TEST\n0123456789'))

    def test_a_name_without_a_parentage_connector_refuses(self):
        self._refuses(_PHOTO.replace('AHMAD BIN TESTABU', 'AHMAD TESTABU'))

    def test_a_name_not_after_the_invoice_number_refuses(self):
        self._refuses(_PHOTO.replace('123456789012\n', 'SILA SEMAK\n'))

    def test_an_address_not_ending_on_postcode_or_state_refuses(self):
        self._refuses(_PHOTO.replace('WP KUALA LUMPUR\nJumlah', 'TINGKAT 3\nJumlah'))

    def test_a_missing_period_refuses(self):
        # Review round 1: with no period the bill date cannot be checked, so no lock.
        self._refuses(_PHOTO.replace('04.04.2026 - 03.05.2026', 'empat April'))

    def test_a_bill_date_away_from_the_period_end_refuses(self):
        # Review round 1 (MED-1): a misread year or month would flip the bill current / stale.
        self._refuses(_PHOTO.replace('05 Mei 2026', '05 Mei 2025'))
        self._refuses(_PHOTO.replace('05 Mei 2026', '05 Dis 2026'))
        self._refuses(_PHOTO.replace('05 Mei 2026', '02 Mei 2026'))     # before the period ends
        self._refuses(_PHOTO.replace('05 Mei 2026', '04 Jun 2026'))     # 32 days after
        self._refuses(_PHOTO.replace('05 Mei 2026', '31 Feb 2026'))     # no such day

    def test_a_bill_date_up_to_31_days_after_the_period_locks(self):
        self.assertEqual(parse_tnb_photo(_PHOTO.replace('05 Mei 2026', '03 Mei 2026'))['bill_date'],
                         '03 Mei 2026')
        self.assertEqual(parse_tnb_photo(_PHOTO.replace('05 Mei 2026', '03 Jun 2026'))['bill_date'],
                         '03 Jun 2026')

    def test_a_negative_current_charge_refuses(self):
        # Review round 1 (LOW-4): 626.67 - 50.00 - 0.02 = 576.65 reconciles, but a charge is never negative.
        self._refuses(_PHOTO.replace('268.45', '626.67').replace('308.22', '-50.00'))

    def test_a_label_line_inside_the_address_refuses(self):
        # Review round 1 (LOW-5): a digit-free bill label is never part of an address.
        for label in ('No. Akaun', 'Tarikh Bil', 'Jumlah'):
            self._refuses(_PHOTO.replace('TAMAN TEST', f'TAMAN TEST\n{label}'))


class TestLaneSwitchValues(SimpleTestCase):
    """Review round 1 (LOW-1): only a real True or the text '1' / 'true' / 'yes' turns a lane on."""

    def test_setting_values(self):
        from apps.scholarship.doc_parse_tnb import PHOTO_SWITCH, lane_on
        for value, on in ((True, True), ('1', True), ('true', True), ('Yes', True), (False, False),
                          ('0', False), ('False', False), ('no', False), ('', False), (1, False)):
            with self.subTest(value=value), override_settings(**{PHOTO_SWITCH: value}):
                self.assertIs(lane_on(PHOTO_SWITCH), on)

    def test_env_text_values(self):
        from apps.scholarship.doc_parse_tnb import PHOTO_SWITCH, lane_on
        for value, on in (('TRUE', True), ('false', False), ('off', False)):
            with self.subTest(value=value), mock.patch.dict('os.environ', {PHOTO_SWITCH: value}):
                self.assertIs(lane_on(PHOTO_SWITCH), on)


class TestLaneStamp(SimpleTestCase):
    def test_existing_format_a_and_b_lanes(self):
        from apps.scholarship.tests.test_doc_parse import _TNB
        self.assertEqual(rules_parser_version('electricity_bill', _TNB), 'electricity_parse tnb_a 1.1.0')
        express = ("myTNB\nExpress Payment\n1. Verify Your Account\n220000000000\n"
                   "2, JLN UJIAN, TMN TEST, 40400,\nSHAH ALAM, Selangor.\nMY AMOUNT DUE\n12.05\n")
        self.assertEqual(rules_parser_version('electricity_bill', express), 'electricity_parse tnb_b 1.1.0')

    @_ON
    def test_photo_lane_stamp(self):
        self.assertEqual(rules_parser_version('electricity_bill', _PHOTO),
                         'electricity_parse tnb_a_photo 1.1.0')

    def test_no_stamp_for_an_unread_bill_or_another_type(self):
        self.assertEqual(rules_parser_version('electricity_bill', 'CamScanner'), '')
        self.assertEqual(rules_parser_version('str', 'anything'), '')

    def test_the_read_records_the_lane_beside_a_rules_read(self):
        from apps.scholarship.tests.test_doc_parse import _TNB
        from apps.scholarship.vision import field_extraction as fe
        doc = SimpleNamespace(doc_type='electricity_bill')
        with mock.patch.object(fe, '_read_approval', side_effect=lambda d, ex, t, f: ex):
            ex = fe._read_labelled_doc(doc, {'error': '', 'text': _TNB}, None)
        self.assertEqual(ex['parser_version'], 'electricity_parse tnb_a 1.1.0')

    def test_a_gemini_filled_mixed_read_is_not_stamped(self):
        # Review round 1 (LOW-2): the unread EPF table filled by Gemini is not a rules read.
        from apps.scholarship.vision import field_extraction as fe
        ai = {'fields': {'contribution_status': 'has', 'monthly_contribution': 'RM1.00'},
              'warnings': [], 'error': ''}
        doc = SimpleNamespace(doc_type='epf')
        with mock.patch.object(fe._v, 'extract_document_fields', return_value=ai), \
                mock.patch.object(fe, '_read_approval', side_effect=lambda d, ex, t, f: ex):
            ex = fe._read_labelled_doc(doc, {'error': '', 'text': _EPF}, None)
        self.assertEqual(ex['capture'], 'mixed')
        self.assertNotIn('parser_version', ex)


# A KWSP Penyata Ahli whose CARUMAN SEMASA cells OCR joined (date + figures on one line, two
# month labels on one line) and split (one row's figures over two lines). Grand total 868.00.
_EPF_HEAD = """SULIT DAN PERSENDIRIAN
AHMAD BIN TESTABU
NO 5 JALAN TEST
40000 SHAH ALAM
PENYATA AHLI TAHUN 2026
No. Ahli KWSP : 12345678
JUMLAH SIMPANAN: RM1,000.00
"""
_EPF_TABLE = """CARUMAN SEMASA
Jan-26 Feb-26
Caruman IWS
16/01/2026 221.00 187.00 408.00
20/02/2026 250.00
210.00 460.00
868.00
PENGELUARAN
"""
_EPF = _EPF_HEAD + _EPF_TABLE
_EPF_ON = override_settings(OCR_FIRST_EPF_RELAXED_ENABLED=True)


class TestEpfRelaxedRows(SimpleTestCase):
    def test_switch_off_keeps_the_old_unknown(self):
        r = parse_by_labels('epf', _EPF)
        self.assertEqual(r['contribution_status'], 'unknown')
        self.assertEqual(rules_parser_version('epf', _EPF), 'epf_parse kwsp_penyata 1.1.0')

    @_EPF_ON
    def test_joined_and_split_cells_reconcile_and_lock(self):
        r = parse_by_labels('epf', _EPF)
        self.assertEqual(r['contribution_status'], 'has')
        self.assertEqual(r['monthly_contribution'], 'RM460.00')        # the LATEST month
        self.assertEqual(r['avg_monthly_contribution'], 'RM434.00')
        self.assertEqual(r['months_counted'], '2')
        self.assertEqual(r['employer_contribution_total'], 'RM471.00')
        self.assertEqual(r['employee_contribution_total'], 'RM397.00')
        self.assertEqual(rules_parser_version('epf', _EPF), 'epf_parse kwsp_penyata_relaxed 1.1.0')

    @_EPF_ON
    def test_a_header_without_its_space_is_found(self):
        r = parse_by_labels('epf', _EPF.replace('CARUMAN SEMASA', 'CARUMANSEMASA'))
        self.assertEqual(r['monthly_contribution'], 'RM460.00')

    def _refuses(self, table):
        with _EPF_ON:
            self.assertEqual(doc_parse_epf._caruman_rows(_EPF_HEAD + table), [])
            self.assertEqual(parse_by_labels('epf', _EPF_HEAD + table)['contribution_status'], 'unknown')

    def test_shares_that_do_not_make_the_total_refuse(self):
        self._refuses(_EPF_TABLE.replace('187.00 408.00', '188.00 408.00'))

    def test_month_labels_not_matching_the_rows_refuse(self):
        self._refuses(_EPF_TABLE.replace('Jan-26 Feb-26', 'Jan-26'))

    def test_dates_out_of_order_refuse(self):
        self._refuses(_EPF_TABLE.replace('16/01/2026', '16/03/2026'))

    def test_a_wrong_grand_total_refuses(self):
        self._refuses(_EPF_TABLE.replace('868.00', '869.00'))

    def test_a_row_short_of_figures_refuses(self):
        self._refuses(_EPF_TABLE.replace('210.00 460.00\n', '460.00\n'))

    def test_two_loose_figures_refuse(self):
        self._refuses(_EPF_TABLE.replace('868.00', '868.00\n5.00'))

    def test_an_unreadable_figure_refuses_and_never_slides_the_total(self):
        # Review round 1 (MED-2): skipping "25O.00" slid the grand total into the last row.
        self._refuses("CARUMAN SEMASA\nJan-26 Feb-26\n16/01/2026 113.00 97.00 210.00\n"
                      "20/02/2026 25O.00 210.00 460.00\n670.00\nPENGELUARAN\n")
        self._refuses(_EPF_TABLE.replace('868.00', '868.0O'))

    def test_swapped_shares_refuse(self):
        # Review round 1 (LOW-3): the employer share is never smaller than the member share.
        self._refuses(_EPF_TABLE.replace('221.00 187.00', '187.00 221.00'))

    def test_an_all_zero_table_refuses_in_the_relaxed_read(self):
        # Review round 1 (LOW-6): 0 + 0 = 0 proves nothing, so the relaxed read never makes 'zero'.
        table = ("CARUMAN SEMASA\nJan-26 Feb-26\n16/01/2026 0.00 0.00 0.00\n20/02/2026 0.00\n0.00 0.00\n"
                 "PENGELUARAN\n")
        self._refuses(table)
        self.assertEqual(parse_by_labels('epf', _EPF_HEAD + table)['contribution_status'], 'unknown')

    def test_the_strict_cell_read_still_answers_zero_and_refuses_a_swap(self):
        zero = "CARUMAN SEMASA\nJan-26\n16/01/2026\n0.00\n0.00\n0.00\nPENGELUARAN\n"
        self.assertEqual(parse_by_labels('epf', _EPF_HEAD + zero)['contribution_status'], 'zero')
        good = "CARUMAN SEMASA\nJan-26\n16/01/2026\n221.00\n187.00\n408.00\nPENGELUARAN\n"
        self.assertEqual(parse_by_labels('epf', _EPF_HEAD + good)['contribution_status'], 'has')
        swapped = good.replace('221.00\n187.00', '187.00\n221.00')
        self.assertEqual(doc_parse_epf._strict_rows(_EPF_HEAD + swapped), [])
        inline = "CARUMAN SEMASA\nJan-26 16/01/2026 187.00 221.00 408.00\nPENGELUARAN\n"
        self.assertEqual(doc_parse_epf._strict_rows(_EPF_HEAD + inline), [])

    @_EPF_ON
    def test_a_strict_read_is_never_replaced(self):
        from apps.scholarship.tests.test_doc_parse import _KWSP
        self.assertEqual(doc_parse_epf._caruman_rows(_KWSP), doc_parse_epf._strict_rows(_KWSP))
        self.assertEqual(rules_parser_version('epf', _KWSP), 'epf_parse kwsp_penyata 1.1.0')
