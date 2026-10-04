"""TD-150 (2026-10-04) — the course matcher must never tie a student to the wrong public course.

``offer_pathway.resolve_catalogue_course`` turns an offer letter into a catalogue ``course_id`` only
on a confident, UNIQUE match; anything else stays label-only. TD-332 (the same day) stopped a
tertiary letter matching a pre-U course or a course of another level. Two shapes from the entry
were still reachable, and both now read "cannot tell" — no id — by the same conservative rule:

* **#95 — a generic letter, a specialised course.** "Diploma Teknologi Maklumat" at Politeknik Ungku
  Omar, where the catalogue holds only specialisations ("… (Pembangunan Perisian dan Aplikasi)" and
  the recommender's synthetic majors). With ONE such course at the campus the letter matched it as
  unique, and the specialisation was arbitrary. The letter's words being a strict subset of the
  course's means the course says something the letter does not.
* **#31 — a private arm.** A letter from Universiti Malaya's Saluran Terbuka (SATU) — an IPTS option
  the owner ruled red (TD-145) — still pinned the PUBLIC course whose name it shared.

What must NOT move is pinned beside each: a letter carrying MORE words than the course (a code
prefix) still matches, a degree name's "dengan Kepujian" is not a specialisation, and a PISMP
course's "(SJKT)" — the school type no letter states — is not one either.
"""
from django.test import TestCase

from apps.courses.models import Course, CourseInstitution, FieldTaxonomy, Institution
from apps.scholarship import offer_pathway as op
from apps.scholarship.catalogue_levels import (
    names_a_specialisation_the_letter_does_not, private_arm_letter)

PUO = 'Politeknik Ungku Omar'
PSP = 'Politeknik Seberang Perai'
UM = 'Universiti Malaya'


