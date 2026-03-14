"""
API views for courses and eligibility.

Endpoints:
- POST /api/v1/eligibility/check/ - Run eligibility check
- POST /api/v1/ranking/ - Calculate fit scores
- GET /api/v1/courses/ - List courses
- GET /api/v1/courses/<id>/ - Course detail
- GET /api/v1/courses/search/ - Search/browse courses
- GET /api/v1/institutions/ - List institutions
- GET/POST/DELETE /api/v1/saved-courses/ - Saved courses
- GET /api/v1/quiz/questions/ - Get quiz questions
- POST /api/v1/quiz/submit/ - Submit quiz answers
- GET/PUT /api/v1/profile/ - Student profile
- GET/POST /api/v1/outcomes/ - Admission outcomes
- PUT/DELETE /api/v1/outcomes/<id>/ - Outcome detail
"""
import json
import logging
import math
from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.apps import apps

from django.db.models import Count, OuterRef, Q, Subquery

from .models import Course, CourseInstitution, CourseRequirement, Institution, StudentProfile, SavedCourse, AdmissionOutcome, StpmCourse, StpmRequirement
from .engine import (
    StudentProfile as EngineStudentProfile,
    check_eligibility,
    prepare_merit_inputs,
    calculate_merit_score,
    check_merit_probability,
)
from .pathways import check_matric_track, check_stpm_bidang
from .serializers import (
    CourseSerializer,
    InstitutionSerializer,
    MascoOccupationSerializer,
    CourseRequirementSerializer,
    EligibilityRequestSerializer,
    EligibilityResponseSerializer,
    RankingRequestSerializer,
)
from .ranking_engine import get_ranked_results, get_credential_priority
from .stpm_engine import check_stpm_eligibility
from .stpm_ranking import get_stpm_ranked_results
from .insights_engine import generate_insights
from .quiz_data import get_quiz_questions, QUESTION_IDS, SUPPORTED_LANGUAGES
from .quiz_engine import process_quiz_answers
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

logger = logging.getLogger(__name__)


