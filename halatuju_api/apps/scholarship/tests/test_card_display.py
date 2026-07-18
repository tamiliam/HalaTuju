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

    def test_clause_number(self):
        # #47: a bare numbered-clause header latched as a value — junk, never a real field.
        for s in ['2.4.', '2.5', '3', '(iv)', '(3)', '2.4.1']:
            self.assertTrue(cd.looks_like_clause_number(s), s)
        for s in ['Kolej Matrikulasi Perak', 'Tingkatan Enam', 'Sains Sosial', '']:
            self.assertFalse(cd.looks_like_clause_number(s), s)
        # sanitise drops a clause-number in either slot
        p, i, _rep = cd.sanitise_offer_slots('2.4.', 'Kolej Matrikulasi Perak')
        self.assertEqual((p, i), ('', 'Kolej Matrikulasi Perak'))

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
        cls.pismp = Course.objects.create(course_id='50PD040T00P', course='Bahasa Tamil Pendidikan Rendah (SJKT)',
                                          level='Ijazah Sarjana Muda', department='X', field='Edu', field_key=cls.tax)

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

    def test_course_appends_track_for_stpm_and_matric_only(self):
        stpm = self._app(chosen_programme={'course_name': 'Tingkatan Enam'},
                         chosen_pathway='stpm', pre_u_track='sains_sosial')
        self.assertEqual(cd.resolve_course(stpm), 'Tingkatan Enam (Sains Sosial)')
        matric = self._app(chosen_programme={'course_name': 'Program Matrikulasi'},
                           chosen_pathway='matric', pre_u_track='perakaunan')
        self.assertEqual(cd.resolve_course(matric), 'Program Matrikulasi (Perakaunan)')
        # A poly course carries no track even if a stray pre_u_track is set.
        poly = self._app(chosen_programme={'course_name': 'Diploma Kejuruteraan Mekanikal'},
                         chosen_pathway='poly', pre_u_track='sains')
        self.assertEqual(cd.resolve_course(poly), 'Diploma Kejuruteraan Mekanikal')

    def test_course_taxonomy_fallback(self):
        a = self._app(chosen_programme={}, field_of_study='zz_mek')
        self.assertEqual(cd.resolve_course(a), 'Mechanical')

    def test_course_sane_freetext_kept(self):
        a = self._app(chosen_programme={'course_name': 'Diploma Kejuruteraan Mekanikal'})
        self.assertEqual(cd.resolve_course(a), 'Diploma Kejuruteraan Mekanikal')

    def test_institution_rejects_date(self):
        a = self._app(chosen_programme={'institution': 'Tarikh dan Masa Daftar: 15 JUN 2026'})
        self.assertEqual(cd.resolve_institution(a), '')

    def test_institution_shows_school(self):
        # Owner 2026-07-17: a Form-6 school IS shown — it's the institution the student attends.
        a = self._app(chosen_programme={'institution': 'Sekolah Menengah Kebangsaan Maxwell'},
                      pre_u_institution='SMK Maxwell')
        self.assertEqual(cd.resolve_institution(a), 'Sekolah Menengah Kebangsaan Maxwell')

    def test_institution_single_source_no_preu_fallback(self):
        # ONLY chosen_programme.institution — never the pre_u_institution duplicate. Empty
        # cp.institution → '' (data is fixed at source, not papered over from pre_u).
        a = self._app(chosen_programme={'course_name': 'Tingkatan Enam'},
                      pre_u_institution='SMK Maxwell')
        self.assertEqual(cd.resolve_institution(a), '')

    def test_institution_sane_freetext_kept(self):
        a = self._app(chosen_programme={'institution': 'Politeknik Ungku Omar'})
        self.assertEqual(cd.resolve_institution(a), 'Politeknik Ungku Omar')

    # ── degree + specialisation split (PISMP) ────────────────────────────────────
    def test_pismp_split_pinned_bidang(self):
        # A pinned PISMP course: title = the constant degree, stream = the catalogue bidang.
        a = self._app(chosen_pathway='pismp',
                      chosen_programme={'course_id': '50PD040T00P',
                                        'course_name': 'Bahasa Tamil Pendidikan Rendah (SJKT)'})
        self.assertEqual(cd.programme_split(a),
                         {'title': 'Ijazah Sarjana Muda Perguruan',
                          'stream': 'Bahasa Tamil Pendidikan Rendah (SJKT)'})
        # The single-line sponsor form joins the two with a dash.
        self.assertEqual(cd.resolve_course(a),
                         'Ijazah Sarjana Muda Perguruan — Bahasa Tamil Pendidikan Rendah (SJKT)')

    def test_pismp_unpinned_shows_degree_alone(self):
        # An UNPINNED PISMP (no course_id — awaiting the Aliran/Bidang pick) must NOT echo the
        # generic offer course_name as the bidang; the degree stands alone until a course lands.
        a = self._app(chosen_pathway='pismp',
                      chosen_programme={'course_name': 'Program Ijazah Sarjana Muda Perguruan (PISMP)'})
        self.assertEqual(cd.programme_split(a),
                         {'title': 'Ijazah Sarjana Muda Perguruan', 'stream': ''})
        self.assertEqual(cd.resolve_course(a), 'Ijazah Sarjana Muda Perguruan')

    def test_split_stpm_matric_carry_track_others_bare(self):
        stpm = self._app(chosen_programme={'course_name': 'Tingkatan Enam'},
                         chosen_pathway='stpm', pre_u_track='sains_sosial')
        self.assertEqual(cd.programme_split(stpm),
                         {'title': 'Tingkatan Enam', 'stream': 'Sains Sosial'})
        poly = self._app(chosen_programme={'course_name': 'Diploma Kejuruteraan Mekanikal'},
                         chosen_pathway='poly')
        self.assertEqual(cd.programme_split(poly),
                         {'title': 'Diploma Kejuruteraan Mekanikal', 'stream': ''})


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


