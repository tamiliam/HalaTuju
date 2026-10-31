"""Offer realignment, Parts A and B (2026-10-31) — the matcher sees the degree catalogue, reads the
noise real letters carry, and lets the ISSUER stand in for a hostel institution line.

Every string below is a live offer letter's own programme / institution / issuer (no names, no IC
numbers), and every expected course is the one the owner's review named. The catalogue rows are the
live rows for those courses, plus DISTRACTORS that a looser matcher would wrongly take: a more
specialised course at the same university (TD-150), the same degree name at another university, an
Asasi at UiTM for a degree letter (TD-332), and a sibling engineering degree at UTHM.
"""
from django.test import TestCase

from apps.courses.course_pathway import course_pathway_type, pathway_for_requirement
from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution, StpmCourse,
    StpmRequirement)
from apps.scholarship import offer_pathway as op
from apps.scholarship.offer_course_match import (
    is_bumiputera_only, letter_place, letter_programme, match_offer_course)

UM, UITM, UNIMAS, UPM = 'Universiti Malaya', 'Universiti Teknologi MARA', 'Universiti Malaysia Sarawak', 'Universiti Putra Malaysia'
UMS, UTHM, UIAM, PUO = 'Universiti Malaysia Sabah', 'Universiti Tun Hussein Onn Malaysia', 'Universiti Islam Antarabangsa Malaysia', 'Politeknik Ungku Omar'
BPP = 'Bahagian Pengambilan Pelajar'

