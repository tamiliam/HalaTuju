"""TD-411 (2026-10-28) — a PDF text layer that is only a scanner app's stamp is no layer; the KWSP app
balance screen is an EPF proof (at most suspect).

Doc 3281, a real KWSP Penyata Ahli scanned with CamScanner, had the 46-character layer "CamScanner" × 4,
so it passed the old 25-character bar, was "read" as that word, never went to Vision, and every scorer
saw nothing. Doc 1395, a real "Semakan Baki Simpanan" app screenshot, matched three generic Penyata
probes (p=0.15) and read `not_epf`. Synthetic text only — no real document, no Vision / Gemini call.
"""
import importlib.util
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import vision
from apps.scholarship.genuineness.epf_app_doc import epf_app_scores, score_app_screen, screen_at_most_suspect
from apps.scholarship.genuineness.results_doc import (EPF_SIGNATURES, MODEL_VERSION, _norm_fold_upper_alnum,
                                                      _score_list, misfiled_as, signature_genuineness)
from apps.scholarship.pdf_pages import MIN_TEXT_LAYER_CHARS, usable_text_layer
from apps.scholarship.tests.test_doc_signatures import GENUINE_EPF, GENUINE_PAYSLIP, WRONG_TYPE_EPF

CAMSCANNER_ONLY = 'CamScanner\n\nCamScanner\n\nCamScanner\n\nCamScanner'      # doc 3281's layer: 46 chars
REAL_LAYER = ('KUMPULAN WANG SIMPANAN PEKERJA\nPENYATA AHLI TAHUN 2026\nNo. Ahli KWSP : 90000017\n'
              'JUMLAH SIMPANAN: RM12,345.60\nPenyata ini adalah cetakan komputer.')

# A KWSP app "Semakan Baki Simpanan" screen as Vision reads it (doc 1395's shape; invented figures).
EPF_APP_SCREEN = """Semakan Baki Simpanan
KWSP EPF
Baki Simpanan 2026
RM 8,512.40
Bulan Caruman | Transaksi | Tarikh | Caruman Majikan(RM) | Caruman Ahli(RM) | Jumlah(RM)
Jan-26 Caruman - IWS 16/01/2026 221.00 187.00 408.00
Feb-26 Caruman - IWS 20/02/2026 221.00 187.00 408.00
Mac-26 Caruman - IWS 20/03/2026 221.00 187.00 408.00
Kembali
Dapatkan Penyata
"""
# A printed Penyata Ahli in the shape Vision reads one (an eval snapshot's layout; invented person + figures).
PRINTED_PENYATA = """KWSP
EPF
SULIT DAN PERSENDIRIAN
MEENA A/P TESTRAJ
NO 1 JALAN CONTOH 2/3
TAMAN CONTOH
68100 BATU CAVES
Selangor
PENYATA AHLI TAHUN 2026
Tarikh Penyata
: 31/05/2026
No. Ahli KWSP
90000017
No. Kad Pengenalan
No. Majikan
: 850505105050
: 000000000
JUMLAH SIMPANAN: RM12,345.60
RINGKASAN AKAUN
Jenis Akaun
Akaun Persaraan (Akaun 1)
Akaun Sejahtera (Akaun 2)
Akaun Fleksibel (Akaun 3)
Baki Pembuka
JUMLAH (RM)
CARUMAN SEMASA
Bulan
Transaksi
Caruman
Jan-26
Caruman IWS
Feb-26
Caruman - IWS
JUMLAH (RM)
Caruman Majikan
Tarikh
Caruman Ahli
Jumlah
16/01/2026
221.00
187.00
408.00
Penyata ini adalah cetakan komputer dan tidak memerlukan tandatangan.
Menara KWSP No 1, Persiaran Kwasa Utama, Seksyen U4, 40150 Shah Alam, Selangor
Tel: 03-89226000/www.kwsp.gov.my
Cetakan myEPF
Muka Surat 1
"""
# A payslip with its EPF deduction lines — must still read not_epf in the EPF slot.
PAYSLIP_WITH_EPF = """PENYATA GAJI BULANAN OKTOBER 2026
SYARIKAT CONTOH SDN BHD
NAMA : RAVI A/L CONTOH   NO. PEKERJA : 1234
PENDAPATAN  Gaji Pokok 2,400.00  Elaun 150.00
POTONGAN  KWSP (EPF) Pekerja 281.00  PERKESO 12.25  EIS 4.90
CARUMAN MAJIKAN  KWSP 332.00  PERKESO 42.95
No. Majikan KWSP 012345678
GAJI BERSIH 2,251.85
"""


