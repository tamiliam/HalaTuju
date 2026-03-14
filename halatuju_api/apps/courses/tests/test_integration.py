"""
Integration test for the full eligibility → ranking flow.

Exercises the critical user path: a student submits grades, gets eligible
courses, then those courses are ranked by fit score based on quiz signals.
This catches cross-module breaks that unit tests miss.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.tests.conftest import load_requirements_df


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestEligibilityToRankingFlow(TestCase):
    """End-to-end: eligibility check → ranking with realistic student data."""
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.client = APIClient()

    def test_full_flow_eligibility_then_ranking(self):
        """
        A realistic student gets eligible courses, then those courses
        are ranked by fit score. Verifies the two endpoints compose correctly.
        """
        # Step 1: Eligibility check
        eligibility_response = self.client.post('/api/v1/eligibility/check/', {
            'grades': {
                'bm': 'A', 'eng': 'A', 'hist': 'B+', 'math': 'A',
                'sci': 'A', 'phy': 'B+', 'chem': 'B+',
            },
            'gender': 'male',
            'nationality': 'malaysian',
            'colorblind': False,
            'disability': False,
        }, format='json')

        self.assertEqual(eligibility_response.status_code, 200)
        eligibility_data = eligibility_response.json()

        eligible_courses = eligibility_data['eligible_courses']
        self.assertGreater(len(eligible_courses), 0,
                           "Realistic student should have eligible courses")

        # Verify eligibility response shape
        self.assertIn('total_count', eligibility_data)
        self.assertIn('stats', eligibility_data)
        self.assertEqual(eligibility_data['total_count'], len(eligible_courses))

        # Verify each course has the fields ranking expects
        for course in eligible_courses[:5]:
            self.assertIn('course_id', course)
            self.assertIn('course_name', course)
            self.assertIn('source_type', course)

        # Step 2: Ranking — feed eligible courses + quiz signals
        ranking_payload = {
            'eligible_courses': [
                {
                    'course_id': c['course_id'],
                    'institution_id': c.get('institution_id', ''),
                    'course_name': c['course_name'],
                    'merit_cutoff': c.get('merit_cutoff'),
                    'student_merit': c.get('student_merit', 0),
                    'source_type': c.get('source_type', ''),
                }
                for c in eligible_courses
            ],
            'student_signals': {
                'work_preference_signals': {
                    'hands_on': 2, 'analytical': 1, 'creative': 0,
                    'social': 0, 'leadership': 0,
                },
                'environment_signals': {
                    'outdoor': 1, 'lab': 1, 'office': 0,
                    'workshop': 1, 'clinical': 0,
                },
                'field_interest': {
                    'field_mechanical': 3,
                    'field_digital': 1,
                },
            },
        }

        ranking_response = self.client.post(
            '/api/v1/ranking/', ranking_payload, format='json'
        )

        self.assertEqual(ranking_response.status_code, 200)
        ranking_data = ranking_response.json()

        # Verify ranking response shape
        self.assertIn('top_5', ranking_data)
        self.assertIn('rest', ranking_data)
        self.assertIn('total_ranked', ranking_data)

        # All eligible courses should be ranked
        total_ranked = len(ranking_data['top_5']) + len(ranking_data['rest'])
        self.assertEqual(ranking_data['total_ranked'], total_ranked)
        self.assertEqual(total_ranked, len(eligible_courses))

        # Top 5 should have fit scores in descending order
        top_5 = ranking_data['top_5']
        if len(top_5) >= 2:
            scores = [c['fit_score'] for c in top_5]
            self.assertEqual(scores, sorted(scores, reverse=True),
                             "Top 5 should be sorted by fit_score descending")

        # Every ranked course should have a fit_score
        for course in top_5:
            self.assertIn('fit_score', course)
            self.assertIsInstance(course['fit_score'], (int, float))
            self.assertGreaterEqual(course['fit_score'], 0)
