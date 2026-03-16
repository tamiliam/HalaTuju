"""
Partner admin API views.

Endpoints:
- GET /api/v1/admin/role/ - Check admin role
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
    """Validate partner admin access and resolve org.

    admin_org_code='*' means super admin — sees ALL students.
    admin_org_code='cumig' means partner admin — sees only their referred students.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get_admin_profile(self, request):
        user_id = request.user_id
        if not user_id:
            return None
        try:
            profile = StudentProfile.objects.get(supabase_user_id=user_id)
        except StudentProfile.DoesNotExist:
            return None
        if not profile.admin_org_code:
            return None
        return profile

    def get_partner_org(self, request):
        profile = self.get_admin_profile(request)
        if not profile:
            return None
        if profile.admin_org_code == '*':
            return None  # super admin has no single org
        try:
            return PartnerOrganisation.objects.get(code=profile.admin_org_code, is_active=True)
        except PartnerOrganisation.DoesNotExist:
            return None

    def is_super_admin(self, request):
        profile = self.get_admin_profile(request)
        return profile and profile.admin_org_code == '*'

    def get_partner_students(self, request):
        profile = self.get_admin_profile(request)
        if not profile:
            return None, None

        if profile.admin_org_code == '*':
            # Super admin sees all students
            students = StudentProfile.objects.all().order_by('-created_at')
            return students, None  # org=None for super admin

        org = self.get_partner_org(request)
        if not org:
            return None, None
        students = StudentProfile.objects.filter(
            referred_by_org=org,
        ).order_by('-created_at')
        return students, org


class AdminRoleView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/role/ - Check if user has admin access."""

    def get(self, request):
        profile = self.get_admin_profile(request)
        if not profile:
            return Response({'is_admin': False})
        org = self.get_partner_org(request)
        return Response({
            'is_admin': True,
            'is_super_admin': profile.admin_org_code == '*',
            'org_name': org.name if org else ('Semua Organisasi' if profile.admin_org_code == '*' else None),
        })


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
            'org_name': org.name if org else 'Semua Organisasi',
            'is_super_admin': org is None,
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
            'org_name': org.name if org else 'Semua Organisasi',
            'is_super_admin': org is None,
            'count': students.count(),
            'students': serializer.data,
        })


class PartnerStudentDetailView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/<user_id>/ - Student detail."""

    def get(self, request, user_id):
        profile = self.get_admin_profile(request)
        if not profile:
            return Response({'error': 'Not a partner admin'}, status=403)

        if profile.admin_org_code == '*':
            # Super admin can view any student
            try:
                student = StudentProfile.objects.get(supabase_user_id=user_id)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)
        else:
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

        filename = f'{org.code}_students.csv' if org else 'all_students.csv'
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'IC', 'Gender', 'State', 'Exam Type', 'Date Joined'])

        for s in students:
            writer.writerow([
                s.name, s.nric, s.gender, s.preferred_state,
                s.exam_type, s.created_at.strftime('%Y-%m-%d'),
            ])

        return response