class UsableTextLayerTests(SimpleTestCase):

    def test_camscanner_watermark_only_layer_is_rejected(self):
        self.assertEqual(len(CAMSCANNER_ONLY), 46)
        self.assertGreaterEqual(len(CAMSCANNER_ONLY), MIN_TEXT_LAYER_CHARS)   # the old bar let it through
        self.assertEqual(usable_text_layer(CAMSCANNER_ONLY), '')

    def test_scanned_with_lines_are_rejected(self):
        for stamp in ('Scanned with CamScanner\nScanned with CamScanner',
                      'Scanned by CamScanner\n' * 3, 'Scanned with Adobe Scan\nScanned with Adobe Scan',
                      'Microsoft Lens\nOffice Lens\nGenius Scan\nTapScanner',
                      '— Scanned with CamScanner —\n[CamScanner]\nCamScanner | CamScanner'):
            with self.subTest(stamp=stamp):
                self.assertEqual(usable_text_layer(stamp), '')

    def test_cid_dominated_layer_is_rejected(self):
        self.assertEqual(usable_text_layer('(cid:12)(cid:45)(cid:7) (cid:88)(cid:3)(cid:91) KWSP (cid:5)(cid:6)' * 3), '')

    def test_symbol_garble_and_letter_spaced_layers_are_rejected(self):
        self.assertEqual(usable_text_layer('~~~ ### @@@ ||| %%% ^^^ &&& *** ((( ))) +++ === ;;;'), '')
        self.assertEqual(usable_text_layer('K W S P P E N Y A T A A H L I T A H U N'), '')

    def test_real_digital_text_is_kept_unchanged(self):
        self.assertEqual(usable_text_layer(REAL_LAYER), REAL_LAYER)
        self.assertEqual(usable_text_layer(GENUINE_EPF.strip()), GENUINE_EPF.strip())

    def test_a_garbled_but_partly_real_layer_keeps_every_byte(self):
        # Control characters (a half-garbled STPM layer read today by the STPM parser) are not split on.
        layer = 'MAJLIS PEPERIKSAAN MALAYSIA\nSIJIL TINGGI PERSEKOLAHAN\x1c\x1e\x02 PNGK 3.58'
        self.assertEqual(usable_text_layer(layer), layer)

    def test_a_real_layer_with_a_camscanner_footer_is_kept_without_the_footer(self):
        out = usable_text_layer(REAL_LAYER + '\nScanned with CamScanner')
        self.assertEqual(out, REAL_LAYER)
        out = usable_text_layer('CamScanner\n' + REAL_LAYER)
        self.assertEqual(out, REAL_LAYER)

    def test_too_short_is_still_rejected_and_the_threshold_is_production_s(self):
        self.assertEqual(usable_text_layer('x' * 24), '')
        self.assertEqual(usable_text_layer('x' * 25), 'x' * 25)
        self.assertEqual(vision._MIN_PDF_TEXT, MIN_TEXT_LAYER_CHARS)

    def test_a_stamp_word_inside_a_content_line_is_kept_whole(self):
        text = 'Simple Scan Enterprise Sdn Bhd\nNo. 12, Jalan Contoh, 40000 Shah Alam\nPENYATA GAJI OKTOBER 2026'
        self.assertEqual(usable_text_layer(text), text)
        self.assertEqual(usable_text_layer(text + '\nCamScanner'), text)     # only the stamp-only line goes

    def test_scanned_by_a_person_is_not_a_stamp(self):
        text = 'Surat Pengesahan Pendapatan\nScanned by Pegawai Kewangan\nKampung Contoh, 09000 Kulim, Kedah'
        self.assertEqual(usable_text_layer(text), text)
        self.assertEqual(usable_text_layer('Scanned by Pegawai Kewangan'), 'Scanned by Pegawai Kewangan')

    def test_the_word_scanner_in_real_text_is_not_a_stamp(self):
        text = 'Jabatan Pengimbas: scanner operator ADAM BIN SAMPEL, Seksyen 7, 40000 Shah Alam'
        self.assertEqual(usable_text_layer(text), text)


