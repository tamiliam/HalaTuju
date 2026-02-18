"""
API views for AI reports.

Endpoints:
- POST /api/v1/reports/generate/ - Generate AI counselor report
- GET /api/v1/reports/<id>/ - Get report detail
- GET /api/v1/reports/ - List student's reports
"""
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .models import GeneratedReport
from .report_engine import generate_report

logger = logging.getLogger(__name__)


class GenerateReportView(APIView):
    """
    POST /api/v1/reports/generate/

    Generate an AI counselor report from eligibility results.

    Request body:
    {
        "eligible_courses": [...],   // from eligibility check response
        "insights": {...},           // from eligibility check response
        "lang": "bm"                 // optional, default "bm"
    }

    Response:
    {
        "report_id": 1,
        "markdown": "...",
        "counsellor_name": "Cikgu Gopal",
        "model_used": "gemini-2.5-flash"
    }
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        # Validate required fields
        eligible_courses = request.data.get('eligible_courses')
        if not eligible_courses or not isinstance(eligible_courses, list):
            return Response(
                {'error': 'eligible_courses is required (list)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        insights = request.data.get('insights', {})
        lang = request.data.get('lang', 'bm')
        if lang not in ('bm', 'en'):
            lang = 'bm'

        # Load student profile for grades and signals
        profile, _ = StudentProfile.objects.get_or_create(
            supabase_user_id=request.user_id
        )
        grades = profile.grades or {}
        student_signals = profile.student_signals or {}

        # Call Gemini via report engine
        result = generate_report(
            grades=grades,
            eligible_courses=eligible_courses,
            insights=insights,
            student_signals=student_signals,
            lang=lang,
        )

        if 'error' in result:
            return Response(
                {'error': result['error']},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Save report to DB
        report = GeneratedReport.objects.create(
            student=profile,
            title=f'Laporan Kaunseling — {result["counsellor_name"]}',
            content=result['markdown'],
            summary=insights.get('summary_text', ''),
            student_profile_snapshot={
                'grades': grades,
                'gender': profile.gender,
                'nationality': profile.nationality,
                'student_signals': student_signals,
            },
            eligible_courses_snapshot=eligible_courses,
            model_used=result['model_used'],
            generation_time_ms=result.get('generation_time_ms'),
        )

        logger.info(
            f'Report {report.id} generated for {request.user_id} '
            f'({result["model_used"]}, {result.get("generation_time_ms")}ms)'
        )

        return Response({
            'report_id': report.id,
            'markdown': result['markdown'],
            'counsellor_name': result['counsellor_name'],
            'model_used': result['model_used'],
        }, status=status.HTTP_201_CREATED)


class ReportDetailView(APIView):
    """GET /api/v1/reports/<report_id>/"""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, report_id):
        try:
            report = GeneratedReport.objects.get(
                id=report_id,
                student__supabase_user_id=request.user_id,
            )
        except GeneratedReport.DoesNotExist:
            return Response(
                {'error': 'Report not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'report_id': report.id,
            'title': report.title,
            'markdown': report.content,
            'summary': report.summary,
            'model_used': report.model_used,
            'created_at': report.created_at.isoformat(),
        })


class ReportListView(APIView):
    """GET /api/v1/reports/ — List student's generated reports."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        reports = GeneratedReport.objects.filter(
            student__supabase_user_id=request.user_id,
        ).order_by('-created_at')

        return Response({
            'reports': [
                {
                    'report_id': r.id,
                    'title': r.title,
                    'summary': r.summary,
                    'model_used': r.model_used,
                    'created_at': r.created_at.isoformat(),
                }
                for r in reports
            ],
            'count': reports.count(),
        })
