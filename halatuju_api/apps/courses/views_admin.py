"""
Partner admin API views.

Endpoints:
- GET /api/v1/admin/role/ - Check admin role (with email fallback + UID backfill)
- GET /api/v1/admin/dashboard/ - Partner dashboard stats
- GET /api/v1/admin/students/ - List referred students
- GET /api/v1/admin/students/export/ - CSV export of referred students
- GET /api/v1/admin/students/<user_id>/ - Student detail
- DELETE /api/v1/admin/students/<user_id>/ - Delete student (super admin only)
- POST /api/v1/admin/invite/ - Invite a partner admin (super admin only)
- GET /api/v1/admin/orgs/ - List organisations (for invite dropdown)
- GET /api/v1/admin/admins/ - List all admins (super admin only)
- PATCH /api/v1/admin/admins/<id>/revoke/ - Revoke or restore admin access (super admin only)
- GET/PUT /api/v1/admin/profile/ - View/edit own admin profile
"""
import csv
import logging
from collections import Counter
import requests as http_requests
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .models import StudentProfile, PartnerOrganisation, PartnerAdmin
from .serializers_admin import PartnerStudentListSerializer, PartnerStudentDetailSerializer

logger = logging.getLogger(__name__)


class PartnerAdminMixin:
    """Validate partner admin access via partner_admins table.

    Lookup order:
    1. By supabase_user_id (fast path)
    2. By email from JWT (first-login backfill)
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get_admin(self, request):
        user_id = request.user_id
        if not user_id:
            return None

        # Fast path: lookup by UID
        admin = PartnerAdmin.objects.filter(supabase_user_id=user_id, is_active=True).select_related('org').first()
        if admin:
            return admin

        # Fallback: lookup by email, backfill UID
        email = getattr(request, 'supabase_user', {}).get('email')
        if email:
            admin = PartnerAdmin.objects.filter(email=email, supabase_user_id__isnull=True, is_active=True).select_related('org').first()
            if admin:
                admin.supabase_user_id = user_id
                admin.save(update_fields=['supabase_user_id'])
                return admin

        return None

    def get_partner_students(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, None, None

        if admin.is_super_admin:
            students = StudentProfile.objects.all().order_by('-created_at')
            return students, None, admin

        if not admin.org:
            return None, None, None

        students = StudentProfile.objects.filter(
            referred_by_org=admin.org,
        ).order_by('-created_at')
        return students, admin.org, admin


class AdminRoleView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/role/ - Check if user has admin access."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'is_admin': False})
        return Response({
            'is_admin': True,
            'is_super_admin': admin.is_super_admin,
            'org_name': admin.org.name if admin.org else None,
            'admin_name': admin.name,
        })


class PartnerDashboardView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/dashboard/ - Partner dashboard statistics."""

    def get(self, request):
        students, org, admin = self.get_partner_students(request)
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
            'is_super_admin': admin.is_super_admin,
            'total_students': total,
            'completed_onboarding': completed,
            'by_exam_type': by_exam,
            'top_fields': top_fields,
        })


class PartnerStudentListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/ - List referred students."""

    def get(self, request):
        students, org, admin = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        students = students.select_related('referred_by_org')
        serializer = PartnerStudentListSerializer(students, many=True)
        return Response({
            'org_name': org.name if org else 'Semua Organisasi',
            'is_super_admin': admin.is_super_admin,
            'count': students.count(),
            'students': serializer.data,
        })


class PartnerStudentDetailView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/<user_id>/ - Student detail."""

    def get(self, request, user_id):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)

        if admin.is_super_admin:
            try:
                student = StudentProfile.objects.get(supabase_user_id=user_id)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)
        else:
            students, org, _ = self.get_partner_students(request)
            if students is None:
                return Response({'error': 'Not a partner admin'}, status=403)
            try:
                student = students.get(supabase_user_id=user_id)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)

        serializer = PartnerStudentDetailSerializer(student)
        return Response(serializer.data)

    def delete(self, request, user_id):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        try:
            student = StudentProfile.objects.get(supabase_user_id=user_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        student.delete()
        return Response({'message': 'Student deleted'}, status=200)


class PartnerStudentExportView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/export/ - CSV export of referred students."""

    def get(self, request):
        students, org, _ = self.get_partner_students(request)
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


class AdminInviteView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/invite/ - Invite a partner admin (super admin only)."""

    def post(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        email = request.data.get('email', '').strip().lower()
        name = request.data.get('name', '').strip()
        org_id = request.data.get('org_id')
        new_org_name = request.data.get('new_org_name', '').strip()
        new_org_code = request.data.get('new_org_code', '').strip().lower()

        if not email or not name:
            return Response({'error': 'email and name are required'}, status=400)

        if PartnerAdmin.objects.filter(email=email).exists():
            return Response({'error': 'Admin with this email already exists'}, status=409)

        org = None
        if new_org_name and new_org_code:
            org, _ = PartnerOrganisation.objects.get_or_create(
                code=new_org_code,
                defaults={
                    'name': new_org_name,
                    'contact_person': request.data.get('contact_person', ''),
                    'phone': request.data.get('org_phone', ''),
                },
            )
        elif org_id:
            try:
                org = PartnerOrganisation.objects.get(id=org_id)
            except PartnerOrganisation.DoesNotExist:
                return Response({'error': 'Organisation not found'}, status=404)

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')

        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        invite_resp = http_requests.post(
            f'{supabase_url}/auth/v1/invite',
            json={'email': email},
            headers={
                'apikey': service_role_key,
                'Authorization': f'Bearer {service_role_key}',
                'Content-Type': 'application/json',
            },
        )

        if invite_resp.status_code not in (200, 201):
            logger.error(f"Supabase invite failed: {invite_resp.status_code} {invite_resp.text}")
            return Response({'error': 'Failed to send invite email'}, status=502)

        PartnerAdmin.objects.create(
            email=email,
            name=name,
            org=org,
        )

        return Response({
            'message': f'Invite sent to {email}',
            'org': org.name if org else None,
        }, status=201)


class AdminOrgsView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/orgs/ - List organisations for invite dropdown."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        orgs = PartnerOrganisation.objects.filter(is_active=True).values(
            'id', 'code', 'name', 'contact_person', 'phone',
        )
        return Response({'orgs': list(orgs)})


class AdminListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/admins/ - List all admins (super admin only)."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        admins = PartnerAdmin.objects.select_related('org').order_by('-created_at')
        data = []
        for a in admins:
            data.append({
                'id': a.id,
                'name': a.name,
                'email': a.email,
                'is_super_admin': a.is_super_admin,
                'is_active': a.is_active,
                'org_name': a.org.name if a.org else None,
                'created_at': a.created_at.isoformat(),
            })
        return Response({'admins': data})


class AdminRevokeView(PartnerAdminMixin, APIView):
    """PATCH /api/v1/admin/admins/<id>/revoke/ - Revoke or restore admin access."""

    def patch(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        try:
            target = PartnerAdmin.objects.get(id=admin_id)
        except PartnerAdmin.DoesNotExist:
            return Response({'error': 'Admin not found'}, status=404)

        if target.is_super_admin:
            return Response({'error': 'Cannot revoke super admin'}, status=400)

        action = request.data.get('action')
        if action == 'revoke':
            target.is_active = False
            target.save(update_fields=['is_active'])
            return Response({'message': f'{target.name} access revoked'})
        elif action == 'restore':
            target.is_active = True
            target.save(update_fields=['is_active'])
            return Response({'message': f'{target.name} access restored'})
        else:
            return Response({'error': 'action must be "revoke" or "restore"'}, status=400)


class AdminProfileView(PartnerAdminMixin, APIView):
    """GET/PUT /api/v1/admin/profile/ - View/edit own admin profile."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not an admin'}, status=403)

        return Response({
            'id': admin.id,
            'name': admin.name,
            'email': admin.email,
            'is_super_admin': admin.is_super_admin,
            'org_name': admin.org.name if admin.org else None,
            'org_contact_person': admin.org.contact_person if admin.org else None,
            'org_phone': admin.org.phone if admin.org else None,
        })

    def put(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not an admin'}, status=403)

        name = request.data.get('name', '').strip()
        if name:
            admin.name = name
            admin.save(update_fields=['name'])

        # Org admins can edit their org's contact info
        if admin.org:
            contact = request.data.get('org_contact_person')
            phone = request.data.get('org_phone')
            if contact is not None:
                admin.org.contact_person = contact.strip()
            if phone is not None:
                admin.org.phone = phone.strip()
            if contact is not None or phone is not None:
                admin.org.save(update_fields=['contact_person', 'phone'])

        return Response({'message': 'Profile updated'})
