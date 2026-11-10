"""
The Matriculation and Form 6 (STPM) rows of an SPM student's eligible list reach the ranking with
their track and mata gred.

The web posts the eligibility route's items to POST /api/v1/ranking/ unchanged
(dashboard -> getRankedResults), and the pre-U scorer (`ranking_pre_u.calculate_matric_stpm_fit_score`)
reads `track_id` and `mata_gred` from each item. The route used to leave both out, so a Form 6 row
never got its academic bonus and no Matric / Form 6 row got its field preference. SPM (non-pre-U)
rows must not change: they carry neither key.

Made-up students only.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.tests.conftest import load_requirements_df

#: A made-up science student: every subject A+ (matric merit 90 + co-curriculum 5 = 95; Form 6
#: Science mata gred 1 + 1 + 1 = 3).
SCIENCE_A_PLUS = {s: 'A+' for s in ('bm', 'eng', 'hist', 'math', 'addmath', 'phy', 'chem', 'bio',
                                    'moral')}

#: The keys an SPM (non-pre-U) item has always carried; the fix must not add to them.
SPM_ITEM_KEYS = {
    'course_id', 'course_name', 'level', 'field', 'field_key', 'source_type', 'pathway_type',
    'merit_cutoff', 'student_merit', 'merit_label', 'merit_color', 'merit_display_student',
    'merit_display_cutoff', 'institution_name', 'institution_count', 'institution_state', 'aliran',
}

PRE_U = ('matric', 'stpm')


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUItemsReachTheRanking(TestCase):
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.client = APIClient()

    def _eligible(self, grades=SCIENCE_A_PLUS):
        r = self.client.post('/api/v1/eligibility/check/', {'grades': grades, 'gender': 'male'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        return r.json()['eligible_courses']

    def _ranked(self, items, signals):
        """What the dashboard does: post the eligibility items, as they came, to the ranking."""
        r = self.client.post('/api/v1/ranking/', {'eligible_courses': items,
                                                  'student_signals': signals}, format='json')
        self.assertEqual(r.status_code, 200)
        return {c['course_id']: c for c in r.json()['ranked']}

    def test_pre_u_items_carry_the_track_and_the_mata_gred(self):
        by_id = {c['course_id']: c for c in self._eligible()}
        self.assertEqual(by_id['matric-kejuruteraan']['track_id'], 'kejuruteraan')
        self.assertIsNone(by_id['matric-kejuruteraan']['mata_gred'])
        self.assertEqual(by_id['matric-sains']['track_id'], 'sains')
        self.assertEqual(by_id['stpm-sains']['track_id'], 'sains')
        self.assertEqual(by_id['stpm-sains']['mata_gred'], 3)

    def test_form6_row_gets_the_academic_bonus(self):
        ranked = self._ranked(self._eligible(), {})
        # 100 base + 5 Form 6 prestige + 8 (mata gred 3 <= 4); High merit, no penalty.
        self.assertEqual(ranked['stpm-sains']['fit_score'], 113)

    def test_matric_row_gets_the_academic_bonus(self):
        ranked = self._ranked(self._eligible(), {})
        # 100 base + 8 Matric prestige + 8 (matric merit 95 >= 94); High merit, no penalty.
        self.assertEqual(ranked['matric-sains']['fit_score'], 116)

    def test_matric_row_gets_the_field_preference(self):
        ranked = self._ranked(self._eligible(), {'field_interest': {'field_mechanical': 2}})
        row = ranked['matric-kejuruteraan']
        self.assertEqual(row['fit_score'], 119)          # 116 + 3 field preference
        self.assertIn('matches your interest in Engineering', row['fit_reasons'])

    def test_form6_row_gets_the_field_preference(self):
        ranked = self._ranked(self._eligible(), {'field_interest': {'field_health': 2}})
        row = ranked['stpm-sains']
        self.assertEqual(row['fit_score'], 116)          # 113 + 3 field preference
        self.assertIn('matches your interest in Science', row['fit_reasons'])

    def test_spm_items_carry_no_pre_u_keys(self):
        spm = [c for c in self._eligible() if c['pathway_type'] not in PRE_U]
        self.assertTrue(spm)
        for c in spm:
            self.assertEqual(set(c), SPM_ITEM_KEYS, c['course_id'])

    def test_spm_scores_do_not_move(self):
        """An SPM row's score does not depend on the pre-U rows around it, nor on the new keys:
        the same rows ranked with and without the pre-U rows score the same."""
        signals = {'field_interest': {'field_mechanical': 2, 'field_health': 2},
                   'work_preference_signals': {'hands_on': 2, 'creative': 1}}
        items = self._eligible()
        spm = [c for c in items if c['pathway_type'] not in PRE_U]
        everything = self._ranked(items, signals)
        alone = self._ranked(spm, signals)
        for cid, row in alone.items():
            self.assertEqual(everything[cid]['fit_score'], row['fit_score'], cid)
            self.assertEqual(everything[cid]['fit_reasons'], row['fit_reasons'], cid)


class TestComputeCourseMeritTrack(TestCase):
    """`compute_course_merit` hands back the track it worked out (and the mata gred for Form 6)."""

    def _merit(self, merit_type, course_id, grades):
        from apps.courses.eligibility_service import compute_course_merit
        return compute_course_merit(merit_type=merit_type, source_type=merit_type.split('_')[0],
                                    merit_cutoff=None, student_merit=80.0, course_id=course_id,
                                    data={'coq_score': 5.0}, grades=grades)

    def test_matric(self):
        r = self._merit('matric', 'matric-kejuruteraan', SCIENCE_A_PLUS)
        self.assertEqual((r['track_id'], r['mata_gred']), ('kejuruteraan', None))

    def test_form6(self):
        r = self._merit('stpm_mata_gred', 'stpm-sains-sosial', SCIENCE_A_PLUS)
        self.assertEqual((r['track_id'], r['mata_gred']), ('sains_sosial', 3))

    def test_standard_has_neither(self):
        r = self._merit('standard', 'DIP001', SCIENCE_A_PLUS)
        self.assertEqual((r['track_id'], r['mata_gred']), (None, None))