class VisionCallSitesFallThroughTests(SimpleTestCase):
    """Both production readers of a PDF's layer send an unusable layer to Vision (the page image)."""

    @patch('apps.scholarship.vision._pdf_first_page_png', return_value=b'FAKEPNG')
    @patch('apps.scholarship.vision._pdf_text_layer', return_value=CAMSCANNER_ONLY)
    @patch('apps.scholarship.vision._vision_document_text', return_value={'text': 'PENYATA AHLI', 'error': None})
    def test_extract_text_sends_a_watermark_only_pdf_to_vision(self, seam, _t, _r):
        out = vision.extract_text(b'%PDF- camscanner', 'application/pdf')
        seam.assert_called_once_with(b'FAKEPNG')
        self.assertEqual(out['text'], 'PENYATA AHLI')

    @patch('apps.scholarship.vision._pdf_text_layer', return_value=REAL_LAYER)
    @patch('apps.scholarship.vision._vision_document_text')
    def test_extract_text_keeps_a_real_layer(self, seam, _t):
        self.assertEqual(vision.extract_text(b'%PDF- digital', 'application/pdf')['text'], REAL_LAYER)
        seam.assert_not_called()

    def _full(self, layer):
        doc = SimpleNamespace(storage_path='test/epf/1.pdf', content_type='application/pdf', application=None)
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'%PDF-1.4 bytes'), \
             patch('apps.scholarship.vision._pdf_text_layer', return_value=layer), \
             patch('apps.scholarship.vision._vision_words',
                   return_value={'text': 'VISION READ', 'words': [], 'error': None}) as seam:
            return vision.ocr_document_full(doc), seam

    def test_ocr_document_full_sends_a_watermark_only_pdf_to_vision(self):
        out, seam = self._full(CAMSCANNER_ONLY)
        seam.assert_called_once()
        self.assertEqual(out['text'], 'VISION READ')
        self.assertEqual(out['words'], [])

    def test_ocr_document_full_keeps_a_real_layer(self):
        out, seam = self._full(REAL_LAYER + '\nScanned with CamScanner')
        seam.assert_not_called()
        self.assertEqual(out['text'], REAL_LAYER)
        self.assertIsNone(out['words'])


class CaptureMirrorsProductionTests(SimpleTestCase):
    def test_the_eval_capture_applies_the_same_rule(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'eval', 'capture_ocr.py')
        spec = importlib.util.spec_from_file_location('eval_capture_ocr_td411', path)
        cap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cap)
        self.assertIs(cap.usable_text_layer, usable_text_layer)
        self.assertEqual(cap.choose_path(True, CAMSCANNER_ONLY), 'vision')
        self.assertEqual(cap.choose_path(True, REAL_LAYER), 'text_layer')


