"""TD-332 and TD-331 (2026-10-04): the PROGRAMME axis of an offer letter, judged through the catalogue.

* **TD-332** — ``offer_pathway.resolve_catalogue_course`` aligned a degree letter with a SCHOOL's pre-U
  virtual course on one shared word: "IJAZAH SARJANA MUDA SAINS GUNAAN" at UTHM found stpm-sains at
  "SMK Bandar Tun Hussein Onn 2" (whose name holds every distinctive word of UTHM's), so
  ``programme_agreement`` read a false CLASH and painted the Pathway chip red. A tertiary letter now
  never resolves to a pre-U virtual course, nor to a course whose name states another level.
* **TD-331** — a confirm that changes the programme at the SAME university kept the old
  ``course_id``, so the sponsor card showed the old course. When the verdict's own
  ``programme_agreement`` says 'clash' (and the letter states its level), the id is re-pinned or
  dropped by the TD-145 rule; 'unknown' keeps it.

Runs on the TD-145 catalogue (three universities, plus the ~580 seeded schools).
"""
from apps.courses.models import Course, CourseInstitution, FieldTaxonomy
from apps.scholarship import offer_pathway as op
from apps.scholarship.card_display import programme_split
from apps.scholarship.services import confirm_pathway
from apps.scholarship.tests.test_td145_wrong_university import UPNM, UTHM, _Catalogue

SAINS_DEGREE = 'IJAZAH SARJANA MUDA SAINS GUNAAN'


