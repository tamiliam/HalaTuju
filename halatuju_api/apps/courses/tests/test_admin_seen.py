"""Staff sign-in: `first_seen_at` and `last_seen_at` on `PartnerAdmin`.

Until 2026-08-03 the console recorded NOTHING about whether an invited person ever arrived. There
was no `last_login`, no `accepted_at` — so an invitation nobody acted on and a colleague of a year
were the same row to every reader, and the staff table honestly could not tell them apart.

Two claims carry the weight here:

1. **`first_seen_at` is written exactly once, ever.** It is a conditional UPDATE filtered on the
   column still being NULL, so the rowcount is `1` on the first visit and `0` on every visit after.
   That rowcount is what will close an invitation in the next sprint, so a second `True` would
   re-accept an invitation that was already settled — `test_it_reports_first_arrival_ONCE` is the
   guard.

2. **A visit is not an edit.** The stamp goes through `.update()`, never `.save()`, so it cannot
   touch a neighbouring field or race with a concurrent write. Asserted by mutating the row
   underneath an in-memory instance and watching the change survive.

And the honest-NULL rule: nothing here may report "never signed in". Both columns are empty for
everyone who was already on the system, so NULL means *not recorded*.
"""
from datetime import timedelta

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.courses.views_admin import _touch_seen

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ROLE_URL = '/api/v1/admin/role/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheStamp(TestCase):
    def setUp(self):
        self.admin = PartnerAdmin.objects.create(
            supabase_user_id='seen-uid', role='reviewer', is_active=True,
            name='Newcomer', email='newcomer@example.org')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("seen-uid")}')

    def test_nothing_is_recorded_before_they_arrive(self):
        self.assertIsNone(self.admin.first_seen_at)
        self.assertIsNone(self.admin.last_seen_at)

    def test_opening_the_console_records_both(self):
        self.assertEqual(self.client.get(ROLE_URL).status_code, 200)
        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.first_seen_at)
        self.assertIsNotNone(self.admin.last_seen_at)

    def test_it_reports_first_arrival_ONCE(self):
        # This bool closes an invitation. A second True would re-accept one already settled.
        self.assertTrue(_touch_seen(self.admin))
        self.assertFalse(_touch_seen(self.admin))
        fresh = PartnerAdmin.objects.get(pk=self.admin.pk)
        self.assertFalse(_touch_seen(fresh))

    def test_TWO_CALLERS_RACING_still_produce_exactly_one_first_arrival(self):
        """⚠ THE ONE THAT ACTUALLY TESTS THE GUARD.

        The test above passes even with the conditional stripped out, because the cheap
        `if admin.first_seen_at is None` short-circuit catches the sequential case — proven by
        biting it. The conditional UPDATE exists for the case that check CANNOT see: two requests
        that both read the row while it was still NULL, which is what a console does when a
        session establishes in two tabs at once.

        Two independent in-memory instances, both believing they are first. Exactly one may win.
        """
        a = PartnerAdmin.objects.get(pk=self.admin.pk)
        b = PartnerAdmin.objects.get(pk=self.admin.pk)
        self.assertIsNone(a.first_seen_at)
        self.assertIsNone(b.first_seen_at)
        results = [_touch_seen(a), _touch_seen(b)]
        self.assertEqual(results.count(True), 1, 'exactly one caller may report first arrival')

    def test_first_seen_never_moves_again(self):
        _touch_seen(self.admin)
        original = PartnerAdmin.objects.get(pk=self.admin.pk).first_seen_at
        PartnerAdmin.objects.filter(pk=self.admin.pk).update(
            last_seen_at=timezone.now() - timedelta(days=30))
        _touch_seen(PartnerAdmin.objects.get(pk=self.admin.pk))
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).first_seen_at, original)

    def test_last_seen_is_throttled(self):
        _touch_seen(self.admin)
        stamped = PartnerAdmin.objects.get(pk=self.admin.pk).last_seen_at
        _touch_seen(PartnerAdmin.objects.get(pk=self.admin.pk))
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).last_seen_at, stamped)

    def test_last_seen_moves_once_the_window_passes(self):
        # A throttle that never released would freeze the answer at somebody's first visit.
        _touch_seen(self.admin)
        stale = timezone.now() - timedelta(hours=48)
        PartnerAdmin.objects.filter(pk=self.admin.pk).update(last_seen_at=stale)
        _touch_seen(PartnerAdmin.objects.get(pk=self.admin.pk))
        self.assertGreater(PartnerAdmin.objects.get(pk=self.admin.pk).last_seen_at, stale)

    def test_a_visit_is_not_an_edit(self):
        # `.update()` not `.save()`: a stale in-memory instance must not write its own copy of a
        # field somebody else changed in the meantime.
        PartnerAdmin.objects.filter(pk=self.admin.pk).update(name='Renamed Elsewhere')
        _touch_seen(self.admin)            # self.admin still holds the OLD name
        self.assertEqual(PartnerAdmin.objects.get(pk=self.admin.pk).name, 'Renamed Elsewhere')

    def test_a_failure_to_record_never_breaks_the_console(self):
        # Telemetry is not worth a person's session. Fault-injected.
        from unittest.mock import patch
        with patch.object(PartnerAdmin.objects.__class__, 'filter',
                          side_effect=RuntimeError('database on fire')):
            self.assertFalse(_touch_seen(self.admin))
        self.assertEqual(self.client.get(ROLE_URL).status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestThePayload(TestCase):
    def setUp(self):
        self.super = PartnerAdmin.objects.create(
            supabase_user_id='seen-su', is_super_admin=True, role='super', is_active=True,
            name='Super', email='su@example.org')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("seen-su")}')

    def test_the_staff_list_carries_both_stamps(self):
        seen = timezone.now()
        PartnerAdmin.objects.create(
            supabase_user_id='seen-r', role='reviewer', is_active=True,
            name='Arrived', email='arrived@example.org',
            first_seen_at=seen, last_seen_at=seen)
        PartnerAdmin.objects.create(
            supabase_user_id='seen-n', role='reviewer', is_active=True,
            name='Not Recorded', email='norecord@example.org')
        rows = {a['email']: a for a in self.client.get('/api/v1/admin/admins/').json()['admins']}
        self.assertIsNotNone(rows['arrived@example.org']['first_seen_at'])
        # ⚠ NULL travels as null — the screen decides it means "not recorded". The server must not
        # invent a date, and must not omit the key, or the front end cannot tell the two apart.
        self.assertIsNone(rows['norecord@example.org']['first_seen_at'])
        self.assertIn('last_seen_at', rows['norecord@example.org'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheInvitationOnTheStaffList(TestCase):
    """The staff payload carries how far each person's invitation got.

    This is the whole point of the record: before it, the three states below were one word.
    """

    def setUp(self):
        self.super = PartnerAdmin.objects.create(
            supabase_user_id='inv-su', is_super_admin=True, role='super', is_active=True,
            name='Super', email='su-inv@example.org')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("inv-su")}')

    def _rows(self):
        return {a['email']: a for a in self.client.get('/api/v1/admin/admins/').json()['admins']}

    def test_it_tells_the_three_states_apart(self):
        from datetime import timedelta
        from apps.scholarship import invitations

        arrived = PartnerAdmin.objects.create(
            supabase_user_id='inv-a', role='reviewer', is_active=True, name='Arrived',
            email='arrived@example.org', first_seen_at=timezone.now())
        lapsed = PartnerAdmin.objects.create(
            supabase_user_id='inv-l', role='reviewer', is_active=True, name='Lapsed',
            email='lapsed@example.org')
        silent = PartnerAdmin.objects.create(
            supabase_user_id='inv-s', role='reviewer', is_active=True, name='Silent',
            email='silent@example.org')

        invitations.create_or_refresh(audience='staff', email=arrived.email,
                                      partner_admin=arrived, credential_issued=True)
        invitations.accept_for_admin(arrived)
        past = timezone.now() - timedelta(days=30)
        for who, issued in ((lapsed, True), (silent, False)):
            inv = invitations.create_or_refresh(audience='staff', email=who.email,
                                                partner_admin=who, credential_issued=issued)
            inv.expires_at = past
            inv.save(update_fields=['expires_at'])

        rows = self._rows()
        self.assertEqual(rows['arrived@example.org']['invitation']['status'], 'accepted')
        # A password was issued and has lapsed — a Resend is genuinely required.
        self.assertEqual(rows['lapsed@example.org']['invitation']['status'], 'expired')
        # ⚠ Nothing was ever issued, so nothing expired. Calling this "expired" would send an
        # org_admin hunting for a credential that never existed.
        self.assertEqual(rows['silent@example.org']['invitation']['status'], 'no_reply')

    def test_somebody_with_no_invitation_on_record_reports_none_rather_than_a_guess(self):
        PartnerAdmin.objects.create(
            supabase_user_id='inv-old', role='reviewer', is_active=True, name='Predates',
            email='predates@example.org')
        self.assertIsNone(self._rows()['predates@example.org']['invitation'])
