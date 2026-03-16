"""
Partner admin API views.

Endpoints:
- GET /api/v1/admin/dashboard/ - Partner dashboard stats
- GET /api/v1/admin/students/ - List referred students
- GET /api/v1/admin/students/export/ - CSV export of referred students
- GET /api/v1/admin/students/<user_id>/ - Student detail
"""
import csv
from collections import Counter
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .models import StudentProfile, PartnerOrganisation
from .serializers_admin import PartnerStudentListSerializer, PartnerStudentDetailSerializer


class PartnerAdminMixin:
    """Validate partner admin access and resolve org."""
    permission_classes = [SupabaseIsAuthenticated]

    def get_partner_org(self, request):
        user_id = request.user_id
        if not user_id:
            return None
        try:
            profile = StudentProfile.objects.get(supabase_user_id=user_id)
        except StudentProfile.DoesNotExist:
            return None
        if not profile.admin_org_code:
            return None
        try:
            return PartnerOrganisation.objects.get(code=profile.admin_org_code, is_active=True)
        except PartnerOrganisation.DoesNotExist:
            return None

    def get_partner_students(self, request):
        org = self.get_partner_org(request)
        if not org:
            return None, None
        students = StudentProfile.objects.filter(
            referred_by_org=org,
        ).order_by('-created_at')
        return students, org


class PartnerDashboardView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/dashboard/ - Partner dashboard statistics."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        total = students.count()
        completed = students.exclude(grades={}).count()
        by_exam = {
            'spm': students.filter(exam_type='spm').count(),
            'stpm': students.filter(exam_type='stpm').count(),
        }

        field_counter = Counter()
        for s in students:
            signals = s.student_signals or {}
            fi = signals.get('field_interest', {})
            if isinstance(fi, dict):
                for field in fi:
                    field_counter[field] += 1
        top_fields = [{'field': f, 'count': c} for f, c in field_counter.most_common(5)]

        return Response({
            'org_name': org.name,
            'total_students': total,
            'completed_onboarding': completed,
            'by_exam_type': by_exam,
            'top_fields': top_fields,
        })


class PartnerStudentListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/ - List referred students."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        serializer = PartnerStudentListSerializer(students, many=True)
        return Response({
            'org_name': org.name,
            'count': students.count(),
            'students': serializer.data,
        })


class PartnerStudentDetailView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/<user_id>/ - Student detail."""

    def get(self, request, user_id):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        try:
            student = students.get(supabase_user_id=user_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        serializer = PartnerStudentDetailSerializer(student)
        return Response(serializer.data)


class PartnerStudentExportView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/export/ - CSV export of referred students."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{org.code}_students.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'IC', 'Gender', 'State', 'Exam Type', 'Date Joined'])

        for s in students:
            writer.writerow([
                s.name, s.nric, s.gender, s.preferred_state,
                s.exam_type, s.created_at.strftime('%Y-%m-%d'),
            ])

        return response