#: (id, name, acronym, type)
INSTITUTIONS = (
    ('RA-UM', UM, 'UM', 'IPTA'), ('RA-UITM', UITM, 'UiTM', 'IPTA'),
    ('RA-UNIMAS', UNIMAS, 'UNIMAS', 'IPTA'), ('RA-UPM', UPM, 'UPM', 'IPTA'),
    ('RA-UMS', UMS, 'UMS', 'IPTA'), ('RA-UTHM', UTHM, 'UTHM', 'IPTA'),
    ('RA-UIAM', UIAM, 'UIAM', 'IPTA'), ('RA-PUO', PUO, 'PUO', 'Politeknik'),
    # Review 2026-10-31 — the rows a looser institution test named wrongly:
    ('RA-MARA-BPT', 'Majlis Amanah Rakyat (MARA) - Bahagian Pendidikan Tinggi', 'MARA', 'MARA'),
    ('RA-UTM', 'Universiti Teknologi Malaysia', 'UTM', 'IPTA'),
    ('RA-UMK', 'Universiti Malaysia Kelantan', 'UMK', 'IPTA'),
    ('RA-UMT', 'Universiti Malaysia Terengganu', 'UMT', 'IPTA'),
    ('RA-UNIMAP', 'Universiti Malaysia Perlis', 'UniMAP', 'IPTA'),
    ('RA-PMK', 'Politeknik Melaka', 'PMK', 'Politeknik'),
    ('RA-IKM-LUMUT', 'Institut Kemahiran MARA Lumut', 'IKM', 'ILKA'),
    ('RA-IKM-BESERI', 'Institut Kemahiran MARA Beseri', 'IKM', 'ILKA'),
    ('RA-GM-1', 'GIATMARA Arau', 'GIATMARA', 'ILKA'), ('RA-GM-2', 'GIATMARA Kangar', 'GIATMARA', 'ILKA'),
    ('RA-KK-ARAU', 'Kolej Komuniti Arau', '', 'Kolej Komuniti'),
    ('RA-KK-KANGAR', 'Kolej Komuniti Kangar', '', 'Kolej Komuniti'),
)
#: (course_id, name, institution id, Bumiputera-only)
DEGREES = (
    ('UM6343002', 'Sarjana Muda Pengurusan Muamalat', 'RA-UM', False),
    ('UE6343001', 'Sarjana Muda Perniagaan Kewangan (Kepujian)', 'RA-UITM', True),
    ('UE6343002', 'Sarjana Muda Perniagaan Insurans (Kepujian)', 'RA-UITM', True),
    ('UE6343009', 'Sarjana Muda Perniagaan Kewangan Islam (Kepujian)', 'RA-UITM', True),   # TD-150
    ('UE6813002', 'Sarjana Muda Pengurusan Sukan (Kepujian)', 'RA-UITM', True),
    ('UE6813001', 'Sarjana Muda Sains Sukan (Kepujian)', 'RA-UITM', True),
    ('UE6380001', 'Sarjana Muda Undang-Undang (Kepujian) #', 'RA-UITM', True),
    ('UY6380001', 'Sarjana Muda Undang-Undang (Kepujian) #', 'RA-UIAM', False),          # other uni
    ('UE6314001', 'Sarjana Muda Perakaunan (Kepujian)', 'RA-UITM', True),
    ('UW6526001', 'Sarjana Muda Ukur Bahan dengan Kepujian', 'RA-UNIMAS', False),
    ('UW6762002', 'Sarjana Muda Kaunseling dengan Kepujian #', 'RA-UNIMAS', False),
    ('UB6523001', 'Sarjana Muda Kejuruteraan Elektronik dengan Kepujian', 'RA-UTHM', False),
    ('UB6523002', 'Sarjana Muda Kejuruteraan Elektrik dengan Kepujian', 'RA-UTHM', False),
    ('UW6526002', 'Sarjana Muda Kejuruteraan Awam dengan Kepujian', 'RA-UNIMAS', False),
    ('UT6481003', 'Sarjana Muda Sains Komputer dengan Kepujian', 'RA-UTM', False),
    ('UE6481001', 'Sarjana Muda Sains Komputer (Kepujian)', 'RA-UITM', True),
    # One computer-engineering degree at each state-named university, none at UiTM (finding 5).
    ('UR6523002', 'Sarjana Muda Kejuruteraan Komputer dengan Kepujian', 'RA-UNIMAP', False),
    ('UH6523009', 'Sarjana Muda Kejuruteraan Komputer dengan Kepujian', 'RA-UMS', False),
    ('UW6523009', 'Sarjana Muda Kejuruteraan Komputer dengan Kepujian', 'RA-UNIMAS', False),
    ('UL6523009', 'Sarjana Muda Kejuruteraan Komputer dengan Kepujian', 'RA-UMK', False),
    ('UG6523009', 'Sarjana Muda Kejuruteraan Komputer dengan Kepujian', 'RA-UMT', False),
)
#: (course_id, name, level, institution id, source_type, Bumiputera-only)
SPM_COURSES = (
    ('UP4310001', 'Diploma Pembangunan Manusia (Kampus Bintulu, Sarawak)', 'Diploma', 'RA-UPM', 'ua', False),
    ('UH0010001', 'Asasi Sains', 'Asasi', 'RA-UMS', 'ua', True),
    ('UH0010002', 'Asasi Sains Pertanian', 'Asasi', 'RA-UMS', 'ua', False),             # TD-150
    ('UH4520001', 'Diploma Kejuruteraan Kimia (Minyak Dan Gas)', 'Diploma', 'RA-UMS', 'ua', False),
    ('UE0380001', 'Asasi Undang-Undang (KPM)', 'Asasi', 'RA-UITM', 'ua', True),          # TD-332
    ('RA-POLY-DPM', 'Diploma Pengurusan Muamalat', 'Diploma', 'RA-PUO', 'poly', False),
    ('OP4481001', 'Diploma in Computer Science', 'Diploma', 'RA-MARA-BPT', 'ua', True),
    ('UE4481001', 'Diploma Sains Komputer', 'Diploma', 'RA-UITM', 'ua', True),
    ('RA-PMK-DKK', 'Diploma Kejuruteraan Komputer', 'Diploma', 'RA-PMK', 'poly', False),
    ('RA-IKM-DTKM', 'Diploma Teknologi Kejuruteraan Mekanikal', 'Diploma', 'RA-IKM-LUMUT', 'tvet', True),
    ('RA-KK-DPL', 'Diploma Pelancongan', 'Diploma', 'RA-KK-ARAU', 'kkom', True),
)
#: Second campuses of multi-campus courses: (course_id, institution id).
EXTRA_CAMPUSES = (('RA-IKM-DTKM', 'RA-IKM-BESERI'), ('RA-KK-DPL', 'RA-KK-KANGAR'))


