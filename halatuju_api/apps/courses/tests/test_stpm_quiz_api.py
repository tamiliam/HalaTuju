"""
Tests for STPM quiz API endpoints — questions, resolve, and submit.
"""
import json
import pytest
from django.test import TestCase
from rest_framework.test import APIClient


class TestStpmQuizQuestionsEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/stpm/quiz/questions/'

    def test_returns_200_with_valid_subjects(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t', 'lang': 'en'},
        )
        assert resp.status_code == 200

    def test_returns_branch_and_seed(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t'},
        )
        data = resp.json()
        assert data['branch'] == 'science'
        assert 'riasec_seed' in data
        assert 'I' in data['riasec_seed']

    def test_returns_questions_array(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'economics,accounting,business_studies'},
        )
        data = resp.json()
        assert len(data['questions']) == 2  # Q1 + Q2
        assert data['questions'][0]['id'] == 'q1_readiness'
        assert data['questions'][1]['id'] == 'q2a_field'

    def test_returns_q3_variants(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t'},
        )
        data = resp.json()
        assert 'q3_variants' in data
        assert 'field_engineering' in data['q3_variants']

    def test_returns_q5_and_trunk(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t'},
        )
        data = resp.json()
        assert 'q5' in data
        assert 'trunk_remaining' in data
        assert len(data['trunk_remaining']) == 4

    def test_missing_subjects_returns_400(self):
        resp = self.client.get(self.url)
        assert resp.status_code == 400

    def test_single_subject_returns_400(self):
        resp = self.client.get(self.url, {'subjects': 'physics'})
        assert resp.status_code == 400

    def test_grades_json_parsed(self):
        grades = json.dumps({'physics': 'A', 'chemistry': 'B+'})
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t', 'grades': grades},
        )
        assert resp.status_code == 200
        assert 'grades' in resp.json()

    def test_invalid_grades_json_returns_400(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t', 'grades': 'not json'},
        )
        assert resp.status_code == 400

    def test_bm_language(self):
        resp = self.client.get(
            self.url,
            {'subjects': 'physics,chemistry,mathematics_t', 'lang': 'bm'},
        )
        data = resp.json()
        prompt = data['questions'][0]['prompt']
        assert 'universiti' in prompt.lower()


class TestStpmQuizResolveEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/stpm/quiz/resolve/'

    def test_returns_200_with_valid_data(self):
        resp = self.client.post(
            self.url,
            {
                'field_signal': 'field_engineering',
                'branch': 'science',
                'grades': {'physics': 'A'},
                'lang': 'en',
            },
            format='json',
        )
        assert resp.status_code == 200

    def test_returns_q3_and_q4(self):
        resp = self.client.post(
            self.url,
            {
                'field_signal': 'field_engineering',
                'branch': 'science',
                'grades': {'physics': 'A'},
            },
            format='json',
        )
        data = resp.json()
        assert data['q3']['id'] == 'q3s_engineering'
        assert data['q4'] is not None

    def test_missing_field_signal_returns_400(self):
        resp = self.client.post(
            self.url,
            {'branch': 'science'},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_branch_returns_400(self):
        resp = self.client.post(
            self.url,
            {'field_signal': 'field_engineering'},
            format='json',
        )
        assert resp.status_code == 400


class TestStpmQuizSubmitEndpoint(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/stpm/quiz/submit/'
        self.valid_payload = {
            'answers': [
                {'question_id': 'q1_readiness', 'option_index': 0},
                {'question_id': 'q2s_field', 'option_index': 0},
                {'question_id': 'q3s_engineering', 'option_index': 0},
                {'question_id': 'q4_confidence_strong', 'option_index': 0},
                {'question_id': 'q5_cross_domain', 'option_index': 5},
                {'question_id': 'q7_challenge', 'option_index': 0},
                {'question_id': 'q8_motivation', 'option_index': 0},
                {'question_id': 'q9_career', 'option_index': 0},
                {'question_id': 'q10_family', 'option_index': 1},
            ],
            'subjects': ['physics', 'chemistry', 'mathematics_t'],
            'grades': {'physics': 'A', 'chemistry': 'B+', 'mathematics_t': 'A-'},
            'lang': 'en',
        }

    def test_returns_200_with_valid_data(self):
        resp = self.client.post(self.url, self.valid_payload, format='json')
        assert resp.status_code == 200

    def test_returns_student_signals(self):
        resp = self.client.post(self.url, self.valid_payload, format='json')
        data = resp.json()
        assert 'student_signals' in data
        assert 'riasec_seed' in data['student_signals']
        assert 'field_interest' in data['student_signals']

    def test_returns_signal_strength(self):
        resp = self.client.post(self.url, self.valid_payload, format='json')
        data = resp.json()
        assert 'signal_strength' in data

    def test_returns_branch(self):
        resp = self.client.post(self.url, self.valid_payload, format='json')
        data = resp.json()
        assert data['branch'] == 'science'

    def test_missing_answers_returns_400(self):
        resp = self.client.post(
            self.url,
            {'subjects': ['physics'], 'grades': {}},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_subjects_returns_400(self):
        resp = self.client.post(
            self.url,
            {'answers': [{'question_id': 'q1_readiness', 'option_index': 0}]},
            format='json',
        )
        assert resp.status_code == 400

    def test_answer_missing_question_id_returns_400(self):
        payload = dict(self.valid_payload)
        payload['answers'] = [{'option_index': 0}]
        resp = self.client.post(self.url, payload, format='json')
        assert resp.status_code == 400

    def test_answer_missing_option_index_returns_400(self):
        payload = dict(self.valid_payload)
        payload['answers'] = [{'question_id': 'q1_readiness'}]
        resp = self.client.post(self.url, payload, format='json')
        assert resp.status_code == 400

    def test_invalid_question_id_returns_400(self):
        payload = dict(self.valid_payload)
        payload['answers'] = [{'question_id': 'nonexistent', 'option_index': 0}]
        resp = self.client.post(self.url, payload, format='json')
        assert resp.status_code == 400

    def test_arts_branch_submission(self):
        payload = {
            'answers': [
                {'question_id': 'q1_readiness', 'option_index': 1},
                {'question_id': 'q2a_field', 'option_index': 0},
                {'question_id': 'q3a_business', 'option_index': 0},
                {'question_id': 'q4_confidence_strong', 'option_index': 0},
                {'question_id': 'q5_cross_domain', 'option_index': 4},
                {'question_id': 'q7_challenge', 'option_index': 1},
                {'question_id': 'q8_motivation', 'option_index': 1},
                {'question_id': 'q9_career', 'option_index': 1},
                {'question_id': 'q10_family', 'option_index': 0},
            ],
            'subjects': ['economics', 'accounting', 'business_studies'],
            'grades': {'economics': 'A', 'accounting': 'B+'},
        }
        resp = self.client.post(self.url, payload, format='json')
        assert resp.status_code == 200
        data = resp.json()
        assert data['branch'] == 'arts'
        assert 'field_business' in data['student_signals']['field_interest']
