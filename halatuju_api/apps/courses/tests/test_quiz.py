"""
Tests for quiz API endpoints and quiz engine logic.

Covers:
- GET /api/v1/quiz/questions/ (3 languages, default, invalid lang)
- POST /api/v1/quiz/submit/ (full submission, signal accumulation, taxonomy)
- Validation (missing answers, bad question_id, bad option_index)
- Engine unit tests (taxonomy mapping, empty signals, signal strength)
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.quiz_engine import process_quiz_answers
from apps.courses.quiz_data import QUESTION_IDS, QUIZ_QUESTIONS


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizQuestionsEndpoint(TestCase):
    """GET /api/v1/quiz/questions/ tests."""

    def setUp(self):
        self.client = APIClient()

    def test_get_questions_default_english(self):
        response = self.client.get('/api/v1/quiz/questions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'en')
        self.assertEqual(response.data['total'], 6)
        self.assertEqual(len(response.data['questions']), 6)

    def test_get_questions_bm(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=bm')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'bm')
        # First question should be in BM
        self.assertIn('memenatkan', response.data['questions'][0]['prompt'])

    def test_get_questions_tamil(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=ta')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'ta')

    def test_invalid_lang_falls_back_to_english(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=zz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'en')


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizSubmitEndpoint(TestCase):
    """POST /api/v1/quiz/submit/ tests."""

    def setUp(self):
        self.client = APIClient()

    def _full_answers(self):
        """All 6 questions answered with first option (index 0)."""
        return [
            {'question_id': qid, 'option_index': 0}
            for qid in QUESTION_IDS
        ]

    def test_submit_full_answers_returns_200(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': self._full_answers()},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('student_signals', response.data)
        self.assertIn('signal_strength', response.data)

    def test_submit_returns_all_five_categories(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': self._full_answers()},
            format='json',
        )
        categories = response.data['student_signals']
        expected = [
            'work_preference_signals',
            'learning_tolerance_signals',
            'environment_signals',
            'value_tradeoff_signals',
            'energy_sensitivity_signals',
        ]
        for cat in expected:
            self.assertIn(cat, categories)

    def test_submit_empty_answers_returns_400(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': []},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_missing_question_id_returns_400(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'option_index': 0}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('missing question_id', response.data['error'])

    def test_submit_invalid_question_id_returns_400(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'question_id': 'q99_fake', 'option_index': 0}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unknown question_id', response.data['error'])

    def test_submit_option_index_out_of_range_returns_400(self):
        response = self.client.post(
            '/api/v1/quiz/submit/',
            {'answers': [{'question_id': 'q1_modality', 'option_index': 99}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('out of range', response.data['error'])


class TestQuizEngine(TestCase):
    """Unit tests for quiz_engine.process_quiz_answers()."""

    def test_signal_accumulation_first_option_all_questions(self):
        """First option of each question: hands_on=2, workshop=1, learning_by_doing=1,
        stability=2, low_people=1, allowance=3."""
        answers = [
            {'question_id': qid, 'option_index': 0}
            for qid in QUESTION_IDS
        ]
        result = process_quiz_answers(answers)
        signals = result['student_signals']

        self.assertEqual(signals['work_preference_signals']['hands_on'], 2)
        self.assertEqual(signals['environment_signals']['workshop_environment'], 1)
        self.assertEqual(signals['learning_tolerance_signals']['learning_by_doing'], 1)
        self.assertEqual(signals['value_tradeoff_signals']['stability_priority'], 2)
        self.assertEqual(signals['energy_sensitivity_signals']['low_people_tolerance'], 1)
        self.assertEqual(signals['value_tradeoff_signals']['allowance_priority'], 3)

    def test_signal_strength_classification(self):
        """Score >= 2 = strong, score == 1 = moderate."""
        answers = [
            {'question_id': 'q1_modality', 'option_index': 0},  # hands_on: 2
            {'question_id': 'q2_environment', 'option_index': 0},  # workshop_environment: 1
        ]
        result = process_quiz_answers(answers)
        self.assertEqual(result['signal_strength']['hands_on'], 'strong')
        self.assertEqual(result['signal_strength']['workshop_environment'], 'moderate')

    def test_empty_signals_option_produces_no_output(self):
        """Q5 option 4 ('Nothing in particular') and Q6 option 3 ('No strong preference')
        have empty signal dicts — they should not add anything."""
        answers = [
            {'question_id': 'q5_energy', 'option_index': 4},  # signals: {}
            {'question_id': 'q6_survival', 'option_index': 3},  # signals: {}
        ]
        result = process_quiz_answers(answers)
        # All categories should be empty dicts
        for cat_signals in result['student_signals'].values():
            self.assertEqual(cat_signals, {})
        self.assertEqual(result['signal_strength'], {})

    def test_all_languages_have_same_question_ids(self):
        """EN, BM, TA must all have the same question IDs in the same order."""
        for lang in ['en', 'bm', 'ta']:
            questions = QUIZ_QUESTIONS[lang]
            ids = [q['id'] for q in questions]
            self.assertEqual(ids, QUESTION_IDS, f'{lang} question IDs mismatch')