class TestTheMatcherCannotTellIsNoMatch(TestCase):
    @classmethod
    def setUpTestData(cls):
        ft = FieldTaxonomy.objects.create(key='td150', name_en='IT', name_ms='IT', name_ta='x',
                                          image_slug='td150')

        def inst(iid, name):
            return Institution.objects.create(institution_id=iid, institution_name=name,
                                              acronym=iid.upper(), type='POLY', state='Perak')

        def course(cid, name, level, *campuses):
            c = Course.objects.create(course_id=cid, course=name, level=level, department='x',
                                      field='x', field_key=ft)
            for campus in campuses:
                CourseInstitution.objects.create(course=c, institution=campus)

        puo, psp, um = inst('td150-puo', PUO), inst('td150-psp', PSP), inst('td150-um', UM)
        # #95: Ungku Omar holds ONE IT course, a specialisation; Seberang Perai another major.
        course('TD150-DTM-PERISIAN', 'Diploma Teknologi Maklumat (Pembangunan Perisian dan Aplikasi)',
               'Diploma', puo)
        course('TD150-DTM-DATA', 'Diploma Teknologi Maklumat (Pengurusan Data)', 'Diploma', psp)
        course('TD150-DAC', 'Diploma Perakaunan', 'Diploma', puo)
        course('TD150-UM-EKON', 'Ijazah Sarjana Muda Ekonomi dengan Kepujian', 'Ijazah Sarjana Muda', um)
        # Review fix (2026-10-04): UPU's "Baru" marker, a trailing "#" and "Bacelor" say nothing
        # about WHICH course. UR4851001's shape (UniMAP), and two "Baru" names from the catalogue.
        unimap = inst('td150-unimap', 'Universiti Malaysia Perlis')
        course('UR4851001', 'Diploma Kejuruteraan Alam Sekitar Baru', 'Diploma', unimap)
        course('TD150-ECOM', 'Diploma E-Commerce Baru', 'Diploma', unimap)
        course('TD150-ETNIK', 'Diploma Bahasa Etnik Baru #', 'Diploma', unimap)
        course('TD150-BACELOR', 'Bacelor Sains Komputer', 'Ijazah Sarjana Muda', um)
        course('TD150-PISMP-BT', 'Bahasa Tamil Pendidikan Rendah (SJKT)',
               'Ijazah Sarjana Muda Pendidikan', um)

    # ── #95: a generic letter never pins a specialisation ────────────────────────────────────
    def test_a_generic_it_letter_does_not_pin_the_campus_only_specialisation(self):
        self.assertIsNone(op.resolve_catalogue_course('DIPLOMA TEKNOLOGI MAKLUMAT', PUO.upper()))
        self.assertFalse(op.offer_is_resolvable('DIPLOMA TEKNOLOGI MAKLUMAT', PUO.upper()))

    def test_a_letter_that_names_the_specialisation_still_pins_it(self):
        self.assertEqual(op.resolve_catalogue_course(
            'DIPLOMA TEKNOLOGI MAKLUMAT (PEMBANGUNAN PERISIAN DAN APLIKASI)', PUO.upper())['course_id'],
            'TD150-DTM-PERISIAN')

    def test_another_campus_major_is_never_reached(self):
        # The shape #95 first surfaced as: a major at a DIFFERENT polytechnic.
        self.assertIsNone(op.resolve_catalogue_course(
            'DIPLOMA TEKNOLOGI MAKLUMAT (PENGURUSAN DATA)', PUO.upper()))

    def test_a_letter_with_more_words_than_the_course_still_matches(self):
        # The offer-letter code prefix the bidirectional nesting was written for.
        self.assertEqual(op.resolve_catalogue_course(
            'DAC - DIPLOMA PERAKAUNAN', PUO.upper())['course_id'], 'TD150-DAC')

    def test_the_award_class_is_not_a_specialisation(self):
        self.assertEqual(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA EKONOMI', UM.upper())['course_id'], 'TD150-UM-EKON')

    def test_a_pismp_school_type_is_not_a_specialisation(self):
        self.assertEqual(op.resolve_catalogue_course(
            'BAHASA TAMIL PENDIDIKAN RENDAH', UM.upper())['course_id'],
            'TD150-PISMP-BT')

    def test_upus_new_marker_is_not_a_specialisation(self):
        for letter, cid in (('DIPLOMA KEJURUTERAAN ALAM SEKITAR', 'UR4851001'),
                            ('DIPLOMA E-COMMERCE', 'TD150-ECOM'),
                            ('DIPLOMA BAHASA ETNIK', 'TD150-ETNIK')):
            with self.subTest(letter=letter):
                self.assertEqual(op.resolve_catalogue_course(
                    letter, 'UNIVERSITI MALAYSIA PERLIS')['course_id'], cid)

    def test_bacelor_is_the_generic_bachelor(self):
        self.assertEqual(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA SAINS KOMPUTER', UM.upper())['course_id'], 'TD150-BACELOR')

    # ── #31: a private arm never pins a public course ─────────────────────────────────────────
    def test_a_saluran_terbuka_letter_does_not_pin_the_public_course(self):
        self.assertEqual(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA EKONOMI', UM.upper())['course_id'], 'TD150-UM-EKON')   # the control
        self.assertIsNone(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA EKONOMI', 'SALURAN TERBUKA UNIVERSITI MALAYA (SATU)'))
        self.assertIsNone(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA EKONOMI (PENDIDIKAN BERTERUSAN)', UM.upper()))

    def test_a_sdn_bhd_operator_does_not_pin_a_public_course(self):
        self.assertIsNone(op.resolve_catalogue_course(
            'DIPLOMA PERAKAUNAN', 'POLITEKNIK UNGKU OMAR SDN BHD'))


class TestTheTwoRulesOnTheirOwn(TestCase):
    def test_strictly_fewer_words_is_a_specialisation_the_letter_does_not_name(self):
        self.assertTrue(names_a_specialisation_the_letter_does_not({'teknologi'}, {'teknologi', 'data'}))
        self.assertFalse(names_a_specialisation_the_letter_does_not({'teknologi'}, {'teknologi'}))
        self.assertFalse(names_a_specialisation_the_letter_does_not({'dac', 'akaun'}, {'akaun'}))
        self.assertFalse(names_a_specialisation_the_letter_does_not({'ekonomi'}, {'ekonomi', 'kepujian'}))
        self.assertFalse(names_a_specialisation_the_letter_does_not(set(), {'x'}))

    def test_the_private_arm_reads_the_genuineness_checks_own_phrases(self):
        self.assertTrue(private_arm_letter('', 'Saluran Terbuka Universiti Malaya'))
        self.assertTrue(private_arm_letter('Diploma X', 'UTM SPACE'))
        self.assertFalse(private_arm_letter('Diploma Aeroangkasa', 'Universiti Teknologi Malaysia'))
        self.assertFalse(private_arm_letter('Semester Satu', 'Universiti Malaya'))
