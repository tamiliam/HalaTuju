"""
Tests for quiz API endpoints and quiz engine logic.

Covers:
- GET /api/v1/quiz/questions/ (3 languages, default, invalid lang, icons, multi-select)
- POST /api/v1/quiz/submit/ (full submission, 6 categories, validation)
- Engine unit tests (single/multi-select, weight splitting, Not Sure Yet,
  conditional Q2.5, signal strength, language parity, backward compat)
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.quiz_engine import process_quiz_answers, SIGNAL_TAXONOMY
from apps.courses.quiz_data import QUESTION_IDS, QUIZ_QUESTIONS


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizQuestionsEndpoint(TestCase):
    """GET /api/v1/quiz/questions/ tests."""

    def setUp(self):
        self.client = APIClient()

    def test_get_questions_returns_9(self):
        """GET returns total=9 and 9 questions."""
        response = self.client.get('/api/v1/quiz/questions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 9)
        self.assertEqual(len(response.data['questions']), 9)

    def test_get_questions_bm(self):
        """lang=bm returns BM questions."""
        response = self.client.get('/api/v1/quiz/questions/?lang=bm')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'bm')
        # First question prompt should be in BM
        self.assertIn('menarik', response.data['questions'][0]['prompt'])

    def test_get_questions_tamil(self):
        """lang=ta returns TA questions."""
        response = self.client.get('/api/v1/quiz/questions/?lang=ta')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'ta')

    def test_invalid_lang_falls_back_to_english(self):
        """lang=zz returns EN."""
        response = self.client.get('/api/v1/quiz/questions/?lang=zz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'en')

    def test_questions_include_icon_field(self):
        """Q1 options have 'icon' key."""
        response = self.client.get('/api/v1/quiz/questions/')
        q1 = response.data['questions'][0]
        for opt in q1['options']:
            self.assertIn('icon', opt)

    def test_multi_select_questions_have_select_mode(self):
        """Q1 has select_mode='multi' and max_select=2."""
        response = self.client.get('/api/v1/quiz/questions/')
        q1 = response.data['questions'][0]
        self.assertEqual(q1['select_mode'], 'multi')
        self.assertEqual(q1['max_select'], 2)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizSubmitEndpoint(TestCase):
    """POST /api/v1/quiz/submit/ tests."""

    def setUp(self):
        self.client = APIClient()

    def _make_full_answers(self):
        """Valid full answer set: Q1 single pick, Q2 single pick NOT Big Machines,
        Q3-Q8 all index 0. Q2.5 skipped (Q2 picks Design, not Big Machines)."""
        return [
            {'question_id': 'q1_field1', 'option_index': 0},
            {'question_id': 'q2_field2', 'option_index': 0},
            # Q2.5 included but will be skipped by engine (no field_heavy_industry)
            {'question_id': 'q2_5_heavy', 'option_index': 0},
            {'question_id': 'q3_work', 'option_index': 0},
            {'question_id': 'q4_environment', 'option_index': 0},
            {'question_id': 'q5_learning', 'option_index': 0},
            {'question_id': 'q6_values', 'option_index': 0},
            {'question_id': 'q7_energy', 'option_index': 0},
            {'question_id': 'q8_practical', 'option_index': 0},
        ]

    def test_submit_returns_200(self):
        """Full set of answers returns 200 with student_signals and signal_strength."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': self._make_full_answers()},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('student_signals', response.data)
        self.assertIn('signal_strength', response.data)

    def test_submit_returns_six_categories(self):
        """Response has all 6 categories including field_interest."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': self._make_full_answers()},
            format='json',
        )
        categories = response.data['student_signals']
        expected = [
            'field_interest',
            'work_preference_signals',
            'learning_tolerance_signals',
            'environment_signals',
            'value_tradeoff_signals',
            'energy_sensitivity_signals',
        ]
        for cat in expected:
            self.assertIn(cat, categories)

    def test_submit_empty_answers_returns_400(self):
        """Empty list returns 400."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': []},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_missing_question_id_returns_400(self):
        """Missing question_id returns 400."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'option_index': 0}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('missing question_id', response.data['error'])

    def test_submit_invalid_question_id_returns_400(self):
        """Bad question_id returns 400."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'question_id': 'q99_fake', 'option_index': 0}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown question_id', response.data['error'])

    def test_submit_option_index_out_of_range_returns_400(self):
        """Index 99 returns 400."""
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'question_id': 'q1_field1', 'option_index': 99}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('out of range', response.data['error'])


