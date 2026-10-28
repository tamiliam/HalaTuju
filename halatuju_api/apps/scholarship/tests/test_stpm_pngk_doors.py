"""EVERY DOOR THAT READS AN STPM STUDENT'S CGPA — STPM CGPA sprint C2 (2026-10-28).

Owner ruling: the CGPA is worked out from the grades (`apps/courses/stpm_pngk.py`), never typed.
Each test below drives one reader of `stpm_cgpa` through its real code path and asserts it shows
the PNGK of the grades, not the stale figure stored beside them. The door list is in the sprint's
pull request; a new reader belongs here the day it is added.

The student: five graded subjects (made up) — PNGK (PA + best three) = (4 + 4 + 3.67 + 3.33) / 4 =
3.75, the plain average of all five = 3.40, and a stored figure of 3.21 that matches neither.

CGPA AND MERIT ARE DIFFERENT (owner ruling 2026-10-28). Every CGPA door shows the PNGK; every MERIT
door (`TestTheMeritDoors`) shows overall_from(PNGK, koko) / 4 x 100 — co-curriculum stays in
merit. Her stored co-curriculum score is 8: 0.9 x 3.75 + 0.04 x 8 = 3.695 -> 3.69 -> merit 92.25.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.courses import exam_questions as eq
from apps.courses.serializers import ProfileUpdateSerializer
from apps.courses.serializers_admin import PartnerStudentDetailSerializer
from apps.scholarship import pool, profile_engine
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.serializers_admin import AdminApplicationListSerializer
from apps.scholarship.services.profile_sync import build_intake_snapshot
from apps.scholarship.shortlisting import _academic_ok

from .factories import (TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
                        make_student)

GRADES = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+', 'BIOLOGY': 'C'}
PNGK = 3.75
STORED = 3.21
KOKO = 8.0
MERIT = 92.25
STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_grades=GRADES, stpm_cgpa=STORED,
            stpm_koko=KOKO, completed_qualifications=['spm', 'stpm'], grades={'bm': 'A', 'eng': 'B'})
#: PA + two others — no PNGK can be worked out, so the stored figure stands ("not calculated").
SHORT = {**STPM, 'stpm_grades': {'PA': 'A', 'MATH_T': 'B'}}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheDoors(TestCase):
    def setUp(self):
        self.student = make_student(**STPM)

    def test_overall_cgpa_is_the_pngk_and_the_merit_keeps_koko(self):
        self.assertEqual(eq.overall_cgpa(self.student), PNGK)
        self.assertEqual(eq.merit_100(self.student), MERIT)

    def test_the_model_property(self):
        self.assertEqual(self.student.stpm_pngk, PNGK)

    def test_the_gate(self):
        """`min_stpm_pngk` 3.50: the stored 3.21 would refuse her; her grades pass."""
        cohort = make_cohort(min_stpm_pngk=3.5)
        self.assertEqual(_academic_ok(self.student, cohort), (True, ''))
        low = make_student(**{**STPM, 'stpm_grades': {'PA': 'C', 'MATH_T': 'C', 'PHYSICS': 'C',
                                                      'CHEMISTRY': 'C'}, 'stpm_cgpa': 3.9})
        self.assertEqual(_academic_ok(low, cohort), (False, 'PNGK 2.0 below 3.5'))

    def test_the_officer_list_and_the_student_read(self):
        app = make_application('submitted', student=self.student)
        row = AdminApplicationListSerializer(app).data
        self.assertEqual((row['stpm_pngk'], row['overall_cgpa']), (PNGK, PNGK))
        self.assertEqual(ApplicationReadSerializer(app).data['stpm_pngk'], PNGK)

    def test_the_cockpit(self):
        app = make_application('submitted', student=self.student)
        client = authed_client(make_admin('org_admin', owning_org=app.cohort.owning_organisation))
        r = client.get(f'/api/v1/admin/scholarship/applications/{app.id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual((r.json()['stpm_pngk'], r.json()['overall_cgpa']), (PNGK, PNGK))

    def test_the_sponsor_line_and_the_sponsor_profile_prompt(self):
        self.assertEqual(pool.academic_band(self.student), f'STPM · PNGK {PNGK}')
        app = make_application('submitted', student=self.student)
        self.assertIn(f'STPM PNGK: {PNGK}', profile_engine._build_prompt(app))

    def test_the_submit_snapshot(self):
        snap = build_intake_snapshot(self.student, {})['profile']
        self.assertEqual((snap['stpm_cgpa'], snap['stpm_koko']), (PNGK, KOKO))

    def test_the_student_profile_payload(self):
        r = authed_client(self.student).get('/api/v1/profile/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()['stpm_cgpa'], r.json()['stpm_cgpa_calculated'], r.json()['stpm_koko']),
                         (PNGK, True, KOKO))

    def test_the_partner_student_detail(self):
        self.assertEqual(PartnerStudentDetailSerializer(self.student).data['stpm_cgpa'], PNGK)

    def test_the_student_csv_export(self):
        client = authed_client(make_admin('super', super_admin=True))
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={}):
            r = client.get('/api/v1/admin/students/export/')
        self.assertEqual(r.status_code, 200)
        text = r.content.decode()
        self.assertIn(self.student.name, text)
        row = next(line for line in text.splitlines() if self.student.name in line)
        self.assertIn(f',{PNGK},', row)
        self.assertNotIn(f',{STORED},', row)

    @patch('apps.reports.views.generate_report')
    def test_the_counselling_report(self, gen):
        gen.return_value = {'markdown': 'x', 'model_used': 'm', 'generation_time_ms': 1}
        authed_client(self.student).post(
            '/api/v1/reports/generate/', {'eligible_courses': [{'course_name': 'X'}], 'insights': {}},
            format='json')
        gen.assert_called_once()
        self.assertEqual(gen.call_args[1]['stpm_cgpa'], PNGK)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheMeritDoors(TestCase):
    """Every reader of the MERIT: overall_from(PNGK, koko) / 4 x 100 — not the CGPA / 4 x 100."""

    def setUp(self):
        self.app = make_application('submitted', student=make_student(**STPM))

    def test_the_officer_list_and_the_merit_sort(self):
        self.assertEqual(AdminApplicationListSerializer(self.app).data['merit_score'], MERIT)
        client = authed_client(make_admin('org_admin', owning_org=self.app.cohort.owning_organisation))
        r = client.get('/api/v1/admin/scholarship/applications/?sort=merit')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual([a['merit_score'] for a in r.json()['applications']], [MERIT])

    def test_the_cockpit(self):
        client = authed_client(make_admin('org_admin', owning_org=self.app.cohort.owning_organisation))
        body = client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/').json()
        self.assertEqual((body['merit_score'], body['stpm_pngk']), (MERIT, PNGK))

    def test_the_sponsor_profile_prompt(self):
        self.assertIn(f'Merit score (out of 100): {MERIT}', profile_engine._build_prompt(self.app))

    def test_no_koko_is_no_merit_never_a_made_up_zero(self):
        s = make_student(**{**STPM, 'stpm_koko': None})
        self.assertEqual((eq.merit_100(s), s.stpm_pngk), (None, PNGK))

    def test_the_calculator_agrees_with_the_stored_profile(self):
        from rest_framework.test import APIClient
        r = APIClient().post('/api/v1/calculate/cgpa/', {'stpm_grades': GRADES, 'koko_score': KOKO},
                             format='json')
        self.assertEqual((r.data['cgpa'], r.data['merit_percent']), (PNGK, MERIT))
        self.assertEqual(r.data['counted'], ['PA', 'MATH_T', 'PHYSICS', 'CHEMISTRY'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestNotCalculated(TestCase):
    """Fewer than PA + three: every door keeps showing the stored figure, as before C2."""

    def test_the_stored_figure_stands_everywhere(self):
        s = make_student(**SHORT)
        self.assertEqual((s.stpm_pngk, eq.overall_cgpa(s), eq.merit_100(s)),
                         (STORED, STORED, round(STORED / 4 * 100, 2)))
        self.assertEqual(_academic_ok(s, make_cohort(min_stpm_pngk=3.5)),
                         (False, f'PNGK {STORED} below 3.5'))
        r = authed_client(s).get('/api/v1/profile/')
        self.assertEqual((r.json()['stpm_cgpa'], r.json()['stpm_cgpa_calculated']), (STORED, False))


@override_settings(THIRD_ROUTE_OPEN=True)
class TestTheWriter(TestCase):
    """The profile write stores the PNGK in `stpm_cgpa`, over whatever figure the browser sent."""

    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_grades_and_a_sent_figure_store_the_pngk(self):
        p = make_student()
        saved = self._save(p, {'exam_type': 'stpm', 'results_exam_type': 'stpm',
                               'stpm_grades': GRADES, 'stpm_cgpa': 3.40})
        self.assertEqual(saved.stpm_cgpa, PNGK)

    def test_a_stale_figure_alone_cannot_overwrite_the_grades(self):
        p = make_student(**STPM)
        self.assertEqual(self._save(p, {'stpm_cgpa': 3.9}).stpm_cgpa, PNGK)

    def test_too_few_grades_keep_the_sent_figure(self):
        p = make_student()
        saved = self._save(p, {'stpm_grades': {'PA': 'A', 'MATH_T': 'B'}, 'stpm_cgpa': 3.3})
        self.assertEqual(saved.stpm_cgpa, 3.3)

    def test_the_koko_score_is_stored_and_range_checked(self):
        p = make_student()
        saved = self._save(p, {'exam_type': 'stpm', 'results_exam_type': 'stpm',
                               'stpm_grades': GRADES, 'stpm_koko': 7.5})
        self.assertEqual((saved.stpm_cgpa, saved.stpm_koko), (PNGK, 7.5))
        for bad in (-1, 10.5):
            with self.subTest(koko=bad):
                self.assertFalse(ProfileUpdateSerializer(p, data={'stpm_koko': bad}, partial=True).is_valid())

    def test_completing_the_third_route_clears_the_stpm_koko_too(self):
        p = make_student(**STPM)
        saved = self._save(p, {'exam_type': 'matric', 'results_exam_type': 'matric', 'higher_cgpa': 3.5,
                               'higher_koko': 8, 'completed_qualifications': ['spm', 'matric']})
        self.assertEqual((saved.stpm_grades, saved.stpm_cgpa, saved.stpm_koko), ({}, None, None))

    def test_only_spm_clears_the_stpm_koko_too(self):
        from apps.scholarship.results_route import clear_to_spm
        app = make_application('submitted', student=make_student(**STPM))
        clear_to_spm(app)
        app.profile.refresh_from_db()
        self.assertEqual((app.profile.stpm_cgpa, app.profile.stpm_koko), (None, None))

    def test_a_write_that_does_not_touch_stpm_leaves_the_column_alone(self):
        p = make_student(**STPM)
        self.assertEqual(self._save(p, {'school': 'SMK X'}).stpm_cgpa, STORED)
