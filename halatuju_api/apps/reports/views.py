"""
API views for AI reports.

Endpoints:
- POST /api/v1/reports/generate/ - Generate AI counselor report
- GET /api/v1/reports/<id>/ - Get report detail
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class GenerateReportView(APIView):
    """
    POST /api/v1/reports/generate/

    Generate an AI counselor report based on student profile and quiz results.
    """

    def post(self, request):
        # TODO: Implement AI report generation (port from ai_wrapper.py)
        return Response({
            'message': 'Report generation - coming soon',
            'report_id': None,
        })


class ReportDetailView(APIView):
    """GET /api/v1/reports/<report_id>/"""

    def get(self, request, report_id):
        # TODO: Implement report retrieval
        return Response({
            'message': 'Report detail - coming soon',
            'report_id': report_id,
        })