class TertiaryResolverTest(_Catalogue):
    """TD-332, at the resolver — the one place both the verdict and the confirm ask."""

    def test_a_sains_degree_at_uthm_never_resolves_to_a_school_pre_u_course(self):
        # The reviewer's input. The seeded school really is there and really holds stpm-sains —
        # the precondition, so this test cannot pass on a catalogue that lost the trap.
        self.assertTrue(CourseInstitution.objects.filter(
            course_id='stpm-sains', institution__institution_name__icontains='hussein onn').exists())
        self.assertIsNone(op.resolve_catalogue_course(SAINS_DEGREE, UTHM.upper()))

    def test_so_the_programme_axis_reads_unknown_not_clash(self):
        # 'cannot tell' → unknown, never clash — for every UTHM pick.
        for cid in ('TD-UTHM-ANIM', 'TD-UTHM-SIVIL'):
            with self.subTest(cid=cid):
                self.assertEqual(op.programme_agreement(cid, SAINS_DEGREE, UTHM.upper()), 'unknown')

    def test_a_degree_letter_never_resolves_to_a_diploma(self):
        # UPNM holds only the DIPLOMA of this programme.
        self.assertIsNone(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA KEJURUTERAAN AWAM', UPNM.upper()))
        self.assertEqual(op.programme_agreement(
            'TD-UPNM-DIP', 'IJAZAH SARJANA MUDA KEJURUTERAAN AWAM', UPNM.upper()), 'unknown')

    def test_the_diploma_letter_still_resolves_to_its_diploma(self):
        self.assertEqual(op.resolve_catalogue_course(
            'DIPLOMA KEJURUTERAAN AWAM', UPNM.upper())['course_id'], 'TD-UPNM-DIP')

    def test_the_same_level_degree_still_resolves(self):
        self.assertEqual(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA KEJURUTERAAN AWAM', UTHM.upper())['course_id'], 'TD-UTHM-SIVIL')

    def test_a_letter_with_no_level_word_is_judged_as_before(self):
        # No level to agree on: the old token rule stands (narrowing is for TERTIARY letters only).
        self.assertEqual(op.resolve_catalogue_course(
            'KEJURUTERAAN AWAM', UPNM.upper())['course_id'], 'TD-UPNM-DIP')


class SamePlaceProgrammeChangeTest(_Catalogue):
    """TD-331, at the confirm."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # A UTHM course whose NAME carries no level word — a confident resolve, an unprovable level.
        c = Course.objects.create(course_id='TD-UTHM-GEO', course='Sains Geomatik',
                                  level='Ijazah Sarjana Muda', department='x', field='x',
                                  field_key=FieldTaxonomy.objects.get(key='td145w'))
        CourseInstitution.objects.create(course=c, institution=cls.uthm)

    def _confirm(self, programme, institution=None):
        app = self._app('TD-UTHM-ANIM', 'Ijazah Sarjana Muda Teknologi Animasi',
                        institution=UTHM)
        self._offer(app, programme, institution or UTHM.upper())
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        return app

    def test_a_different_course_at_the_same_university_is_re_pinned(self):
        app = self._confirm('IJAZAH SARJANA MUDA KEJURUTERAAN AWAM')
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-SIVIL')
        # The sponsor card follows: before TD-331 it read the old course, Teknologi Animasi.
        self.assertEqual(programme_split(app)['title'], 'Ijazah Sarjana Muda Kejuruteraan Awam')

    def test_a_different_course_of_unprovable_level_drops_the_id(self):
        app = self._confirm('IJAZAH SARJANA MUDA SAINS GEOMATIK')
        self.assertNotIn('course_id', app.chosen_programme)

    def test_cannot_tell_keeps_the_id(self):
        # Seni Bina is not in UTHM's catalogue → programme_agreement 'unknown' → nothing stale.
        app = self._confirm('IJAZAH SARJANA MUDA SENI BINA')
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-ANIM')

    def test_a_sains_degree_keeps_the_id_rather_than_reading_a_false_clash(self):
        # TD-332 through the confirm: the resolver no longer finds stpm-sains, so nothing is stale.
        app = self._confirm(SAINS_DEGREE)
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-ANIM')

    def test_a_letter_with_no_level_word_keeps_the_id(self):
        # The resolver says another course, but the letter does not say what level it is: the
        # confirm does not act on a programme change it cannot place (the conservative half).
        self.assertEqual(op.programme_agreement('TD-UTHM-ANIM', 'KEJURUTERAAN AWAM', UTHM.upper()),
                         'clash')
        app = self._confirm('KEJURUTERAAN AWAM')
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-ANIM')

    def test_the_same_programme_keeps_the_id(self):
        app = self._confirm('IJAZAH SARJANA MUDA TEKNOLOGI ANIMASI')
        self.assertEqual(app.chosen_programme['course_id'], 'TD-UTHM-ANIM')

    def test_a_pre_u_confirm_is_untouched(self):
        # Never pre-U: a declared STPM student confirming a Form-6 letter keeps the pre-U shape.
        app = self._app('stpm-sains', 'Tingkatan Enam', pathway='stpm')
        self._offer(app, 'TINGKATAN ENAM SEMESTER 1 (SAINS)',
                    'SMK BANDAR TUN HUSSEIN ONN 2')
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')
        self.assertEqual(app.chosen_programme.get('course_id'), 'stpm-sains')


class LevelIsReadFromTheRightPlaceTest(_Catalogue):
    """The review's two fixes (2026-10-04): the LETTER's level comes from its programme first, and a
    COURSE's level from its own ``Course.level`` field (whole words of the name only if blank)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from apps.courses.models import Institution
        ft = FieldTaxonomy.objects.get(key='td145w')

        def course(cid, name, level, campus):
            c = Course.objects.create(course_id=cid, course=name, level=level, department='x',
                                      field='x', field_key=ft)
            CourseInstitution.objects.create(course=c, institution=campus)

        zen = Institution.objects.create(institution_id='td-zen', institution_name='Pusat Asasi Zentara',
                                         acronym='PAZ', type='UA', state='Johor')
        course('TD-ZEN-DIP', 'Diploma Pengurusan Zentara', 'Diploma', zen)
        course('TD-UTHM-HUB', 'Sarjana Muda Hubungan Antarabangsa (Diplomasi) dengan Kepujian',
               'Ijazah Sarjana Muda', cls.uthm)
        course('TD-UMK-ASASI-P', 'Program Asasi Pengurusan', 'Diploma', cls.umk)   # as UU0345001
        course('TD-UM-BLANK', 'Sarjana Muda Kajian Diplomasi', '', cls.um)

    def test_a_diploma_letter_at_an_asasi_named_place_reads_as_a_diploma(self):
        # The institution's "Asasi" used to win over the programme's "Diploma".
        self.assertEqual(op.resolve_catalogue_course(
            'DIPLOMA PENGURUSAN ZENTARA', 'PUSAT ASASI ZENTARA')['course_id'], 'TD-ZEN-DIP')

    def test_diplomasi_is_not_a_diploma(self):
        # RE-POINTED by TD-150 (2026-10-04). This letter omits the course's "(Diplomasi)", so it is
        # more general than the course and TD-150 now refuses the match on its own ("cannot tell" —
        # the next test). The LEVEL rule this test was written for is held with that one refusal
        # switched off: a course NAMED "Diplomasi" is not a diploma, so the degree letter still
        # reaches it. (A letter that PRINTS "(DIPLOMASI)" cannot show it: `detect_pathway_type`
        # reads the letter itself as a diploma by substring — TD-333.)
        from unittest import mock
        with mock.patch.object(op, 'names_a_specialisation_the_letter_does_not', return_value=False):
            self.assertEqual(op.resolve_catalogue_course(
                'IJAZAH SARJANA MUDA HUBUNGAN ANTARABANGSA', UTHM.upper())['course_id'], 'TD-UTHM-HUB')

    def test_a_letter_that_omits_the_specialisation_cannot_tell_td150(self):
        self.assertIsNone(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA HUBUNGAN ANTARABANGSA', UTHM.upper()))

    def test_the_level_field_decides_not_the_name(self):
        # "Program Asasi Pengurusan" is levelled Diploma in the catalogue (UU0345001's shape).
        self.assertEqual(op.resolve_catalogue_course(
            'DIPLOMA PENGURUSAN', 'UNIVERSITI MALAYSIA KELANTAN')['course_id'], 'TD-UMK-ASASI-P')

    def test_a_blank_level_falls_back_to_whole_words_of_the_name(self):
        self.assertEqual(op.resolve_catalogue_course(
            'IJAZAH SARJANA MUDA KAJIAN DIPLOMASI', 'UNIVERSITI MALAYA')['course_id'], 'TD-UM-BLANK')

    def test_course_levels_reads_whole_words_and_knows_when_it_cannot_tell(self):
        from types import SimpleNamespace as C
        from apps.scholarship.catalogue_levels import course_levels
        self.assertEqual(course_levels(C(level='Sijil Lanjutan', course='x')), {'diploma'})
        self.assertEqual(course_levels(C(level='Ijazah Sarjana Muda Pendidikan', course='x')),
                         {'degree', 'pismp'})
        self.assertEqual(course_levels(C(level='', course='Kajian Diplomasi')), set())
        self.assertEqual(course_levels(C(level='Pengajian Lain', course='Diploma X')), set())
