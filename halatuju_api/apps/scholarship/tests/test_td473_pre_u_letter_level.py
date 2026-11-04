"""TD-473: a pre-U offer letter (matriculation / STPM / Form 6) on a tertiary or PISMP application
reads Pathway ``mismatch`` — the LEVEL is checked before the shared word (owner, decisions.md
2026-11-03 rule 1: a yellow chip + the Check 2 query, never red, no band loss).

App 187 (doc 2511) is the found case: "Program Matrikulasi" at "Kolej Matrikulasi Kejuruteraan Johor"
ticked ``match`` against a Kejuruteraan Awam degree by the word KEJURUTERAAN.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.pathway_engine import offer_pathway_match, student_offer_check
from apps.scholarship.pathway_match import pre_u_letter_on_tertiary_pick

MATRIC_PROG = 'PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN MALAYSIA'
MATRIC_INST = 'KOLEJ MATRIKULASI KEJURUTERAAN JOHOR'


def _doc(programme, institution, *, chosen_pathway, course_name='', pick_inst='', pre_u_inst=''):
    app = SimpleNamespace(
        profile=SimpleNamespace(name='Ali bin Abu', nric='050101-01-1234'),
        chosen_programme={'course_name': course_name, 'institution': pick_inst},
        chosen_pathway=chosen_pathway, pre_u_track='', pre_u_institution=pre_u_inst, cohort=None)
    fields = {'candidate_name': 'Ali bin Abu', 'candidate_nric': '050101-01-1234',
              'programme': programme, 'institution': institution}
    return SimpleNamespace(doc_type='offer_letter', application=app,
                           vision_fields={'fields': fields, 'student_verdict': 'ok'})


class TestTheLevelComesFirst(SimpleTestCase):
    def test_app_187_a_matric_letter_on_a_degree_pick_is_a_mismatch(self):
        # Before TD-473 the shared word KEJURUTERAAN made this a 'match'.
        self.assertEqual(offer_pathway_match('Kejuruteraan Awam', 'Kejuruteraan Johor', MATRIC_PROG,
                                             MATRIC_INST), 'match')
        self.assertEqual(offer_pathway_match('Kejuruteraan Awam', 'Kejuruteraan Johor', MATRIC_PROG,
                                             MATRIC_INST, declared_type='degree'), 'mismatch')

    def test_the_whole_read_says_mismatch(self):
        chk = student_offer_check(_doc(MATRIC_PROG, MATRIC_INST, chosen_pathway='university',
                                       course_name='Ijazah Sarjana Muda Kejuruteraan Awam'))
        self.assertEqual(chk['pathway'], 'mismatch')

    def test_a_form_6_letter_on_each_tertiary_code(self):
        for code in ('degree', 'university', 'poly', 'pismp', 'kkom', 'iljtm', 'ilkbs', 'mara'):
            with self.subTest(code=code):
                self.assertTrue(pre_u_letter_on_tertiary_pick(code, 'Tingkatan Enam Semester 1',
                                                              'SMK Majakir, Papar'))

    def test_a_pre_u_pick_is_untouched(self):
        for code in ('matric', 'stpm', 'asasi', '', 'something_new'):
            with self.subTest(code=code):
                self.assertFalse(pre_u_letter_on_tertiary_pick(code, MATRIC_PROG, MATRIC_INST))
        chk = student_offer_check(_doc(MATRIC_PROG, MATRIC_INST, chosen_pathway='matric',
                                       pre_u_inst='Kolej Matrikulasi Johor'))
        self.assertEqual(chk['pathway'], 'match')

    def test_a_degree_letter_that_names_stpm_as_its_entry_route_is_not_pre_u(self):
        prog = 'IJAZAH SARJANA MUDA PENDIDIKAN (LEPASAN STPM / MATRIKULASI)'
        self.assertFalse(pre_u_letter_on_tertiary_pick('degree', prog, 'Universiti Pendidikan Sultan Idris'))
        self.assertFalse(pre_u_letter_on_tertiary_pick('pismp', 'PISMP AMBILAN LEPASAN STPM',
                                                       'IPG Kampus Ipoh'))
        self.assertFalse(pre_u_letter_on_tertiary_pick('poly', 'Diploma (lepasan Matrikulasi)',
                                                       'Politeknik Ungku Omar'))

    def test_review_a_tertiary_letter_naming_its_entry_route_is_not_pre_u(self):
        # Adversarial review round 1: each of these read as pre-U before the fix.
        cases = [
            ('university', 'KEJURUTERAAN AWAM (LEPASAN STPM)', 'UNIVERSITI TEKNOLOGI MALAYSIA'),
            ('university', 'UH6521001 SAINS KOMPUTER', 'UNIVERSITI MALAYA (Kemasukan lepasan Matrikulasi)'),
            ('poly', 'Kejuruteraan Mekanikal', 'Politeknik Ungku Omar (lepasan SPM / STPM)'),
            ('kkom', 'Sijil Teknologi Elektrik (lepasan STPM)', 'Kolej Komuniti Selayang'),
            ('degree', 'Sains Komputer (lepasan Matrikulasi / STPM)', ''),
            # Round 2.
            ('university', 'Kejuruteraan Awam (Aliran STPM)', 'UTM Skudai'),
            ('university', 'UH6521001 Sains Komputer (STPM)', 'UM'),
            ('university', 'Sains Komputer bagi calon STPM / Matrikulasi', 'UiTM Shah Alam'),
            ('university', 'Perubatan (Lepasan STPM / Asasi / Matrikulasi)', 'UKM'),
            ('pismp', 'PISMP (lepasan STPM)', 'Maktab Perguruan Sultan Idris'),
            ('university', 'Sekolah Kejuruteraan Awam (lepasan STPM)', 'Universiti Teknologi Malaysia'),
            # Round 3: a tertiary or vocational name beside a pre-U one wins.
            ('pismp', 'Diploma Pendidikan', 'Kolej Matrikulasi (kampus IPG)'),
            ('poly', 'Sijil Kemahiran (lepasan STPM)', 'SMK Vokasional'),
        ]
        for code, prog, inst in cases:
            with self.subTest(prog=prog, inst=inst):
                self.assertFalse(pre_u_letter_on_tertiary_pick(code, prog, inst))

    def test_real_pre_u_letter_shapes_are_still_caught(self):
        cases = [
            ('PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN MALAYSIA', 'KOLEJ MATRIKULASI KEJURUTERAAN JOHOR'),
            ('Tawaran Kemasukan ke Program Matrikulasi Sesi 2026/2027', 'Kolej Matrikulasi Melaka'),
            ('Program Matrikulasi bagi calon lepasan SPM', 'Kolej Matrikulasi Pulau Pinang'),
            ('Tingkatan Enam Semester 1', 'SEKOLAH MENENGAH KEBANGSAAN MAJAKIR, PAPAR'),   # app 276
            ('Sijil Tinggi Persekolahan Malaysia (STPM) Tingkatan Enam', 'Kolej Tingkatan Enam Gombak'),
            # Round 2: what the programme-word rule missed.
            ('Kemasukan Murid Lepasan SPM Tingkatan Enam', 'SMK Majakir'),
            ('Tingkatan Enam bagi calon Sijil Pelajaran Malaysia', 'Sekolah Menengah Kebangsaan Temerloh'),
            ('Tingkatan 6 (Sijil Tinggi Agama Malaysia)', 'SMK Mentakab'),
            ('Program Matrikulasi KPM untuk kemasukan ke Universiti Awam', 'Kolej Matrikulasi Johor'),
            ('', '-KOLEJ MATRIKULASI P.PINANG (KMPP)'),
            ('', 'KOLEJ TINGKATAN ENAM TUANKU MUHRIZ'),
            # Round 3.
            ('Tingkatan Enam', 'SMKA Sheikh Abdul Malek'),
            ('Tingkatan Enam', 'Pusat Tingkatan Enam Seremban'),
            ('Tingkatan 6', 'SM Teknik Kuala Lumpur'),
            ('Tingkatan Enam', 'SMK(P) Methodist'),
        ]
        for prog, inst in cases:
            with self.subTest(prog=prog):
                self.assertTrue(pre_u_letter_on_tertiary_pick('degree', prog, inst))

    def test_a_tertiary_letter_on_a_tertiary_pick_is_untouched(self):
        self.assertFalse(pre_u_letter_on_tertiary_pick('university', 'Ijazah Sarjana Muda Kejuruteraan Awam',
                                                       'Universiti Teknologi Malaysia'))
        self.assertEqual(offer_pathway_match('Kejuruteraan Awam', '', 'Ijazah Sarjana Muda Kejuruteraan Awam',
                                             '', declared_type='university'), 'match')

    def test_case_and_blanks_never_raise(self):
        self.assertTrue(pre_u_letter_on_tertiary_pick(' Degree ', 'program matrikulasi', 'kolej matrikulasi perak'))
        # The institution decides: a blank one, or a school whose letter names no Form 6, decides nothing.
        self.assertFalse(pre_u_letter_on_tertiary_pick('degree', 'program matrikulasi', ''))
        self.assertFalse(pre_u_letter_on_tertiary_pick('degree', 'Surat Tawaran', 'SMK Majakir'))
        self.assertFalse(pre_u_letter_on_tertiary_pick('degree', '', ''))
        self.assertFalse(pre_u_letter_on_tertiary_pick('degree', None, None))
        self.assertFalse(pre_u_letter_on_tertiary_pick(None, MATRIC_PROG, MATRIC_INST))
