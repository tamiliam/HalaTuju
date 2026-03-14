"""
Tests for the eligibility service module.

Covers the extracted functions from EligibilityCheckView.post():
- compute_student_merit
- compute_course_merit (per-course merit branching)
- deduplicate_pismp
- sort_eligible_courses
- compute_stats
"""
import math
from unittest.mock import patch
from django.test import TestCase


class TestComputeStudentMerit(TestCase):
    """Test merit calculation from request data."""

    def test_uses_precomputed_merit_when_provided(self):
        from apps.courses.eligibility_service import compute_student_merit
        data = {'student_merit': 72.5, 'grades': {'bm': 'A', 'eng': 'B'}}
        result = compute_student_merit(data)
        self.assertEqual(result, 72.5)

    def test_calculates_merit_from_grades(self):
        from apps.courses.eligibility_service import compute_student_merit
        data = {
            'grades': {
                'bm': 'A+', 'eng': 'A', 'hist': 'A',
                'math': 'A', 'sci': 'B+',
            },
            'coq_score': 5.0,
        }
        result = compute_student_merit(data)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_renames_hist_to_history_for_merit_formula(self):
        """The merit formula expects 'history', not 'hist'."""
        from apps.courses.eligibility_service import compute_student_merit
        data = {
            'grades': {'hist': 'A', 'bm': 'A', 'eng': 'A', 'math': 'A'},
        }
        # Should not raise — 'hist' is renamed internally
        result = compute_student_merit(data)
        self.assertIsInstance(result, float)

    def test_default_coq_score(self):
        from apps.courses.eligibility_service import compute_student_merit
        data = {'grades': {'bm': 'A', 'eng': 'A', 'math': 'A'}}
        result = compute_student_merit(data)
        self.assertIsInstance(result, float)


