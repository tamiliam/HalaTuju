"""STPM CGPA sprint C4 (2026-10-28) — the two Check-2 asks that complete an STPM student's results
(`apps/scholarship/stpm_asks.py`), the marker's writer, the one-off flag command, and the 0.01 CGPA
match. Synthetic data only — no real student.
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.courses.models import StudentProfile
from apps.courses.serializers import ProfileUpdateSerializer
from apps.scholarship import stpm_asks
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.higher_results import student_higher_check
from apps.scholarship.models import ApplicantDocument, ResolutionItem

from .factories import TEST_JWT_SECRET, authed_client, make_application, make_student

FULL = {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+'}      # PNGK 3.67
SHORT = {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'}                       # PA + two: no PNGK
STPM = dict(exam_type='stpm', results_exam_type='stpm', grades={'bm': 'A'},
            completed_qualifications=['spm', 'stpm'], stpm_cgpa=3.67, stpm_koko=8.0)


def _app(stage='profile_complete', **profile):
    student = make_student(name='Test Calon', nric='030101-14-5678', **{**STPM, 'stpm_grades': FULL, **profile})
    return make_application(stage, student=student)


def _item(app, code):
    return ResolutionItem.objects.filter(application=app, source='check2', code=code).first()


class TestTheGradesAsk(TestCase):
    def test_raised_when_fewer_than_pa_and_three(self):
        app = _app(stpm_grades=SHORT)
        sync_check2_queries(app)
        item = _item(app, stpm_asks.GRADES_CODE)
        self.assertEqual((item.status, item.kind, item.fact), ('open', 'explanation', 'academic'))

    def test_not_raised_when_the_grades_give_a_pngk(self):
        app = _app()
        sync_check2_queries(app)
        self.assertIsNone(_item(app, stpm_asks.GRADES_CODE))

    def test_not_raised_before_submit_nor_for_an_spm_holder(self):
        app = _app('submitted', stpm_grades=SHORT)
        self.assertEqual(stpm_asks.wanted(app), set())
        spm = make_application('profile_complete', student=make_student(
            name='Test Dua', nric='030202-14-5678', exam_type='spm', grades={'bm': 'A'}))
        sync_check2_queries(spm)
        self.assertFalse(ResolutionItem.objects.filter(application=spm, code__in=stpm_asks.CODES).exists())

    def test_auto_resolves_when_the_grades_are_completed(self):
        app = _app(stpm_grades=SHORT)
        sync_check2_queries(app)
        StudentProfile.objects.filter(pk=app.profile.pk).update(stpm_grades=FULL)
        app.refresh_from_db()
        sync_check2_queries(app)
        item = _item(app, stpm_asks.GRADES_CODE)
        self.assertEqual((item.status, item.resolved_by), ('resolved', 'system'))

    def test_a_system_close_reopens_if_the_gap_returns_but_a_student_answer_stands(self):
        app = _app(stpm_grades=SHORT)
        sync_check2_queries(app)
        item = _item(app, stpm_asks.GRADES_CODE)
        item.status, item.resolved_by = 'resolved', 'system'
        item.save()
        sync_check2_queries(app)
        self.assertEqual(_item(app, stpm_asks.GRADES_CODE).status, 'open')
        ResolutionItem.objects.filter(pk=item.pk).update(status='resolved', resolved_by='student')
        sync_check2_queries(app)
        self.assertEqual(_item(app, stpm_asks.GRADES_CODE).status, 'resolved')

    def test_a_form_six_students_exploratory_grades_are_never_asked(self):
        # Declared STPM, a few course-guide grades, no completion recorded and no typed CGPA.
        app = _app(stpm_grades=SHORT, results_exam_type='', completed_qualifications=[], stpm_cgpa=None)
        self.assertFalse(stpm_asks.holds_completed_stpm(app.profile))
        sync_check2_queries(app)
        self.assertIsNone(_item(app, stpm_asks.GRADES_CODE))

    def test_a_legacy_holder_with_only_a_typed_cgpa_is_asked(self):
        app = _app(stpm_grades={}, results_exam_type='', completed_qualifications=[], stpm_cgpa=3.40)
        self.assertTrue(stpm_asks.holds_completed_stpm(app.profile))
        sync_check2_queries(app)
        self.assertEqual(_item(app, stpm_asks.GRADES_CODE).status, 'open')

    def test_not_raised_once_the_machine_may_no_longer_ask(self):
        app = _app('interviewing', stpm_grades=SHORT)
        sync_check2_queries(app)
        self.assertIsNone(_item(app, stpm_asks.GRADES_CODE))


class TestTheKokoAsk(TestCase):
    def test_raised_only_when_flagged(self):
        flagged = _app(stpm_koko_unconfirmed=True)
        sync_check2_queries(flagged)
        self.assertEqual(_item(flagged, stpm_asks.KOKO_CODE).status, 'open')
        for value in (None, False):
            with self.subTest(flag=value):
                app = make_application('profile_complete', student=make_student(
                    name='Test Calon', nric=f'03010{1 if value is None else 2}-14-5679',
                    **STPM, stpm_grades=FULL, stpm_koko_unconfirmed=value))
                sync_check2_queries(app)
                self.assertIsNone(_item(app, stpm_asks.KOKO_CODE))

    def test_auto_resolves_when_the_writer_clears_the_flag(self):
        app = _app(stpm_koko_unconfirmed=True)
        sync_check2_queries(app)
        s = ProfileUpdateSerializer(app.profile, data={'stpm_grades': FULL, 'stpm_koko': 9.0,
                                                       'stpm_koko_confirmed': True}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        app.refresh_from_db()
        self.assertIs(app.profile.stpm_koko_unconfirmed, False)
        sync_check2_queries(app)
        self.assertEqual(_item(app, stpm_asks.KOKO_CODE).status, 'resolved')


class TestTheWriterClearsTheFlag(TestCase):
    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_a_score_saved_through_the_onboarding_step_clears_it(self):
        p = make_student(**STPM, stpm_grades=FULL, stpm_koko_unconfirmed=True)
        saved = self._save(p, {'stpm_koko': 7.0, 'stpm_koko_confirmed': True})
        self.assertEqual((saved.stpm_koko, saved.stpm_koko_unconfirmed), (7.0, False))

    def test_a_sign_in_resend_without_the_confirmation_does_not(self):
        p = make_student(**STPM, stpm_grades=FULL, stpm_koko_unconfirmed=True)
        self.assertIs(self._save(p, {'stpm_koko': 8.0}).stpm_koko_unconfirmed, True)

    def test_the_confirmation_needs_a_score_and_never_marks_an_unflagged_profile(self):
        p = make_student(**STPM, stpm_grades=FULL, stpm_koko_unconfirmed=True)
        self.assertIs(self._save(p, {'stpm_koko_confirmed': True}).stpm_koko_unconfirmed, True)
        q = make_student(name='Test Dua', nric='030202-14-5678', **STPM, stpm_grades=FULL)
        self.assertIsNone(self._save(q, {'stpm_koko': 7.0, 'stpm_koko_confirmed': True}).stpm_koko_unconfirmed)


class TestTheFlagCommand(TestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('flag_stpm_koko_unconfirmed', *args, stdout=out)
        return out.getvalue()

    def test_preview_writes_nothing_and_apply_flags_only_stpm_profiles(self):
        stpm = _app()
        spm = make_application('profile_complete', student=make_student(
            name='Test Dua', nric='030202-14-5678', exam_type='spm', grades={'bm': 'A'}))
        ids = f'{stpm.id},{spm.id},999999'
        out = self._run('--applications', ids)
        self.assertIn(f'#{stpm.id}\tprofile_complete\tflag', out)
        self.assertIn(f'#{spm.id}\tprofile_complete\tnot STPM', out)
        self.assertIn('#999999\t-\tno application', out)
        self.assertIn('PREVIEW', out)
        stpm.profile.refresh_from_db()
        self.assertIsNone(stpm.profile.stpm_koko_unconfirmed)
        self.assertIn('Applied: 1 profile(s) flagged.', self._run('--applications', ids, '--apply'))
        stpm.profile.refresh_from_db()
        spm.profile.refresh_from_db()
        self.assertIs(stpm.profile.stpm_koko_unconfirmed, True)
        self.assertIsNone(spm.profile.stpm_koko_unconfirmed)
        self.assertIn(f'#{stpm.id}\tprofile_complete\talready flagged', self._run('--applications', ids, '--apply'))

    def test_unsubmitted_and_final_status_applications_are_skipped(self):
        draft = _app('submitted')
        done = make_application('profile_complete', student=make_student(
            name='Test Dua', nric='030202-14-5678', **STPM, stpm_grades=FULL))
        type(done).objects.filter(pk=done.pk).update(status='rejected')
        out = self._run('--applications', f'{draft.id},{done.id}', '--apply')
        self.assertIn(f'#{draft.id}\tsubmitted\tnot submitted', out)
        self.assertIn(f'#{done.id}\trejected\tfinal status', out)
        self.assertIn('Applied: 0 profile(s) flagged.', out)

    def test_the_ids_are_required_and_numeric(self):
        with self.assertRaises(CommandError):
            self._run('--applications', '12,abc')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestTheStudentCannotTypeTheAskClosed(TestCase):
    def test_a_typed_answer_is_refused_for_both_asks(self):
        app = _app(stpm_grades=SHORT, stpm_koko_unconfirmed=True)
        sync_check2_queries(app)
        client = authed_client(app.profile.pk)
        for code in stpm_asks.CODES:
            with self.subTest(code=code):
                item = _item(app, code)
                r = client.post(f'/api/v1/scholarship/resolution-items/{item.id}/resolve/',
                                {'text': 'done'}, format='json')
                self.assertEqual((r.status_code, r.json()['error']), (400, 'answer_on_page'))
                item.refresh_from_db()
                self.assertEqual(item.status, 'open')


class TestTheStpmCgpaMatchIsWithinOneHundredth(TestCase):
    def test_one_hundredth_matches_two_now_differs(self):
        rows = [{'subject': 'PENGAJIAN AM', 'grade': 'A'}, {'subject': 'MATEMATIK (T)', 'grade': 'A-'},
                {'subject': 'FIZIK', 'grade': 'A-'}, {'subject': 'KIMIA', 'grade': 'B+'}]
        for cgpa, want in (('3.68', 'match'), ('3.69', 'mismatch')):    # PNGK 3.67; 0.02 was a match
            with self.subTest(cgpa=cgpa):
                app = _app()
                doc = ApplicantDocument.objects.create(
                    application=app, doc_type='higher_results', storage_path='test/higher_results',
                    vision_fields={'fields': {'candidate_name': 'TEST CALON', 'cgpa': cgpa, 'cgpa_label': 'PNGK',
                                              'results_kind_detected': 'stpm', 'results': rows},
                                   'student_verdict': 'ok', 'error': ''})
                self.assertEqual(student_higher_check(doc)['cgpa_status'], want)


@override_settings(THIRD_ROUTE_OPEN=True)
class TestTheThirdRouteKeepsItsOneDecimalTolerance(TestCase):
    def _chk(self, cgpa):
        app = make_application('profile_complete', student=make_student(
            name='Test Calon', nric='030101-14-5678', exam_type='matric', results_exam_type='matric',
            grades={'bm': 'A'}, higher_cgpa=3.47, completed_qualifications=['spm', 'matric']))
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='higher_results', storage_path='test/higher_results',
            vision_fields={'fields': {'candidate_name': 'TEST CALON', 'cgpa': cgpa, 'cgpa_label': 'PNGK',
                                      'results_kind_detected': 'matric'}, 'student_verdict': 'ok', 'error': ''})
        return student_higher_check(doc)['cgpa_status']

    def test_a_one_decimal_print_still_matches_a_typed_cgpa(self):
        self.assertEqual(self._chk('3.5'), 'match')            # typed 3.47, printed to one place
        self.assertEqual(self._chk('3.60'), 'mismatch')
