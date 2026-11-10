"""The SPM quiz: the questions, the submit, and the signals saved from it."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import StudentProfile
from ..quiz_data import get_quiz_questions, SUPPORTED_LANGUAGES
from ..quiz_engine import process_quiz_answers


class QuizQuestionsView(APIView):
    """
    GET /api/v1/quiz/questions/?lang=en

    Returns the 6 quiz questions in the requested language.
    Public endpoint — no auth required.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        lang = request.query_params.get('lang', 'en')
        if lang not in SUPPORTED_LANGUAGES:
            lang = 'en'

        questions = get_quiz_questions(lang)
        return Response({
            'questions': questions,
            'total': len(questions),
            'lang': lang,
        })


class QuizSubmitView(APIView):
    """
    POST /api/v1/quiz/submit/

    Submit quiz answers and receive categorised student signals.
    Public endpoint — no auth required (signals are returned, not stored).

    Request body:
    {
        "answers": [
            {"question_id": "q1_modality", "option_index": 0},
            {"question_id": "q2_environment", "option_index": 2},
            {"question_id": "q3_multi", "option_indices": [0, 2]},
            ...
        ],
        "lang": "en"  // optional, defaults to "en"
    }

    Single-select questions use "option_index" (int).
    Multi-select questions use "option_indices" (list of ints).

    Response:
    {
        "student_signals": {
            "work_preference_signals": {"hands_on": 2},
            ...
        },
        "signal_strength": {"hands_on": "strong", ...}
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        answers = request.data.get('answers')
        lang = request.data.get('lang', 'en')

        if not answers or not isinstance(answers, list):
            return Response(
                {'error': 'answers must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate each answer has required fields
        for i, answer in enumerate(answers):
            if 'question_id' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing question_id'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'option_index' not in answer and 'option_indices' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing option_index or option_indices'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = process_quiz_answers(answers, lang=lang)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _persist_quiz_signals(request, result.get('student_signals'))
        return Response(result)


def _persist_quiz_signals(request, student_signals):
    """Opportunistically save quiz signals to the caller's profile.

    The quiz endpoints are ``AllowAny`` so anonymous browsers can take the quiz
    without an account; for signed-in (non-anonymous) callers we additionally
    persist the resulting ``student_signals`` so downstream features that read
    ``profile.student_signals`` — most notably the /scholarship/application
    completeness check — see the quiz as done. Silent no-op when there's no
    user, an anonymous user, no profile yet, or no signals to save.
    """
    if not student_signals:
        return
    user_id = getattr(request, 'user_id', None)
    if not user_id:
        return
    supabase_user = getattr(request, 'supabase_user', None) or {}
    if supabase_user.get('is_anonymous', False):
        return
    try:
        profile = StudentProfile.objects.get(supabase_user_id=user_id)
        profile.student_signals = student_signals
        profile.save(update_fields=['student_signals'])
    except StudentProfile.DoesNotExist:
        return
    except Exception as e:  # noqa: BLE001 — opportunistic save; never fail the request
        import logging
        logging.getLogger('apps.courses.views').warning('quiz signal persist failed: %s', e)