def seed_realign_catalogue():
    """The rows above, idempotently. Shared with ``test_offer_realign``."""
    ft, _ = FieldTaxonomy.objects.get_or_create(key='realign', defaults={
        'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'realign'})
    inst = {}
    for iid, name, acr, typ in INSTITUTIONS:
        inst[iid], _ = Institution.objects.get_or_create(institution_id=iid, defaults={
            'institution_name': name, 'acronym': acr, 'type': typ, 'state': 'Selangor'})
    for cid, name, iid, bumi in DEGREES:
        sc, _ = StpmCourse.objects.get_or_create(course_id=cid, defaults={
            'course_name': name, 'university': inst[iid].institution_name, 'institution': inst[iid],
            'field_key': ft})
        StpmRequirement.objects.get_or_create(course=sc, defaults={'req_bumiputera': bumi})
    for cid, name, level, iid, st, bumi in SPM_COURSES:
        c, _ = Course.objects.get_or_create(course_id=cid, defaults={
            'course': name, 'level': level, 'department': 'x', 'field': 'x', 'field_key': ft})
        CourseInstitution.objects.get_or_create(course=c, institution=inst[iid])
        CourseRequirement.objects.get_or_create(course=c, defaults={'source_type': st, 'req_bumiputera': bumi})
    for cid, iid in EXTRA_CAMPUSES:
        CourseInstitution.objects.get_or_create(course_id=cid, institution=inst[iid])


def _cid(programme, institution, issuer=''):
    return (match_offer_course(programme, institution, issuer) or {}).get('course_id')


class LiveLettersResolveTest(TestCase):
    """Each live string resolves to the course named in the owner's review."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_a_plain_degree_name_at_its_university(self):
        self.assertEqual(_cid('SARJANA MUDA PENGURUSAN MUAMALAT', UM, UM), 'UM6343002')

    def test_uitm_local_code_and_acronym_campus_line(self):
        self.assertEqual(_cid('BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)',
                              'UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU', 'UNIVERSITI TEKNOLOGI MARA'),
                         'UE6343001')
        self.assertEqual(_cid('BA271 SARJANA MUDA PERNIAGAAN INSURANS (KEPUJIAN)',
                              'KOLEJ DAHLIA, UITM CAWANGAN SELANGOR, KAMPUS PUNCAK ALAM',
                              'UNIVERSITI TEKNOLOGI MARA'), 'UE6343002')

    def test_uitm_college_line_with_an_administrative_issuer(self):
        self.assertEqual(_cid('SR241 SARJANA MUDA PENGURUSAN SUKAN (KEPUJIAN)',
                              'KOLEJ MERANTI, UNIVERSITI TEKNOLOGI MARA, 40450 SHAH ALAM', BPP), 'UE6813002')

    def test_a_faculty_tail_does_not_block_the_match(self):
        self.assertEqual(_cid('SARJANA MUDA SAINS SUKAN (KEPUJIAN) FAKULTI SAINS SUKAN DAN REKREASI',
                              'UiTM CAWANGAN SARAWAK, KAMPUS SAMARAHAN',
                              'Bahagian Pengambilan Pelajar Universiti Teknologi'), 'UE6813001')

    def test_a_printed_course_code_wins(self):
        self.assertEqual(_cid('Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001', '',
                              'Pejabat Timbalan Naib Canselor (Akademik dan Antarabangsa)'), 'UW6526001')
        # …with a hostel line, against a catalogue name carrying UPU's trailing " #".
        self.assertEqual(_cid('Sarjana Muda Kaunseling dengan Kepujian - UW6762002', 'Kolej Cempaka', UNIMAS),
                         'UW6762002')

    def test_the_uitm_law_and_accounting_degrees(self):
        self.assertEqual(_cid('SARJANA MUDA UNDANG-UNDANG (KEPUJIAN)',
                              'KOLEJ PERINDU, UNIVERSITI TEKNOLOGI MARA, 40450 SHAH ALAM', BPP), 'UE6380001')
        self.assertEqual(_cid('SARJANA MUDA PERAKAUNAN (KEPUJIAN)', 'UiTM KAMPUS SEGAMAT', BPP), 'UE6314001')
        self.assertEqual(_cid('SARJANA MUDA PERAKAUNAN (KEPUJIAN)', 'UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU',
                              BPP), 'UE6314001')

    def test_a_hostel_line_yields_to_the_issuer(self):
        self.assertEqual(_cid('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', UPM), 'UP4310001')
        self.assertEqual(_cid('SARJANA MUDA KEJURUTERAAN ELEKTRONIK DENGAN KEPUJIAN',
                              'KOLEJ KEDIAMAN PERWIRA - DEWAN SULTAN IBRAHIM',
                              'UNIVERSITI TUN HUSSEIN ONN MALAYSIA'), 'UB6523001')

    def test_asasi_and_diploma_at_ums(self):
        self.assertEqual(_cid('Asasi Sains', UMS), 'UH0010001')
        self.assertEqual(_cid('DIPLOMA KEJURUTERAAN KIMIA (MINYAK DAN GAS)', UMS), 'UH4520001')

    def test_resolve_catalogue_course_is_the_same_matcher(self):
        # Every caller of the old name reaches the new matcher, the issuer included.
        self.assertEqual(op.resolve_catalogue_course('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', UPM),
                         match_offer_course('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', UPM))
        self.assertTrue(op.offer_is_resolvable('SARJANA MUDA PENGURUSAN MUAMALAT', UM))
        self.assertEqual(op.programme_agreement('UB6523001', 'SARJANA MUDA KEJURUTERAAN ELEKTRONIK DENGAN KEPUJIAN',
                                                'KOLEJ KEDIAMAN PERWIRA', UTHM), 'match')
        self.assertEqual(op.programme_agreement('UB6523002', 'SARJANA MUDA KEJURUTERAAN ELEKTRONIK DENGAN KEPUJIAN',
                                                'KOLEJ KEDIAMAN PERWIRA', UTHM), 'clash')

    def test_the_return_shape_names_the_catalogue_place(self):
        self.assertEqual(match_offer_course('SARJANA MUDA PENGURUSAN MUAMALAT', UM),
                         {'course_id': 'UM6343002', 'course_name': 'Sarjana Muda Pengurusan Muamalat',
                          'institution': UM})
        self.assertEqual(match_offer_course('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', UPM)['institution'],
                         UPM)


class WhatMustNotResolveTest(TestCase):
    """A wrong course_id is worse than none."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_a_printed_code_at_a_different_named_institution_does_not_resolve(self):
        self.assertIsNone(_cid('Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001', UM))

    def test_an_unknown_printed_code_falls_back_to_the_name(self):
        self.assertEqual(_cid('SARJANA MUDA PENGURUSAN MUAMALAT - UM9999999', UM), 'UM6343002')

    def test_without_the_issuer_a_hostel_line_names_nothing(self):
        self.assertIsNone(_cid('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG'))

    def test_an_institution_line_naming_another_institution_never_borrows_the_issuer(self):
        # #11's shape: a polytechnic letter against a university course stays unresolved, even
        # when the issuer happens to name the university.
        self.assertIsNone(_cid('DIPLOMA PEMBANGUNAN MANUSIA', PUO, UPM))

    def test_a_degree_letter_never_takes_an_asasi_and_a_generic_name_no_specialisation(self):
        self.assertNotEqual(_cid('SARJANA MUDA UNDANG-UNDANG (KEPUJIAN)', UITM), 'UE0380001')
        self.assertIsNone(_cid('Asasi', UMS))
        self.assertNotEqual(_cid('BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)', UITM), 'UE6343009')

    def test_a_private_arm_letter_never_resolves(self):
        self.assertIsNone(_cid('SARJANA MUDA PENGURUSAN MUAMALAT', 'UM SATU - SALURAN TERBUKA', UM))
        # …and when only the letterhead names the private arm (the issuer now stands in for a line).
        self.assertIsNone(_cid('SARJANA MUDA PENGURUSAN MUAMALAT', 'KOLEJ KEDIAMAN',
                               'Universiti Malaya Saluran Terbuka (SATU)'))

    def test_letter_programme_drops_only_the_noise(self):
        self.assertEqual(letter_programme('BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)'),
                         'SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)')
        self.assertEqual(letter_programme('Sarjana Muda Kaunseling dengan Kepujian - UW6762002'),
                         'Sarjana Muda Kaunseling dengan Kepujian')
        self.assertEqual(letter_programme('SARJANA MUDA SAINS SUKAN (KEPUJIAN) FAKULTI SAINS SUKAN DAN ...'),
                         'SARJANA MUDA SAINS SUKAN (KEPUJIAN)')
        self.assertEqual(letter_programme('DAC - DIPLOMA PERAKAUNAN'), 'DAC - DIPLOMA PERAKAUNAN')


class AnAmbiguousNameIsNoMatchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()
        uitm = Institution.objects.get(institution_id='RA-UITM')
        twin = StpmCourse.objects.create(
            course_id='UE6314002', course_name='Sarjana Muda Perakaunan (Kepujian)', university=UITM,
            institution=uitm, field_key=FieldTaxonomy.objects.get(key='realign'))
        StpmRequirement.objects.create(course=twin, req_bumiputera=True)

    def test_two_courses_of_one_name_at_one_university(self):
        self.assertIsNone(_cid('SARJANA MUDA PERAKAUNAN (KEPUJIAN)', 'UiTM KAMPUS SEGAMAT', BPP))
        self.assertFalse(op.offer_is_resolvable('SARJANA MUDA PERAKAUNAN (KEPUJIAN)', 'UiTM KAMPUS SEGAMAT'))


class LetterPlaceTest(TestCase):
    """Part B: one definition of the letter's place, read by the verdict and the writer alike."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_a_hostel_line_yields_to_an_issuer_that_names_the_campus(self):
        self.assertEqual(letter_place('UP4310001', 'KOLEJ SRI RAJANG', UPM), UPM)
        self.assertEqual(letter_place('UP4310001', '', UPM), UPM)

    def test_a_line_that_names_the_campus_or_another_institution_stays(self):
        self.assertEqual(letter_place('UP4310001', 'UPM KAMPUS BINTULU', UPM), 'UPM KAMPUS BINTULU')
        self.assertEqual(letter_place('UP4310001', PUO, UPM), PUO)

    def test_an_issuer_that_names_no_campus_changes_nothing(self):
        self.assertEqual(letter_place('UP4310001', 'KOLEJ SRI RAJANG', BPP), 'KOLEJ SRI RAJANG')
        self.assertEqual(letter_place('UP4310001', 'KOLEJ SRI RAJANG', ''), 'KOLEJ SRI RAJANG')

    def test_the_175_shape_agrees_and_does_not_contradict(self):
        self.assertEqual(op.institution_agreement('UP4310001', '', 'KOLEJ SRI RAJANG', UPM), 'match')
        self.assertFalse(op.offer_contradicts_course_institution('UP4310001', 'KOLEJ SRI RAJANG', UPM))
        # Before the issuer was read, the same letter contradicted the course.
        self.assertTrue(op.offer_contradicts_course_institution('UP4310001', 'KOLEJ SRI RAJANG'))

    def test_a_polytechnic_letter_against_a_university_course_stays_a_clash(self):
        self.assertEqual(op.institution_agreement('UP4310001', '', PUO, UPM), 'clash')
        self.assertTrue(op.offer_contradicts_course_institution('UP4310001', PUO, UPM))


class CourseFlagsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_the_bumiputera_flag_is_read_from_either_catalogue(self):
        self.assertTrue(is_bumiputera_only('UE6343001'))      # StpmRequirement
        self.assertTrue(is_bumiputera_only('UH0010001'))      # CourseRequirement
        self.assertFalse(is_bumiputera_only('UM6343002'))
        self.assertFalse(is_bumiputera_only(''))

    def test_the_course_pathway_is_the_pickers_own(self):
        self.assertEqual(course_pathway_type('UE6343001'), 'university')   # an STPM degree
        self.assertEqual(course_pathway_type('UH0010001'), 'asasi')
        self.assertEqual(course_pathway_type('UP4310001'), 'university')   # a UA diploma
        self.assertEqual(course_pathway_type('RA-POLY-DPM'), 'poly')
        self.assertEqual(course_pathway_type('NOPE'), '')
        self.assertEqual(pathway_for_requirement('ua', 'Asasi'), 'asasi')
        self.assertEqual(pathway_for_requirement('kkom', 'Diploma'), 'kkom')


class ReviewFindingsTest(TestCase):
    """The adversarial review of 851b7cb9 (2026-10-31): each input string is the reviewer's own."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def test_1_mara_inside_a_uitm_line_never_names_maras_division(self):
        self.assertNotEqual(_cid('DIPLOMA IN COMPUTER SCIENCE', 'UNIVERSITI TEKNOLOGI MARA'), 'OP4481001')
        self.assertIsNone(_cid('DIPLOMA IN COMPUTER SCIENCE', 'UNIVERSITI TEKNOLOGI MARA'))
        # A SHARED acronym names nothing on its own (GIATMARA, IKM: many rows).
        self.assertIsNone(_cid('DIPLOMA TEKNOLOGI KEJURUTERAAN MEKANIKAL', 'GIATMARA'))

    def test_2_a_utm_letter_is_utm_never_uitm(self):
        self.assertEqual(_cid('SARJANA MUDA SAINS KOMPUTER DENGAN KEPUJIAN', 'UNIVERSITI TEKNOLOGI MALAYSIA'),
                         'UT6481003')

    def test_3_a_campus_only_when_the_letter_names_exactly_one(self):
        m = match_offer_course('DIPLOMA TEKNOLOGI KEJURUTERAAN MEKANIKAL', 'IKM BESERI')
        self.assertTrue(m is None or m['institution'] in ('', 'Institut Kemahiran MARA Beseri'))
        self.assertNotEqual((m or {}).get('institution'), 'Institut Kemahiran MARA Lumut')
        two = match_offer_course('DIPLOMA PELANCONGAN', 'KOMUNITI ARAU KANGAR')       # names both campuses
        self.assertEqual((two['course_id'], two['institution']), ('RA-KK-DPL', ''))
        one = match_offer_course('DIPLOMA PELANCONGAN', 'KOLEJ KOMUNITI KANGAR')
        self.assertEqual((one['course_id'], one['institution']), ('RA-KK-DPL', 'Kolej Komuniti Kangar'))

    def test_4_a_printed_code_must_agree_with_the_printed_name(self):
        self.assertIsNone(_cid('Sarjana Muda Ukur Bahan dengan Kepujian - UW6526002', UNIMAS))
        self.assertEqual(_cid('Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001', UNIMAS), 'UW6526001')

    def test_5_a_state_word_never_names_a_university(self):
        degree = 'SARJANA MUDA KEJURUTERAAN KOMPUTER'
        self.assertNotEqual(_cid(degree, 'UiTM CAWANGAN PERLIS, KAMPUS ARAU'), 'UR6523002')
        for line in ('UiTM CAWANGAN PERLIS, KAMPUS ARAU', 'UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU',
                     'UiTM CAWANGAN SARAWAK, KAMPUS SAMARAHAN', 'UiTM CAWANGAN KELANTAN, KAMPUS MACHANG',
                     'UiTM CAWANGAN TERENGGANU, KAMPUS DUNGUN'):
            with self.subTest(line=line):
                self.assertIsNone(_cid(degree, line))
        self.assertIsNone(_cid('DIPLOMA KEJURUTERAAN KOMPUTER', 'UiTM CAWANGAN MELAKA, KAMPUS JASIN'))
        # …and with no university named at all, a place word alone names nothing either.
        self.assertIsNone(_cid(degree, 'KOLEJ KEDIAMAN SABAH'))
        # The universities themselves are still named by their own names and acronyms.
        self.assertEqual(_cid(degree, 'Universiti Malaysia Perlis'), 'UR6523002')
        self.assertEqual(_cid(degree, 'UMS KAMPUS INDUK'), 'UH6523009')


class CentreLinesDoNotOutrankTheLetterheadTest(TestCase):
    """Round-2 review (2026-10-31): a centre line's words sit inside some university's name ("Sains"
    is in Universiti Sains Malaysia, "Teknologi" in Universiti Teknologi Malaysia). Such a line must
    not name those universities ahead of the letterhead that names the real one. The COUNTERFACTUAL
    rows below are the trap: with them in the catalogue the old fallback resolved #349 to UTM."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()
        ft = FieldTaxonomy.objects.get(key='realign')
        usm = Institution.objects.create(institution_id='RA-USM', institution_name='Universiti Sains Malaysia',
                                         acronym='USM', type='IPTA', state='Pulau Pinang')
        usim = Institution.objects.create(institution_id='RA-USIM', institution_name='Universiti Sains Islam Malaysia',
                                          acronym='USIM', type='IPTA', state='Negeri Sembilan')
        um = Institution.objects.get(institution_id='RA-UM')
        utm = Institution.objects.get(institution_id='RA-UTM')
        # Two distinctive words, both inside the #349 centre line: the word tier DOES name it, so only
        # the letterhead-first order keeps #349 at UMS (the ordering's own bite).
        akst = Institution.objects.create(institution_id='RA-AKST', institution_name='Akademi Sains Teknologi',
                                          acronym='', type='IPTS', state='Selangor')
        for cid, name, inst, bumi in (('UM0421001', 'Asasi Sains Hayat', um, True),
                                      ('RA-UTM-ASASI', 'Asasi Sains', utm, False),          # counterfactual
                                      ('RA-USM-ASH', 'Asasi Sains Hayat', usm, False),      # counterfactual
                                      ('RA-USIM-ASH', 'Asasi Sains Hayat', usim, False),    # counterfactual
                                      ('RA-AKST-AS', 'Asasi Sains', akst, False)):          # counterfactual
            c = Course.objects.create(course_id=cid, course=name, level='Asasi', department='x', field='x',
                                      field_key=ft)
            CourseInstitution.objects.create(course=c, institution=inst)
            CourseRequirement.objects.create(course=c, source_type='ua', req_bumiputera=bumi)

    def test_349_shape_resolves_through_the_issuer_never_utm(self):
        self.assertEqual(_cid('Asasi Sains', 'Pusat Persediaan Sains dan Teknologi (PPST)',
                              'Universiti Malaysia Sabah'), 'UH0010001')

    def test_322_shape_resolves_through_the_issuer_never_usm_or_usim(self):
        self.assertEqual(_cid('ASASI SAINS HAYAT', 'Pusat Asasi Sains', 'Universiti Malaya'), 'UM0421001')

    def test_without_a_letterhead_a_centre_line_names_no_university_by_a_shared_word(self):
        # One distinctive word ("Sains", "Teknologi") never names Universiti Sains / Teknologi Malaysia.
        self.assertIsNone(_cid('ASASI SAINS HAYAT', 'Pusat Asasi Sains'))
        self.assertNotEqual(_cid('Asasi Sains', 'Pusat Persediaan Sains dan Teknologi (PPST)'), 'RA-UTM-ASASI')
