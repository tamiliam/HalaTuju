"""Card display derivation + slot sanity (card_display) + the repair command.

Covers the read-side resolution matrices (catalogue / sane free-text / junk / pre-U label /
taxonomy fallback), the school-block PRIVACY rule (both directions), the write-side
sanitiser, and the repair command's report/apply on the three live bug shapes."""
from django.test import SimpleTestCase, TestCase

from apps.courses.models import Course, FieldTaxonomy
from apps.scholarship import card_display as cd
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.courses.models import StudentProfile


class TestPatterns(SimpleTestCase):
    def test_school_block_both_directions(self):
        for s in ['SMK Maxwell', 'Sekolah Menengah Kebangsaan Maxwell',
                  'SJK(T) Ladang', 'SMJK Yu Hua', 'sekolah jenis kebangsaan']:
            self.assertTrue(cd.looks_like_school(s), s)
        for s in ['Politeknik Sultan Idris Shah', 'Universiti Malaya', 'Kolej Matrikulasi Pahang',
                  'Kolej Tingkatan Enam Gombak', 'Institut Pendidikan Guru Kampus Tuanku Bainun']:
            self.assertFalse(cd.looks_like_school(s), s)

    def test_date_junk(self):
        self.assertTrue(cd.looks_like_date('Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI - 11.00 PAGI)'))
        self.assertTrue(cd.looks_like_date('20/06/2026'))
        self.assertFalse(cd.looks_like_date('Politeknik Ungku Omar'))

    def test_institution_shape(self):
        self.assertTrue(cd.looks_like_institution('Politeknik Sultan Idris Shah'))
        self.assertTrue(cd.looks_like_institution('Kolej Komuniti Bakri'))
        self.assertFalse(cd.looks_like_institution('Diploma Kejuruteraan Mekanikal'))

    def test_preu_label(self):
        self.assertEqual(cd.preu_label('stpm', 'sains'), 'STPM · Sains')
        self.assertEqual(cd.preu_label('stpm', 'sains_sosial'), 'STPM · Sains Sosial')
        self.assertEqual(cd.preu_label('matric', 'perakaunan'), 'Matrikulasi · Perakaunan')
        self.assertEqual(cd.preu_label('asasi', ''), 'Asasi')
        self.assertEqual(cd.preu_label('poly', ''), '')

    def test_sanitise_offer_slots(self):
        # #125 shape: institution-shaped programme + date institution.
        p, i, rep = cd.sanitise_offer_slots(
            'Politeknik Sultan Idris Shah', 'Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI)')
        self.assertEqual(p, '')
        self.assertEqual(i, 'Politeknik Sultan Idris Shah')
        self.assertIn('15 JUN 2026', rep)
        # clean pair passes through
        p, i, rep = cd.sanitise_offer_slots('Diploma Kejuruteraan Elektrik', 'Politeknik Ungku Omar')
        self.assertEqual((p, i, rep), ('Diploma Kejuruteraan Elektrik', 'Politeknik Ungku Omar', ''))


class TestResolution(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.tax = FieldTaxonomy.objects.create(key='zz_mek', name_en='Mechanical', name_ms='Mekanikal',
                                               name_ta='இயந்திரவியல்', image_slug='mekanikal-am')
        cls.course = Course.objects.create(course_id='ZZC1', course='Asasi Teknologi Kejuruteraan (Asasi TVET)',
                                           level='Asasi', department='X', field='Eng', field_key=cls.tax)

    def _app(self, **over):
        p = StudentProfile.objects.create(supabase_user_id=f'cd-{ScholarshipApplication.objects.count()}')
        return ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, **over)

    def test_course_catalogue_wins(self):
        a = self._app(chosen_programme={'course_id': 'ZZC1', 'course_name': 'Politeknik Sultan Idris Shah'},
                      field_of_study='zz_mek')
        self.assertEqual(cd.resolve_course(a), 'Asasi Teknologi Kejuruteraan (Asasi TVET)')

    def test_course_rejects_institution_shaped_name_falls_to_label(self):
        a = self._app(chosen_programme={'course_name': 'Politeknik Sultan Idris Shah'},
                      chosen_pathway='asasi', field_of_study='zz_mek')
        self.assertEqual(cd.resolve_course(a), 'Asasi')

    def test_course_taxonomy_fallback(self):
        a = self._app(chosen_programme={}, field_of_study='zz_mek')
        self.assertEqual(cd.resolve_course(a), 'Mechanical')

    def test_course_sane_freetext_kept(self):
        a = self._app(chosen_programme={'course_name': 'Diploma Kejuruteraan Mekanikal'})
        self.assertEqual(cd.resolve_course(a), 'Diploma Kejuruteraan Mekanikal')

    def test_institution_rejects_date(self):
        a = self._app(chosen_programme={'institution': 'Tarikh dan Masa Daftar: 15 JUN 2026'})
        self.assertEqual(cd.resolve_institution(a), '')

    def test_institution_blocks_school(self):
        # PRIVACY: a Form-6 school in either slot never resolves to a sponsor-facing value.
        a = self._app(chosen_programme={'institution': 'Sekolah Menengah Kebangsaan Maxwell'},
                      pre_u_institution='SMK Maxwell')
        self.assertEqual(cd.resolve_institution(a), '')

    def test_institution_sane_freetext_kept(self):
        a = self._app(chosen_programme={'institution': 'Politeknik Ungku Omar'})
        self.assertEqual(cd.resolve_institution(a), 'Politeknik Ungku Omar')


class TestRepairCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.tax = FieldTaxonomy.objects.create(key='zz_mek2', name_en='Mech', name_ms='Mek',
                                               name_ta='இ', image_slug='mekanikal-am')
        Course.objects.create(course_id='ZZC2', course='Asasi Teknologi Kejuruteraan (Asasi TVET)',
                              level='Asasi', department='X', field='Eng', field_key=cls.tax)

    def _app(self, **over):
        p = StudentProfile.objects.create(supabase_user_id=f'rc-{ScholarshipApplication.objects.count()}')
        return ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, **over)

    def test_proposes_and_applies_125_shape(self):
        from apps.scholarship.management.commands.repair_chosen_programme import propose_repair
        a = self._app(chosen_programme={'course_id': 'ZZC2', 'course_name': 'Politeknik Sultan Idris Shah',
                                        'institution': 'Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI)'},
                      reporting_date=None)
        rep = propose_repair(a)
        self.assertIsNotNone(rep)
        self.assertEqual(rep['course_name'], 'Asasi Teknologi Kejuruteraan (Asasi TVET)')
        self.assertEqual(rep['institution'], 'Politeknik Sultan Idris Shah')
        self.assertIsNotNone(rep['reporting_fill'])   # date recovered from the junk institution

    def test_clean_row_no_repair(self):
        from apps.scholarship.management.commands.repair_chosen_programme import propose_repair
        a = self._app(chosen_programme={'course_id': 'ZZC2', 'course_name': 'Asasi Teknologi Kejuruteraan (Asasi TVET)',
                                        'institution': 'Politeknik Ungku Omar'})
        self.assertIsNone(propose_repair(a))

    def test_school_row_left_alone(self):
        # A Form-6 school in institution is legitimate officer data — repair NEVER touches it
        # (the sponsor-card school-block handles privacy at read time).
        from apps.scholarship.management.commands.repair_chosen_programme import propose_repair
        a = self._app(chosen_programme={'course_name': 'Tingkatan Enam',
                                        'institution': 'Sekolah Menengah Kebangsaan Maxwell'})
        self.assertIsNone(propose_repair(a))
