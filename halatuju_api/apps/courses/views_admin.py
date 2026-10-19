"""
Partner admin API views.

Endpoints:
- GET /api/v1/admin/role/ - Check admin role (with email fallback + UID backfill)
- GET /api/v1/admin/dashboard/ - Partner dashboard stats
- GET /api/v1/admin/students/ - List referred students
- GET /api/v1/admin/students/export/ - CSV export of referred students
- GET /api/v1/admin/students/<user_id>/ - Student detail
- DELETE /api/v1/admin/students/<user_id>/ - Delete student (super admin only)
- GET /api/v1/admin/orgs/ - List organisations (for invite dropdown)
- GET/PUT /api/v1/admin/profile/ - View/edit own admin profile
(The staff-account views — invite, admins list, revoke/restore, resend and delete — are in
`views_staff.py` since request #39 Sprint 1, 2026-10-19; the role switch is
`apps.scholarship.views_admin.staff`.)
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
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated, auth_sub
from halatuju.pagination import FlexiblePageNumberPagination

from . import password_change_flag, referral_links, staff_permissions, staff_reinvite
from .recovery_session import is_fresh_recovery_for
from .search import apply_people_search
from .supabase_admin import _service_headers
from .models import StudentProfile, PartnerAdmin
from .serializers_admin import PartnerStudentListSerializer, PartnerStudentDetailSerializer

logger = logging.getLogger(__name__)


def send_partner_welcome_email(*args, **kwargs):
    """The ONE module-level `courses → scholarship` import, made lazy (code health H16).

    It was `from apps.scholarship.emails import send_partner_welcome_email` at the top of this
    file — the single import in the whole back-edge that ran at import time, which is the half of
    a cross-app edge that can take the service down at start-up rather than merely tangle it. The
    other two dozen were already lazy, each inside the function that needs it.

    This is a seam, not an indirection: the name, the three call sites below and the patch target
    `apps.courses.views_admin.send_partner_welcome_email` are all exactly what they were. Doing it
    as three lazy imports instead would have been three import statements where there was one, and
    the app-boundary standard counts statements.
    """
    from apps.scholarship import emails
    return emails.send_partner_welcome_email(*args, **kwargs)

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


class PartnerAdminMixin:
    """Validate partner admin access via partner_admins table.

    Lookup order:
    1. By supabase_user_id (fast path)
    2. By email from JWT (first-login backfill)
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get_admin(self, request):
        # ⚠ THE REAL JWT SUBJECT, NEVER `request.user_id` (TD-254). A student's profile alias
        # redirects `user_id` at the auth seam; staff identity must not follow it.
        user_id = auth_sub(request)
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


def _invitations_for(admins):
    """`{partner_admin_id: Invitation}` for a page of staff, in ONE query.

    Two multi-valued relations counted in one queryset multiply each other, and an invitation is
    multi-valued per admin (a superseded grant leaves its history behind). So this is fetched
    separately and joined in Python — the same discipline `_reviewer_workloads` documents.
    """
    try:
        from apps.scholarship.models import Invitation
        out = {}
        for inv in (Invitation.objects.filter(audience='staff', partner_admin__in=admins)
                    .order_by('partner_admin_id', '-created_at')):
            out.setdefault(inv.partner_admin_id, inv)   # newest per admin wins
        return out
    except Exception:   # noqa: BLE001 — the staff table must render without it
        logger.warning('Could not load invitations for the staff list', exc_info=True)
        return {}


def _invitation_dict(inv):
    """What the screen is told about one invitation. Allowlist; None when there is no record."""
    if inv is None:
        return None
    from apps.scholarship import invitations
    return {
        'status': invitations.status_of(inv),
        'sent_at': inv.last_sent_at.isoformat() if inv.last_sent_at else None,
        'send_count': inv.send_count,
        # ⚠ Tri-state on purpose. NULL is "not recorded" — every backfilled row is NULL, because
        # whether a historic email arrived is unknowable. False is a real failure we watched happen.
        'last_send_ok': inv.last_send_ok,
        'last_send_error': inv.last_send_error,
        'expires_at': inv.expires_at.isoformat() if inv.expires_at else None,
        'credential_issued': inv.credential_issued,
    }


