"""Offer-letter → chosen-pathway auto-fill (the undecided→decided case).

Pure detectors (no DB) + the conservative catalogue resolver + the
``services.autofill_pathway_from_offer`` orchestration (real ORM, the lesson-#55
rule: every attribute the code reads must resolve to a real value).
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import (
    Course, CourseInstitution, FieldTaxonomy, Institution, StudentProfile,
)
from apps.scholarship import card_display, offer_pathway as op
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.offer_parse import parse_govt_offer
from apps.scholarship.services import autofill_pathway_from_offer


# ───────────────────────── pure detectors (no DB) ──────────────────────────
class TestDetectors(SimpleTestCase):
    def test_detect_pre_u_stpm(self):
        self.assertEqual(op.detect_pathway_type('Tingkatan Enam Semester 1', 'SMK X'), 'stpm')
        self.assertTrue(op.is_pre_u('stpm'))

    def test_detect_matriculation(self):
        self.assertEqual(op.detect_pathway_type('Program Matrikulasi (Sains)', 'KM Kedah'), 'matric')
        self.assertTrue(op.is_pre_u('matric'))

    def test_detect_tertiary_not_pre_u(self):
        self.assertEqual(op.detect_pathway_type('DAC - DIPLOMA PERAKAUNAN', 'Politeknik'), 'diploma')
        self.assertEqual(op.detect_pathway_type('Asasi Perubatan', 'UPNM'), 'asasi')
        self.assertEqual(op.detect_pathway_type('Ijazah Sarjana Muda Kejuruteraan', 'UM'), 'degree')
        for t in ('diploma', 'asasi', 'degree', 'pismp', ''):
            self.assertFalse(op.is_pre_u(t))

    def test_detect_politeknik_fallback(self):
        # A bare polytechnic name (no programme keyword) → diploma (#125-class); a specific keyword wins.
        self.assertEqual(op.detect_pathway_type('', 'POLITEKNIK SULTAN IDRIS SHAH'), 'diploma')
        self.assertEqual(op.detect_pathway_type('Asasi Teknologi Kejuruteraan', 'Politeknik X'), 'asasi')

    def test_pathway_family_tertiary_collapse(self):
        # diploma/poly/degree/university all collapse to one 'tertiary' family (a university student
        # with a university diploma has NOT switched); pre-U tracks + pismp stay distinct.
        for t in ('diploma', 'poly', 'degree', 'university', 'ua', 'politeknik'):
            self.assertEqual(op.pathway_family(t), 'tertiary', t)
        self.assertEqual(op.pathway_family('Matriculation'), 'matric')   # legacy label
        self.assertEqual(op.pathway_family('random'), '')                # unknown → '' (never a switch)
        self.assertEqual(op.pathway_family('university'), op.pathway_family('diploma'))   # not a switch
        self.assertNotEqual(op.pathway_family('stpm'), op.pathway_family('pismp'))        # a real switch

    def test_parse_stpm_stream(self):
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1 (Sains Sosial)'), 'sains_sosial')
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1 (SAINS)'), 'sains')
        # No stream printed → '' (never guess).
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1'), '')

    def test_parse_matric_track(self):
        cases = {
            'Program Matrikulasi (Sains)': 'sains',
            'Program Matrikulasi Jurusan PERAKAUNAN': 'perakaunan',
            'Matriculation (Accounting)': 'perakaunan',
            'Program Matrikulasi Kejuruteraan': 'kejuruteraan',
            'Matriculation Engineering': 'kejuruteraan',
            'Program Matrikulasi Sains Komputer': 'sains_komputer',
            'Modul Computer Science': 'sains_komputer',
            # generic letter with no jurusan → '' (leave to the apply form / grades)
            'Program Matrikulasi Kementerian Pendidikan': '',
        }
        for raw, want in cases.items():
            self.assertEqual(op.parse_matric_track(raw), want, raw)

    def test_infer_stpm_bidang(self):
        # Science electives present → sains; none → sains_sosial.
        self.assertEqual(op.infer_stpm_bidang({'math': 'A'}, ['phy', 'chem', 'bio', 'addmath']), 'sains')
        self.assertEqual(op.infer_stpm_bidang({'bm': 'A', 'eng': 'A', 'geo': 'A', 'sci': 'A'}, []),
                         'sains_sosial')
        self.assertEqual(op.infer_stpm_bidang(None, None), 'sains_sosial')

    def test_infer_pismp_aliran(self):
        import types
        ns = types.SimpleNamespace
        # Vernacular SPM subject → the matching school stream (lowercase code the picker uses); else sk.
        self.assertEqual(op.infer_pismp_aliran(ns(grades={'bahasa_tamil': 'A', 'bm': 'B'})), 'sjkt')
        self.assertEqual(op.infer_pismp_aliran(ns(grades={'b_cina': 'A'})), 'sjkc')
        self.assertEqual(op.infer_pismp_aliran(ns(grades={'bm': 'A', 'math': 'A'})), 'sk')
        self.assertEqual(op.infer_pismp_aliran(ns(stream_subjects=['bahasa_tamil'])), 'sjkt')
        self.assertEqual(op.infer_pismp_aliran(None), 'sk')

    def test_canonical_pre_u_course(self):
        self.assertEqual(op.canonical_pre_u_course('matric'), 'Program Matrikulasi')
        self.assertEqual(op.canonical_pre_u_course('stpm'), 'Tingkatan Enam')
        for t in ('poly', 'asasi', 'pismp', 'university', '', None):
            self.assertEqual(op.canonical_pre_u_course(t), '')

    def test_preu_course_id(self):
        self.assertEqual(op.preu_course_id('matric', 'perakaunan'), 'matric-perakaunan')
        self.assertEqual(op.preu_course_id('matric', 'sains_komputer'), 'matric-sains-komputer')
        self.assertEqual(op.preu_course_id('stpm', 'sains_sosial'), 'stpm-sains-sosial')
        self.assertEqual(op.preu_course_id('poly', 'whatever'), '')

    def test_clean_school_name(self):
        # ALL-CAPS full form → Title Case, identity unchanged.
        self.assertEqual(op.clean_school_name('SEKOLAH MENENGAH KEBANGSAAN MAXWELL', ''),
                         'Sekolah Menengah Kebangsaan Maxwell')
        # Picks the address-free value over the address blob, then expands the acronym to full.
        self.assertEqual(
            op.clean_school_name('SEKOLAH MENENGAH KEBANGSAAN SEBERANG JAYA, 13700 PERAI', 'SMK SEBERANG JAYA'),
            'Sekolah Menengah Kebangsaan Seberang Jaya')
        # Prefers the fuller form when both are address-free (full > abbreviation).
        self.assertEqual(op.clean_school_name('KOLEJ TINGKATAN ENAM SRI ISTANA', 'KTE SRI ISTANA'),
                         'Kolej Tingkatan Enam Sri Istana')
        self.assertEqual(op.clean_school_name('', ''), '')

    def test_title_case_programme(self):
        # The live bug: a shouty offer programme → Title Case, with "(PISMP)" kept as an acronym.
        self.assertEqual(
            op.title_case_programme('PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)'),
            'Program Ijazah Sarjana Muda Perguruan (PISMP)')
        # Connectors lower-cased (never the first word); short parenthetical acronym kept upper.
        self.assertEqual(
            op.title_case_programme('DIPLOMA PENGURUSAN LOGISTIK DAN RANTAIAN BEKALAN'),
            'Diploma Pengurusan Logistik dan Rantaian Bekalan')
        self.assertEqual(
            op.title_case_programme('DIPLOMA KEJURUTERAAN ELEKTRONIK (KOMUNIKASI)'),
            'Diploma Kejuruteraan Elektronik (Komunikasi)')
        # An ALREADY mixed-case name is returned byte-for-byte — we never re-case a styled name.
        for already in ('Diploma Teknologi Maklumat (Software & App Development)',
                        'Bachelor of Computer Science', 'Asasipintar UKM #'):
            self.assertEqual(op.title_case_programme(already), already)
        # Idempotent + empty-safe.
        once = op.title_case_programme('PROGRAM IJAZAH SARJANA MUDA PERGURUAN (PISMP)')
        self.assertEqual(op.title_case_programme(once), once)
        self.assertEqual(op.title_case_programme(''), '')

    def test_name_aligns_subset_either_direction(self):
        # Catalogue ⊆ offer (offer carries a code prefix) → aligns.
        self.assertTrue(op._name_aligns({'dac', 'perakaunan'}, {'perakaunan'}))
        # A single shared generic-ish token is NOT enough (neither is a subset).
        self.assertFalse(op._name_aligns({'teknikal', 'malaysia', 'melaka'}, {'malaysia', 'sabah'}))


# ───────────── clause-number guard (#47: numbered-clause tokens as data) ────
_STPM_HEAD = [
    'KEMENTERIAN PENDIDIKAN MALAYSIA',
    'SEKTOR OPERASI SEKOLAH',
    'TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026',
    'Nama : TAMOTHARAN A/L GUNASEGARAN',
    'No. Kad Pengenalan : 080101-01-1234',
]


class TestClauseNumberGuard(SimpleTestCase):
    def test_detector_flags_only_numbering(self):
        for junk in ('2.4.', '2.5.', '2', '2.4', '3)', '(iv)', ' 2.6. ', '(i).'):
            self.assertTrue(card_display.looks_like_clause_number(junk), junk)
        for real in ('SAINS SOSIAL', 'KOLEJ TINGKATAN ENAM SRI ISTANA',
                     'Politeknik Ungku Omar', '1 JULAI 2026', 'sains', '', 'Civil'):
            self.assertFalse(card_display.looks_like_clause_number(real), real)

    def test_sanitise_drops_clause_number_from_either_slot(self):
        # A numbered-clause header in either slot is never stored.
        prog, inst, _rep = card_display.sanitise_offer_slots('2.4.', '2.5.')
        self.assertEqual((prog, inst), ('', ''))
        prog, inst, _rep = card_display.sanitise_offer_slots('Tingkatan Enam', '2.5.')
        self.assertEqual((prog, inst), ('Tingkatan Enam', ''))

    def test_parser_defers_to_gemini_on_clause_number(self):
        # A glued Form-6 OCR where the section labels' values are the NEXT clause numbers →
        # the deterministic read latches '2.5.'/'2.6.' as stream/institution → defer to Gemini.
        text = '\n'.join(_STPM_HEAD + [
            '2.4. Bidang : 2.5.',
            '2.5. Pusat Tingkatan Enam : 2.6.',
            '2.6. Tarikh Lapor Diri : 1 JULAI 2026',
        ])
        self.assertIsNone(parse_govt_offer(text))

    def test_parser_reads_clean_stpm_values(self):
        # Control: the same layout with REAL values reads cleanly (guard isn't over-eager).
        text = '\n'.join(_STPM_HEAD + [
            '2.4. Bidang : SAINS SOSIAL',
            '2.5. Pusat Tingkatan Enam : KOLEJ TINGKATAN ENAM SRI ISTANA',
            '2.6. Tarikh Lapor Diri : 1 JULAI 2026',
        ])
        parsed = parse_govt_offer(text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['stream'], 'SAINS SOSIAL')
        self.assertEqual(parsed['institution'], 'KOLEJ TINGKATAN ENAM SRI ISTANA')
        self.assertFalse(card_display.looks_like_clause_number(parsed['institution']))


# ──────────────────── catalogue resolver + auto-fill (DB) ───────────────────
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.ft = FieldTaxonomy.objects.create(
            key='acc', name_en='Accounting', name_ms='Perakaunan', name_ta='கணக்கியல்',
            image_slug='acc')

    def _app(self, **over):
        prof = StudentProfile.objects.create(
            supabase_user_id=f'op-{self.id()}-{over.get("tag", "")}',
            name=over.pop('name', 'SWETHA A/P PILAAPPARAO'),
            nric=over.pop('nric', '081011-01-1416'))
        defaults = dict(cohort=self.cohort, profile=prof, status='profile_complete',
                        chosen_pathway='', pre_u_institution='', pre_u_track='',
                        pathways_considered=['stpm'], pathway_certainty='uncertain',
                        chosen_programme={})
        over.pop('tag', None)
        defaults.update(over)
        return ScholarshipApplication.objects.create(**defaults)

    def _offer(self, app, programme, institution, *, name=None, nric=None, verdict='ok'):
        prof = app.profile
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {
                'candidate_name': name if name is not None else prof.name,
                'candidate_nric': (nric if nric is not None else prof.nric).replace('-', ''),
                'programme': programme, 'institution': institution},
                'student_verdict': verdict, 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())


class TestResolveCatalogueCourse(_Base):
    def setUp(self):
        self.psp = Institution.objects.create(
            institution_id='psp', institution_name='Politeknik Seberang Perai',
            type='Politeknik', state='Pulau Pinang')
        self.course = Course.objects.create(
            course_id='DAC', course='Diploma Perakaunan', level='Diploma',
            department='Commerce', field='Accounting', field_key=self.ft)
        CourseInstitution.objects.create(course=self.course, institution=self.psp)

    def test_confident_unique_match_returns_course_id(self):
        m = op.resolve_catalogue_course('DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        self.assertIsNotNone(m)
        self.assertEqual(m['course_id'], 'DAC')
        self.assertEqual(m['course_name'], 'Diploma Perakaunan')

    def test_no_institution_match_returns_none(self):
        self.assertIsNone(op.resolve_catalogue_course('DIPLOMA PERAKAUNAN', 'Politeknik Kuching'))

    def test_ambiguous_two_courses_returns_none(self):
        kuc = Institution.objects.create(
            institution_id='pks', institution_name='Politeknik Kuching Sarawak',
            type='Politeknik', state='Sarawak')
        kuc2 = Institution.objects.create(
            institution_id='pk', institution_name='Politeknik Kuching',
            type='Politeknik', state='Sarawak')
        for cid, inst in (('DIT1', kuc), ('DIT2', kuc2)):
            c = Course.objects.create(course_id=cid, course='Diploma Teknologi Maklumat',
                                      level='Diploma', department='IT', field='IT', field_key=self.ft)
            CourseInstitution.objects.create(course=c, institution=inst)
        # Both institutions align with the offer text; two distinct course_ids → ambiguous.
        self.assertIsNone(op.resolve_catalogue_course(
            'DIPLOMA TEKNOLOGI MAKLUMAT', 'POLITEKNIK KUCHING SARAWAK'))


class TestCatalogueInstitution(_Base):
    def setUp(self):
        self.psp = Institution.objects.create(
            institution_id='psp', institution_name='Politeknik Seberang Perai',
            type='Politeknik', state='Pulau Pinang')
        self.c = Course.objects.create(
            course_id='DAC', course='Diploma Perakaunan', level='Diploma',
            department='Commerce', field='Accounting', field_key=self.ft)
        CourseInstitution.objects.create(course=self.c, institution=self.psp)

    def test_single_institution_canonical(self):
        # Offer OCR variant → catalogue canonical name.
        self.assertEqual(
            op.catalogue_institution('DAC', 'POLITEKNIK SEBERANG PERAI (POLITEKNIK PREMIER)'),
            'Politeknik Seberang Perai')

    def test_unknown_course_id(self):
        self.assertEqual(op.catalogue_institution('NOPE', 'x'), '')

    def test_conflict_is_not_swapped(self):
        # course_id's institution is a DIFFERENT place than recorded → never overwrite
        # (a wrong/imprecise course_id to surface, not an OCR variant to iron out).
        self.assertEqual(op.catalogue_institution('DAC', 'Universiti Malaya'), '')

    def test_ambiguous_multiple_matches_returns_blank(self):
        # A hint that aligns with >1 campus of the course is ambiguous → '' (never guess).
        a = Institution.objects.create(institution_id='i1', institution_name='Kolej Tingkatan Enam Sri Istana',
                                       type='School', state='Selangor')
        b = Institution.objects.create(institution_id='i2', institution_name='Kolej Tingkatan Enam Sri Putera',
                                       type='School', state='Perak')
        c = Course.objects.create(course_id='stpm-x', course='T6', level='Pra-U',
                                  department='x', field='x', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=a)
        CourseInstitution.objects.create(course=c, institution=b)
        self.assertEqual(op.catalogue_institution('stpm-x', 'Sekolah Sri'), '')   # {sri} ⊆ both

    def test_generic_name_acronym_strips(self):
        # Catalogue name has no distinctive tokens (all generic) → normalised-equality fallback
        # still irons out a "(UKM)"-style acronym to the canonical form.
        ukm = Institution.objects.create(institution_id='ukm', institution_name='Universiti Kebangsaan Malaysia',
                                         type='University', state='Selangor')
        c = Course.objects.create(course_id='UK1', course='Asasi Sains', level='Asasi',
                                  department='Sci', field='Science', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=ukm)
        self.assertEqual(op.catalogue_institution('UK1', 'Universiti Kebangsaan Malaysia (UKM)'),
                         'Universiti Kebangsaan Malaysia')

    def test_ambiguous_resolved_by_hint_else_blank(self):
        kuc = Institution.objects.create(
            institution_id='pks', institution_name='Politeknik Kuching Sarawak',
            type='Politeknik', state='Sarawak')
        CourseInstitution.objects.create(course=self.c, institution=kuc)
        self.assertEqual(op.catalogue_institution('DAC', 'Politeknik Seberang Perai'),
                         'Politeknik Seberang Perai')
        self.assertEqual(op.catalogue_institution('DAC', ''), '')   # no hint → never guess


class TestAutofillPathwayFromOffer(_Base):
    def test_pre_u_undecided_settles_silently(self):
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1', 'SEKOLAH MENENGAH KEBANGSAAN TUN HUSSEIN ONN')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')
        self.assertEqual(app.pre_u_institution, 'SEKOLAH MENENGAH KEBANGSAAN TUN HUSSEIN ONN')
        # No stream on the offer + no science electives on the SPM record → default bidang.
        self.assertEqual(app.pre_u_track, 'sains_sosial')
        # Course name is standardised (the raw "...Semester 1" is dropped; stream → track).
        self.assertEqual(app.chosen_programme['course_name'], 'Tingkatan Enam')
        self.assertEqual(app.chosen_programme['source'], 'offer_letter_auto')
        self.assertNotIn('course_id', app.chosen_programme)   # pre-U: no catalogue id
        self.assertEqual(app.pathway_certainty, 'sure')        # "exploring" cleared
        self.assertIsNone(app.pathway_confirmed_at)            # NOT stamped (keeps clash detection)

    def test_pre_u_stream_is_parsed(self):
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1 (Sains Sosial)', 'SMK Tinggi Port Dickson')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_track, 'sains_sosial')

    def test_tertiary_confident_match_sets_course_id(self):
        Institution.objects.create(institution_id='psp', institution_name='Politeknik Seberang Perai',
                                   type='Politeknik', state='Pulau Pinang')
        c = Course.objects.create(course_id='DAC', course='Diploma Perakaunan', level='Diploma',
                                  department='Commerce', field='Accounting', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=Institution.objects.get(institution_id='psp'))
        app = self._app()
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('course_id'), 'DAC')
        self.assertEqual(app.chosen_programme['source'], 'offer_letter_auto')
        self.assertEqual(app.chosen_pathway, '')   # tertiary: pathway_type left to the programme

    def test_tertiary_no_catalogue_match_falls_to_labels(self):
        app = self._app()
        self._offer(app, 'DIPLOMA SENI BINA', 'KOLEJ SWASTA TIADA DALAM KATALOG')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_name'], 'DIPLOMA SENI BINA')
        self.assertNotIn('course_id', app.chosen_programme)

    def test_genuine_clash_does_not_autofill(self):
        # Student locked a SPECIFIC course; the offer is a different field → confirm-query case.
        app = self._app(chosen_programme={'course_name': 'Asasi Perubatan', 'institution': ''})
        self._offer(app, 'Program ASASIpintar UKM', "Kolej Pendeta Za'ba, UKM")
        self.assertFalse(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_name'], 'Asasi Perubatan')  # untouched
        self.assertEqual(app.pathway_certainty, 'uncertain')                       # not flipped

    def test_wrong_person_offer_does_not_autofill(self):
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1', 'SMK X',
                    name='YESWINDRAN A/L MURALY', nric='081227020661')
        self.assertFalse(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, '')

    def test_no_offer_letter_is_noop(self):
        app = self._app()
        self.assertFalse(autofill_pathway_from_offer(app))

    def test_idempotent(self):
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1', 'SMK Tun Hussein Onn')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        # Second run changes nothing → False.
        self.assertFalse(autofill_pathway_from_offer(app))

    def test_locked_specific_pick_is_protected(self):
        # Already 'sure' with a precise catalogue id + the offer agrees → nothing to do.
        app = self._app(pathway_certainty='sure',
                        chosen_programme={'course_id': 'DAC', 'course_name': 'Diploma Perakaunan',
                                          'institution': 'Politeknik Seberang Perai'})
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        self.assertFalse(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'DAC')

    def test_matric_track_parsed_from_offer(self):
        app = self._app(pathways_considered=['matric'])
        self._offer(app, 'Program Matrikulasi Jurusan PERAKAUNAN', 'KOLEJ MATRIKULASI SELANGOR')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'matric')
        self.assertEqual(app.pre_u_track, 'perakaunan')
        # Course name standardised (jurusan is carried by pre_u_track, not the course string).
        self.assertEqual(app.chosen_programme['course_name'], 'Program Matrikulasi')

    def test_stpm_bidang_inferred_from_science_grades(self):
        app = self._app()
        app.profile.grades = {'phy': 'B', 'chem': 'B', 'bio': 'C', 'addmath': 'C', 'math': 'A'}
        app.profile.save(update_fields=['grades'])
        self._offer(app, 'Tingkatan Enam Semester 1', 'SMK X')   # no stream on the letter
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.pre_u_track, 'sains')

    def test_locked_pre_u_still_gets_track_standardised(self):
        # A locked STPM pick with a blank track still gets the track filled (the track is a
        # property of the student, not of the locked chosen-programme record).
        app = self._app(chosen_pathway='stpm', pathway_certainty='sure', pre_u_track='',
                        chosen_programme={'course_id': 'STPM-X', 'course_name': 'Tingkatan Enam',
                                          'institution': 'SMK X'})
        self._offer(app, 'Tingkatan Enam Semester 1 (Sains Sosial)', 'SMK X')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.pre_u_track, 'sains_sosial')
        self.assertEqual(app.chosen_programme['course_id'], 'STPM-X')   # locked pick untouched

    def test_institution_aligned_to_catalogue_even_when_locked(self):
        # A locked, catalogue-linked tertiary pick whose institution drifted (offer OCR
        # variant) is re-aligned to the recommender catalogue — single source of truth.
        Institution.objects.create(institution_id='psp', institution_name='Politeknik Seberang Perai',
                                   type='Politeknik', state='Pulau Pinang')
        c = Course.objects.create(course_id='DAC', course='Diploma Perakaunan', level='Diploma',
                                  department='Commerce', field='Accounting', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=Institution.objects.get(institution_id='psp'))
        app = self._app(pathway_certainty='sure',
                        chosen_programme={'course_id': 'DAC', 'course_name': 'Diploma Perakaunan',
                                          'institution': 'POLITEKNIK SEBERANG PERAI (POLITEKNIK PREMIER)'})
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Politeknik Seberang Perai')
        self.assertEqual(app.chosen_programme['course_id'], 'DAC')

    def test_clause_number_institution_never_stored(self):
        # #47: a stored offer whose institution is a leaked clause number must not reach ANY
        # field — not chosen_programme, not pre_u_institution.
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1', '2.5.')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertFalse(card_display.looks_like_clause_number(app.pre_u_institution))
        self.assertNotEqual(app.pre_u_institution, '2.5.')
        stored_inst = (app.chosen_programme or {}).get('institution', '')
        self.assertFalse(card_display.looks_like_clause_number(stored_inst))

    def test_blank_institution_filled_from_offer_hint_multicampus(self):
        # Multi-campus course + blank stored institution → disambiguate via the OFFER's
        # institution (Velan #76 case: POLY-DIP-019 at 18 polys, offer names Ungku Omar).
        puo = Institution.objects.create(institution_id='puo', institution_name='Politeknik Ungku Omar',
                                         type='Politeknik', state='Perak')
        psp = Institution.objects.create(institution_id='psp2', institution_name='Politeknik Seberang Perai',
                                         type='Politeknik', state='Pulau Pinang')
        c = Course.objects.create(course_id='POLY-X', course='Diploma Kejuruteraan Mekanikal', level='Diploma',
                                  department='Eng', field='Eng', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=puo)
        CourseInstitution.objects.create(course=c, institution=psp)
        app = self._app(pathway_certainty='sure',
                        chosen_programme={'course_id': 'POLY-X', 'course_name': 'Diploma Kejuruteraan Mekanikal'})
        self._offer(app, 'DKM - DIPLOMA KEJURUTERAAN MEKANIKAL', 'POLITEKNIK UNGKU OMAR (POLITEKNIK PREMIER)')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Politeknik Ungku Omar')


class TestPolyInstitutionFromLiveOffer(_Base):
    """Read-time poly-campus disambiguation (owner 2026-07-17): the cockpit serves a blank
    poly-diploma institution filled LIVE from the offer, so display never waits on a re-run."""
    def setUp(self):
        # One POLY diploma at TWO campuses → catalogue_single_institution can't disambiguate;
        # only the offer names the real one.
        self.psp = Institution.objects.create(institution_id='psp', institution_name='Politeknik Seberang Perai',
                                              type='Politeknik', state='Pulau Pinang')
        self.puo = Institution.objects.create(institution_id='puo', institution_name='Politeknik Ungku Omar',
                                              type='Politeknik', state='Perak')
        c = Course.objects.create(course_id='POLY-DIP-049', course='Diploma Perakaunan', level='Diploma',
                                  department='Commerce', field='Accounting', field_key=self.ft)
        CourseInstitution.objects.create(course=c, institution=self.psp)
        CourseInstitution.objects.create(course=c, institution=self.puo)

    def _poly_app(self, **over):
        cp = over.pop('chosen_programme', {'course_id': 'POLY-DIP-049', 'course_name': 'Diploma Perakaunan'})
        return self._app(chosen_programme=cp, chosen_pathway='poly', pathway_certainty='sure', **over)

    def test_resolves_valid_campus_from_offer(self):
        app = self._poly_app()
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        self.assertEqual(op.poly_institution_from_live_offer(app), 'Politeknik Seberang Perai')

    def test_non_poly_course_is_blank(self):
        # A degree pick is out of scope — never fill (owner: BrightPath doesn't cover degrees).
        app = self._app(chosen_programme={'course_id': 'UU6380001', 'course_name': 'Law'}, chosen_pathway='')
        self._offer(app, 'SARJANA MUDA UNDANG-UNDANG', 'Universiti Utara Malaysia')
        self.assertEqual(op.poly_institution_from_live_offer(app), '')

    def test_no_offer_is_blank(self):
        self.assertEqual(op.poly_institution_from_live_offer(self._poly_app()), '')

    def test_wrong_person_offer_is_blank(self):
        app = self._poly_app()
        self._offer(app, 'DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI',
                    name='SOMEONE ELSE', nric='990101010101')
        self.assertEqual(op.poly_institution_from_live_offer(app), '')

    def test_offer_campus_not_of_course_is_blank(self):
        # Offer names a polytechnic that isn't a campus of THIS course → never contradict.
        app = self._poly_app()
        self._offer(app, 'DIPLOMA PERAKAUNAN', 'Politeknik Kota Bharu')
        self.assertEqual(op.poly_institution_from_live_offer(app), '')

    def test_serializer_fills_blank_poly_institution(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = self._poly_app()
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        cp = AdminApplicationDetailSerializer().get_chosen_programme(app)
        self.assertEqual(cp['institution'], 'Politeknik Seberang Perai')

    def test_serializer_preserves_non_blank_institution(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = self._poly_app(chosen_programme={'course_id': 'POLY-DIP-049',
            'course_name': 'Diploma Perakaunan', 'institution': 'Politeknik Ungku Omar'})
        self._offer(app, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        cp = AdminApplicationDetailSerializer().get_chosen_programme(app)
        self.assertEqual(cp['institution'], 'Politeknik Ungku Omar')   # never overwritten
