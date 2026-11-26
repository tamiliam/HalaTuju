"""Pre-U sprint (2026-11-26): the Angka Giliran's two shapes, the "pre-U studied at" field, and the
STPM / higher -> SPM switch's one explicit signal (`apps.courses.results_switch`)."""
from django.test import SimpleTestCase, TestCase

from apps.courses import angka_giliran as ag
from apps.courses import public as eq
from apps.courses.serializers import ProfileUpdateSerializer
from apps.scholarship import family
from apps.scholarship.services.profile_sync import build_intake_snapshot, sync_profile_fields
from apps.scholarship.tests.factories import make_application, make_student

SPM = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
STPM = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}
STPM_HOLDER = dict(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.5, stpm_koko=8,
                   results_exam_type='stpm', completed_qualifications=['spm', 'stpm'],
                   pre_u_studied_at='SMK CONTOH KAJANG', pre_u_institution='SMK CONTOH KAJANG')
MATRIC_HOLDER = dict(exam_type='matric', grades=SPM, higher_cgpa=3.5, higher_koko=8,
                     results_exam_type='matric', completed_qualifications=['spm', 'matric'])
#: What the onboarding sync sends after the SPM grades are saved.
SPM_SAVE = {'exam_type': 'spm', 'results_exam_type': 'spm', 'completed_qualifications': ['spm'],
            'grades': SPM}


def _save(profile, data):
    s = ProfileUpdateSerializer(profile, data=data, partial=True)
    assert s.is_valid(), s.errors
    return s.save()


class TestTheAngkaGiliranShapes(SimpleTestCase):
    def test_both_shapes_pass_and_are_normalised(self):
        for raw, want in [('AB123C456', 'AB123C456'), ('ab123c456', 'AB123C456'),
                          ('AB1234/5678', 'AB1234/5678'), (' ab 1234 / 5678 ', 'AB1234/5678'),
                          ('', '')]:
            with self.subTest(raw=raw):
                self.assertTrue(ag.is_valid(raw))
                self.assertEqual(ag.normalise(raw), want)

    def test_other_shapes_fail(self):
        for raw in ['AB123456', 'AB12345678', 'AB1234-5678', 'A1234/5678', 'AB123C45', 'AB1234/567',
                    '123C456AB', 'AB1234/56789']:
            with self.subTest(raw=raw):
                self.assertFalse(ag.is_valid(raw))

    def test_the_column_holds_the_stpm_shape(self):
        from apps.courses.models import StudentProfile
        self.assertEqual(StudentProfile._meta.get_field('angka_giliran').max_length, ag.MAX_LENGTH)
        self.assertEqual(len('AB1234/5678'), ag.MAX_LENGTH)


