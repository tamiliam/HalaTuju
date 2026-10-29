"""Matric/Diploma M4b — the owner's four rulings (2026-10-29) on Matriculation / polytechnic pages in
the higher-results slot (`genuineness/matric_poly_doc.py`, MODEL_VERSION 1.22.0):
  (1) a semester RESULT SLIP is not accepted — ask for the full academic transcript;
  (2) a polytechnic STUDENT-PORTAL screenshot is not accepted — ask for the transcript (as 1A);
  (3) a Matriculation OFFER LETTER here is marked "not a results document";
  (4) no suspect band (genuine or nothing).
Synthetic twins of each page's fixed wording; a real transcript is never asked to re-upload.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import matric_poly_doc as m
from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.test_matric_parse import four_sem_pages
from apps.scholarship.tests.test_matric_poly_doc import KPM_LETTER, MATRIC, MATRIC_OFFER, POLY, PORTAL
from apps.scholarship.tests.test_poly_diploma_parse import NL, UITM
from apps.scholarship.tests.test_third_route_s3 import DEGREE, MATRIC_HELD, _app

#: A Matriculation semester result slip: the KPM header, ONE semester, the slip's title and disclaimer.
SLIP_HEAD = ['KEMENTERIAN PENDIDIKAN', 'BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION',
             'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', '{sem} SESI 2025/2026',
             'NAMA / NAME : SITI AMINAH BINTI ALI', 'KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK',
             'SC025 COMPUTER SCIENCE 2 5 A 4.00', 'PNGS / GPA : 4.00', 'PNGK / CGPA : 4.00']
DISCLAIMER = ['Slip keputusan ini bukan transkrip akademik. Keputusan muktamad adalah seperti yang tercatat',
              'sebelum transkrip akademik sebenar dikeluarkan.',
              'This result slip is not an academic transcript. The final result is as appeared in the academic transcript.']


def matric_slip(sem='SEMESTER II', final=True):
    lines = [ln.format(sem=sem) for ln in SLIP_HEAD]
    if final:
        lines.append('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI')
    return NL.join(lines + DISCLAIMER)


#: A polytechnic semester result slip (the shape of the two corpus slips).
POLY_SLIP = NL.join(['SLIP KEPUTUSAN PENILAIAN AKHIR', 'KEPUTUSAN PENILAIAN AKHIR SEMESTER', 'SESI I : 2025/2026',
                     'PROGRAM DIPLOMA PENGURUSAN LOGISTIK', 'POLITEKNIK CONTOH',
                     'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'SEMESTER : TIGA', 'KELAS SEMASA : DLS3C',
                     'KOD NAMA KURSUS JAM KREDIT GRED NILAI MATA MATA KREDIT STATUS',
                     'DPB10063 PRINCIPLES OF MANAGEMENT 3.0 A 4.00 12.00', 'PNM : 3.53 HPNM : 3.16'])


class TestTheRulings(SimpleTestCase):
    def assertRuled(self, text, seen, status):
        sg = score(text)
        self.assertEqual((sg.get('status'), sg.get('type')), (status, seen))
        self.assertIn('owner ruling 2026-10-29', sg['reason'])

    def test_1_a_matriculation_semester_result_slip(self):
        self.assertRuled(matric_slip(), m.MATRIC_SLIP, 'not_matric_result')                  # final, Lulus dan Tamat
        self.assertRuled(matric_slip('SEMESTER I', final=False), m.MATRIC_SLIP, 'not_matric_result')
        self.assertRuled(matric_slip('SEMESTER IV'), m.MATRIC_SLIP, 'not_matric_result')      # a 2-year programme's
        self.assertIn('full academic transcript', score(matric_slip())['reason'])

    def test_1_a_polytechnic_semester_result_slip(self):
        self.assertRuled(POLY_SLIP, m.POLY_SLIP, 'not_poly_result')

    def test_2_the_polytechnic_student_portal(self):
        self.assertRuled(PORTAL, m.POLY_PORTAL, 'not_poly_result')

    def test_3_a_matriculation_offer_letter(self):
        self.assertRuled(MATRIC_OFFER, m.MATRIC_OFFER, 'not_matric_result')
        self.assertIn('not a results document', score(MATRIC_OFFER)['reason'])

    def test_a_real_transcript_is_never_asked_to_re_upload(self):
        """Even one that carries an offer letter's or a slip's word somewhere on it."""
        for text in (MATRIC, POLY, MATRIC + NL + 'TAHNIAH ATAS KEMASUKAN', POLY + NL + 'HPNM JAM KREDIT'):
            self.assertEqual(score(text).get('status'), 'genuine')
        self.assertEqual(score(four_sem_pages()[0]), {})                # page 1 of a 2-year transcript: unsure

    def test_a_transcript_is_never_ruled_whatever_else_it_prints(self):
        """The guard before every ruling: a page that passes a transcript's own gates is a transcript."""
        portal_words = NL.join(['KEPUTUSAN PEPERIKSAAN MENGIKUT SEMESTER', 'DAFTAR HHP', 'STATUS DAFTAR LATIHAN INDUSTRI'])
        self.assertEqual(score(MATRIC + NL + portal_words).get('status'), 'genuine')

    def test_an_offer_is_told_only_on_a_matric_page_with_no_transcript_grid(self):
        import re
        cropped = re.sub(r'SEMESTER II\n.*?PNGS / GPA : 3\.33\n', '', MATRIC, flags=re.S)
        self.assertEqual(score(cropped + NL + 'TAWARAN KEMASUKAN'), {})       # a grid: not an offer, unsure
        two_ways = NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN KEMASUKAN KE PROGRAM DIPLOMA'])
        self.assertEqual(score(two_ways), {})                                  # Matriculation AND Diploma: no kind

    def test_unsure_stays_not_checked(self):
        """One slip phrase only, one portal phrase, one offer word, a letter of no ruled kind."""
        one_phrase = NL.join([ln.format(sem='SEMESTER II') for ln in SLIP_HEAD]).replace(
            'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', 'SLIP KEPUTUSAN PEPERIKSAAN')
        for text in (one_phrase, NL.join(['POLITEKNIK CONTOH', 'SEMAKAN BUTIRAN PELAJAR', 'DIPLOMA X', 'HPNM 3.1']),
                     NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN PROGRAM MATRIKULASI']), KPM_LETTER):
            self.assertEqual(score(text), {})

    def test_the_rulings_stay_in_their_families(self):
        for text in (UITM, UITM + NL + 'SLIP KEPUTUSAN PEPERIKSAAN EXAMINATION RESULT SLIP',
                     'PUSAT ASASI SAINS ' + NL.join(DISCLAIMER), 'SIJIL PELAJARAN MALAYSIA 2024 BAHASA MELAYU A TAWARAN'):
            self.assertEqual(score(text), {}, text[:30])
        kk_slip = POLY_SLIP.replace('POLITEKNIK CONTOH', 'KOLEJ KOMUNITI CONTOH')
        self.assertEqual(score(kk_slip), {})                            # no polytechnic's own name

    def test_4_no_suspect_is_ever_stored(self):
        for text in (MATRIC, POLY, matric_slip(), POLY_SLIP, PORTAL, MATRIC_OFFER, KPM_LETTER, four_sem_pages()[0]):
            self.assertNotEqual(score(text).get('status'), 'suspect')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheLivePath(TestCase):
    def test_a_slip_is_stored_as_not_a_result_and_the_card_steps_down(self):
        from apps.scholarship.anomaly_engine import _detect_document_not_genuine
        from apps.scholarship.verdict_engine import build_verdict
        app = _app(MATRIC_HELD, DEGREE)
        doc = ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind='matric',
                                               storage_path='test/hr-m4b', content_type='image/jpeg')
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {'candidate_name': 'PRIYA', 'cgpa': '3.50', 'cgpa_label': 'PNGK'},
                                 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=['Priya'], ocr={'text': matric_slip(), 'words': None, 'image': b'img', 'error': None})
        doc.refresh_from_db()
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen']), ('not_matric_result', m.MATRIC_SLIP))
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        academic = next(f for f in build_verdict(fresh) if f['fact'] == 'academic')
        self.assertIn('document_not_genuine', {i['code'] for i in academic['unresolved']})
        self.assertEqual(academic['status'], 'recommend', [i['code'] for i in academic['unresolved']])
        hit = _detect_document_not_genuine(fresh)
        if hit is not None:                                                  # only when the card anchors Academic
            self.assertEqual((hit.params['doc'], hit.params['seen']), ('Matriculation results', m.MATRIC_SLIP))

    def test_the_versions_moved(self):
        import re
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in MODEL_VERSION.split('.')), (1, 22, 0))
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'[-.]', VERDICT_ENGINE_VERSION)), (2026, 10, 29, 3))
