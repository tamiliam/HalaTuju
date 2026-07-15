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
- POST /api/v1/admin/admins/<id>/resend/ - Re-send sign-in details / rotate the temp password (super admin only)
- GET/PUT /api/v1/admin/profile/ - View/edit own admin profile
"""
import csv
import json
import logging
import secrets
from collections import Counter
import requests as http_requests
from django.conf import settings
from django.utils import timezone
from django.db import connection
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from halatuju.pagination import FlexiblePageNumberPagination

from apps.scholarship.emails import send_partner_welcome_email
from .search import apply_people_search
from .models import StudentProfile, PartnerOrganisation, PartnerAdmin
from .serializers_admin import PartnerStudentListSerializer, PartnerStudentDetailSerializer

logger = logging.getLogger(__name__)

# Unambiguous alphabet — no O/0, I/l/1 — because this password gets read off a phone screen and
# typed by hand, and a partner who mistypes it has no other way in.
_PW_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'


def generate_temp_password(groups=3, size=4):
    """A one-time password for a newly created partner account, e.g. 'Kx7m-Pq4t-Rd92'.
    Hyphen-grouped so it can be dictated over the phone if the email goes astray."""
    return '-'.join(
        ''.join(secrets.choice(_PW_ALPHABET) for _ in range(size)) for _ in range(groups)
    )


# A Google address signs in with Google, so we never issue it a password (owner 2026-07-14). Only
# the unambiguous personal-Google domains — a custom Workspace domain can't be told from the address
# and harmlessly gets a temp password it can ignore (Google sign-in auto-links either way).
_GOOGLE_EMAIL_DOMAINS = {'gmail.com', 'googlemail.com'}


def is_google_email(email):
    return (email or '').rsplit('@', 1)[-1].lower() in _GOOGLE_EMAIL_DOMAINS


def _service_headers(service_role_key):
    return {
        'apikey': service_role_key,
        'Authorization': f'Bearer {service_role_key}',
        'Content-Type': 'application/json',
    }


def _create_supabase_user(supabase_url, service_role_key, email, name, temp_password):
    """Create the partner's Supabase auth account directly, with a password we choose.

    We deliberately do NOT use /auth/v1/invite: its email carries a magic link that expires in 24
    hours (Supabase's maximum) and cannot be re-sent to an address that already has an auth user,
    so a partner who missed the window was permanently stuck. Creating the account outright means
    nothing expires, and we send our own email instead.

    `email_confirm` is load-bearing: PartnerAdminMixin.get_admin only links a PartnerAdmin row by
    email when the JWT's `email_verified` claim is true. Without it the partner would sign in
    successfully and still have no role.

    Returns (user_id, already_registered, error). `already_registered` means the address already
    had a HalaTuju account (student or Google) — not a failure: they keep their existing login and
    we just grant the role, matching them by verified email on next sign-in.
    """
    resp = http_requests.post(
        f'{supabase_url}/auth/v1/admin/users',
        json={
            'email': email,
            'password': temp_password,
            'email_confirm': True,
            # `temp_password_issued_at` starts the 7-day clock: the login gate refuses an unchanged
            # temp password past the TTL, and the daily `expire_temp_passwords` job rotates it dead.
            'user_metadata': {'name': name, 'must_change_password': True,
                              'temp_password_issued_at': timezone.now().isoformat()},
        },
        headers=_service_headers(service_role_key),
    )
    if resp.status_code in (200, 201):
        try:
            return (resp.json() or {}).get('id'), False, None
        except ValueError:
            # Created, but we cannot read the UID — fall back to the email-match backfill.
            return None, False, None

    try:
        body = resp.json() or {}
    except ValueError:
        body = {}
    if resp.status_code in (400, 422) and (
        body.get('error_code') == 'email_exists' or body.get('code') == 'email_exists'
        or 'already been registered' in str(body.get('msg', ''))
    ):
        return None, True, None

    logger.error('Supabase user creation failed: %s %s', resp.status_code, resp.text)
    return None, False, 'create_failed'


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
        admin = PartnerAdmin.objects.filter(supabase_user_id=user_id, is_active=True).select_related('org', 'owning_organisation').first()
        if admin:
            return admin

        # Fallback: lookup by email, backfill UID. Defence-in-depth (TD audit 2026-06-14):
        # only link a provisioned admin row to a caller whose email claim is VERIFIED, so a
        # JWT carrying an admin's unverified email can never acquire (super-)admin privilege.
        su = getattr(request, 'supabase_user', None) or {}
        email = su.get('email')
        if email and su.get('email_verified'):
            admin = PartnerAdmin.objects.filter(email=email, supabase_user_id__isnull=True, is_active=True).select_related('org', 'owning_organisation').first()
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
          super         → ALL students (the platform-wide directory is PLATFORM-only).
          partner       → only their OWN referral organisation's students.
          admin / org_admin / qc / reviewer / anyone else → no access (None → 403).

        SURFACE PARTITION (2026-07-15, security fix): the ALL-students branch is now
        SUPER-ONLY. Previously `has_role(admin,'admin')` granted a B40 `admin` (and any
        org role) the platform-wide student directory — every course-selector student's
        PII, far beyond their own programme. The Phase-1 fence covered the scholarship
        surface; this closes the courses admin surface. `partner` is unchanged (referral
        semantics — that IS the partner role's purpose).
        """
        admin = self.get_admin(request)
        if not admin:
            return None, None, None

        # super only: the platform-wide student directory.
        if admin.is_super:
            students = StudentProfile.objects.all().order_by('-created_at')
            return students, None, admin

        # partner: scoped to their own referral organisation only.
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
        # reviewer_profile_complete: gates the reviewer's first-login landing (they stay on
        # /admin/profile until their compulsory fields are filled). True for every non-reviewer.
        from apps.scholarship.reviewer_onboarding import reviewer_profile_complete
        return Response({
            'is_admin': True,
            'is_super_admin': admin.is_super_admin,
            'role': 'super' if admin.is_super else admin.role,
            'admin_id': admin.id,
            # `org_name` is the REFERRAL org (None for an org_admin). The Administration
            # panel's org section keys off `owning_org_*` — the B40 tenant this staff
            # member administers (their access boundary), NOT the referral org.
            'org_name': admin.org.name if admin.org else None,
            'owning_org_id': admin.owning_organisation_id,
            'owning_org_name': admin.owning_organisation.name if admin.owning_organisation_id else None,
            'admin_name': admin.name,
            'reviewer_profile_complete': reviewer_profile_complete(admin),
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


# Programme-staff roles an org_admin may manage (invite / list / resend / revoke). Never
# partner (referral), never super, never org_admin — no privilege escalation.
_ORG_ADMIN_MANAGEABLE_ROLES = {'reviewer', 'admin', 'qc'}


def _staff_target_manageable(caller, target):
    """Whether ``caller`` may manage (resend/revoke) the staff row ``target``. A platform
    super manages anyone; an ``org_admin`` manages ONLY non-super programme staff
    (reviewer/admin/qc) bound to the caller's OWN owning organisation. Anyone else: no.
    Caller/target visibility failures collapse to a 404 at the call site (no existence leak)."""
    if caller is None or target is None:
        return False
    if caller.is_super:
        return True
    if caller.role == 'org_admin':
        if target.is_super or target.role not in _ORG_ADMIN_MANAGEABLE_ROLES:
            return False
        return (caller.owning_organisation_id is not None
                and target.owning_organisation_id == caller.owning_organisation_id)
    return False


class AdminInviteView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/invite/ — invite staff. A platform super may add any staff role
    (incl. a new organisation admin = add-tenant); an org_admin may add programme staff
    (reviewer/admin/qc) to their OWN organisation only."""

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Admin access required'}, status=403)
        # Who may invite: the PLATFORM super (any staff role incl. a new org admin), OR an
        # ORGANISATION admin (org_admin) delegating programme staff within their OWN org.
        caller_super = admin.is_super
        caller_org_admin = (admin.role == 'org_admin')
        if not (caller_super or caller_org_admin):
            return Response({'error': 'Super admin access required'}, status=403)

        email = request.data.get('email', '').strip().lower()
        name = request.data.get('name', '').strip()
        org_id = request.data.get('org_id')
        new_org_name = request.data.get('new_org_name', '').strip()
        new_org_code = request.data.get('new_org_code', '').strip().lower()

        # Roles this caller may grant. A super may create any staff role including a new
        # ORGANISATION admin (add-tenant); an org_admin may add only programme staff to
        # their own org (never partner/super/org_admin — no privilege escalation).
        if caller_super:
            invitable = {'admin', 'partner', 'reviewer', 'qc', 'org_admin'}
        else:
            invitable = {'reviewer', 'admin', 'qc'}
        role = request.data.get('role', 'reviewer')
        if role not in invitable:
            if caller_super:
                role = 'reviewer'   # forgiving default (unchanged super behaviour)
            else:
                return Response({'error': 'You cannot grant that role.', 'code': 'role_not_allowed'}, status=403)

        if not email or not name:
            return Response({'error': 'email and name are required'}, status=400)

        if PartnerAdmin.objects.filter(email=email).exists():
            return Response({'error': 'Admin with this email already exists'}, status=409)

        # ── Resolve the referral org (`org`, partner only) + the B40 tenant fence
        #    (`owning_organisation`). The two are DISTINCT: referral ≠ ownership. ──
        org = None
        owning_org = None
        if caller_org_admin:
            # An org_admin's invites ALWAYS land in the caller's own organisation; any org
            # inputs are ignored (role already restricted to reviewer/admin/qc above).
            owning_org = admin.owning_organisation
            if owning_org is None:
                return Response({'error': 'Your account is not bound to an organisation.',
                                 'code': 'no_owning_org'}, status=400)
        elif role == 'partner':
            # A REFERRAL partner (a platform concept — roadshow orgs of the course selector),
            # scoped to their referral org's students. No B40 tenant access (owning_org stays None).
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
        elif role == 'org_admin':
            # A5 — a super installs a new organisation's ADMIN, creating/selecting its TENANT
            # (the owning_organisation, NOT the referral `org`) and switching the scholarship
            # module on. This is the thin add-tenant slice of the superadmin portal.
            if new_org_name and new_org_code:
                owning_org, created = PartnerOrganisation.objects.get_or_create(
                    code=new_org_code,
                    defaults={
                        'name': new_org_name,
                        'contact_person': request.data.get('contact_person', ''),
                        'phone': request.data.get('org_phone', ''),
                        'module_scholarship': True,
                    },
                )
                if not created and not owning_org.module_scholarship:
                    owning_org.module_scholarship = True
                    owning_org.save(update_fields=['module_scholarship'])
            elif org_id:
                try:
                    owning_org = PartnerOrganisation.objects.get(id=org_id)
                except PartnerOrganisation.DoesNotExist:
                    return Response({'error': 'Organisation not found'}, status=404)
                if not owning_org.module_scholarship:
                    owning_org.module_scholarship = True
                    owning_org.save(update_fields=['module_scholarship'])
            if owning_org is None:
                return Response({'error': 'A tenant organisation is required.', 'code': 'tenant_required'}, status=400)
        else:
            # A super inviting a B40 staff role (admin/reviewer/qc) → bind to org #1 (BrightPath)
            # for the access fence. super stays global (NULL). (Per-org staff picker is future.)
            owning_org = PartnerOrganisation.objects.filter(code='brightpath').first()

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')

        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        # Option 1 (owner 2026-07-14): a Google address signs in with Google — never issue it a
        # password. Create ONLY the PartnerAdmin row (supabase_user_id stays None and links by
        # verified email on first Google sign-in, exactly like the already-registered path), and
        # send the no-password "sign in with Google" email. No Supabase account is created here — it
        # materialises when they first sign in with Google.
        if is_google_email(email):
            PartnerAdmin.objects.create(
                email=email, name=name, org=org, role=role,
                owning_organisation=owning_org,
                supabase_user_id=None, is_super_admin=(role == 'super'),
            )
            emailed = send_partner_welcome_email(email, name, role, temp_password=None, google=True)
            message = f'{name} added — they sign in with Google ({email}).'
            if not emailed:
                message = f'{name} was added, but the email could not be sent. Use Resend to try again.'
            return Response({
                'message': message, 'org': (org or owning_org).name if (org or owning_org) else None, 'role': role,
                'already_registered': False, 'google': True, 'emailed': emailed,
            }, status=201)

        # Non-Google: create the Supabase account OURSELVES rather than sending a Supabase invite
        # (see `_create_supabase_user` for why). The temp password never leaves this request except
        # in the welcome email, and expires after the 7-day TTL (login gate + expire cron).
        temp_password = generate_temp_password()
        user_id, already_registered, err = _create_supabase_user(
            supabase_url, service_role_key, email, name, temp_password,
        )
        if err:
            return Response({'error': 'Failed to create the partner account'}, status=502)

        PartnerAdmin.objects.create(
            email=email,
            name=name,
            org=org,
            role=role,
            owning_organisation=owning_org,
            # We know the Supabase UID at creation now, so store it instead of waiting for the
            # email-match backfill in get_admin. (None on the already-registered path — their
            # existing account is matched by verified email on next sign-in, as before.)
            supabase_user_id=user_id,
            # Keep the legacy flag in lockstep with the role (expand-contract):
            # several call sites still gate on is_super_admin directly.
            is_super_admin=(role == 'super'),
        )

        # The email is the ONLY carrier of the temp password, so a failed send strands the
        # invitee — report it instead of swallowing it, and the UI tells the owner to Resend.
        emailed = send_partner_welcome_email(
            email, name, role, temp_password=None if already_registered else temp_password,
        )

        message = (
            f'{name} already has an account — access granted. They can sign in as they always do.'
            if already_registered else f'Account created. Sign-in details emailed to {email}.'
        )
        if not emailed:
            message = f'{name} was added, but the email could not be sent. Use Resend to try again.'
        return Response({
            'message': message,
            'org': (org or owning_org).name if (org or owning_org) else None,
            'role': role,
            'already_registered': already_registered,
            'emailed': emailed,
        }, status=201)


class AdminResendView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/admins/<id>/resend/ - Re-send a partner's sign-in details.

    The reason this exists: the old Supabase invite link expired after 24 hours and there was NO
    way to send another one (this view's sibling 409s on an existing PartnerAdmin, and Supabase
    refuses to re-invite an address that already has an auth user), so a partner who missed the
    window was stuck — which is exactly what happened on 2026-07-10. Resending is safe now
    because the email carries no token: we simply rotate the temporary password and re-send it.
    """

    def post(self, request, admin_id):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)

        target = PartnerAdmin.objects.filter(id=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            # Not found OR not manageable by this caller (cross-org / super target) — 404,
            # so an org_admin can't probe for the existence of other orgs' or platform staff.
            return Response({'error': 'Admin not found'}, status=404)

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')
        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        # No UID = the account pre-existed ours (student/Google sign-up), so we never issued a
        # password and must not reset theirs. Re-send the "sign in as you always do" note.
        temp_password = None
        if target.supabase_user_id:
            temp_password = generate_temp_password()
            resp = http_requests.put(
                f'{supabase_url}/auth/v1/admin/users/{target.supabase_user_id}',
                json={'password': temp_password,
                      # Reset the 7-day clock — a Resend gives a fresh temp password AND a fresh TTL.
                      'user_metadata': {'name': target.name, 'must_change_password': True,
                                        'temp_password_issued_at': timezone.now().isoformat()}},
                headers=_service_headers(service_role_key),
            )
            if resp.status_code not in (200, 201):
                logger.error('Supabase password rotation failed: %s %s', resp.status_code, resp.text)
                return Response({'error': 'Failed to reset the password'}, status=502)

        emailed = send_partner_welcome_email(
            target.email, target.name, target.role, temp_password=temp_password,
        )
        if not emailed:
            return Response({'error': 'Failed to send the email', 'emailed': False}, status=502)
        return Response({
            'message': f'Sign-in details re-sent to {target.email}.',
            'emailed': True,
        })


class AdminSetPasswordView(APIView):
    """POST /api/v1/admin/set-password/ - a temp-password partner sets their OWN password.

    The client cannot use `supabase.auth.updateUser({ password })`: the project requires
    re-authentication for a password change (GoTrue "Current password required when setting new
    password"), and the set-password page has no current password to supply. So we set it
    server-side with the SERVICE ROLE (the same key the invite/resend flows already use), which the
    admin API applies without re-auth.

    Scoped tightly so this is NOT a general re-auth bypass: it only ever sets the CALLER'S OWN uid
    (from their JWT), and ONLY while that account still owes a password change
    (`must_change_password`, read authoritatively from Supabase). Once a partner has set their own
    password, the endpoint refuses — everyone else keeps the project's secure-change policy.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        uid = getattr(request, 'user_id', None)
        if not uid:
            return Response({'error': 'not_authenticated'}, status=401)
        password = request.data.get('password') or ''
        if len(password) < 8:
            return Response({'error': 'password_too_short'}, status=400)

        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')
        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)
        headers = _service_headers(service_role_key)
        user_url = f'{supabase_url}/auth/v1/admin/users/{uid}'

        # Read current metadata: authoritative must_change_password gate + preserve `name`.
        try:
            gr = http_requests.get(user_url, headers=headers, timeout=15)
        except Exception:  # noqa: BLE001
            return Response({'error': 'supabase_unreachable'}, status=502)
        if gr.status_code != 200:
            return Response({'error': 'user_lookup_failed'}, status=502)
        meta = (gr.json() or {}).get('user_metadata') or {}
        if not meta.get('must_change_password'):
            # Not mid-onboarding — do not let this stand in for a normal (re-auth'd) password change.
            return Response({'error': 'not_pending_password_change'}, status=403)

        # Supabase admin updateUser MERGES user_metadata (omitting a key does NOT delete it), so we
        # explicitly null the temp-password fields to clear them.
        new_meta = {**meta, 'must_change_password': False,
                    'temp_password_issued_at': None, 'temp_password_expired': None}
        try:
            pr = http_requests.put(
                user_url, json={'password': password, 'user_metadata': new_meta},
                headers=headers, timeout=15)
        except Exception:  # noqa: BLE001
            return Response({'error': 'supabase_unreachable'}, status=502)
        if pr.status_code not in (200, 201):
            logger.error('set-password failed: %s %s', pr.status_code, pr.text)
            return Response({'error': 'set_password_failed'}, status=502)
        return Response({'ok': True})


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
    """GET /api/v1/admin/admins/ — list staff. Super sees ALL; an org_admin sees only the
    non-super programme staff in their OWN organisation."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)

        admins = PartnerAdmin.objects.select_related('org').order_by('-created_at')
        if not admin.is_super:
            # org_admin: only their own org's manageable staff (never supers / other orgs).
            admins = admins.filter(
                owning_organisation_id=admin.owning_organisation_id,
                role__in=_ORG_ADMIN_MANAGEABLE_ROLES,
                is_super_admin=False,
            )
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
        if not admin or not (admin.is_super or admin.role == 'org_admin'):
            return Response({'error': 'Super admin access required'}, status=403)

        target = PartnerAdmin.objects.filter(id=admin_id).first()
        if target is None or not _staff_target_manageable(admin, target):
            # 404 for a missing row OR a target outside this caller's remit (cross-org / super).
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
    PLATFORM surface — SUPER-ONLY (Course Data is the course-selector base, not an org's
    programme; surface partition 2026-07-15).
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)
        if not admin.is_super:
            return Response({'error': 'forbidden'}, status=403)
        return Response(_course_data_payload())


class AdminCourseDataCheckView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/course-data/check/ — run the READ-ONLY health check on demand.

    Runs `course_data_check` (audit_data + concurrent link reachability — NO --fix, NO scrape,
    NO catalogue writes) synchronously, then returns the refreshed dashboard payload so the page
    updates immediately. SUPER-ONLY (platform surface; it issues ~650 outbound link checks). The
    weekly cron runs the same command. NEVER mutates the catalogue.
    """

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)
        if not admin.is_super:
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
