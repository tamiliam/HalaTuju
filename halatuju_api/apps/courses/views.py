"""
API views for courses and eligibility.

Endpoints:
- POST /api/v1/eligibility/check/ - Run eligibility check
- POST /api/v1/ranking/ - Calculate fit scores
- GET /api/v1/courses/ - List courses
- GET /api/v1/courses/<id>/ - Course detail
- GET /api/v1/institutions/ - List institutions
- GET/POST/DELETE /api/v1/saved-courses/ - Saved courses
- GET /api/v1/quiz/questions/ - Get quiz questions
- POST /api/v1/quiz/submit/ - Submit quiz answers
- GET/PUT /api/v1/profile/ - Student profile
- GET/POST /api/v1/outcomes/ - Admission outcomes
- PUT/DELETE /api/v1/outcomes/<id>/ - Outcome detail
"""
import logging
import math
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.apps import apps

from .models import Course, Institution, StudentProfile, SavedCourse, AdmissionOutcome
from .engine import (
    StudentProfile as EngineStudentProfile,
    check_eligibility,
    prepare_merit_inputs,
    calculate_merit_score,
    check_merit_probability,
)
from .serializers import (
    CourseSerializer,
    InstitutionSerializer,
    MascoOccupationSerializer,
    EligibilityRequestSerializer,
    EligibilityResponseSerializer,
    RankingRequestSerializer,
)
from .ranking_engine import get_ranked_results
from .insights_engine import generate_insights
from .quiz_data import get_quiz_questions, QUESTION_IDS, SUPPORTED_LANGUAGES
from .quiz_engine import process_quiz_answers
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

logger = logging.getLogger(__name__)


