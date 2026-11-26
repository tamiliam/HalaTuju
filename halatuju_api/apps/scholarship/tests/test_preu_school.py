"""Pre-U sprint (2026-11-26): the Angka Giliran's two shapes, the "pre-U studied at" field, and the
STPM / higher -> SPM switch's one explicit signal (`apps.courses.results_switch`)."""
from datetime import timedelta

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
        for status in ('withdrawn', 'expired', 'rejected'):   # rejected and not reopened
            with self.subTest(status=status):
                type(app).objects.filter(pk=app.pk).update(status=status)
                self.assertFalse(held_results_locked(app.profile))

    def test_a_closed_application_still_locks(self):
        """Review round 1: a closed case may have been awarded on the held results."""
        from apps.courses.results_switch import held_results_locked
        app = make_application('submitted', student=make_student(**STPM_HOLDER))
        type(app).objects.filter(pk=app.pk).update(status='closed')
        self.assertTrue(held_results_locked(app.profile))
        s = ProfileUpdateSerializer(app.profile, data={**SPM_SAVE, 'clear_held_results': True}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors['clear_held_results'][0].code, 'held_results_locked')

    def test_a_rejected_application_may_switch(self):
        app = make_application('submitted', student=make_student(**STPM_HOLDER))
        type(app).objects.filter(pk=app.pk).update(status='rejected')
        p = _save(app.profile, {**SPM_SAVE, 'clear_held_results': True})
        self.assertEqual(eq.results_held(p), 'spm')
        self.assertIsNotNone(p.held_results_cleared_at)           # round 2: the switch's stamp

    def test_a_reopened_rejected_application_still_locks(self):
        """Review round 2: a reopened rejection stays 'rejected' with decision_reopened_at set."""
        from django.utils import timezone
        from apps.courses.results_switch import held_results_locked
        app = make_application('submitted', student=make_student(**STPM_HOLDER))
        type(app).objects.filter(pk=app.pk).update(status='rejected', decision_reopened_at=timezone.now())
        self.assertTrue(held_results_locked(app.profile))
        s = ProfileUpdateSerializer(app.profile, data={**SPM_SAVE, 'clear_held_results': True}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors['clear_held_results'][0].code, 'held_results_locked')

    def test_the_switch_also_clears_the_koko_ask_marker_and_keeps_spm_valid_fields(self):
        p = make_student(**STPM_HOLDER, stpm_koko_unconfirmed=True, muet_band=4,
                         spm_prereq_grades={'bm': 'A'})
        p = _save(p, {**SPM_SAVE, 'clear_held_results': True})
        p.refresh_from_db()
        self.assertIsNone(p.stpm_koko_unconfirmed)
        self.assertEqual((p.muet_band, p.spm_prereq_grades), (4, {'bm': 'A'}))


def _switched():
    """A former STPM holder after the switch to SPM went through."""
    p = _save(make_student(**STPM_HOLDER), {**SPM_SAVE, 'clear_held_results': True})
    p.refresh_from_db()
    return p


def _after(p, seconds=60):
    """A completion time this long after the switch's stamp (negative = before it)."""
    return (p.held_results_cleared_at + timedelta(seconds=seconds)).isoformat()