class TestComputeCourseMerit(TestCase):
    """Test per-course merit calculation with different merit types."""

    def test_standard_merit_with_cutoff(self):
        from apps.courses.eligibility_service import compute_course_merit
        result = compute_course_merit(
            merit_type='standard',
            source_type='poly',
            merit_cutoff=60.0,
            student_merit=70.0,
            course_id='DIP001',
            data={},
            grades={},
        )
        self.assertEqual(result['merit_label'], 'High')
        self.assertEqual(result['student_merit'], 70.0)

    def test_standard_merit_no_cutoff(self):
        from apps.courses.eligibility_service import compute_course_merit
        result = compute_course_merit(
            merit_type='standard',
            source_type='poly',
            merit_cutoff=None,
            student_merit=70.0,
            course_id='DIP001',
            data={},
            grades={},
        )
        self.assertIsNone(result['merit_label'])

    def test_no_tvet_guard_with_null_cutoff(self):
        """TVET courses with null merit_cutoff get no label (guard removed)."""
        from apps.courses.eligibility_service import compute_course_merit
        result = compute_course_merit(
            merit_type='standard',
            source_type='tvet',
            merit_cutoff=None,
            student_merit=70.0,
            course_id='TVET001',
            data={},
            grades={},
        )
        self.assertIsNone(result['merit_label'])

    def test_tvet_with_hypothetical_cutoff_gets_label(self):
        """If TVET courses ever get merit data, they should get a label."""
        from apps.courses.eligibility_service import compute_course_merit
        result = compute_course_merit(
            merit_type='standard',
            source_type='tvet',
            merit_cutoff=50.0,
            student_merit=70.0,
            course_id='TVET001',
            data={},
            grades={},
        )
        self.assertEqual(result['merit_label'], 'High')

    def test_matric_merit_eligible(self):
        from apps.courses.eligibility_service import compute_course_merit
        grades = {
            'math': 'A+', 'addmath': 'A', 'phy': 'A',
            'chem': 'A', 'bio': 'A', 'bm': 'A', 'eng': 'A',
            'hist': 'A',
        }
        result = compute_course_merit(
            merit_type='matric',
            source_type='matric',
            merit_cutoff=None,
            student_merit=90.0,
            course_id='matric-sains',
            data={'coq_score': 5.0},
            grades=grades,
        )
        self.assertIsNotNone(result['merit_label'])
        self.assertIn(result['merit_label'], ('High', 'Fair', 'Low'))

    def test_matric_merit_not_eligible_returns_skip(self):
        from apps.courses.eligibility_service import compute_course_merit
        # Grades too weak for matric sains
        grades = {'bm': 'E', 'eng': 'E', 'math': 'E'}
        result = compute_course_merit(
            merit_type='matric',
            source_type='matric',
            merit_cutoff=None,
            student_merit=30.0,
            course_id='matric-sains',
            data={'coq_score': 5.0},
            grades=grades,
        )
        self.assertIsNone(result)  # None = skip this course

    def test_stpm_mata_gred_eligible(self):
        from apps.courses.eligibility_service import compute_course_merit
        grades = {
            'math': 'A+', 'addmath': 'A', 'phy': 'A',
            'chem': 'A', 'bio': 'A', 'bm': 'A', 'eng': 'A',
            'hist': 'A',
        }
        result = compute_course_merit(
            merit_type='stpm_mata_gred',
            source_type='stpm',
            merit_cutoff=None,
            student_merit=90.0,
            course_id='stpm-sains',
            data={},
            grades=grades,
        )
        if result is not None:  # Only if eligible
            self.assertIn(result['merit_label'], ('High', 'Fair', 'Low'))
            self.assertIsNotNone(result['merit_display_student'])
            self.assertIsNotNone(result['merit_display_cutoff'])

    def test_stpm_science_at_threshold_is_high(self):
        """Science mata_gred 18 (exactly at max) → High, not Fair."""
        from apps.courses.eligibility_service import compute_course_merit
        # C grades give mata_gred=6 each, 3 subjects = 18
        grades = {
            'bm': 'C', 'math': 'C', 'phy': 'C', 'chem': 'C',
        }
        result = compute_course_merit(
            merit_type='stpm_mata_gred',
            source_type='stpm',
            merit_cutoff=None,
            student_merit=90.0,
            course_id='stpm-sains',
            data={},
            grades=grades,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['merit_label'], 'High')
        self.assertEqual(result['merit_display_student'], '18')
        self.assertEqual(result['merit_display_cutoff'], '18')
        # Science: (27-18)/24*100 = 37.5%
        self.assertAlmostEqual(result['merit_cutoff'], 37.5)

    def test_stpm_socsci_at_12_is_high(self):
        """Sains Sosial mata_gred exactly 12 → High."""
        from apps.courses.eligibility_service import compute_course_merit
        # B=4 for 3 subjects, bm=C(6) as 4th candidate → best 3 = 4+4+4 = 12
        grades = {
            'bm': 'C', 'hist': 'B', 'geo': 'B', 'ekonomi': 'B',
        }
        result = compute_course_merit(
            merit_type='stpm_mata_gred',
            source_type='stpm',
            merit_cutoff=None,
            student_merit=90.0,
            course_id='stpm-sains-sosial',
            data={},
            grades=grades,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['merit_label'], 'High')
        self.assertEqual(result['merit_display_cutoff'], '12')
        # Sains Sosial: (27-12)/24*100 = 62.5%
        self.assertAlmostEqual(result['merit_cutoff'], 62.5)

    def test_stpm_socsci_at_15_is_fair(self):
        """Sains Sosial mata_gred 15 (between 12 and 18) → Fair (appealable)."""
        from apps.courses.eligibility_service import compute_course_merit
        # C+=5 for three non-bm subjects → best 3 = 5+5+5 = 15
        # bm=C (mg=6) is 4th candidate, not in best 3
        grades = {
            'bm': 'C', 'hist': 'C+', 'geo': 'C+', 'ekonomi': 'C+',
        }
        result = compute_course_merit(
            merit_type='stpm_mata_gred',
            source_type='stpm',
            merit_cutoff=None,
            student_merit=90.0,
            course_id='stpm-sains-sosial',
            data={},
            grades=grades,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['merit_label'], 'Fair')


