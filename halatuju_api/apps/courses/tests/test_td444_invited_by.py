"""TD-444: a staff invitation records who sent it.

Before: `_record_invitation` read `request._inviting_admin`, which nothing ever set, so every staff
`Invitation` row stored `invited_by` NULL. Now the Invite and Resend views pass the admin who pressed
the button, as `invitations.record_send` already takes its `actor`.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_admin_auth import TEST_JWT_SECRET, _token
from apps.scholarship.models import Invitation

EMAIL = 'td444-invitee@example.org'
POST = 'apps.courses.views_admin.http_requests.post'


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class TestStaffInvitationRecordsTheInviter(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.first = PartnerAdmin.objects.create(supabase_user_id='first-uid', role='super',
                                                is_active=True, name='First', email='first@halatuju.com')
        cls.second = PartnerAdmin.objects.create(supabase_user_id='second-uid', role='super',
                                                 is_active=True, name='Second', email='second@halatuju.com')

    def _client(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def _invite(self):
        created = MagicMock(status_code=201, text='{"id": "invitee-uid"}',
                            json=lambda: {'id': 'invitee-uid'})
        with patch(POST, return_value=created):
            r = self._client('first-uid').post(
                '/api/v1/admin/invite/',
                {'email': EMAIL, 'name': 'Invitee', 'role': 'reviewer', 'gift_scope': 'every'},
                format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return Invitation.objects.get(audience='staff', email=EMAIL)

    def test_an_invite_stores_the_admin_who_sent_it(self):
        self.assertEqual(self._invite().invited_by, self.first)

    def test_a_resend_by_someone_else_keeps_the_first_inviter(self):
        inv = self._invite()
        target = PartnerAdmin.objects.get(email=EMAIL)
        # No UID: Resend rotates nothing and calls no Supabase endpoint (TD-440's "not ours" branch).
        PartnerAdmin.objects.filter(pk=target.pk).update(supabase_user_id=None)
        r = self._client('second-uid').post(f'/api/v1/admin/admins/{target.id}/resend/', {},
                                            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        inv.refresh_from_db()
        self.assertEqual(Invitation.objects.filter(audience='staff', email=EMAIL).count(), 1)
        self.assertEqual(inv.invited_by, self.first)

    def test_a_resend_with_no_open_invitation_stores_the_resender(self):
        target = PartnerAdmin.objects.create(role='reviewer', is_active=True, name='Old Invitee',
                                             email='td444-old@example.org')
        r = self._client('second-uid').post(f'/api/v1/admin/admins/{target.id}/resend/', {},
                                            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Invitation.objects.get(audience='staff', email='td444-old@example.org')
                         .invited_by, self.second)
