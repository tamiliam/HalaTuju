"""GET/PUT /api/v1/scholarship/guardian-contact/ — the student's own parent/guardian contact.

Request #26 (2026-10-05). The rules live in `guardian_contact.py`; this file is wiring.

⚠ WHY THIS IS NOT ON `/api/v1/profile/` (ProfileView), where the brief first placed it. The profile
view is in `apps/courses`, and the contact's rules are scholarship rules (the signing window, the
change record). Reaching them from `courses` adds an `apps.courses → apps.scholarship` import, and
that back-edge is held at its budget by `test_code_standards.TestTheAppBoundary` — it may not
grow. So the profile page asks scholarship directly, through this endpoint, and ProfileView is
untouched.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import StudentProfile
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated

from . import guardian_contact


class StudentGuardianContactView(APIView):
    """GET → `{has_scholarship_application, guardian_contact_locked, name, phone}`.
    PUT `{name, phone}` → the same, plus `changed`. Refusals carry a stable `code`:
    `no_application` (403, R4 — nothing to correct before applying), `guardian_contact_locked`
    (409, R2 — the bursary agreement is being signed), or a validation code (400)."""
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request):
        profile = StudentProfile.objects.filter(supabase_user_id=request.user_id).first()
        return Response(guardian_contact.contact_payload(profile))

    def put(self, request):
        profile = StudentProfile.objects.filter(supabase_user_id=request.user_id).first()
        if not guardian_contact.has_scholarship_application(profile):
            return _refuse('no_application', status.HTTP_403_FORBIDDEN)
        su = getattr(request, 'supabase_user', None) or {}
        try:
            change = guardian_contact.update_guardian_contact(
                profile, name=request.data.get('name'), phone=request.data.get('phone'),
                by_email=su.get('email') or profile.contact_email or '', by_role='student')
        except guardian_contact.GuardianContactError as e:
            code = (status.HTTP_409_CONFLICT if e.code == guardian_contact.LOCKED
                    else status.HTTP_400_BAD_REQUEST)
            return _refuse(e.code, code)
        return Response({**guardian_contact.contact_payload(profile), 'changed': change is not None})


def _refuse(code, http):
    return Response({'error': code, 'code': code}, status=http)