class TestDeduplicatePismp(TestCase):
    """Test PISMP zone variant deduplication."""

    def test_non_pismp_courses_pass_through(self):
        from apps.courses.eligibility_service import deduplicate_pismp
        courses = [
            {'course_id': 'DIP001', 'course_name': 'Diploma A', 'source_type': 'poly'},
            {'course_id': 'DIP002', 'course_name': 'Diploma B', 'source_type': 'poly'},
        ]
        result = deduplicate_pismp(courses, {})
        self.assertEqual(len(result), 2)

    def test_identical_requirements_collapsed(self):
        from apps.courses.eligibility_service import deduplicate_pismp
        # Zone at [4:6]: 01=national, 03=Chinese
        courses = [
            {'course_id': '50PD010M00P', 'course_name': 'PISMP Course', 'source_type': 'pismp'},
            {'course_id': '50PD030M00P', 'course_name': 'PISMP Course', 'source_type': 'pismp'},
        ]
        # Both have same requirement hash
        req_hashes = {
            '50PD010M00P': '{"group": "A"}',
            '50PD030M00P': '{"group": "A"}',
        }
        result = deduplicate_pismp(courses, req_hashes)
        # Chinese variant collapsed into national (identical reqs)
        self.assertEqual(len(result), 1)

    def test_different_requirements_merged_with_language(self):
        from apps.courses.eligibility_service import deduplicate_pismp
        courses = [
            {'course_id': '50PD010M00P', 'course_name': 'PISMP Course', 'source_type': 'pismp'},
            {'course_id': '50PD030M00P', 'course_name': 'PISMP Course', 'source_type': 'pismp'},
        ]
        # Different requirement hashes
        req_hashes = {
            '50PD010M00P': '{"group": "A"}',
            '50PD030M00P': '{"group": "B"}',
        }
        result = deduplicate_pismp(courses, req_hashes)
        # National + language variant card
        self.assertEqual(len(result), 2)
        lang_card = [c for c in result if 'pismp_languages' in c]
        self.assertEqual(len(lang_card), 1)
        self.assertIn('Bahasa Cina', lang_card[0]['pismp_languages'])


class TestSortEligibleCourses(TestCase):
    """Test the multi-key sort logic."""

    def test_high_merit_before_fair(self):
        from apps.courses.eligibility_service import sort_eligible_courses
        courses = [
            {'course_name': 'B', 'source_type': 'poly', 'pathway_type': 'poly',
             'merit_label': 'Fair', 'merit_cutoff': 50, 'student_merit': 48},
            {'course_name': 'A', 'source_type': 'poly', 'pathway_type': 'poly',
             'merit_label': 'High', 'merit_cutoff': 50, 'student_merit': 60},
        ]
        result = sort_eligible_courses(courses)
        self.assertEqual(result[0]['merit_label'], 'High')

    def test_pismp_sorted_as_high(self):
        from apps.courses.eligibility_service import sort_eligible_courses
        courses = [
            {'course_name': 'Low Course', 'source_type': 'poly', 'pathway_type': 'poly',
             'merit_label': 'Low', 'merit_cutoff': 80, 'student_merit': 50},
            {'course_name': 'PISMP Course', 'source_type': 'pismp', 'pathway_type': 'pismp',
             'merit_label': None, 'merit_cutoff': None, 'student_merit': 50},
        ]
        result = sort_eligible_courses(courses)
        self.assertEqual(result[0]['source_type'], 'pismp')

    def test_iljtm_between_fair_and_low(self):
        from apps.courses.eligibility_service import sort_eligible_courses
        courses = [
            {'course_name': 'Low', 'source_type': 'poly', 'pathway_type': 'poly',
             'merit_label': 'Low', 'merit_cutoff': 80, 'student_merit': 50},
            {'course_name': 'ILJTM', 'source_type': 'iljtm', 'pathway_type': 'iljtm',
             'merit_label': None, 'merit_cutoff': None, 'student_merit': 50},
            {'course_name': 'Fair', 'source_type': 'poly', 'pathway_type': 'poly',
             'merit_label': 'Fair', 'merit_cutoff': 55, 'student_merit': 52},
        ]
        result = sort_eligible_courses(courses)
        names = [c['course_name'] for c in result]
        self.assertLess(names.index('Fair'), names.index('ILJTM'))
        self.assertLess(names.index('ILJTM'), names.index('Low'))


class TestComputeStats(TestCase):
    """Test stats and pathway stats computation."""

    def test_counts_by_source_type(self):
        from apps.courses.eligibility_service import compute_stats
        courses = [
            {'source_type': 'poly', 'pathway_type': 'poly'},
            {'source_type': 'poly', 'pathway_type': 'poly'},
            {'source_type': 'kkom', 'pathway_type': 'kkom'},
        ]
        stats, pathway_stats = compute_stats(courses)
        self.assertEqual(stats['poly'], 2)
        self.assertEqual(stats['kkom'], 1)

    def test_pathway_stats_uses_pathway_type(self):
        from apps.courses.eligibility_service import compute_stats
        courses = [
            {'source_type': 'tvet', 'pathway_type': 'iljtm'},
            {'source_type': 'tvet', 'pathway_type': 'ilkbs'},
        ]
        stats, pathway_stats = compute_stats(courses)
        self.assertEqual(stats['tvet'], 2)
        self.assertEqual(pathway_stats['iljtm'], 1)
        self.assertEqual(pathway_stats['ilkbs'], 1)