def _record_invitation(created_admin, role, organisation, request, *, credential_issued):
    """Write the `Invitation` row for a staff invite that has just been provisioned.

    ⚠ **BEST-EFFORT, ALWAYS.** The account exists and the email is about to go; failing the invite
    because we could not file our own paperwork would be the tail wagging the dog. Returns None on
    failure, and the callers below tolerate that.

    Imported inside the function: `courses` must not import `scholarship` at module scope (the
    dependency runs the other way), which is the same discipline `AdminRoleView` already follows
    for `reviewer_profile_complete`.
    """
    try:
        from apps.scholarship import invitations
        return invitations.create_or_refresh(
            audience='staff', email=created_admin.email, name=created_admin.name, role=role,
            organisation=organisation, partner_admin=created_admin,
            invited_by=getattr(request, '_inviting_admin', None),
            credential_issued=credential_issued)
    except Exception:   # noqa: BLE001
        logger.warning('Could not record the invitation for %s', created_admin.email, exc_info=True)
        return None


def _record_invitation_send(inv, ok, error=''):
    """Remember whether the invitation email actually went. See `Invitation`'s send-record block."""
    if inv is None:
        return
    try:
        from apps.scholarship import invitations
        invitations.record_send(inv, ok, error)
    except Exception:   # noqa: BLE001
        pass


def _touch_seen(admin):
    """Record that this person opened the console. Returns True the FIRST time only.

    The analogue of `views_sponsor._touch_last_seen`, which has been doing this for sponsors since
    July while staff had nothing at all — the reason an invitation that was never acted on has been
    indistinguishable from a colleague of a year.

    Two writes, because they answer two questions:

    - **`first_seen_at` is a single conditional UPDATE**, filtered on the column still being NULL.
      That makes it atomic and idempotent, and the rowcount is `1` exactly once in the row's life —
      no second query needed, and it cannot double-fire under concurrent requests. **That rowcount
      is the invitation-acceptance hook**, which is why this returns a bool.
    - **`last_seen_at` is throttled**, because "are they still with us?" is measured in days and an
      UPDATE on every console request buys no extra information.

    `.update()` not `.save()`: never touches another field, cannot race with a concurrent write,
    and a visit does not read as an edit to the account.

    Best-effort throughout — nobody's console breaks because we could not record that they used it.
    """
    from datetime import timedelta
    first = False
    try:
        now = timezone.now()
        if admin.first_seen_at is None:
            first = bool(PartnerAdmin.objects.filter(pk=admin.pk, first_seen_at__isnull=True)
                         .update(first_seen_at=now))
            if first:
                admin.first_seen_at = now
        hours = getattr(settings, 'ADMIN_SEEN_THROTTLE_HOURS', 24)
        if admin.last_seen_at and (now - admin.last_seen_at) < timedelta(hours=hours):
            return first
        PartnerAdmin.objects.filter(pk=admin.pk).update(last_seen_at=now)
        admin.last_seen_at = now
    except Exception:   # noqa: BLE001 — telemetry must never break the caller
        pass
    return first