class EligibilityCheckView(APIView):
    """
    POST /api/v1/eligibility/check/

    Check which courses a student is eligible for based on their profile.

    Request body:
    {
        "grades": {"bm": "A+", "math": "B", "eng": "A", ...},
        "gender": "Lelaki",
        "nationality": "Warganegara",
        "colorblind": "Tidak",
        "disability": "Tidak"
    }

    Response:
    {
        "eligible_courses": [...],
        "total_count": 123,
        "stats": {"poly": 50, "kkom": 30, ...}
    }
    """

    def post(self, request):
        # Validate request
        serializer = EligibilityRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Compute student merit score once (for traffic light indicators)
        grades_for_merit = dict(data.get('grades', {}))
        if 'hist' in grades_for_merit:
            grades_for_merit['history'] = grades_for_merit.pop('hist')
        sec1, sec2, sec3 = prepare_merit_inputs(grades_for_merit)
        merit_result = calculate_merit_score(sec1, sec2, sec3, coq_score=5.0)
        student_merit = merit_result['final_merit']

        # Build StudentProfile for engine
        student = EngineStudentProfile(
            grades=data.get('grades', {}),
            gender=data.get('gender', 'Lelaki'),
            nationality=data.get('nationality', 'Warganegara'),
            colorblind=data.get('colorblind', 'Tidak'),
            disability=data.get('disability', 'Tidak'),
            other_tech=data.get('other_tech', False),
            other_voc=data.get('other_voc', False),
        )

        # Get requirements DataFrame from app config (hybrid approach)
        courses_config = apps.get_app_config('courses')
        df = courses_config.requirements_df

        if df is None or df.empty:
            logger.error("No course requirements loaded")
            return Response(
                {'error': 'Course data not loaded'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Run eligibility check for each course
        eligible_courses = []
        stats = {}

        # Pre-fetch course details for efficient lookups
        course_details = {
            c.course_id: c for c in Course.objects.all()
        }

        for _, row in df.iterrows():
            req = row.to_dict()
            is_eligible, audit = check_eligibility(student, req)

            if is_eligible:
                course_id = req.get('course_id')
                source_type = req.get('source_type', 'poly')

                # Handle NaN values for JSON serialization
                merit_cutoff = req.get('merit_cutoff')
                if merit_cutoff is not None and (math.isnan(merit_cutoff) or math.isinf(merit_cutoff)):
                    merit_cutoff = None

                # Get course details
                course = course_details.get(course_id)
                course_name = course.course if course else course_id
                course_level = course.level if course else ''
                course_field = (course.frontend_label or course.field) if course else ''

                # Compute merit traffic light for this course
                merit_label = None
                merit_color = None
                if merit_cutoff and source_type != 'tvet':
                    merit_label, merit_color = check_merit_probability(
                        student_merit, merit_cutoff
                    )

                eligible_courses.append({
                    'course_id': course_id,
                    'course_name': course_name,
                    'level': course_level,
                    'field': course_field,
                    'source_type': source_type,
                    'merit_cutoff': merit_cutoff,
                    'student_merit': student_merit,
                    'merit_label': merit_label,
                    'merit_color': merit_color,
                })

                # Update stats
                stats[source_type] = stats.get(source_type, 0) + 1

        logger.info(f"Eligibility check: {len(eligible_courses)} courses eligible")

        # Generate deterministic insights from results
        insights = generate_insights(eligible_courses)

        return Response({
            'eligible_courses': eligible_courses,
            'total_count': len(eligible_courses),
            'stats': stats,
            'insights': insights,
        })


class RankingView(APIView):
    """
    POST /api/v1/ranking/

    Calculate fit scores for eligible courses based on student signals.

    Request body:
    {
        "eligible_courses": [
            {"course_id": "DIP001", "institution_id": "POLY-001",
             "course_name": "Diploma Kejuruteraan Mekanikal",
             "merit_cutoff": 45.0, "student_merit": 50.0},
            ...
        ],
        "student_signals": {
            "work_preference_signals": {"hands_on": 2, ...},
            "environment_signals": {...},
            ...
        }
    }

    Response:
    {
        "top_5": [...],
        "rest": [...],
        "total_ranked": 123
    }
    """

    def post(self, request):
        serializer = RankingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        eligible_courses = data['eligible_courses']
        student_signals = data['student_signals']

        # Get cached ranking data from app config
        courses_config = apps.get_app_config('courses')
        course_tags_map = courses_config.course_tags_map
        inst_modifiers_map = courses_config.inst_modifiers_map
        inst_subcategories = courses_config.inst_subcategories

        student_profile = {'student_signals': student_signals}

        result = get_ranked_results(
            eligible_courses,
            student_profile,
            course_tags_map,
            inst_modifiers_map,
            inst_subcategories,
        )

        result['total_ranked'] = len(result['top_5']) + len(result['rest'])

        return Response(result)


class QuizQuestionsView(APIView):
    """
    GET /api/v1/quiz/questions/?lang=en

    Returns the 6 quiz questions in the requested language.
    Public endpoint — no auth required.
    """

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
            ...
        ],
        "lang": "en"  // optional, defaults to "en"
    }

    Response:
    {
        "student_signals": {
            "work_preference_signals": {"hands_on": 2},
            ...
        },
        "signal_strength": {"hands_on": "strong", ...}
    }
    """

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
            if 'option_index' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing option_index'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = process_quiz_answers(answers, lang=lang)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result)


class CourseListView(APIView):
    """GET /api/v1/courses/ - List all courses with pagination."""

    def get(self, request):
        courses = Course.objects.all()
        serializer = CourseSerializer(courses, many=True)
        return Response({
            'courses': serializer.data,
            'count': len(serializer.data),
        })


class CourseDetailView(APIView):
    """GET /api/v1/courses/<course_id>/ - Course detail with institutions."""

    def get(self, request, course_id):
        from .models import CourseInstitution

        try:
            course = Course.objects.get(course_id=course_id)
            course_data = CourseSerializer(course).data

            # Get institutions offering this course, with per-offering details
            links = CourseInstitution.objects.filter(
                course_id=course_id
            ).select_related('institution')

            institutions = []
            for link in links:
                if not link.institution:
                    continue
                inst_data = InstitutionSerializer(link.institution).data
                # Add per-offering details from CourseInstitution
                inst_data['hyperlink'] = link.hyperlink or ''
                inst_data['tuition_fee_semester'] = link.tuition_fee_semester or ''
                inst_data['hostel_fee_semester'] = link.hostel_fee_semester or ''
                inst_data['registration_fee'] = link.registration_fee or ''
                inst_data['monthly_allowance'] = float(link.monthly_allowance) if link.monthly_allowance else None
                inst_data['practical_allowance'] = float(link.practical_allowance) if link.practical_allowance else None
                inst_data['free_hostel'] = link.free_hostel
                inst_data['free_meals'] = link.free_meals
                institutions.append(inst_data)

            # Get career occupations linked to this course
            career_occupations = MascoOccupationSerializer(
                course.career_occupations.all(), many=True
            ).data

            return Response({
                'course': course_data,
                'institutions': institutions,
                'career_occupations': career_occupations,
            })
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InstitutionListView(APIView):
    """GET /api/v1/institutions/ - List all institutions."""

    def get(self, request):
        # Filter by state if provided
        state = request.query_params.get('state')
        qs = Institution.objects.all()
        if state:
            qs = qs.filter(state__iexact=state)

        serializer = InstitutionSerializer(qs, many=True)
        return Response({
            'institutions': serializer.data,
            'count': len(serializer.data),
        })


class InstitutionDetailView(APIView):
    """GET /api/v1/institutions/<id>/ - Institution detail."""

    def get(self, request, institution_id):
        try:
            institution = Institution.objects.get(institution_id=institution_id)
            serializer = InstitutionSerializer(institution)
            return Response(serializer.data)
        except Institution.DoesNotExist:
            return Response(
                {'error': 'Institution not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SavedCoursesView(APIView):
    """
    GET/POST /api/v1/saved-courses/

    Requires authentication.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        saved = SavedCourse.objects.filter(student_id=request.user_id)
        courses = [s.course for s in saved.select_related('course')]
        serializer = CourseSerializer(courses, many=True)
        return Response({'saved_courses': serializer.data})

    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response({'error': 'course_id required'}, status=400)

        try:
            course = Course.objects.get(course_id=course_id)
            profile, _ = StudentProfile.objects.get_or_create(
                supabase_user_id=request.user_id
            )
            SavedCourse.objects.get_or_create(student=profile, course=course)
            return Response({'message': 'Course saved'}, status=201)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=404)