class TestTrackLabelParity(SimpleTestCase):
    """Cross-runtime single-source-of-truth GUARD for the pre-U track/stream Malay labels.

    The same code->label map is needed in two separately-deployed runtimes that cannot share one
    file while running: the backend ``card_display._TRACK_LABEL`` (sponsor card + emails, Python on
    the server) and the FE ``messages/ms.json`` (apply form + officer cockpit, JS in the browser).
    We keep a copy in each, and this test fails the build if they ever DRIFT — so the duplication
    can never silently disagree (option B, owner-approved 2026-07-18). It reads the FE JSON directly
    (Python can parse it); it SKIPS when the web folder isn't checked out (e.g. an api-only build
    context) rather than falsely failing."""

    # Codes present in the FE stream/track sets but deliberately NOT on the sponsor-card map — a
    # placeholder that never labels a real specialisation. Excluded from the parity comparison.
    _FE_ONLY = {'not_sure'}

    @staticmethod
    def _load_fe_track_labels():
        import json
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        ms_path = os.path.normpath(os.path.join(
            here, '..', '..', '..', '..', 'halatuju-web', 'src', 'messages', 'ms.json'))
        if not os.path.exists(ms_path):
            return None
        with open(ms_path, encoding='utf-8') as fh:
            ms = json.load(fh)
        plan = (((ms.get('scholarship') or {}).get('apply') or {}).get('plan') or {})
        merged = {**(plan.get('stream') or {}), **(plan.get('track') or {})}
        for k in TestTrackLabelParity._FE_ONLY:
            merged.pop(k, None)
        return merged

    def test_backend_and_frontend_track_labels_agree(self):
        fe = self._load_fe_track_labels()
        if fe is None:
            self.skipTest('halatuju-web/src/messages/ms.json not present (api-only checkout)')
        self.assertEqual(
            cd._TRACK_LABEL, fe,
            'Pre-U track labels have DRIFTED between the backend (card_display._TRACK_LABEL) and the '
            'FE (messages/ms.json scholarship.apply.plan.stream/.track). Update BOTH so the sponsor '
            'card and the officer cockpit render the same words.')