class CourseSearchView(APIView):
    """
    GET /api/v1/courses/search/

    Browse and search the full course catalogue with filters.
    Public endpoint — no auth required.

    Query params:
      ?q=kejuruteraan          (text search on course name)
      &level=Diploma           (Course.level)
      &field=Teknologi Maklumat (Course.frontend_label / StpmCourse.field)
      &source_type=poly        (CourseRequirement.source_type)
      &state=Selangor          (Institution.state via CourseInstitution)
      &qualification=SPM|STPM  (filter by qualification; empty = both)
      &limit=24&offset=0       (pagination)
    """

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        level = request.query_params.get('level', '').strip()
        field = request.query_params.get('field', '').strip()
        source_type = request.query_params.get('source_type', '').strip()
        state = request.query_params.get('state', '').strip()
        qualification = request.query_params.get('qualification', '').strip().upper()

        # Sort order: credential > source_type > merit > name
        SOURCE_TYPE_ORDER = {
            'ua': 5, 'matric': 4, 'stpm': 4, 'pismp': 3, 'poly': 2, 'kkom': 1,
        }

        # Pagination
        try:
            limit = int(request.query_params.get('limit', 0)) or 10000
        except (ValueError, TypeError):
            limit = 24
        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        # ── SPM courses ──────────────────────────────────────────────
        include_spm = qualification in ('', 'SPM')
        spm_results = []
        spm_count = 0

        # Skip SPM if level/source_type filter is STPM-only
        if include_spm and level and level.lower() == 'ijazah sarjana muda':
            include_spm = False

        # Get pathway map for TVET → iljtm/ilkbs resolution
        courses_config = apps.get_app_config('courses')
        pathway_map = getattr(courses_config, 'course_pathway_map', {})

        if include_spm:
            qs = Course.objects.select_related('requirement').all()

            if q:
                qs = qs.filter(course__icontains=q)
            if level:
                qs = qs.filter(level__iexact=level)
            if field:
                qs = qs.filter(frontend_label__iexact=field)
            if source_type:
                # Map iljtm/ilkbs filter to tvet source_type + post-filter
                if source_type in ('iljtm', 'ilkbs'):
                    qs = qs.filter(requirement__source_type='tvet')
                else:
                    qs = qs.filter(requirement__source_type=source_type)
            if state:
                qs = qs.filter(
                    offerings__institution__state__iexact=state
                ).distinct()

            spm_count = qs.count()

            # Subquery: primary institution (alphabetically first offering)
            first_offering = CourseInstitution.objects.filter(
                course=OuterRef('pk')
            ).order_by('institution__institution_name')

            courses_list = list(qs.annotate(
                institution_count=Count('offerings'),
                primary_institution_name=Subquery(
                    first_offering.values('institution__institution_name')[:1]
                ),
                primary_institution_state=Subquery(
                    first_offering.values('institution__state')[:1]
                ),
            ).order_by('course'))

            for c in courses_list:
                req = getattr(c, 'requirement', None)
                st = req.source_type if req else 'poly'
                merit_cutoff = req.merit_cutoff if req else None
                # Resolve TVET → iljtm/ilkbs using pathway map
                pt = pathway_map.get(c.course_id, st)
                # If filtering by iljtm/ilkbs, skip courses that don't match
                if source_type in ('iljtm', 'ilkbs') and pt != source_type:
                    continue
                spm_results.append({
                    'course_id': c.course_id,
                    'course_name': c.course,
                    'level': c.level,
                    'field': c.frontend_label or c.field,
                    'source_type': st,
                    'pathway_type': pt,
                    'merit_cutoff': merit_cutoff,
                    'institution_count': c.institution_count,
                    'institution_name': c.primary_institution_name or '',
                    'institution_state': c.primary_institution_state or '',
                    'qualification': 'SPM',
                })

            # Adjust count if iljtm/ilkbs filter removed some courses
            if source_type in ('iljtm', 'ilkbs'):
                spm_count = len(spm_results)

        # ── STPM courses ─────────────────────────────────────────────
        include_stpm = qualification in ('', 'STPM')
        stpm_results = []
        stpm_count = 0

        # Skip STPM if level filter doesn't match
        if include_stpm and level and level.lower() != 'ijazah sarjana muda':
            include_stpm = False
        # Skip STPM if source_type filter doesn't match
        if include_stpm and source_type and source_type.lower() != 'ua':
            include_stpm = False
        # State filter doesn't apply to STPM (no state data)
        if include_stpm and state:
            include_stpm = False

        if include_stpm:
            stpm_qs = StpmCourse.objects.select_related('requirement').all()

            # Exclude bumiputera-only courses
            stpm_qs = stpm_qs.exclude(requirement__req_bumiputera=True)

            if q:
                stpm_qs = stpm_qs.filter(course_name__icontains=q)
            if field:
                stpm_qs = stpm_qs.filter(field__iexact=field)

            stpm_count = stpm_qs.count()

            for sc in stpm_qs.order_by('course_name'):
                stpm_results.append({
                    'course_id': sc.course_id,
                    'course_name': sc.course_name,
                    'level': 'Ijazah Sarjana Muda',
                    'field': sc.field or '',
                    'source_type': 'ua',
                    'merit_cutoff': sc.merit_score,
                    'institution_count': 1,
                    'institution_name': sc.university,
                    'institution_state': '',
                    'qualification': 'STPM',
                })

        # ── Merge, sort, paginate ─────────────────────────────────────
        total_count = spm_count + stpm_count
        all_results = spm_results + stpm_results

        # Sort: credential > source_type > merit > name
        all_results.sort(key=lambda r: (
            -get_credential_priority(r['course_name'], r.get('source_type', '')),
            -SOURCE_TYPE_ORDER.get(r['source_type'], 0),
            -(r['merit_cutoff'] or 0),
            r['course_name'],
        ))

        # Paginate the merged, sorted list
        paginated = all_results[offset:offset + limit]

        # ── Build dynamic filter options from full DB ─────────────────
        spm_levels = list(
            Course.objects.values_list('level', flat=True)
            .distinct().order_by('level')
        )
        stpm_levels = ['Ijazah Sarjana Muda'] if StpmCourse.objects.exists() else []
        all_levels = sorted(set(spm_levels + stpm_levels))

        spm_fields = list(
            Course.objects.exclude(frontend_label='')
            .values_list('frontend_label', flat=True)
            .distinct().order_by('frontend_label')
        )
        stpm_fields = list(
            StpmCourse.objects.exclude(field='')
            .values_list('field', flat=True)
            .distinct().order_by('field')
        )
        all_fields = sorted(set(spm_fields + stpm_fields))

        spm_source_types = list(
            CourseRequirement.objects.values_list('source_type', flat=True)
            .distinct().order_by('source_type')
        )
        # Replace 'tvet' with 'iljtm' + 'ilkbs' for filter display
        if 'tvet' in spm_source_types:
            spm_source_types.remove('tvet')
            spm_source_types.extend(['iljtm', 'ilkbs'])
        stpm_source_types = []
        all_source_types = sorted(set(spm_source_types + stpm_source_types))

        filters = {
            'levels': all_levels,
            'fields': all_fields,
            'source_types': all_source_types,
            'states': sorted(
                Institution.objects.exclude(state='')
                .values_list('state', flat=True)
                .distinct().order_by('state')
            ),
            'qualifications': ['SPM', 'STPM'],
        }

        return Response({
            'courses': paginated,
            'total_count': total_count,
            'filters': filters,
        })


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

        # Use pre-computed merit from frontend if provided, otherwise recalculate
        student_merit = data.get('student_merit')
        if student_merit is None:
            grades_for_merit = dict(data.get('grades', {}))
            if 'hist' in grades_for_merit:
                grades_for_merit['history'] = grades_for_merit.pop('hist')
            sec1, sec2, sec3 = prepare_merit_inputs(grades_for_merit)
            coq_score = data.get('coq_score', 5.0)
            merit_result = calculate_merit_score(sec1, sec2, sec3, coq_score=coq_score)
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

        # Pre-fetch institution data per course (count + primary name/state)
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
                merit_display_student = None
                merit_display_cutoff = None
                student_merit_for_course = student_merit
                merit_type = req.get('merit_type', 'standard')

                if merit_type == 'matric':
                    # Matric: use pathways.py grade-point formula
                    track_id_map = {
                        'matric-sains': 'sains',
                        'matric-kejuruteraan': 'kejuruteraan',
                        'matric-sains-komputer': 'sains_komputer',
                        'matric-perakaunan': 'perakaunan',
                    }
                    track_id = track_id_map.get(course_id)
                    if track_id:
                        coq = data.get('coq_score', 5.0)
                        matric_result = check_matric_track(track_id, student.grades, coq)
                        if matric_result['eligible'] and matric_result['merit'] is not None:
                            student_merit_for_course = matric_result['merit']
                            if student_merit_for_course >= 94:
                                merit_label, merit_color = "High", "#2ecc71"
                            elif student_merit_for_course >= 89:
                                merit_label, merit_color = "Fair", "#f1c40f"
                            else:
                                merit_label, merit_color = "Low", "#e74c3c"
                        else:
                            # Pathways formula says not eligible — skip
                            continue

                elif merit_type == 'stpm_mata_gred':
                    # STPM: use pathways.py mata gred formula
                    bidang_id_map = {
                        'stpm-sains': 'sains',
                        'stpm-sains-sosial': 'sains_sosial',
                    }
                    bidang_id = bidang_id_map.get(course_id)
                    if bidang_id:
                        stpm_result = check_stpm_bidang(bidang_id, student.grades)
                        if stpm_result['eligible'] and stpm_result['mata_gred'] is not None:
                            mata_gred = stpm_result['mata_gred']
                            max_mg = stpm_result['max_mata_gred']
                            if mata_gred <= 12:
                                merit_label, merit_color = "High", "#2ecc71"
                            elif mata_gred <= max_mg:
                                merit_label, merit_color = "Fair", "#f1c40f"
                            else:
                                merit_label, merit_color = "Low", "#e74c3c"
                            merit_display_student = str(mata_gred)
                            merit_display_cutoff = str(max_mg)
                            student_merit_for_course = (27 - mata_gred) / 24 * 100
                        else:
                            continue

                else:
                    # Standard SPM merit
                    if merit_cutoff and source_type != 'tvet':
                        merit_label, merit_color = check_merit_probability(
                            student_merit, merit_cutoff
                        )

                # Get pathway_type from startup map
                pathway_type = courses_config.course_pathway_map.get(
                    course_id, source_type
                )

                # Institution data
                inst = course_inst_data.get(course_id, {})

                eligible_courses.append({
                    'course_id': course_id,
                    'course_name': course_name,
                    'level': course_level,
                    'field': course_field,
                    'source_type': source_type,
                    'pathway_type': pathway_type,
                    'merit_cutoff': merit_cutoff,
                    'student_merit': student_merit_for_course,
                    'merit_label': merit_label,
                    'merit_color': merit_color,
                    'merit_display_student': merit_display_student,
                    'merit_display_cutoff': merit_display_cutoff,
                    'institution_name': inst.get('inst_name') or '',
                    'institution_count': inst.get('inst_count') or 0,
                    'institution_state': inst.get('inst_state') or '',
                })

                # Update stats
                stats[source_type] = stats.get(source_type, 0) + 1

        # Deduplicate PISMP zone variants.
        # Zone code in course_id[4:6]: 01/06=National, 03=Chinese, 04=Tamil, 05=Special
        # Rules:
        #   1. Collapse entries with identical subject_group_req (regardless of zone)
        #   2. Chinese/Tamil with DIFFERENT requirements from National →
        #      merge into one card "(Aliran Cina/Tamil)" with pismp_languages
        def _pismp_zone(cid):
            z = cid[4:6] if len(cid) >= 6 else ''
            if z == '03':
                return 'cn'
            if z == '04':
                return 'ta'
            if z == '05':
                return 'sn'
            return 'nat'

        # Build a requirements hash per course_id from the DataFrame
        _req_hash = {}
        for _, row in df.iterrows():
            cid = row.get('course_id', '')
            if row.get('source_type') == 'pismp':
                sgr = row.get('subject_group_req')
                if sgr is not None:
                    try:
                        h = json.dumps(sgr, sort_keys=True) if not isinstance(sgr, str) else sgr
                    except (TypeError, ValueError):
                        h = str(sgr)
                else:
                    h = 'null'
                _req_hash[cid] = h

        # Group PISMP by course name
        pismp_groups = defaultdict(lambda: {'nat': [], 'cn': [], 'ta': [], 'sn': []})
        non_pismp = []
        for c in eligible_courses:
            if c['source_type'] == 'pismp':
                zone = _pismp_zone(c['course_id'])
                pismp_groups[c['course_name']][zone].append(c)
            else:
                non_pismp.append(c)

        _lang_labels = {'cn': 'Bahasa Cina', 'ta': 'Bahasa Tamil'}

        deduped_pismp = []
        for name, zones in pismp_groups.items():
            # National + Special Needs → keep one
            nat_entries = zones['nat'] + zones['sn']
            nat_hash = _req_hash.get(nat_entries[0]['course_id']) if nat_entries else None

            if nat_entries:
                deduped_pismp.append(nat_entries[0])

            # Chinese/Tamil: check if requirements differ from National
            diff_langs = []  # languages with genuinely different requirements
            for lang_zone in ('cn', 'ta'):
                lang_entries = zones[lang_zone]
                if not lang_entries:
                    continue
                lang_hash = _req_hash.get(lang_entries[0]['course_id'])
                if lang_hash == nat_hash:
                    # Identical to National → already covered, skip
                    continue
                diff_langs.append((lang_zone, lang_entries[0]))

            if diff_langs:
                # Merge all different-requirement language variants into one card
                base = diff_langs[0][1].copy()
                langs = [_lang_labels[lz] for lz, _ in diff_langs]
                suffix = '/'.join(langs)
                base['course_name'] = f"{name} (Aliran {suffix})"
                base['pismp_languages'] = langs
                deduped_pismp.append(base)

        eligible_courses = non_pismp + deduped_pismp

        # Update stats after dedup
        stats = {}
        for c in eligible_courses:
            st = c['source_type']
            stats[st] = stats.get(st, 0) + 1

        # Default sort: merit chance first, then delta within tier, then credential > pathway > cutoff
        PATHWAY_PRIORITY = {
            'asasi': 8, 'matric': 7, 'stpm': 6,
            'university': 5, 'ua': 5, 'poly': 4, 'pismp': 3, 'kkom': 2,
            'iljtm': 1, 'ilkbs': 1,
        }
        MERIT_LABEL_PRIORITY = {'High': 3, 'Fair': 2, 'Low': 1}
        def _merit_delta(c):
            """Delta sort only for Fair/Low — High uses credential instead."""
            if c.get('merit_label') in ('Fair', 'Low'):
                return -(c.get('student_merit', 0) - (c['merit_cutoff'] or 0))
            return 0  # High / no data: ignore delta, let credential decide

        def _merit_sort_key(c):
            label = c.get('merit_label') or ''
            if label:
                return -MERIT_LABEL_PRIORITY[label]
            # PISMP has no merit data — place in High tier
            if c.get('source_type') == 'pismp':
                return -MERIT_LABEL_PRIORITY['High']
            # ILJTM/ILKBS sit between Fair and Low
            pt = c.get('pathway_type', c.get('source_type', ''))
            if pt in ('iljtm', 'ilkbs'):
                return -1.5
            return -2  # others without data = Fair

        eligible_courses.sort(key=lambda c: (
            _merit_sort_key(c),
            _merit_delta(c),
            -get_credential_priority(c['course_name'], c.get('source_type', '')),
            -PATHWAY_PRIORITY.get(c.get('pathway_type', c.get('source_type', '')), 0),
            -float(c['merit_cutoff'] or 0),  # competitiveness: higher cutoff first
            c['course_name'],
        ))

        logger.info(f"Eligibility check: {len(eligible_courses)} courses eligible")

        # Build pathway stats from eligible courses
        pathway_stats = {}
        for c in eligible_courses:
            pt = c.get('pathway_type', c['source_type'])
            pathway_stats[pt] = pathway_stats.get(pt, 0) + 1

        # Generate deterministic insights from results
        insights = generate_insights(eligible_courses)

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

            # Get requirements from CourseRequirement
            requirements = None
            merit_cutoff = None
            merit_type = 'standard'
            try:
                req = CourseRequirement.objects.get(course_id=course_id)
                requirements = CourseRequirementSerializer(req).data
                if req.merit_cutoff:
                    merit_cutoff = req.merit_cutoff
                merit_type = req.merit_type or 'standard'

                # PISMP: find paired language variants for this programme
                # e.g. if viewing Chinese-medium (03), also check Tamil-medium (04)
                if req.source_type == 'pismp':
                    zone = course_id[4:6] if len(course_id) >= 6 else ''
                    if zone in ('03', '04'):
                        # Find all zone variants of the same programme name
                        nat_req = CourseRequirement.objects.filter(
                            source_type='pismp',
                            course__course=course.course,
                        ).exclude(course_id=course_id)
                        # Get National hash to compare
                        nat_hash = None
                        for nr in nat_req:
                            nz = nr.course_id[4:6] if len(nr.course_id) >= 6 else ''
                            if nz in ('01', '06'):
                                nat_hash = json.dumps(
                                    nr.subject_group_req, sort_keys=True
                                ) if nr.subject_group_req else 'null'
                                break
                        my_hash = json.dumps(
                            req.subject_group_req, sort_keys=True
                        ) if req.subject_group_req else 'null'
                        # Only add languages if this variant differs from National
                        if my_hash != nat_hash:
                            langs = []
                            # Check all zone variants for language differences
                            for nr in nat_req:
                                nz = nr.course_id[4:6] if len(nr.course_id) >= 6 else ''
                                nr_hash = json.dumps(
                                    nr.subject_group_req, sort_keys=True
                                ) if nr.subject_group_req else 'null'
                                if nz == '03' and nr_hash != nat_hash:
                                    langs.append('Bahasa Cina')
                                elif nz == '04' and nr_hash != nat_hash:
                                    langs.append('Bahasa Tamil')
                            # Include self
                            if zone == '03' and 'Bahasa Cina' not in langs:
                                langs.append('Bahasa Cina')
                            if zone == '04' and 'Bahasa Tamil' not in langs:
                                langs.append('Bahasa Tamil')
                            if langs:
                                requirements['pismp_languages'] = sorted(langs)
            except CourseRequirement.DoesNotExist:
                pass

            response_data = {
                'course': course_data,
                'institutions': institutions,
                'career_occupations': career_occupations,
                'requirements': requirements,
            }
            if merit_cutoff is not None:
                response_data['merit_cutoff'] = merit_cutoff
            if merit_type != 'standard':
                response_data['merit_type'] = merit_type

            return Response(response_data)
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
        saved = SavedCourse.objects.filter(
            student_id=request.user_id
        ).select_related('course')
        data = []
        for sc in saved:
            course_data = CourseSerializer(sc.course).data
            course_data['interest_status'] = sc.interest_status
            data.append(course_data)
        return Response({'saved_courses': data})

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
    """DELETE/PATCH /api/v1/saved-courses/<course_id>/"""
    permission_classes = [SupabaseIsAuthenticated]

    def delete(self, request, course_id):
        deleted, _ = SavedCourse.objects.filter(
            student_id=request.user_id,
            course_id=course_id
        ).delete()

        if deleted:
            return Response({'message': 'Course removed'}, status=200)
        return Response({'error': 'Not found'}, status=404)

    def patch(self, request, course_id):
        try:
            sc = SavedCourse.objects.get(
                student_id=request.user_id,
                course_id=course_id,
            )
        except SavedCourse.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        status_value = request.data.get('interest_status')
        valid = ['interested', 'planning', 'applied', 'got_offer']
        if status_value and status_value in valid:
            sc.interest_status = status_value
            sc.save(update_fields=['interest_status'])
            return Response({'message': 'Status updated'})
        return Response({'error': 'Invalid status'}, status=400)


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
            'nric': profile.nric,
            'address': profile.address,
            'phone': profile.phone,
            'family_income': profile.family_income,
            'siblings': profile.siblings,
            'exam_type': profile.exam_type,
            'stpm_grades': profile.stpm_grades,
            'stpm_cgpa': profile.stpm_cgpa,
            'muet_band': profile.muet_band,
            'spm_prereq_grades': profile.spm_prereq_grades,
        })

    def put(self, request):
        profile, _ = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )

        # Update allowed fields
        for field in ['grades', 'gender', 'nationality', 'colorblind',
                      'disability', 'student_signals', 'preferred_state',
                      'name', 'school', 'nric', 'address', 'phone',
                      'family_income', 'siblings', 'exam_type',
                      'stpm_grades', 'stpm_cgpa', 'muet_band',
                      'spm_prereq_grades']:
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
            'nric', 'address', 'phone', 'family_income', 'siblings',
            'exam_type', 'stpm_grades', 'spm_prereq_grades',
        ]

        for field in sync_fields:
            if field in request.data:
                setattr(profile, field, request.data[field])

        # Numeric STPM fields need type coercion
        stpm_cgpa = request.data.get('stpm_cgpa')
        if stpm_cgpa is not None:
            profile.stpm_cgpa = float(stpm_cgpa)
        muet_band = request.data.get('muet_band')
        if muet_band is not None:
            profile.muet_band = int(muet_band)

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


