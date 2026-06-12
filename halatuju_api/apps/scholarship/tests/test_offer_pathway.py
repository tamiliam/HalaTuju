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
from apps.scholarship import offer_pathway as op
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
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

    def test_parse_stpm_stream(self):
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1 (Sains Sosial)'), 'sains_sosial')
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1 (SAINS)'), 'sains')
        # No stream printed → '' (never guess).
        self.assertEqual(op.parse_stpm_stream('Tingkatan Enam Semester 1'), '')

    def test_name_aligns_subset_either_direction(self):
        # Catalogue ⊆ offer (offer carries a code prefix) → aligns.
        self.assertTrue(op._name_aligns({'dac', 'perakaunan'}, {'perakaunan'}))
        # A single shared generic-ish token is NOT enough (neither is a subset).
        self.assertFalse(op._name_aligns({'teknikal', 'malaysia', 'melaka'}, {'malaysia', 'sabah'}))


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


class TestAutofillPathwayFromOffer(_Base):
    def test_pre_u_undecided_settles_silently(self):
        app = self._app()
        self._offer(app, 'Tingkatan Enam Semester 1', 'SEKOLAH MENENGAH KEBANGSAAN TUN HUSSEIN ONN')
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')
        self.assertEqual(app.pre_u_institution, 'SEKOLAH MENENGAH KEBANGSAAN TUN HUSSEIN ONN')
        self.assertEqual(app.pre_u_track, '')   # no stream printed → left open
        self.assertEqual(app.chosen_programme['course_name'], 'Tingkatan Enam Semester 1')
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
