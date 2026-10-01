"""TD-160: a partner invite whose Supabase create answers 2xx WITHOUT a readable user id.

Before: the PartnerAdmin row was stored with no `supabase_user_id`, so Resend took it for an
account we did not create and never rotated its password. Now the id is read back by email; if
that fails too, the row is still stored and a WARNING names the address.
"""
from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_admin_auth import TEST_JWT_SECRET, _token

EMAIL = 'newpartner@example.org'
POST = 'apps.courses.views_admin.http_requests.post'
GET = 'apps.courses.supabase_admin.http_requests.get'


def _unparseable(**kw):
    def boom():
        raise ValueError('no JSON')
    return MagicMock(status_code=201, text='', json=boom, **kw)


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class TestInviteReadsTheUidBack(TestCase):

    @classmethod
    def setUpTestData(cls):
        PartnerAdmin.objects.create(supabase_user_id='super-uid', is_super_admin=True,
                                    is_active=True, name='Super', email='super@halatuju.com')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("super-uid")}')

    def _invite(self, created, read_back):
        with patch(POST, return_value=created), patch(GET, **read_back) as get:
            r = self.client.post('/api/v1/admin/invite/',
                                 {'email': EMAIL, 'name': 'New Partner', 'role': 'reviewer'},
                                 format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return PartnerAdmin.objects.get(email=EMAIL), get

    def test_a_2xx_with_no_body_reads_the_uid_back_by_email(self):
        users = {'users': [{'id': 'other-uid', 'email': 'x' + EMAIL},     # a substring near-miss
                           {'id': 'readback-uid', 'email': EMAIL.upper()}]}
        row, get = self._invite(_unparseable(), {'return_value': MagicMock(
            status_code=200, json=lambda: users)})
        self.assertEqual(row.supabase_user_id, 'readback-uid')
        self.assertTrue(get.call_args[0][0].endswith('/auth/v1/admin/users'))
        self.assertEqual(get.call_args[1]['params']['filter'], EMAIL)

    def test_a_2xx_body_WITHOUT_an_id_also_reads_back(self):
        created = MagicMock(status_code=200, text='{}', json=lambda: {})
        row, _ = self._invite(created, {'return_value': MagicMock(
            status_code=200, json=lambda: {'users': [{'id': 'rb2', 'email': EMAIL}]})})
        self.assertEqual(row.supabase_user_id, 'rb2')

    def test_a_FAILED_read_back_stores_the_row_and_warns_naming_the_email(self):
        with self.assertLogs('apps.courses.supabase_admin', level='WARNING') as caught:
            row, _ = self._invite(_unparseable(), {'side_effect': ConnectionError('down')})
        self.assertIsNone(row.supabase_user_id)
        self.assertTrue(any(EMAIL in line and 'TD-160' in line for line in caught.output),
                        caught.output)
        # The welcome email still carried the temp password the account was created with.
        self.assertIn('temporary password', mail.outbox[-1].body.lower())
        # ACCEPTED behaviour until their first sign-in links the row by verified email: Resend
        # treats a row with no UID as an account we did not create — it re-sends the "sign in
        # as usual" note and rotates NOTHING (the TD-160 entry's documented recovery stands:
        # first sign-in, forgot-password, or delete and re-invite).
        mail.outbox.clear()
        with patch('apps.courses.views_admin.http_requests.put') as put:
            r = self.client.post(f'/api/v1/admin/admins/{row.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        put.assert_not_called()
        self.assertNotIn('temporary password', mail.outbox[0].body.lower())

    def test_an_AMBIGUOUS_read_back_is_not_trusted(self):
        two = {'users': [{'id': 'a', 'email': EMAIL}, {'id': 'b', 'email': EMAIL}]}
        with self.assertLogs('apps.courses.supabase_admin', level='WARNING'):
            row, _ = self._invite(_unparseable(), {'return_value': MagicMock(
                status_code=200, json=lambda: two)})
        self.assertIsNone(row.supabase_user_id)

    def test_the_happy_path_is_unchanged_and_never_reads_back(self):
        created = MagicMock(status_code=200, text='ok', json=lambda: {'id': 'direct-uid'})
        row, get = self._invite(created, {})
        self.assertEqual(row.supabase_user_id, 'direct-uid')
        get.assert_not_called()
