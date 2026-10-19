"""Request #39 Sprint 1 — the invite's "already exists" answer.

It used to tell everyone "Admin with this email already exists": an org_admin learnt that an address
was in use SOMEWHERE, and nothing they could act on. Now (`views_staff.already_exists_answer`):

- somebody the caller already sees on People (their own organisation; any account for a super) →
  409 `already_on_team`, naming them, their preset and where to go;
- anybody else — another organisation's staff, a super, a referral partner — → 409 `not_invitable`,
  ONE fixed sentence that confirms nothing about the other account (the door list's question: can
  the message tell an org_admin that an address exists in ANOTHER organisation? It must not).

A student's own login is not a staff account: it is still invited on the already-registered path.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.courses.tests.test_admin_auth import TEST_JWT_SECRET, _token
from apps.scholarship.tests.factories import make_admin

NEUTRAL = "This email address can't be invited. Ask HalaTuju support."


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')
class AlreadyOnTheTeam(TestCase):

    def setUp(self):
        self.org_a = PartnerOrganisation.objects.create(code='team-a', name='Org A',
                                                        module_scholarship=True)
        self.org_b = PartnerOrganisation.objects.create(code='team-b', name='Org B',
                                                        module_scholarship=True)
        self.lead_a = make_admin('org_admin', owning_org=self.org_a, name='Suresh')
        self.super = make_admin('super', super_admin=True, name='Owner')
        self.client = APIClient()

    def _invite(self, caller, email, role='reviewer', name='Somebody'):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(caller.supabase_user_id)}')
        return self.client.post('/api/v1/admin/invite/',
                                {'email': email, 'name': name, 'role': role}, format='json')

    # ── the caller's own organisation ──────────────────────────────────────────────────────────
    def test_an_active_colleague_is_named_with_their_preset(self):
        make_admin('reviewer', owning_org=self.org_a, name='Rohini', email='rohini@example.org')
        r = self._invite(self.lead_a, 'rohini@example.org')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {
            'error': 'Rohini is already on your team as Reviewer. To change what they can do, '
                     'open People → Rohini.',
            'code': 'already_on_team', 'name': 'Rohini', 'preset': 'reviewer', 'is_active': True})

    def test_the_address_is_matched_whatever_its_case(self):
        make_admin('reviewer', owning_org=self.org_a, name='Rohini', email='rohini@example.org')
        r = self._invite(self.lead_a, ' Rohini@Example.ORG ')
        self.assertEqual(r.json()['code'], 'already_on_team')

    def test_a_fellow_org_admin_is_named_too_they_are_on_people(self):
        make_admin('org_admin', owning_org=self.org_a, name='Kulaly', email='kulaly@example.org')
        r = self._invite(self.lead_a, 'kulaly@example.org')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['error'], 'Kulaly is already on your team as Organisation admin. '
                                            'To change what they can do, open People → Kulaly.')

    def test_a_switched_off_colleague_who_has_signed_in_is_sent_to_restore(self):
        # Not reusable (TD-335 re-invites only a never-seen, work-free row), so the 409 stands.
        make_admin('finance', owning_org=self.org_a, name='Mala', email='mala@example.org',
                   is_active=False, first_seen_at=timezone.now())
        r = self._invite(self.lead_a, 'mala@example.org')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['error'], 'Mala is on your team as Finance admin, but switched '
                                            'off. To bring them back, open People → Mala.')
        self.assertIs(r.json()['is_active'], False)

    def test_a_google_address_on_the_team_gets_the_same_answer(self):
        make_admin('qc', owning_org=self.org_a, name='Gopal', email='gopal@gmail.com')
        r = self._invite(self.lead_a, 'gopal@gmail.com')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['code'], 'already_on_team')
        self.assertEqual(r.json()['preset'], 'qc')

    def test_a_reinvite_that_loses_its_race_names_them_too(self):
        # `may_reuse` said yes, then `bring_back` found the row taken (a Restore landed first):
        # both branches (Google and password) answer with the same served sentence.
        make_admin('reviewer', owning_org=self.org_a, name='Ravi', email='ravi@example.org',
                   is_active=False)
        make_admin('reviewer', owning_org=self.org_a, name='Gita', email='gita@gmail.com',
                   is_active=False)
        with patch('apps.courses.staff_reinvite.provision', return_value=(None, False, 'not_reusable')):
            for email, name in (('ravi@example.org', 'Ravi'), ('gita@gmail.com', 'Gita')):
                with self.subTest(email=email):
                    r = self._invite(self.lead_a, email)
                    self.assertEqual(r.status_code, 409)
                    self.assertEqual(r.json()['code'], 'already_on_team')
                    self.assertEqual(r.json()['name'], name)

    # ── anybody else: one neutral answer ───────────────────────────────────────────────────────
    def test_another_organisation_s_staff_get_the_neutral_answer(self):
        make_admin('reviewer', owning_org=self.org_b, name='Bala', email='bala@example.org')
        r = self._invite(self.lead_a, 'bala@example.org')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {'error': NEUTRAL, 'code': 'not_invitable'})

    def test_the_neutral_answer_is_identical_for_every_kind_of_other_account(self):
        """Byte-identical bodies: nothing distinguishes another organisation's active admin, its
        switched-off reviewer, its org_admin, a super, a referral partner, or a Google address."""
        others = [
            make_admin('admin', owning_org=self.org_b, email='b-admin@example.org'),
            make_admin('reviewer', owning_org=self.org_b, email='b-off@example.org', is_active=False),
            make_admin('org_admin', owning_org=self.org_b, email='b-lead@example.org'),
            make_admin('super', super_admin=True, email='another-super@example.org'),
            make_admin('admin', super_admin=True, owning_org=self.org_a,
                       email='super-in-a@example.org'),
            make_admin('partner', email='partner@example.org'),
            make_admin('finance', owning_org=self.org_b, email='b-fin@gmail.com'),
        ]
        bodies = set()
        for other in others:
            with self.subTest(email=other.email):
                r = self._invite(self.lead_a, other.email)
                self.assertEqual(r.status_code, 409)
                bodies.add(r.content)
                for leak in (other.name, 'Org B', other.role):
                    self.assertNotIn(leak.encode(), r.content)
        self.assertEqual(bodies, {b'{"error":"This email address can\'t be invited. Ask HalaTuju '
                                  b'support.","code":"not_invitable"}'})

    # ── the platform super sees everyone on People, so is told who it is ───────────────────────
    def test_a_super_is_told_whose_account_it_is(self):
        make_admin('reviewer', owning_org=self.org_b, name='Bala', email='bala@example.org')
        r = self._invite(self.super, 'bala@example.org')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['error'], 'Bala already has a staff account (Reviewer, Org B). '
                                            'To change what they can do, open People → Bala.')
        make_admin('partner', name='Cumig Rep', email='rep@example.org')
        r = self._invite(self.super, 'rep@example.org')
        self.assertEqual(r.json()['error'], 'Cumig Rep already has a staff account (Partner, no '
                                            'organisation). To change what they can do, open '
                                            'People → Cumig Rep.')

    # ── a student's own login is not a staff account ───────────────────────────────────────────
    def test_a_student_login_is_still_invited_on_the_already_registered_path(self):
        exists = MagicMock(status_code=422, text='exists',
                           json=lambda: {'error_code': 'email_exists'})
        student = {'id': 'student-uid', 'email': 'student@example.org', 'app_metadata': {},
                   'identities': [{'provider': 'email'}]}
        with patch('apps.courses.supabase_admin.http_requests.post', return_value=exists), \
                patch('apps.courses.supabase_admin._read_back_user_id', return_value='student-uid'), \
                patch('apps.courses.supabase_admin.read_auth_user', return_value=student):
            r = self._invite(self.lead_a, 'student@example.org', name='Siva')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['already_registered'])
        row = PartnerAdmin.objects.get(email='student@example.org')
        self.assertEqual((row.role, row.owning_organisation_id, row.supabase_user_id),
                         ('reviewer', self.org_a.id, None))
        self.assertIsNone(row.permissions)          # an invitee gets the preset: NULL, no backfill