class TestTheAngkaGiliranOnTheProfileWrite(TestCase):
    def test_the_stpm_index_is_stored_normalised(self):
        p = _save(make_student(), {'angka_giliran': 'ab1234 / 5678'})
        self.assertEqual(p.angka_giliran, 'AB1234/5678')

    def test_a_bad_shape_is_refused(self):
        s = ProfileUpdateSerializer(make_student(), data={'angka_giliran': 'AB12-34'}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertIn('angka_giliran', s.errors)

    def test_the_stored_value_resent_unchanged_passes(self):
        p = make_student(angka_giliran='OLD12')
        self.assertEqual(_save(p, {'angka_giliran': 'OLD12', 'name': 'B'}).angka_giliran, 'OLD12')


class TestPreUStudiedAt(TestCase):
    def test_it_is_not_a_pathway_field(self):
        self.assertNotIn('pre_u_studied_at', family.PROFILE_PATHWAY_FIELDS)
        self.assertNotIn('pre_u_studied_at', family.OFFER_WRITTEN_PATHWAY_FIELDS)

    def test_the_profile_write_keeps_the_destination_untouched(self):
        p = make_student(pre_u_institution='KOLEJ MATRIKULASI PERAK')
        p = _save(p, {'pre_u_studied_at': 'SMK CONTOH KAJANG'})
        self.assertEqual(p.pre_u_studied_at, 'SMK CONTOH KAJANG')
        self.assertEqual(p.pre_u_institution, 'KOLEJ MATRIKULASI PERAK')

    def test_the_apply_form_writes_it_back_and_a_blank_never_wipes_it(self):
        p = make_student()
        self.assertIn('pre_u_studied_at', sync_profile_fields(p, {'pre_u_studied_at': 'SMK A'}))
        sync_profile_fields(p, {'pre_u_studied_at': '  '})
        p.refresh_from_db()
        self.assertEqual(p.pre_u_studied_at, 'SMK A')
        self.assertEqual(build_intake_snapshot(p, {})['profile']['pre_u_studied_at'], 'SMK A')


class TestTheSwitchToSpm(TestCase):
    def test_without_the_signal_the_guard_still_holds(self):
        p = _save(make_student(**STPM_HOLDER), dict(SPM_SAVE))
        self.assertEqual(eq.results_held(p), 'stpm')
        self.assertEqual(p.stpm_grades, STPM)

    def test_the_signal_clears_the_held_stpm_results(self):
        p = _save(make_student(**STPM_HOLDER), {**SPM_SAVE, 'clear_held_results': True,
                                                'stpm_grades': STPM, 'stpm_cgpa': 3.5})
        p.refresh_from_db()
        self.assertEqual(eq.results_held(p), 'spm')
        self.assertEqual((p.stpm_grades, p.stpm_cgpa, p.stpm_koko), ({}, None, None))
        self.assertEqual(p.completed_qualifications, ['spm'])
        self.assertEqual((p.exam_type, p.results_exam_type), ('spm', 'spm'))
        self.assertEqual(p.pre_u_studied_at, '')
        self.assertEqual(p.pre_u_institution, 'SMK CONTOH KAJANG')   # the pathway is not touched

    def test_the_signal_clears_the_held_third_route_results(self):
        p = _save(make_student(**MATRIC_HOLDER), {**SPM_SAVE, 'clear_held_results': True})
        p.refresh_from_db()
        self.assertEqual(eq.results_held(p), 'spm')
        self.assertEqual((p.higher_cgpa, p.higher_koko, p.higher_institution_type), (None, None, ''))

    def test_the_signal_without_the_spm_save_clears_nothing(self):
        for data in [{'clear_held_results': True},
                     {'clear_held_results': True, 'results_exam_type': 'spm'},
                     {'clear_held_results': True, 'grades': SPM},
                     {'clear_held_results': True, 'results_exam_type': 'stpm', 'grades': SPM}]:
            with self.subTest(data=data):
                p = _save(make_student(**STPM_HOLDER), data)
                p.refresh_from_db()
                self.assertEqual(eq.results_held(p), 'stpm')
                self.assertEqual(p.stpm_grades, STPM)

    def test_an_application_in_play_refuses_the_switch(self):
        app = make_application('submitted', student=make_student(**STPM_HOLDER))
        p = app.profile
        s = ProfileUpdateSerializer(p, data={**SPM_SAVE, 'clear_held_results': True}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors['clear_held_results'][0].code, 'held_results_locked')
        p.refresh_from_db()
        self.assertEqual(p.stpm_grades, STPM)

    def test_an_ended_application_does_not_lock(self):
        from apps.courses.results_switch import held_results_locked
        app = make_application('submitted', student=make_student(**STPM_HOLDER))
        self.assertTrue(held_results_locked(app.profile))
        type(app).objects.filter(pk=app.pk).update(status='withdrawn')
        self.assertFalse(held_results_locked(app.profile))

    def test_the_signal_is_never_a_column(self):
        p = _save(make_student(), {'clear_held_results': True, 'name': 'C'})
        self.assertFalse(hasattr(p, 'clear_held_results') and p.clear_held_results is True)
