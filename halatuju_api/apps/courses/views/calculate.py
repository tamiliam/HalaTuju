"""Server-side calculators: merit, CGPA and the pre-U pathways."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..engine import calculate_merit_score, prepare_merit_inputs
from ..exam_questions import third_route_calculation
from ..pathways import check_all_pathways, get_pathway_fit_score
from ..stpm_pngk import stpm_calculation


class CalculateMeritView(APIView):
    """
    POST /api/v1/calculate/merit/

    Accepts frontend grade keys + coq_score, returns academic_merit and final_merit.
    No authentication required.

    Request:  {"grades": {"BM": "A", "BI": "B+", ...}, "coq_score": 8.0}
    Response: {"academic_merit": 85.5, "final_merit": 93.5}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        raw_grades = data.get('grades')
        if not raw_grades or not isinstance(raw_grades, dict):
            return Response(
                {'error': 'grades field is required and must be a dict'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Keys arrive as engine keys (bm, eng, math...) — pass through
        mapped_grades = dict(raw_grades)

        # Engine expects 'history' not 'hist'
        if 'hist' in mapped_grades:
            mapped_grades['history'] = mapped_grades.pop('hist')

        coq_score = float(data.get('coq_score', 5.0))

        # TD-063: honour explicit stream picks if sent; else fall back internally.
        sec1, sec2, sec3 = prepare_merit_inputs(
            mapped_grades, stream_subjects=data.get('stream_subjects'))
        result = calculate_merit_score(sec1, sec2, sec3, coq_score=coq_score)

        return Response({
            'academic_merit': result['academic_merit'],
            'final_merit': result['final_merit'],
        })


class CalculateCgpaView(APIView):
    """
    POST /api/v1/calculate/cgpa/

    Accepts STPM grades + koko_score, returns the CGPA and the merit SEPARATELY (owner ruling
    2026-10-28) — `stpm_pngk.stpm_calculation`. No authentication required.

    Request:  {"stpm_grades": {"PA": "A", "MATH_T": "B+", ...}, "koko_score": 8}
    Response: {"cgpa": 3.75 (the PNGK; null below PA + three), "counted": ["PA", ...],
               "overall": 3.69 (0.9 x PNGK + 0.04 x koko; null without both), "merit_percent": 92.25}

    Third route (S2a): {"kind": "matric"|"asasi"|"diploma", "higher_cgpa": 3.5, "koko_score": 8}
    -> {"cgpa": 3.47, "academic_cgpa": 3.5, "merit_percent": 86.75} (Diploma = CGPA as is), from
    `exam_questions.third_route_calculation` (the gate's own arithmetic); a bad body -> 400.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        if 'higher_cgpa' in data:
            out = third_route_calculation(data)
            if out is None:
                return Response({'error': 'kind, higher_cgpa (0-4] and koko_score are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response(out)
        stpm_grades = data.get('stpm_grades')
        if not stpm_grades or not isinstance(stpm_grades, dict):
            return Response(
                {'error': 'stpm_grades field is required and must be a dict'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(stpm_calculation(stpm_grades, data.get('koko_score')))


class CalculatePathwaysView(APIView):
    """Check all pre-U pathway eligibility and fit scores.

    POST /api/v1/calculate/pathways/
    Body: { grades: {BM: "A", ...}, coq_score: 8.0, signals?: {...} }
    Response: { pathways: [{track_id, eligible, merit, mata_gred, fit_score, ...}] }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        grades_raw = request.data.get('grades')
        if not grades_raw:
            return Response(
                {'error': 'grades is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coq_score = float(request.data.get('coq_score', 0))
        signals = request.data.get('signals')

        # Keys arrive as engine keys — pass through
        grades = dict(grades_raw)

        results = check_all_pathways(grades, coq_score)

        # Add fit scores
        for r in results:
            r['fit_score'] = get_pathway_fit_score(r, signals)

        return Response({'pathways': results})