class AdminRoleView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/role/ - Check if user has admin access.

    ⚠ Also where a staff sign-in is RECORDED. This is the console's `SponsorMeView`: the admin auth
    context calls it once per session for every admin, so it means "a person opened the console" —
    which is the question. `PartnerAdminMixin.get_admin` runs on every admin request instead, so
    stamping there would count a replayed token against any endpoint as a visit.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            # `withdrawn`: about THIS caller's own account only (`staff_reinvite.is_withdrawn`).
            return Response({'is_admin': False, 'withdrawn': staff_reinvite.is_withdrawn(
                auth_sub(request), getattr(request, 'supabase_user', None))})
        # ⚠ THE RETURN VALUE IS THE ACCEPTANCE. `_touch_seen` reports True on the FIRST arrival
        # only — a conditional UPDATE whose rowcount is 1 exactly once in the row's life — so an
        # invitation is closed at the one moment it can be, and cannot be re-accepted later.
        if _touch_seen(admin):
            try:
                from apps.scholarship import invitations
                invitations.accept_for_admin(admin)
            except Exception:   # noqa: BLE001 — bookkeeping never blocks a sign-in
                logger.warning('Could not close the invitation for %s', admin.email, exc_info=True)
        # reviewer_profile_complete: gates the reviewer's first-login landing (they stay on
        # /admin/profile until their compulsory fields are filled). True for every non-reviewer.
        from apps.scholarship.reviewer_onboarding import reviewer_profile_complete
        from . import org_config
        return Response({
            'is_admin': True,
            'is_super_admin': admin.is_super_admin,
            'role': 'super' if admin.is_super else admin.role,
            'admin_id': admin.id,
            # The login page's temp-password gate reads THIS, never a hard-coded mirror of the
            # TTL (Org Config Sprint C) — the served number is resolved for the caller's own
            # organisation, so an org that shortens its TTL shortens the gate too.
            'temp_password_ttl_days': org_config.value(
                admin.owning_organisation, 'temp_password_ttl_days'),
            # `org_name` is the REFERRAL org (None for an org_admin). The Administration
            # panel's org section keys off `owning_org_*` — the B40 tenant this staff
            # member administers (their access boundary), NOT the referral org.
            'org_name': admin.org.name if admin.org else None,
            'owning_org_id': admin.owning_organisation_id,
            'owning_org_name': admin.owning_organisation.name if admin.owning_organisation_id else None,
            'admin_name': admin.name,
            'reviewer_profile_complete': reviewer_profile_complete(admin),
            # Request #39: the RESOLVED staff permissions (never null), the preset they came from
            # and whether they were customised. The server stays the fence; the menu only shows.
            'permissions': list(admin.permission_set),
            'preset': 'super' if admin.is_super else admin.role,
            'custom': staff_permissions.is_custom(admin),
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


def _fetch_auth_data(user_ids, purpose='CSV export'):
    """Look up email + last_sign_in from Supabase Auth's auth.users for the given user IDs.

    Returns {supabase_user_id: {'email': str, 'last_sign_in': 'YYYY-MM-DD' or ''}}.
    Failures are logged but never break the caller. TD-294 (2026-10-03): ``purpose`` names the
    caller in that ERROR line — the officer's applicant-detail GET reads the login email through
    here too, and its failure used to be reported as a "CSV export" nobody had run. Since TD-290
    the line reaches Cloud Logging at ERROR severity with its traceback in ``stack_trace``.
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
        logger.exception('Failed to fetch auth.users data for %s', purpose)
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
# `finance` joined 2026-07-23 (owner decision D5): the org lead appoints their own finance
# checker. Safe against escalation because finance grants LESS than the roles already here —
# it has no B40 scope at all — and it cannot manage staff, so it can never appoint anyone.
_ORG_ADMIN_MANAGEABLE_ROLES = {'reviewer', 'admin', 'qc', 'finance'}

# Everyone who belongs to a TENANT's own staff list — what an org_admin may SEE. Wider than
# `_ORG_ADMIN_MANAGEABLE_ROLES` by exactly one role, `org_admin`, and the gap is the point: you can
# see your fellow organisation admins, you cannot revoke them. Mirrors the frontend's
# `adminStaff.PROGRAMME_STAFF_ROLES`; `super` and `partner` are platform-world and never here.
PROGRAMME_STAFF_ROLES = {'reviewer', 'admin', 'qc', 'finance', 'org_admin'}

# The roles a staff account may be DELETED in (owner, 2026-09-09: *"I am only talking about admin,
# and not reviewers"*). A reviewer is never deletable however empty their record looks — they are
# the people a student's case passes through, and revoking is the answer for one who has left.
_DELETABLE_ROLES = {'admin', 'finance', 'org_admin'}


def scholarship_staff():
    """`(staff_footprint, staff_lifecycle)`: the ONE courses door to scholarship's staff rules."""
    from apps.scholarship import staff_footprint, staff_lifecycle
    return staff_footprint, staff_lifecycle


def _deletable_now(caller, target):
    """Whether ``caller`` may DELETE ``target`` outright, rather than only revoke them.

    Three conditions, all required, and each is refused again by `AdminDeleteView`:
      * the caller may manage them at all (`_staff_target_manageable`);
      * the role is admin-shaped (`_DELETABLE_ROLES`) — never a reviewer, owner 2026-09-09;
      * they have done NO recorded work (`staff_footprint`).
    """
    staff_footprint, _ = scholarship_staff()
    if not _staff_target_manageable(caller, target):
        return False
    if target.is_super or target.role not in _DELETABLE_ROLES:
        return False
    return not staff_footprint.has_footprint(target)


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


class AdminSetPasswordView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/set-password/ - a temp-password partner sets their OWN password.

    The client cannot use `supabase.auth.updateUser({ password })`: the project requires
    re-authentication for a password change (GoTrue "Current password required when setting new
    password"), and the set-password page has no current password to supply. So we set it
    server-side with the SERVICE ROLE (the same key the invite/resend flows already use), which the
    admin API applies without re-auth.

    Scoped tightly so this is NOT a general re-auth bypass: it only ever sets the CALLER'S OWN uid
    (from their JWT), and ONLY while that account still owes a password change
    (`must_change_password` in `app_metadata`, read from Supabase — TD-322, `password_change_flag`;
    never trusted from the browser-writable `user_metadata`) OR the token proves a recovery
    link for this account followed within the last 15 minutes (TD-207, `recovery_session`). An
    ordinary signed-in session is refused — it keeps the project's secure-change policy. ADMINS
    ONLY, on the real JWT subject (review F3): a student or sponsor with a reset link never
    reaches the service-role write, and a TD-254 profile alias never redirects it.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        uid = auth_sub(request)
        if not uid:
            return Response({'error': 'not_authenticated'}, status=401)
        admin = self.get_admin(request)
        if admin is None:
            return Response({'error': 'not_an_admin'}, status=403)
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
        account = gr.json() or {}
        # TD-322: the flag is read from app_metadata (server-writable only); a user_metadata flag
        # counts only for a pre-release invite the server's own Invitation row says is still live.
        # TD-207: a FRESH recovery session for THIS account is authority too ("Forgot password").
        if not (password_change_flag.owes_password_change(
                    account, lambda: _invitations_for([admin]).get(admin.id))
                or is_fresh_recovery_for(request, account.get('email'))):
            # Neither onboarding nor a reset — do not stand in for a normal (re-auth'd) change.
            return Response({'error': 'not_pending_password_change'}, status=403)

        # Supabase admin updateUser MERGES metadata (omitting a key does NOT delete it), so the
        # temp-password fields are cleared by sending null — in both homes, the old one included.
        body = {'password': password, 'app_metadata': password_change_flag.cleared_fields(),
                'user_metadata': password_change_flag.scrubbed_user_metadata(
                    account.get('user_metadata'))}
        try:
            pr = http_requests.put(user_url, json=body, headers=headers, timeout=15)
        except Exception:  # noqa: BLE001
            return Response({'error': 'supabase_unreachable'}, status=502)
        if pr.status_code not in (200, 201):
            logger.error('set-password failed: %s %s', pr.status_code, pr.text)
            return Response({'error': 'set_password_failed'}, status=502)
        return Response({'ok': True})


class AdminOrgsView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/orgs/ - the REFERRAL PARTNERS a partner login may be invited onto (the
    Referral partners page's dropdown, its only reader). Sources Sprint B: the invite refuses any
    other row, so offering tenants and sources here would only offer refusals."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        orgs = referral_links.referral_partners().order_by('name').values(
            'id', 'code', 'name', 'contact_person', 'phone',
        )
        return Response({'orgs': list(orgs)})


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
