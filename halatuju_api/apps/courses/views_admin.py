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
import json
import logging
from collections import Counter
import requests as http_requests
from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from halatuju.pagination import FlexiblePageNumberPagination

from .search import apply_people_search
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

        # Fallback: lookup by email, backfill UID. Defence-in-depth (TD audit 2026-06-14):
        # only link a provisioned admin row to a caller whose email claim is VERIFIED, so a
        # JWT carrying an admin's unverified email can never acquire (super-)admin privilege.
        su = getattr(request, 'supabase_user', None) or {}
        email = su.get('email')
        if email and su.get('email_verified'):
            admin = PartnerAdmin.objects.filter(email=email, supabase_user_id__isnull=True, is_active=True).select_related('org').first()
            if admin:
                admin.supabase_user_id = user_id
                admin.save(update_fields=['supabase_user_id'])
                return admin

        return None

    @staticmethod
    def has_role(admin, *roles):
        """Phase C role check. Treats a legacy super (is_super_admin=True) as
        'super'. 'viewer' is read-only; 'reviewer' is the workhorse; 'super' can
        do everything (so a super passes any role check)."""
        if admin is None:
            return False
        effective = 'super' if admin.is_super else admin.role
        return effective == 'super' or effective in roles

    def get_partner_students(self, request):
        """Role-aware student scope for the Students list, Dashboard and CSV export
        (all three call this one choke-point):
          super / admin → ALL students (admin is read-only elsewhere, but sees all).
          partner       → only their OWN organisation's students.
          reviewer / anyone else → no access (None → the caller returns 403).
        """
        admin = self.get_admin(request)
        if not admin:
            return None, None, None

        # super + admin: every student.
        if self.has_role(admin, 'admin'):
            students = StudentProfile.objects.all().order_by('-created_at')
            return students, None, admin

        # partner: scoped to their own organisation only.
        if admin.role == 'partner' and admin.org:
            students = StudentProfile.objects.filter(
                referred_by_org=admin.org,
            ).order_by('-created_at')
            return students, admin.org, admin

        # reviewer (individual volunteer) and anyone without a valid scope: no Students.
        return None, None, admin


class AdminRoleView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/role/ - Check if user has admin access."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'is_admin': False})
        return Response({
            'is_admin': True,
            'is_super_admin': admin.is_super_admin,
            'role': 'super' if admin.is_super else admin.role,
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
            'org_code': org.code if org else None,
            'is_super_admin': admin.is_super_admin,
            'total_students': total,
            'completed_onboarding': completed,
            'by_exam_type': by_exam,
            'top_fields': top_fields,
        })


class PartnerStudentListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/ - List referred students (paginated).

    Server-side pagination via ``?page`` and ``?page_size`` (see
    ``FlexiblePageNumberPagination``); only one page of rows is serialised and
    returned per request. The CSV export (``PartnerStudentExportView``) is
    intentionally left unpaginated.
    """

    def get(self, request):
        students, org, admin = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        students = students.select_related('referred_by_org')

        # Distinct source options come from the (org-scoped) base set BEFORE the
        # search/exam/source narrowing below — so the Source dropdown always
        # lists every source the admin can see, not just those on this page.
        # .order_by() clears the inherited -created_at ordering: a trailing
        # ORDER BY on an unselected column breaks DISTINCT (dupes on SQLite,
        # a hard error on Postgres).
        source_options = sorted(
            students.order_by()
            .exclude(referral_source__isnull=True)
            .exclude(referral_source='')
            .values_list('referral_source', flat=True)
            .distinct()
        )

        # Free-text search across name / NRIC / phone / email — digits-only for phone+NRIC,
        # and email also covers the student's application notify_email (contact_email is blank
        # for most). Shared with the B40 list via apps.courses.search. The notify_email path
        # crosses a to-many reverse FK → distinct() to avoid duplicate profile rows.
        students = apply_people_search(
            students, request.GET.get('q'),
            name='name', nric='nric', phone='contact_phone', email='contact_email',
            extra_email='scholarship_applications__notify_email', needs_distinct=True)
        exam = request.GET.get('exam')
        if exam in ('spm', 'stpm'):
            students = students.filter(exam_type=exam)
        source = request.GET.get('source')
        if source:
            students = students.filter(referral_source=source)

        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(students, request, view=self)
        serializer = PartnerStudentListSerializer(page, many=True)
        return paginator.envelope(
            serializer.data,
            results_key='students',
            org_name=org.name if org else 'Semua Organisasi',
            is_super_admin=admin.is_super_admin,
            source_options=source_options,
        )


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

        students = students.select_related('referred_by_org')

        filename = f'{org.code}_students.csv' if org else 'all_students.csv'
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'Name', 'IC', 'Angka Giliran', 'Email', 'Phone', 'School',
            'Gender', 'Nationality',
            'Address', 'Postal Code', 'City', 'State',
            'Household Income', 'Household Size', 'Colorblind', 'Disability',
            'Exam Type', 'SPM Grades', 'STPM Grades', 'STPM CGPA', 'MUET Band',
            'Financial Pressure', 'Travel Willingness',
            'Referral Source', 'Referred By Org',
            'Date Joined', 'Last Sign-In',
        ])

        auth_data = _fetch_auth_data([s.supabase_user_id for s in students])

        for s in students:
            ad = auth_data.get(s.supabase_user_id, {})
            org_name = s.referred_by_org.name if s.referred_by_org_id else ''
            writer.writerow([
                s.name, s.nric, s.angka_giliran, ad.get('email', ''),
                s.contact_phone, s.school,
                s.gender, s.nationality,
                s.address, s.postal_code, s.city, s.preferred_state,
                _fmt_int(s.household_income),
                _fmt_int(s.household_size),
                _fmt_bool(s.colorblind), _fmt_bool(s.disability),
                s.exam_type,
                _fmt_json(s.grades), _fmt_json(s.stpm_grades),
                _fmt_num(s.stpm_cgpa), _fmt_int(s.muet_band),
                s.financial_pressure, s.travel_willingness,
                s.referral_source or '', org_name,
                s.created_at.strftime('%Y-%m-%d'),
                ad.get('last_sign_in', ''),
            ])

        return response


def _fetch_auth_data(user_ids):
    """Look up email + last_sign_in from Supabase Auth's auth.users for the given user IDs.

    Returns {supabase_user_id: {'email': str, 'last_sign_in': 'YYYY-MM-DD' or ''}}.
    Failures are logged but never break the export.
    """
    if not user_ids:
        return {}
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id::text, email, to_char(last_sign_in_at, 'YYYY-MM-DD') "
                "FROM auth.users WHERE id::text = ANY(%s)",
                [list(user_ids)],
            )
            return {
                uid: {'email': email or '', 'last_sign_in': lsi or ''}
                for uid, email, lsi in cur.fetchall()
            }
    except Exception:
        logger.exception('Failed to fetch auth.users data for CSV export')
        return {}


def _fmt_bool(value):
    if value is True:
        return 'Yes'
    if value is False:
        return 'No'
    return ''


def _fmt_int(value):
    return '' if value is None else str(value)


def _fmt_num(value):
    return '' if value is None else str(value)


def _fmt_json(value):
    if not value:
        return ''
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


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

        # The inviter chooses the new admin's role. Super is NOT invitable here
        # (there is one super admin — the owner); default to the safe workhorse.
        INVITABLE_ROLES = {'admin', 'partner', 'reviewer'}
        role = request.data.get('role', 'reviewer')
        if role not in INVITABLE_ROLES:
            role = 'reviewer'

        if not email or not name:
            return Response({'error': 'email and name are required'}, status=400)

        if PartnerAdmin.objects.filter(email=email).exists():
            return Response({'error': 'Admin with this email already exists'}, status=409)

        # Organisation applies ONLY to a partner (an org rep, scoped to their org's
        # students). Admin + reviewer are not org-scoped, so any org input is ignored.
        org = None
        if role == 'partner':
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
            if org is None:
                return Response({'error': 'A partner must belong to an organisation', 'code': 'org_required'}, status=400)

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')

        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        # Pass the invitee's name as user metadata so the Supabase "Invite user"
        # email template can greet them by name via {{ .Data.name }}.
        invite_resp = http_requests.post(
            f'{supabase_url}/auth/v1/invite',
            json={'email': email, 'data': {'name': name}},
            headers={
                'apikey': service_role_key,
                'Authorization': f'Bearer {service_role_key}',
                'Content-Type': 'application/json',
            },
        )

        # Supabase refuses to invite an email that already has an account (422
        # email_exists) — e.g. the person already signed in as a student or via
        # Google. That is NOT a failure: they already have a login, so we skip the
        # invite email and just grant the role. `get_admin` links the PartnerAdmin
        # row to their account by email on their next sign-in (no UID needed here).
        already_registered = False
        if invite_resp.status_code not in (200, 201):
            try:
                err_code = invite_resp.json().get('error_code')
            except ValueError:
                err_code = None
            if invite_resp.status_code == 422 and err_code == 'email_exists':
                already_registered = True
            else:
                logger.error(f"Supabase invite failed: {invite_resp.status_code} {invite_resp.text}")
                return Response({'error': 'Failed to send invite email'}, status=502)

        PartnerAdmin.objects.create(
            email=email,
            name=name,
            org=org,
            role=role,
            # Keep the legacy flag in lockstep with the role (expand-contract):
            # several call sites still gate on is_super_admin directly.
            is_super_admin=(role == 'super'),
        )

        message = (
            f'{name} already has an account — access granted. They will see it the '
            f'next time they sign in (no invite email needed).'
            if already_registered else f'Invite sent to {email}'
        )
        return Response({
            'message': message,
            'org': org.name if org else None,
            'role': role,
            'already_registered': already_registered,
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
                'role': 'super' if a.is_super else a.role,
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


def _course_data_payload():
    """Dashboard payload: per-source freshness (recorded status) + live coverage counts."""
    from .models import CourseDataStatus
    from .course_data_status import coverage_snapshot

    statuses = {}
    for row in CourseDataStatus.objects.all():
        statuses[row.key] = {
            'last_run_at': row.last_run_at.isoformat() if row.last_run_at else None,
            'summary': row.summary or {},
            'detail': row.detail or '',
        }
    for key, _label in CourseDataStatus.KEY_CHOICES:  # missing → null = "never run"
        statuses.setdefault(key, None)
    return {'statuses': statuses, 'coverage': coverage_snapshot()}


class AdminCourseDataView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/course-data/ — read-only Course Data dashboard.

    Returns per-source freshness (last-run status the tools record) + live coverage counts.
    Any admin role may view (read-only reporting).
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)
        return Response(_course_data_payload())


class AdminCourseDataCheckView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/course-data/check/ — run the READ-ONLY health check on demand.

    Runs `course_data_check` (audit_data + concurrent link reachability — NO --fix, NO scrape,
    NO catalogue writes) synchronously, then returns the refreshed dashboard payload so the page
    updates immediately. Super/admin only (it issues ~650 outbound link checks). The weekly cron
    runs the same command. NEVER mutates the catalogue.
    """

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)
        if not self.has_role(admin, 'super', 'admin'):
            return Response({'error': 'forbidden'}, status=403)

        import io
        from django.core.management import call_command
        try:
            call_command('course_data_check', stdout=io.StringIO())
        except Exception as e:  # noqa: BLE001 — report, never 500 the dashboard
            import logging
            logging.getLogger(__name__).warning('course_data_check failed: %s', e, exc_info=True)
            return Response({'error': str(e)[:300], **_course_data_payload()}, status=200)
        return Response(_course_data_payload())