class TestTheClearedResultsStayCleared(TestCase):
    """Review round 1: a stale browser copy of the cleared STPM / third-route results never
    comes back; a genuine move back to that exam still saves."""

    def _assert_spm_only(self, p):
        p.refresh_from_db()
        self.assertEqual(eq.results_held(p), 'spm')
        self.assertEqual((p.stpm_grades, p.stpm_cgpa, p.stpm_koko), ({}, None, None))
        self.assertEqual((p.higher_cgpa, p.higher_koko), (None, None))
        self.assertEqual(p.completed_qualifications, ['spm'])

    def test_a_second_device_resend_is_ignored(self):
        # Device 2 hydrated 'spm' from the server but still holds its STPM keys.
        p = _save(_switched(), {**SPM_SAVE, 'stpm_grades': STPM, 'stpm_cgpa': 3.5, 'stpm_koko': 8,
                                'name': 'D'})
        self._assert_spm_only(p)
        self.assertEqual(p.name, 'D')                       # the rest of the sync still saves

    def test_a_sign_in_resend_without_the_results_set_is_ignored(self):
        p = _save(_switched(), {'stpm_grades': STPM, 'stpm_cgpa': 3.5, 'higher_cgpa': 3.9})
        self._assert_spm_only(p)

    def test_a_lost_response_resend_is_ignored(self):
        # The clear went through but the answer was lost: the same browser syncs again, with its
        # STPM keys and the SPM completion it recorded on the grades page, and no clear.
        p = _switched()
        p = _save(p, {**SPM_SAVE, 'stpm_grades': STPM, 'stpm_cgpa': 3.5, 'stpm_koko_confirmed': True})
        self._assert_spm_only(p)

    def test_a_genuine_move_to_stpm_still_saves(self):
        p = _switched()
        p = _save(p, {'exam_type': 'stpm', 'results_exam_type': 'stpm', 'results_completed_at': _after(p),
                      'completed_qualifications': ['spm', 'stpm'], 'grades': SPM,
                      'stpm_grades': STPM, 'stpm_cgpa': 3.5})
        p.refresh_from_db()
        self.assertEqual(eq.results_held(p), 'stpm')
        self.assertEqual(p.stpm_grades, STPM)

    def test_a_genuine_move_to_matriculation_still_saves(self):
        from django.test import override_settings
        with override_settings(THIRD_ROUTE_OPEN=True):
            p = _switched()
            p = _save(p, {'exam_type': 'matric', 'results_exam_type': 'matric',
                          'results_completed_at': _after(p),
                          'completed_qualifications': ['spm', 'matric'], 'grades': SPM,
                          'higher_cgpa': 3.6, 'stpm_grades': STPM})
        p.refresh_from_db()
        self.assertEqual(eq.results_held(p), 'matric')
        self.assertEqual(p.higher_cgpa, 3.6)
        self.assertEqual(p.stpm_grades, {})                 # a matric write never revives STPM

    def test_a_stale_device_completion_is_ignored(self):
        """Review round 2: a second device still RECORDS STPM, completed before the switch (or with
        no time at all, an older web release) — the completion and its results are dropped."""
        for when in ('before', 'none'):
            with self.subTest(when=when):
                p = _switched()
                data = {'exam_type': 'stpm', 'results_exam_type': 'stpm', 'grades': SPM,
                        'completed_qualifications': ['spm', 'stpm'], 'stpm_grades': STPM,
                        'stpm_cgpa': 3.5, 'name': 'F'}
                if when == 'before':
                    data['results_completed_at'] = _after(p, -3600)
                p = _save(p, data)
                self._assert_spm_only(p)
                self.assertEqual((p.exam_type, p.results_exam_type, p.name), ('spm', 'spm', 'F'))

    def test_a_stale_device_cannot_overwrite_a_later_move_back(self):
        p = _switched()
        p = _save(p, {'results_exam_type': 'stpm', 'results_completed_at': _after(p),
                      'completed_qualifications': ['spm', 'stpm'], 'stpm_grades': STPM, 'stpm_cgpa': 3.5})
        p = _save(p, {'results_exam_type': 'stpm', 'results_completed_at': _after(p, -60),
                      'completed_qualifications': ['spm', 'stpm'], 'stpm_grades': {'PA': 'C'},
                      'stpm_cgpa': 2.0})
        p.refresh_from_db()
        self.assertEqual((eq.results_held(p), p.stpm_grades, p.stpm_cgpa), ('stpm', STPM, 3.5))

    def test_a_never_switched_student_needs_no_completion_time(self):
        p = make_student(**STPM_HOLDER)
        self.assertIsNone(p.held_results_cleared_at)
        p = _save(p, {'results_exam_type': 'stpm', 'completed_qualifications': ['spm', 'stpm'],
                      'stpm_grades': {'PA': 'B'}, 'stpm_cgpa': 3.0})
        self.assertEqual((p.stpm_grades, p.stpm_cgpa), ({'PA': 'B'}, 3.0))
        self.assertIsNone(p.held_results_cleared_at)

    def test_an_spm_student_with_no_history_moves_to_stpm_as_before(self):
        p = make_student(exam_type='spm', grades=SPM, results_exam_type='spm',
                         completed_qualifications=['spm'])
        p = _save(p, {'results_exam_type': 'stpm', 'completed_qualifications': ['spm', 'stpm'],
                      'stpm_grades': STPM, 'stpm_cgpa': 3.5})
        self.assertEqual(eq.results_held(p), 'stpm')


class TestTheBlankPreUStudiedAtOnThePut(TestCase):
    def test_a_blank_never_wipes_a_stored_one(self):
        p = _save(make_student(pre_u_studied_at='SMK A'), {'pre_u_studied_at': '  ', 'name': 'E'})
        p.refresh_from_db()
        self.assertEqual(p.pre_u_studied_at, 'SMK A')

    def test_a_change_to_another_one_passes(self):
        p = _save(make_student(pre_u_studied_at='SMK A'), {'pre_u_studied_at': 'SMK B'})
        self.assertEqual(p.pre_u_studied_at, 'SMK B')

    def test_the_signal_is_never_a_column(self):
        p = _save(make_student(), {'clear_held_results': True, 'name': 'C'})
        self.assertFalse(hasattr(p, 'clear_held_results') and p.clear_held_results is True)
