"""GET / PUT /api/v1/admin/profile/ — a referral partner's own name and organisation contact.

Moved VERBATIM out of `views_admin.py` at common profile S3 (2026-10-31), a moves-only split:
`views_admin.py` sat exactly at its `oversize_files` allowance (795 + 20), and S3 had to add a line
to it (the first sign-in on the activity list, `AdminRoleView`). The one change after the move is
the activity row a save writes (`staff_activity_hook`). `urls.py` routes here.
"""
from rest_framework.views import APIView
from rest_framework.response import Response

from . import staff_activity_hook
from .views_admin import PartnerAdminMixin


class AdminProfileView(PartnerAdminMixin, APIView):
    """GET/PUT /api/v1/admin/profile/ - View/edit own admin profile."""
    source_partner_methods = ('get',)   # their own row; S3 gives a source its own profile write

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

        changed = []    # S4 review L4: only what CHANGED is named
        name = request.data.get('name', '').strip()
        if name:
            changed += ['name'] if name != admin.name else []
            admin.name = name
            admin.save(update_fields=['name'])

        # Org admins can edit their org's contact info
        if admin.org:
            contact = request.data.get('org_contact_person')
            phone = request.data.get('org_phone')
            before = (admin.org.contact_person, admin.org.phone)
            if contact is not None:
                admin.org.contact_person = contact.strip()
            if phone is not None:
                admin.org.phone = phone.strip()
            if contact is not None or phone is not None:
                admin.org.save(update_fields=['contact_person', 'phone'])
                if (admin.org.contact_person, admin.org.phone) != before:
                    changed.append('organisation')

        # Common profile S3: on the person's own activity list (best-effort; never raises).
        if changed:
            staff_activity_hook.record(admin, 'profile_updated', meta={'fields': changed})
        return Response({'message': 'Profile updated'})