class SavedCourseDetailView(APIView):
    """DELETE /api/v1/saved-courses/<course_id>/"""
    permission_classes = [SupabaseIsAuthenticated]

    def delete(self, request, course_id):
        deleted, _ = SavedCourse.objects.filter(
            student_id=request.user_id,
            course_id=course_id
        ).delete()

        if deleted:
            return Response({'message': 'Course removed'}, status=200)
        return Response({'error': 'Not found'}, status=404)


class ProfileView(APIView):
    """
    GET/PUT /api/v1/profile/

    Requires authentication.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        profile, created = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        return Response({
            'grades': profile.grades,
            'gender': profile.gender,
            'nationality': profile.nationality,
            'colorblind': profile.colorblind,
            'disability': profile.disability,
            'student_signals': profile.student_signals,
            'preferred_state': profile.preferred_state,
            'name': profile.name,
            'school': profile.school,
        })

    def put(self, request):
        profile, _ = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        # Update allowed fields
        for field in ['grades', 'gender', 'nationality', 'colorblind',
                      'disability', 'student_signals', 'preferred_state',
                      'name', 'school']:
            if field in request.data:
                setattr(profile, field, request.data[field])

        profile.save()
        return Response({'message': 'Profile updated'})


class ProfileSyncView(APIView):
    """
    POST /api/v1/profile/sync/

    Sync localStorage data to backend profile after first login.
    Accepts grades, demographics, quiz signals, name, and school in one call.
    Creates the profile if it doesn't exist.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        profile, created = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        sync_fields = [
            'grades', 'gender', 'nationality', 'colorblind', 'disability',
            'student_signals', 'preferred_state', 'name', 'school',
        ]

        for field in sync_fields:
            if field in request.data:
                setattr(profile, field, request.data[field])

        profile.save()
        return Response({
            'message': 'Profile synced',
            'created': created,
        })


class OutcomeListView(APIView):
    """
    GET /api/v1/outcomes/ — List own admission outcomes.
    POST /api/v1/outcomes/ — Create a new outcome.

    Requires authentication. All queries filtered to requesting user.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        outcomes = AdmissionOutcome.objects.filter(
            student_id=request.user_id
        ).select_related('course', 'institution')

        data = []
        for o in outcomes:
            data.append({
                'id': o.id,
                'course_id': o.course_id,
                'course_name': o.course.course if o.course else o.course_id,
                'institution_id': o.institution_id,
                'institution_name': o.institution.institution_name if o.institution else None,
                'status': o.status,
                'intake_year': o.intake_year,
                'intake_session': o.intake_session,
                'notes': o.notes,
                'applied_at': o.applied_at,
                'outcome_at': o.outcome_at,
                'created_at': o.created_at.isoformat(),
                'updated_at': o.updated_at.isoformat(),
            })

        return Response({'outcomes': data, 'count': len(data)})

    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response(
                {'error': 'course_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            course = Course.objects.get(course_id=course_id)
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile, _ = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        institution = None
        institution_id = request.data.get('institution_id')
        if institution_id:
            try:
                institution = Institution.objects.get(institution_id=institution_id)
            except Institution.DoesNotExist:
                pass

        outcome, created = AdmissionOutcome.objects.get_or_create(
            student=profile,
            course=course,
            institution=institution,
            defaults={
                'status': request.data.get('status', 'applied'),
                'intake_year': request.data.get('intake_year'),
                'intake_session': request.data.get('intake_session', ''),
                'notes': request.data.get('notes', ''),
                'applied_at': request.data.get('applied_at'),
            },
        )

        if not created:
            return Response(
                {'error': 'Outcome already exists for this course/institution'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'id': outcome.id,
            'message': 'Outcome created',
        }, status=status.HTTP_201_CREATED)


class OutcomeDetailView(APIView):
    """
    PUT /api/v1/outcomes/<id>/ — Update outcome status.
    DELETE /api/v1/outcomes/<id>/ — Delete outcome.

    Requires authentication. Only own outcomes.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def _get_outcome(self, request, outcome_id):
        try:
            return AdmissionOutcome.objects.get(
                id=outcome_id,
                student_id=request.user_id,
            )
        except AdmissionOutcome.DoesNotExist:
            return None

    def put(self, request, outcome_id):
        outcome = self._get_outcome(request, outcome_id)
        if not outcome:
            return Response(
                {'error': 'Outcome not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        for field in ['status', 'intake_year', 'intake_session', 'notes',
                       'applied_at', 'outcome_at']:
            if field in request.data:
                setattr(outcome, field, request.data[field])

        outcome.save()
        return Response({'message': 'Outcome updated'})

    def delete(self, request, outcome_id):
        outcome = self._get_outcome(request, outcome_id)
        if not outcome:
            return Response(
                {'error': 'Outcome not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        outcome.delete()
        return Response({'message': 'Outcome deleted'})
