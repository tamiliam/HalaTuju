"""GET /api/v1/admin/staff/ — the Staff list (Sprint M1a, 2026-11-10; owner O1-O3, O7, O9). Brief §3.

Everyone on the team, whatever group they sit in or none: active and suspended staff, members ("No group")
and mentors' own logins. NOT listed: an archived row (gone from every list, M1a §5), a person who has not
accepted yet (`first_seen_at` NULL: they live on Invitations only, O1), a super, a source user and a
referral `partner` (platform-world, not a team's).

The read gate is `AdminListView`'s (`team_roster`). A super sees every organisation, or one with
`?organisation=<id>` (it NARROWS; an unknown id is 404, never "show everything"); anybody else sees their
OWN organisation only, and `manageable` (the write fence, per row) is false wherever they may not act. The
row fields and the fixed query budget: `apps.scholarship.staff_list`, reached through the ONE courses →
scholarship door (`views_admin.scholarship_staff()`). No phone and no email (O9, O16).
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from . import staff_tables
from .models import PartnerAdmin, PartnerOrganisation
from .staff_fence import PROGRAMME_STAFF_ROLES
from .views_admin import PartnerAdminMixin, scholarship_staff

#: The roles the Staff list shows: programme staff (members too) and mentors' own logins.
LISTED_ROLES = (*sorted(PROGRAMME_STAFF_ROLES), PartnerAdmin.MENTOR_ROLE)


class StaffListView(PartnerAdminMixin, APIView):
    def get(self, request):
        admin = self.get_admin(request)
        if not staff_tables.opens_door(admin, 'team_roster'):
            return Response({'error': 'Access denied'}, status=403)
        people = (PartnerAdmin.objects.select_related('mentor', 'owning_organisation')
                  .filter(archived_at=None, first_seen_at__isnull=False, role__in=LISTED_ROLES)
                  .order_by('name', 'id'))
        if admin.is_super:
            asked = request.query_params.get('organisation')
            if asked not in (None, ''):
                if not str(asked).isdigit():
                    return Response({'error': 'organisation must be an id', 'code': 'bad_organisation'},
                                    status=400)
                if not PartnerOrganisation.objects.filter(pk=int(asked)).exists():
                    return Response({'error': 'Organisation not found', 'code': 'not_found'}, status=404)
                people = people.filter(owning_organisation_id=int(asked))
        else:
            people = people.filter(owning_organisation_id=admin.owning_organisation_id)
            if admin.owning_organisation_id is None:
                people = people.none()
        _, staff_lifecycle = scholarship_staff()
        return Response({'staff': staff_lifecycle.staff_list_rows(admin, people)})