class StpmEligibilityCheckView(APIView):
    """POST /api/v1/stpm/eligibility/check/ — check STPM degree eligibility."""

    def post(self, request):
        stpm_grades = request.data.get('stpm_grades')
        spm_grades = request.data.get('spm_grades', {})
        cgpa = request.data.get('cgpa')
        muet_band = request.data.get('muet_band')

        if not stpm_grades or cgpa is None or muet_band is None:
            return Response(
                {'error': 'stpm_grades, cgpa, and muet_band are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = check_stpm_eligibility(
            stpm_grades=stpm_grades,
            spm_grades=spm_grades,
            cgpa=float(cgpa),
            muet_band=int(muet_band),
            gender=request.data.get('gender', ''),
            nationality=request.data.get('nationality', 'Warganegara'),
            colorblind=request.data.get('colorblind', 'Tidak'),
        )

        return Response({
            'eligible_courses': results,
            'total_eligible': len(results),
        })


class StpmRankingView(APIView):
    """POST /api/v1/stpm/ranking/ — rank eligible STPM courses by fit score."""

    def post(self, request):
        courses = request.data.get('eligible_courses')
        if courses is None:
            return Response(
                {'error': 'eligible_courses is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        student_cgpa = float(request.data.get('student_cgpa', 0))
        signals = request.data.get('student_signals', {})

        ranked = get_stpm_ranked_results(courses, student_cgpa, signals)
        return Response({
            'ranked_courses': ranked,
            'total': len(ranked),
        })


class StpmSearchView(APIView):
    """
    GET /api/v1/stpm/search/
    Browse and search STPM degree courses with filters.
    Public endpoint — no auth required.
    """

    def get(self, request):
        qs = StpmCourse.objects.select_related('requirement').all()

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(course_name__icontains=q)

        university = request.query_params.get('university', '').strip()
        if university:
            qs = qs.filter(university=university)

        stream = request.query_params.get('stream', '').strip()
        if stream:
            if stream in ('science', 'arts'):
                qs = qs.filter(stream__in=[stream, 'both'])
            else:
                qs = qs.filter(stream=stream)

        total_count = qs.count()

        try:
            limit = int(request.query_params.get('limit', 0)) or 10000
        except (ValueError, TypeError):
            limit = 24
        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        courses = qs.order_by('university', 'course_name')[offset:offset + limit]

        results = []
        for prog in courses:
            req = getattr(prog, 'requirement', None)
            results.append({
                'course_id': prog.course_id,
                'course_name': prog.course_name,
                'university': prog.university,
                'stream': prog.stream,
                'min_cgpa': req.min_cgpa if req else 2.0,
                'min_muet_band': req.min_muet_band if req else 1,
                'req_interview': req.req_interview if req else False,
                'no_colorblind': req.no_colorblind if req else False,
            })

        filters = {
            'universities': sorted(
                StpmCourse.objects.values_list('university', flat=True)
                .distinct().order_by('university')
            ),
            'streams': sorted(
                StpmCourse.objects.values_list('stream', flat=True)
                .distinct().order_by('stream')
            ),
        }

        return Response({
            'courses': results,
            'total_count': total_count,
            'filters': filters,
        })


class StpmCourseDetailView(APIView):
    """GET /api/v1/stpm/courses/<course_id>/ — single STPM course detail."""

    STPM_SUBJECT_FIELDS = [
        ('stpm_req_pa', 'Pengajian Am'),
        ('stpm_req_math_t', 'Mathematics (T)'),
        ('stpm_req_math_m', 'Mathematics (M)'),
        ('stpm_req_physics', 'Physics'),
        ('stpm_req_chemistry', 'Chemistry'),
        ('stpm_req_biology', 'Biology'),
        ('stpm_req_economics', 'Economics'),
        ('stpm_req_accounting', 'Accounting'),
        ('stpm_req_business', 'Business Studies'),
    ]

    SPM_PREREQ_FIELDS = [
        ('spm_credit_bm', 'Bahasa Melayu (credit)'),
        ('spm_pass_sejarah', 'Sejarah (pass)'),
        ('spm_credit_bi', 'Bahasa Inggeris (credit)'),
        ('spm_pass_bi', 'Bahasa Inggeris (pass)'),
        ('spm_credit_math', 'Matematik (credit)'),
        ('spm_pass_math', 'Matematik (pass)'),
        ('spm_credit_addmath', 'Matematik Tambahan (credit)'),
        ('spm_credit_science', 'Sains (credit)'),
    ]

    def get(self, request, course_id):
        try:
            prog = StpmCourse.objects.select_related('requirement').get(
                course_id=course_id
            )
        except StpmCourse.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        req = getattr(prog, 'requirement', None)

        stpm_subjects = []
        if req:
            for field_name, label in self.STPM_SUBJECT_FIELDS:
                if getattr(req, field_name, False):
                    stpm_subjects.append(label)

        spm_prerequisites = []
        if req:
            for field_name, label in self.SPM_PREREQ_FIELDS:
                if getattr(req, field_name, False):
                    spm_prerequisites.append(label)

        requirements = {}
        if req:
            requirements = {
                'min_cgpa': req.min_cgpa,
                'min_muet_band': req.min_muet_band,
                'stpm_min_subjects': req.stpm_min_subjects,
                'stpm_min_grade': req.stpm_min_grade,
                'stpm_subjects': stpm_subjects,
                'stpm_subject_group': req.stpm_subject_group,
                'spm_prerequisites': spm_prerequisites,
                'spm_subject_group': req.spm_subject_group,
                'req_interview': req.req_interview,
                'no_colorblind': req.no_colorblind,
                'req_medical_fitness': req.req_medical_fitness,
                'req_malaysian': req.req_malaysian,
                'req_bumiputera': req.req_bumiputera,
            }

        # Look up full institution data by university name
        institution_data = None
        try:
            inst = Institution.objects.get(
                institution_name=prog.university
            )
            institution_data = {
                'institution_id': inst.institution_id,
                'institution_name': inst.institution_name,
                'acronym': inst.acronym or '',
                'type': inst.type or '',
                'category': inst.category or '',
                'state': inst.state or '',
                'url': inst.url or '',
            }
        except Institution.DoesNotExist:
            pass

        return Response({
            'course_id': prog.course_id,
            'course_name': prog.course_name,
            'university': prog.university,
            'stream': prog.stream,
            'field': prog.field,
            'category': prog.category,
            'description': prog.description,
            'merit_score': prog.merit_score,
            'requirements': requirements,
            'institution': institution_data,
        })


class CalculateMeritView(APIView):
    """
    POST /api/v1/calculate/merit/

    Accepts frontend grade keys + coq_score, returns academic_merit and final_merit.
    No authentication required.

    Request:  {"grades": {"BM": "A", "BI": "B+", ...}, "coq_score": 8.0}
    Response: {"academic_merit": 85.5, "final_merit": 93.5}
    """

    def post(self, request):
        data = request.data
        raw_grades = data.get('grades')
        if not raw_grades or not isinstance(raw_grades, dict):
            return Response(
                {'error': 'grades field is required and must be a dict'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Map frontend keys (BM, BI, MAT...) to engine keys (bm, eng, math...)
        key_map = EligibilityRequestSerializer.GRADE_KEY_MAP
        mapped_grades = {}
        for key, grade in raw_grades.items():
            engine_key = key_map.get(key, key.lower())
            mapped_grades[engine_key] = grade

        # Engine expects 'history' not 'hist'
        if 'hist' in mapped_grades:
            mapped_grades['history'] = mapped_grades.pop('hist')

        coq_score = float(data.get('coq_score', 5.0))

        sec1, sec2, sec3 = prepare_merit_inputs(mapped_grades)
        result = calculate_merit_score(sec1, sec2, sec3, coq_score=coq_score)

        return Response({
            'academic_merit': result['academic_merit'],
            'final_merit': result['final_merit'],
        })
