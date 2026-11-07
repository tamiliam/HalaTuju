"""A1.11a / TD-441 item 3 — the first-sign-in link is a compare-and-set.

`_find_admin` reads the staff row by email, then checks the login over the network
(`link_refusal`). A staff email move, a revoke or another link committing in that window used to be
overwritten by a write by primary key alone. The admin read is mocked; nothing touches the network.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_sec02_staff_link import CONFIRMED, EMAIL, READ, ROLE, SUB, _forged_token
from apps.scholarship.tests.factories import TEST_JWT_SECRET, make_admin, make_org


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheLinkIsACompareAndSet(TestCase):
    def setUp(self):
        self.row = make_admin('reviewer', owning_org=make_org(), email=EMAIL, name='Rohini')
        PartnerAdmin.objects.filter(pk=self.row.pk).update(supabase_user_id=None)

    def _sign_in_while(self, change):
        """Sign in; ``change`` commits on the row DURING the network check."""
        def read(uid):
            PartnerAdmin.objects.filter(pk=self.row.pk).update(**change)
            return CONFIRMED
        with patch(READ, side_effect=read):
            r = self.client.get(ROLE, HTTP_AUTHORIZATION=f'Bearer {_forged_token()}')
        self.row.refresh_from_db()
        return r

    def test_an_email_moved_during_the_check_is_not_linked(self):
        r = self._sign_in_while({'email': 'someone.else@example.org'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['is_admin'])
        self.assertIsNone(self.row.supabase_user_id)

    def test_another_link_landing_first_is_not_overwritten(self):
        r = self._sign_in_while({'supabase_user_id': 'the-other-login'})
        self.assertFalse(r.json()['is_admin'])
        self.assertEqual(self.row.supabase_user_id, 'the-other-login')

    def test_a_revoke_during_the_check_is_not_linked(self):
        r = self._sign_in_while({'is_active': False})
        self.assertFalse(r.json()['is_admin'])
        self.assertIsNone(self.row.supabase_user_id)

    def test_an_untouched_row_still_links(self):
        r = self._sign_in_while({'name': 'Rohini K'})
        self.assertTrue(r.json()['is_admin'], r.content)
        self.assertEqual(self.row.supabase_user_id, SUB)
