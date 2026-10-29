"""The STPM quiz endpoints: `StpmQuizQuestionsView`, `StpmQuizResolveView`, `StpmQuizSubmitView`.

Moved verbatim out of `views.py` (Bumi coverage Sprint D1, 2026-10-29), a moves-only split:
`views.py` is a ledgered oversize file (see `halatuju_api/CLAUDE.md`, `## Code standards`) and sat
3 lines under its allowance, and Sprint D1 adds the Bumiputera doors to its SPM views. `urls.py`
routes to this module; the only other edit is the import block, which came with the code.
"""
import json

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .stpm_quiz_engine import (
    get_stpm_quiz_questions,
    resolve_q3_and_q4,
    process_stpm_quiz,
)
from .views import _persist_quiz_signals


class StpmQuizQuestionsView(APIView):
    """
    GET /api/v1/stpm/quiz/questions/

    Returns the STPM quiz questions for a student based on their subjects.
    Subjects determine the branch (Science/Arts/Mixed) and which questions
    are shown. Q3/Q4 are resolved after Q2 is answered.

    Query params:
        subjects: comma-separated subject keys (e.g. 'physics,chemistry,mathematics_t')
        grades: JSON-encoded subject→grade mapping (e.g. '{"physics":"A","chemistry":"B+"}')
        lang: language code (en/bm/ta, defaults to en)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        subjects_raw = request.query_params.get('subjects', '')
        grades_raw = request.query_params.get('grades', '{}')
        lang = request.query_params.get('lang', 'en')

        if not subjects_raw:
            return Response(
                {'error': 'subjects parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subjects = [s.strip() for s in subjects_raw.split(',') if s.strip()]
        if len(subjects) < 2:
            return Response(
                {'error': 'At least 2 STPM subjects are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            grades = json.loads(grades_raw)
        except (json.JSONDecodeError, TypeError):
            return Response(
                {'error': 'grades must be valid JSON'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = get_stpm_quiz_questions(subjects, grades, lang)
        return Response(result)


class StpmQuizResolveView(APIView):
    """
    POST /api/v1/stpm/quiz/resolve/

    After the student answers Q2, resolve Q3 and Q4 based on their
    chosen field direction and actual grades.

    Request body:
    {
        "field_signal": "field_engineering",
        "branch": "science",
        "grades": {"physics": "A", "chemistry": "B+"},
        "lang": "en"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        field_signal = request.data.get('field_signal')
        branch = request.data.get('branch')
        grades = request.data.get('grades', {})
        lang = request.data.get('lang', 'en')

        if not field_signal:
            return Response(
                {'error': 'field_signal is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not branch:
            return Response(
                {'error': 'branch is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = resolve_q3_and_q4(field_signal, branch, grades, lang)
        return Response(result)


class StpmQuizSubmitView(APIView):
    """
    POST /api/v1/stpm/quiz/submit/

    Submit STPM quiz answers and receive categorised student signals.

    Request body:
    {
        "answers": [
            {"question_id": "q1_readiness", "option_index": 0},
            {"question_id": "q2s_field", "option_index": 1},
            ...
        ],
        "subjects": ["physics", "chemistry", "mathematics_t"],
        "grades": {"physics": "A", "chemistry": "B+", "mathematics_t": "A-"},
        "lang": "en"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        answers = request.data.get('answers')
        subjects = request.data.get('subjects')
        grades = request.data.get('grades', {})
        lang = request.data.get('lang', 'en')

        if not answers or not isinstance(answers, list):
            return Response(
                {'error': 'answers must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not subjects or not isinstance(subjects, list):
            return Response(
                {'error': 'subjects must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for i, answer in enumerate(answers):
            if 'question_id' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing question_id'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'option_index' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing option_index'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = process_stpm_quiz(answers, subjects, grades, lang=lang)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _persist_quiz_signals(request, result.get('student_signals'))
        return Response(result)