class TestQuizEngine(TestCase):
    """Unit tests for quiz_engine.process_quiz_answers()."""

    def _make_full_answers(self):
        """Valid full answer set using single-select format."""
        return [
            {'question_id': 'q1_field1', 'option_index': 0},
            {'question_id': 'q2_field2', 'option_index': 0},
            {'question_id': 'q2_5_heavy', 'option_index': 0},
            {'question_id': 'q3_work', 'option_index': 0},
            {'question_id': 'q4_environment', 'option_index': 0},
            {'question_id': 'q5_learning', 'option_index': 0},
            {'question_id': 'q6_values', 'option_index': 0},
            {'question_id': 'q7_energy', 'option_index': 0},
            {'question_id': 'q8_practical', 'option_index': 0},
        ]

    def test_single_select_field_interest(self):
        """Q1 option_indices=[0] produces field_mechanical: 3."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0]}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['field_interest']
        self.assertEqual(signals['field_mechanical'], 3)

    def test_multi_select_weight_split(self):
        """Q1 option_indices=[0,1] produces field_mechanical: 2, field_digital: 2."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0, 1]}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['field_interest']
        self.assertEqual(signals['field_mechanical'], 2)
        self.assertEqual(signals['field_digital'], 2)

    def test_not_sure_distributes_evenly(self):
        """Q1 option_indices=[4] (Not Sure Yet) gives all 4 fields 1 each."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [4]}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['field_interest']
        self.assertEqual(signals['field_mechanical'], 1)
        self.assertEqual(signals['field_digital'], 1)
        self.assertEqual(signals['field_business'], 1)
        self.assertEqual(signals['field_health'], 1)

    def test_not_sure_exclusive(self):
        """Q1 option_indices=[0,4] raises ValueError — Not Sure is exclusive."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0, 4]}]
        with self.assertRaises(ValueError) as ctx:
            process_quiz_answers(answers)
        self.assertIn('Not Sure Yet', str(ctx.exception))

    def test_conditional_q2_5_fires(self):
        """Q2 picks Big Machines (idx 3) + Q2.5 answer produces field_electrical: 3."""
        answers = [
            {'question_id': 'q2_field2', 'option_indices': [3]},
            {'question_id': 'q2_5_heavy', 'option_index': 0},  # Electrical
        ]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['field_interest']
        self.assertEqual(signals['field_electrical'], 3)

    def test_conditional_q2_5_skipped(self):
        """Q2 picks Design (idx 0) + Q2.5 answer — field_electrical NOT in signals."""
        answers = [
            {'question_id': 'q2_field2', 'option_indices': [0]},  # Design
            {'question_id': 'q2_5_heavy', 'option_index': 0},  # Electrical — skipped
        ]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['field_interest']
        self.assertNotIn('field_electrical', signals)

    def test_high_stamina_signal(self):
        """Q7 option_index=3 produces high_stamina: 1."""
        answers = [{'question_id': 'q7_energy', 'option_index': 3}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['energy_sensitivity_signals']
        self.assertEqual(signals['high_stamina'], 1)

    def test_quality_priority_signal(self):
        """Q8 option_index=3 produces quality_priority: 1."""
        answers = [{'question_id': 'q8_practical', 'option_index': 3}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['value_tradeoff_signals']
        self.assertEqual(signals['quality_priority'], 1)

    def test_q4_not_sure_produces_no_signal(self):
        """Q4 option_index=4 (Not Sure Yet) produces empty environment_signals."""
        answers = [{'question_id': 'q4_environment', 'option_index': 4}]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['environment_signals'], {})

    def test_signal_strength_classification(self):
        """Score >= 2 = strong, score == 1 = moderate."""
        answers = [
            {'question_id': 'q1_field1', 'option_index': 0},  # field_mechanical: 3
            {'question_id': 'q4_environment', 'option_index': 0},  # workshop_environment: 1
        ]
        result = process_quiz_answers(answers)
        self.assertEqual(result['signal_strength']['field_mechanical'], 'strong')
        self.assertEqual(result['signal_strength']['workshop_environment'], 'moderate')

    def test_all_languages_have_same_question_ids(self):
        """EN, BM, TA must all have the same question IDs in the same order."""
        for lang in ['en', 'bm', 'ta']:
            questions = QUIZ_QUESTIONS[lang]
            ids = [q['id'] for q in questions]
            self.assertEqual(ids, QUESTION_IDS, f'{lang} question IDs mismatch')

    def test_backward_compat_single_select(self):
        """Q3 with option_index=0 produces hands_on: 2 (old format still works)."""
        answers = [{'question_id': 'q3_work', 'option_index': 0}]
        result = process_quiz_answers(answers)
        signals = result['student_signals']['work_preference_signals']
        self.assertEqual(signals['hands_on'], 2)