class EpfAppScreenTests(SimpleTestCase):

    def test_the_kwsp_app_balance_screen_reads_suspect(self):
        g = signature_genuineness(EPF_APP_SCREEN, doc_type='epf')
        self.assertEqual(g['status'], 'suspect')
        self.assertEqual(g['type'], 'epf_app')
        self.assertIn('app screenshot', g['reason'])
        self.assertEqual(g['model_version'], MODEL_VERSION)

    def test_before_1_17_it_read_not_epf(self):
        # The Penyata list alone (the pre-1.17.0 model) puts the screen well under the suspect floor.
        p = _score_list(EPF_SIGNATURES, _norm_fold_upper_alnum(EPF_APP_SCREEN), False, False)['probability']
        self.assertLess(p, 0.35)

    def test_a_full_app_screen_clears_the_genuine_band_on_its_list_and_is_capped_to_suspect(self):
        tn = _norm_fold_upper_alnum(EPF_APP_SCREEN)
        self.assertGreaterEqual(score_app_screen(tn)['probability'], 0.70)
        g = signature_genuineness(EPF_APP_SCREEN, doc_type='epf')
        self.assertEqual((g['type'], g['status']), ('epf_app', 'suspect'))
        self.assertGreaterEqual(g['probability'], 0.70)

    def test_an_anchored_partial_screen_is_suspect(self):
        part = 'Semakan Baki Simpanan\nKWSP\nBaki Simpanan 2026 RM 100\nBulan Caruman Caruman Majikan Caruman Ahli'
        self.assertEqual(signature_genuineness(part, doc_type='epf')['status'], 'suspect')

    def test_without_an_anchor_the_app_list_does_not_compete(self):
        table = ('KWSP\nBulan Caruman Transaksi Caruman Majikan Caruman Ahli\nCaruman - IWS\nKembali\n'
                 'Baki Simpanan RM 100')
        self.assertEqual(epf_app_scores(_norm_fold_upper_alnum(table)), {})
        g = signature_genuineness(table, doc_type='epf')
        self.assertEqual((g['type'], g['status']), ('epf', 'not_epf'))

    def test_a_bank_or_tabung_haji_balance_stays_not_epf(self):
        text = ('LEMBAGA TABUNG HAJI\nPenyata Akaun Simpanan\nBaki Simpanan RM 3,210.00\n'
                'Tarikh Transaksi Keterangan Jumlah\nSimpanan Tunai 100.00\nKembali')
        self.assertEqual(signature_genuineness(text, doc_type='epf')['status'], 'not_epf')

    def test_kembali_is_a_whole_word_probe(self):
        tn = _norm_fold_upper_alnum('Semakan Baki Simpanan. Wang akan dikembalikan; pengembalian caruman')
        self.assertNotIn('Kembali', score_app_screen(tn)['present'])
        self.assertIn('Kembali', score_app_screen(_norm_fold_upper_alnum('Kembali'))['present'])

    def test_the_app_family_is_never_genuine(self):
        self.assertEqual(screen_at_most_suspect('epf_app', 'genuine', 'r'), ('suspect', 'an app screenshot, not the printed statement — r'))
        self.assertEqual(screen_at_most_suspect('epf', 'genuine', 'r'), ('genuine', 'r'))
        self.assertEqual(screen_at_most_suspect('epf_app', 'not_epf', 'r'), ('not_epf', 'r'))

    def test_a_payslip_with_epf_deductions_still_reads_not_epf(self):
        for slip in (PAYSLIP_WITH_EPF, GENUINE_PAYSLIP):
            with self.subTest(slip=slip[:20]):
                g = signature_genuineness(slip, doc_type='epf')
                self.assertEqual(g['status'], 'not_epf')
                self.assertLess(g['probability'], 0.35)

    def test_wrong_type_kwsp_forms_still_read_not_epf(self):
        self.assertEqual(signature_genuineness(WRONG_TYPE_EPF, doc_type='epf')['status'], 'not_epf')

    def test_a_printed_penyata_ahli_scores_exactly_as_before(self):
        tn = _norm_fold_upper_alnum(GENUINE_EPF)
        old = _score_list(EPF_SIGNATURES, tn, False, False)
        g = signature_genuineness(GENUINE_EPF, doc_type='epf')
        self.assertEqual((g['type'], g['probability'], g['status']), ('epf', old['probability'], 'genuine'))
        self.assertEqual(epf_app_scores(tn), {})                    # no app anchor: the app list never competes

    def test_a_realistic_printed_penyata_stays_epf_with_its_old_status(self):
        tn = _norm_fold_upper_alnum(PRINTED_PENYATA)
        old = _score_list(EPF_SIGNATURES, tn, False, False)
        g = signature_genuineness(PRINTED_PENYATA, doc_type='epf')
        self.assertEqual((g['type'], g['probability'], g['status']), ('epf', old['probability'], 'genuine'))
        # A CROPPED Penyata (its contribution table only) keeps its old score and type.
        crop = PRINTED_PENYATA.split('CARUMAN SEMASA')[1]
        old_c = _score_list(EPF_SIGNATURES, _norm_fold_upper_alnum(crop), False, False)
        g_c = signature_genuineness(crop, doc_type='epf')
        self.assertEqual((g_c['type'], g_c['probability']), ('epf', old_c['probability']))

    def test_the_app_screen_is_not_a_misfile_into_the_salary_slot(self):
        # The misfile backstop keeps the Penyata list only: a screenshot never clears it (and is suspect anyway).
        self.assertEqual(misfiled_as('salary_slip', EPF_APP_SCREEN), {})
