"""The SPM eligibility check and the ranking."""
import logging
import json
import math

from django.apps import apps
from django.db.models import Count, OuterRef, Subquery
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..bumiputera import resolve_bumiputera
from ..eligibility_service import (
    compute_course_merit,
    compute_stats,
    compute_student_merit,
    deduplicate_pismp,
    sort_eligible_courses,
)
from ..engine import check_eligibility, StudentProfile as EngineStudentProfile
from ..insights_engine import generate_insights
from ..models import Course, CourseInstitution
from ..pismp_taxonomy import aliran_of
from ..ranking_engine import get_ranked_results
from ..serializers import EligibilityRequestSerializer, RankingRequestSerializer

logger = logging.getLogger('apps.courses.views')


class EligibilityCheckView(APIView):
    """
    POST /api/v1/eligibility/check/

    Check which courses a student is eligible for based on their profile.

    Request body:
    {
        "grades": {"bm": "A+", "math": "B", "eng": "A", ...},
        "gender": "Lelaki",
        "nationality": "Warganegara",
        "colorblind": false,
        "disability": false
    }

    Response:
    {
        "eligible_courses": [...],
        "total_count": 123,
        "stats": {"poly": 50, "kkom": 30, ...}
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EligibilityRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        student_merit = compute_student_merit(data)

        student = EngineStudentProfile(
            grades=data.get('grades', {}),
            gender=data.get('gender', 'Lelaki'),
            nationality=data.get('nationality', 'Warganegara'),
            colorblind=data.get('colorblind', False),
            disability=data.get('disability', False),
            other_tech=data.get('other_tech', False),
            other_voc=data.get('other_voc', False),
            bumiputera=resolve_bumiputera(data.get('bumiputera'), data.get('nationality', 'Warganegara')),
        )

        courses_config = apps.get_app_config('courses')
        df = courses_config.ensure_data()  # TD-047: an empty frame retries the load once first

        if df is None or df.empty:
            logger.error("No course requirements loaded")
            return Response(
                {'error': 'Course data not loaded'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Pre-fetch lookups
        course_details = {
            c.course_id: c for c in Course.objects.all()
        }
        first_offering = CourseInstitution.objects.filter(
            course=OuterRef('pk')
        ).order_by('institution__institution_name')
        course_inst_data = {
            c['course_id']: c for c in Course.objects.annotate(
                inst_count=Count('offerings'),
                inst_name=Subquery(
                    first_offering.values('institution__institution_name')[:1]
                ),
                inst_state=Subquery(
                    first_offering.values('institution__state')[:1]
                ),
            ).values('course_id', 'inst_count', 'inst_name', 'inst_state')
        }

        # Single pass: eligibility check + PISMP req hash collection
        eligible_courses = []
        pismp_req_hashes = {}

        for _, row in df.iterrows():
            req = row.to_dict()

            # Collect PISMP requirement hashes in same pass (fixes TD-044)
            course_id = req.get('course_id', '')
            if req.get('source_type') == 'pismp':
                sgr = req.get('subject_group_req')
                if sgr is not None:
                    try:
                        pismp_req_hashes[course_id] = (
                            json.dumps(sgr, sort_keys=True)
                            if not isinstance(sgr, str) else sgr
                        )
                    except (TypeError, ValueError):
                        pismp_req_hashes[course_id] = str(sgr)
                else:
                    pismp_req_hashes[course_id] = 'null'

            is_eligible, audit = check_eligibility(student, req)
            if not is_eligible:
                continue

            source_type = req.get('source_type', 'poly')

            # Handle NaN for JSON serialization
            merit_cutoff = req.get('merit_cutoff')
            if merit_cutoff is not None and (math.isnan(merit_cutoff) or math.isinf(merit_cutoff)):
                merit_cutoff = None

            # Per-course merit calculation
            merit_type = req.get('merit_type', 'standard')
            merit_result = compute_course_merit(
                merit_type=merit_type,
                source_type=source_type,
                merit_cutoff=merit_cutoff,
                student_merit=student_merit,
                course_id=course_id,
                data=data,
                grades=student.grades,
            )
            if merit_result is None:
                continue  # Pathway says not eligible

            # Course details
            course = course_details.get(course_id)
            course_name = course.course if course else course_id
            pathway_type = courses_config.course_pathway_map.get(
                course_id, source_type
            )
            inst = course_inst_data.get(course_id, {})

            eligible_courses.append({
                'course_id': course_id,
                'course_name': course_name,
                'level': course.level if course else '',
                'field': course.field if course else '',
                'field_key': (course.field_key_id or '') if course else '',
                'source_type': source_type,
                'pathway_type': pathway_type,
                'merit_cutoff': merit_result['merit_cutoff'],
                'student_merit': merit_result['student_merit'],
                'merit_label': merit_result['merit_label'],
                'merit_color': merit_result['merit_color'],
                'merit_display_student': merit_result['merit_display_student'],
                'merit_display_cutoff': merit_result['merit_display_cutoff'],
                'institution_name': inst.get('inst_name') or '',
                'institution_count': inst.get('inst_count') or 0,
                'institution_state': inst.get('inst_state') or '',
                # Aliran (school type) — only for PISMP, so the apply-form picker can
                # group teacher-training courses by SK/SJKC/SJKT before the bidang.
                'aliran': aliran_of(course_name, course_id) if source_type == 'pismp' else '',
            })

        eligible_courses = deduplicate_pismp(eligible_courses, pismp_req_hashes)
        eligible_courses = sort_eligible_courses(eligible_courses)
        stats, pathway_stats = compute_stats(eligible_courses)
        insights = generate_insights(eligible_courses)

        logger.info(f"Eligibility check: {len(eligible_courses)} courses eligible")

        return Response({
            'eligible_courses': eligible_courses,
            'total_count': len(eligible_courses),
            'stats': stats,
            'pathway_stats': pathway_stats,
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
        "ranked": [...],
        "total_ranked": 123
    }
    """
    permission_classes = [AllowAny]

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

        result['total_ranked'] = len(result['ranked'])

        return Response(result)
