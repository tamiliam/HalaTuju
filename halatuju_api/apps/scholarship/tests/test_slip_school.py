"""TD-733 + TD-734 (25 Nov 2026): the school the SPM slip prints, and the college a higher-results
document prints. Both are read from text the record already stores: no new read, no AI call."""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.scholarship.academic_compare import slip_school
from apps.scholarship.higher_results import _college_read, student_higher_check
from apps.scholarship.serializers.documents import ApplicantDocumentSerializer
from apps.scholarship.tests.factories import create_document, make_application, make_student


def _word(text, cx, cy):
    return {'text': text, 'cx': cx, 'cy': cy, 'h': 12}


class TestSlipSchool(SimpleTestCase):
    def test_a_local_read_keeps_the_row(self):
        f = {'_debug_rows': ['NAMA : PRIYA', 'SEKOLAH : SMK CONVENT, TAIPING', 'BAHASA MELAYU A']}
        self.assertEqual(slip_school(f), 'SMK CONVENT, TAIPING')

    def test_a_gemini_read_keeps_words_that_are_regrouped_into_rows(self):
        cap = [_word('NAMA', 10, 10), _word(':', 50, 10), _word('PRIYA', 70, 10),
               _word('SEKOLAH', 10, 40), _word(':', 80, 40), _word('SMK', 100, 41), _word('CONVENT', 140, 40)]
        self.assertEqual(slip_school({'_slip_ocr_diag': {'capture': cap}}), 'SMK CONVENT')

    def test_persekolahan_and_aliran_sekolah_are_not_the_school_line(self):
        f = {'_debug_rows': ['SIJIL TINGGI PERSEKOLAHAN MALAYSIA : 2025', 'ALIRAN SEKOLAH : SAINS',
                             'JENIS SEKOLAH : SMK']}
        self.assertEqual(slip_school(f), '')

    def test_no_stored_text_gives_nothing(self):
        self.assertEqual(slip_school({}), '')
        self.assertEqual(slip_school({'_slip_ocr_diag': {'reason': 'x'}}), '')
        self.assertEqual(slip_school({'_slip_ocr_diag': {'capture': [{'text': 'SEKOLAH'}]}}), '')

    def test_a_certificate_read_has_no_rows_so_no_school(self):
        self.assertEqual(slip_school({'candidate_name': 'PRIYA', 'results': []}), '')

    def test_an_empty_school_after_the_label_is_nothing(self):
        self.assertEqual(slip_school({'_debug_rows': ['SEKOLAH :']}), '')


def _slip_doc(school_rows, profile_school):
    student = make_student(name='Priya', nric='030101-14-1234', school=profile_school)
    app = make_application('shortlisted', student=student)
    vf = {'fields': {'candidate_name': 'PRIYA', '_debug_rows': school_rows}, 'student_verdict': 'ok'}
    return create_document(application=app, doc_type='results_slip', storage_path='t/slip', vision_fields=vf)


class TestSlipSchoolServed(TestCase):
    def test_a_same_name_school_matches_through_school_match(self):
        doc = _slip_doc(['SEKOLAH : SMK CONVENT'], 'SMK CONVENT, TAIPING')
        self.assertEqual(ApplicantDocumentSerializer._slip_school(doc),
                         {'school': 'SMK CONVENT', 'school_status': 'match'})

    def test_a_different_school_is_a_mismatch(self):
        doc = _slip_doc(['SEKOLAH : SMK BUKIT JALIL'], 'SMK CONVENT, TAIPING')
        self.assertEqual(ApplicantDocumentSerializer._slip_school(doc)['school_status'], 'mismatch')

    def test_no_stored_text_is_no_ref(self):
        doc = _slip_doc(['NAMA : PRIYA'], 'SMK CONVENT')
        self.assertEqual(ApplicantDocumentSerializer._slip_school(doc),
                         {'school': '', 'school_status': 'no_ref'})

    def test_the_check_keys_of_student_slip_check_are_untouched_and_school_is_merged(self):
        from apps.scholarship.academic_engine import student_slip_check
        doc = _slip_doc(['SEKOLAH : SMK CONVENT'], 'SMK CONVENT')
        base = student_slip_check(doc)
        self.assertNotIn('school', base)
        merged = ApplicantDocumentSerializer(doc).data['academic_check']
        self.assertEqual({k: v for k, v in merged.items() if k not in ('school', 'school_status')}, base)
        self.assertEqual((merged['school'], merged['school_status']), ('SMK CONVENT', 'match'))

    def test_a_higher_result_in_the_spm_slot_serves_no_school(self):
        student = make_student(name='Priya', nric='030101-14-1234', school='SMK CONVENT')
        app = make_application('shortlisted', student=student)
        stpm_cert = {'candidate_name': 'PRIYA', 'exam': 'MALAYSIA HIGHER SCHOOL CERTIFICATE 2025',
                     '_debug_rows': ['SEKOLAH : SMK CONVENT'],
                     'results': [{'subject': s, 'grade': '', 'band': 'LULUS PENUH'}
                                 for s in ('PENGAJIAN AM', 'MATEMATIK (T)', 'FIZIK', 'KIMIA')]}
        doc = create_document(application=app, doc_type='results_slip', storage_path='t/s',
                              vision_fields={'fields': stpm_cert, 'student_verdict': 'ok'})
        chk = ApplicantDocumentSerializer(doc).data['academic_check']
        self.assertEqual(chk['higher_kind'], 'stpm')
        self.assertNotIn('school', chk)
        self.assertNotIn('school_status', chk)


class TestCollegeRead(SimpleTestCase):
    def test_a_college_is_served_as_read(self):
        self.assertEqual(_college_read({'institution': ' Kolej Matrikulasi Selangor '}, True),
                         'Kolej Matrikulasi Selangor')

    def test_an_issuer_is_not_a_college(self):
        for issuer in ('KEMENTERIAN PENDIDIKAN MALAYSIA', 'Ministry of Education', 'BAHAGIAN MATRIKULASI',
                       'MAJLIS PEPERIKSAAN MALAYSIA', 'Lembaga Peperiksaan'):
            with self.subTest(issuer=issuer):
                self.assertEqual(_college_read({'institution': issuer}, True), '')

    def test_blank_or_unread_is_nothing(self):
        self.assertEqual(_college_read({'institution': ''}, True), '')
        self.assertEqual(_college_read({}, True), '')
        self.assertEqual(_college_read({'institution': 'POLITEKNIK X'}, False), '')


class TestHigherCheckServesTheCollege(TestCase):
    def test_student_higher_check_carries_institution(self):
        student = make_student(name='Priya', nric='030101-14-1234', exam_type='matric',
                               results_exam_type='matric', higher_cgpa=3.5, higher_koko=8,
                               completed_qualifications=['spm', 'matric'])
        app = make_application('shortlisted', student=student)
        for inst, want in (('KOLEJ MATRIKULASI PAHANG', 'KOLEJ MATRIKULASI PAHANG'),
                           ('KEMENTERIAN PENDIDIKAN MALAYSIA', '')):
            vf = {'fields': {'candidate_name': 'PRIYA', 'cgpa': '3.5', 'institution': inst,
                             'results_kind_detected': 'matric'}, 'student_verdict': 'ok'}
            doc = create_document(application=app, doc_type='higher_results', storage_path='t/h',
                                  vision_fields=vf, results_kind='matric')
            self.assertEqual(student_higher_check(doc)['institution'], want)
