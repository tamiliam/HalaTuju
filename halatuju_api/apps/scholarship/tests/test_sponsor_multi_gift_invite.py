"""Invitations I3 (2026-11-08; owner ruling 1, open point B) — a sponsor invitation names several
gifts, or Every gift, and registering opens one PENDING membership per gift, each vetted as today.

The rules pinned here:
  - gifts A+B -> two pending memberships on registration; Every gift -> one per gift ACTIVE in the
    invitation's organisation when they register (not when invited, and not one started later);
  - one gift, the old `programme_id`, and nothing-with-one-active-gift behave exactly as before;
  - a stranger off the public form while several gifts are active joins NOTHING;
  - registration is create-only: an approved / rejected / suspended membership is never downgraded;
  - a resend keeps the gifts; a gift outside the caller's reach is 404, never stored.
"""
from importlib import import_module

import jwt
from django.apps import apps as django_apps
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import sponsorship
from apps.scholarship.models import (
    Invitation, InvitationGift, Programme, Sponsor, SponsorProgrammeMembership,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme,
)

INVITE = '/api/v1/admin/invitations/'
REGISTER = '/api/v1/sponsor/register/'
FULL = {'name': 'Test Giver', 'phone': '012-000 0000', 'source': 'google', 'consent': True}
EMAIL = 'multi.giver@example.com'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Case(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Migration 0098 seeds BrightPath (active) into every test DB: switched off so each test
        # states exactly how many gifts are open.
        Programme.objects.update(is_active=False)
        cls.org = make_org('i3-org')
        cls.other = make_org('i3-other')
        cls.a = make_programme(organisation=cls.org, code='i3-a', name_en='Gift A', is_active=True)
        cls.b = make_programme(organisation=cls.org, code='i3-b', name_en='Gift B', is_active=True)
        cls.theirs = make_programme(organisation=cls.other, code='i3-theirs', is_active=True)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org, uid='i3-oa')
        cls.super = make_admin('super', super_admin=True, uid='i3-super')

    def _invite(self, admin=None, **extra):
        return authed_client(admin or self.org_admin).post(
            INVITE, {'audience': 'sponsor', 'email': EMAIL, 'name': 'Test Giver', **extra},
            format='json')

    def _register(self, uid='i3-giver', email=EMAIL):
        token = jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
                            'email': email, 'is_anonymous': False}, TEST_JWT_SECRET,
                           algorithm='HS256')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = client.post(REGISTER, FULL, format='json')
        self.assertIn(r.status_code, (200, 201), r.content)
        return Sponsor.objects.get(supabase_user_id=uid)

    def _review(self, sponsor, action):
        r = authed_client(self.org_admin).post(
            f'/api/v1/admin/sponsors/{sponsor.id}/review/', {'action': action}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    @staticmethod
    def _memberships(sponsor):
        return {m.programme.code: m.status
                for m in SponsorProgrammeMembership.objects.filter(sponsor=sponsor)}

    def _inv(self):
        return Invitation.objects.get(audience='sponsor', email=EMAIL)


class TestSeveralGifts(_Case):
    def test_gifts_A_and_B_open_two_pending_memberships_each_vetted(self):
        r = self._invite(programme_ids=[self.a.id, self.b.id])
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertEqual(sorted(inv.gift_rows.values_list('programme_id', flat=True)),
                         sorted([self.a.id, self.b.id]))
        self.assertIsNone(inv.programme_id)          # the mirror: several -> NULL
        self.assertFalse(inv.every_gift)

        sponsor = self._register()
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'pending', 'i3-b': 'pending'})
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'approved'})
        # ...and each is still its own decision afterwards.
        sponsorship.set_programme_membership(sponsor, self.b, 'rejected', vetted_by='x@example.com')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'rejected'})

    def test_registering_twice_never_duplicates(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        self._register()
        sponsor = self._register()                     # the existing-sponsor completion path
        self.assertEqual(SponsorProgrammeMembership.objects.filter(sponsor=sponsor).count(), 2)


class TestEveryGift(_Case):
    def test_every_gift_means_the_gifts_active_WHEN_THEY_REGISTER(self):
        r = self._invite(programme_ids=[])
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertTrue(inv.every_gift)
        self.assertIsNone(inv.programme_id)
        self.assertFalse(inv.gift_rows.exists())       # not resolved until they register
        # After the invite: B closes, C opens. Registration joins A and C — and never another
        # organisation's gift.
        Programme.objects.filter(pk=self.b.pk).update(is_active=False)
        make_programme(organisation=self.org, code='i3-c', is_active=True)

        sponsor = self._register()
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'pending', 'i3-c': 'pending'})

    def test_a_gift_started_after_they_registered_is_not_joined_by_vetting(self):
        self._invite(programme_ids=[])
        sponsor = self._register()
        make_programme(organisation=self.org, code='i3-later', is_active=True)
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'approved'})

    def test_an_organisation_less_super_must_name_the_gifts(self):
        r = self._invite(self.super, programme_ids=[])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_required')
        self.assertFalse(Invitation.objects.filter(email=EMAIL).exists())


class TestOneGiftIsUnchanged(_Case):
    def test_one_named_gift_writes_the_row_and_the_mirror(self):
        self._invite(programme_ids=[self.b.id])
        inv = self._inv()
        self.assertEqual(inv.programme_id, self.b.id)
        self.assertEqual(list(inv.gift_rows.values_list('programme_id', flat=True)), [self.b.id])
        self.assertEqual(self._memberships(self._register()), {'i3-b': 'pending'})

    def test_the_old_programme_id_still_works(self):
        r = self._invite(programme_id=self.a.id)
        self.assertIn(r.status_code, (201, 502), r.content)
        self.assertEqual(self._inv().programme_id, self.a.id)
        self.assertEqual(self._memberships(self._register()), {'i3-a': 'pending'})

    def test_nothing_named_with_one_active_gift_files_them_into_it(self):
        Programme.objects.filter(pk=self.b.pk).update(is_active=False)
        self._invite()
        self.assertEqual(self._inv().programme_id, self.a.id)
        self.assertEqual(self._memberships(self._register()), {'i3-a': 'pending'})

    def test_nothing_named_with_two_active_gifts_still_asks(self):
        r = self._invite()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_required')

    def test_an_invitation_written_before_0205_with_only_the_mirror_still_counts(self):
        Invitation.objects.create(audience='sponsor', email=EMAIL, organisation=self.org,
                                  programme=self.b, code='i3-legacy')
        self.assertEqual(self._memberships(self._register()), {'i3-b': 'pending'})


class TestTheStrangerAndTheDowngrade(_Case):
    def test_a_stranger_with_two_active_gifts_joins_nothing(self):
        sponsor = self._register(uid='i3-stranger', email='stranger@example.com')
        self.assertEqual(self._memberships(sponsor), {})

    def test_registration_never_downgrades_an_existing_membership(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        sponsor = Sponsor.objects.create(supabase_user_id='i3-giver', name='Test Giver',
                                         email=EMAIL, status='pending')
        SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=self.a,
                                                  status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=self.b,
                                                  status='suspended')
        self._register()                               # the completion path, account pending
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'suspended'})


class TestTheInviteForm(_Case):
    def test_a_resend_keeps_the_gifts(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        r = self._invite()                              # the waiting row's Resend: no gift sent
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertEqual(sorted(inv.gift_rows.values_list('programme_id', flat=True)),
                         sorted([self.a.id, self.b.id]))
        self.assertEqual(Invitation.objects.filter(email=EMAIL).count(), 1)

    def test_a_resend_of_every_gift_keeps_every_gift(self):
        self._invite(programme_ids=[])
        self._invite()
        self.assertTrue(self._inv().every_gift)

    def test_a_re_invite_that_names_gifts_replaces_them(self):
        self._invite(programme_ids=[])
        self._invite(programme_ids=[self.a.id])
        inv = self._inv()
        self.assertFalse(inv.every_gift)
        self.assertEqual(inv.programme_id, self.a.id)

    def test_another_organisations_gift_is_refused_and_nothing_is_stored(self):
        r = self._invite(programme_ids=[self.a.id, self.theirs.id])
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Invitation.objects.filter(email=EMAIL).exists())

    def test_an_inactive_gift_or_a_junk_id_is_refused(self):
        closed = make_programme(organisation=self.org, code='i3-closed', is_active=False)
        for ids in ([closed.id], ['x'], [True], [0]):
            self.assertEqual(self._invite(programme_ids=ids).status_code, 404, ids)
        self.assertEqual(self._invite(programme_ids='1').status_code, 400)

    def test_a_super_may_not_span_two_organisations(self):
        r = self._invite(self.super, programme_ids=[self.a.id, self.theirs.id])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'gifts_span_organisations')

    def test_the_waiting_row_lists_the_gifts(self):
        self._invite(programme_ids=[self.b.id, self.a.id])
        row = authed_client(self.org_admin).get(f'{INVITE}?kind=sponsors').json()['invitations'][0]
        self.assertEqual([g['code'] for g in row['gifts']], ['i3-a', 'i3-b'])
        self.assertFalse(row['every_gift'])
        self.assertEqual(row['programme_name'], '')     # one-gift field: blank for several

        self._invite(programme_ids=[])
        row = authed_client(self.org_admin).get(f'{INVITE}?kind=sponsors').json()['invitations'][0]
        self.assertEqual((row['gifts'], row['every_gift']), ([], True))

        self._invite(programme_ids=[self.a.id])
        row = authed_client(self.org_admin).get(f'{INVITE}?kind=sponsors').json()['invitations'][0]
        self.assertEqual((row['programme'], row['programme_name']), ('i3-a', 'Gift A'))


class TestTheBackfill(_Case):
    def test_each_sponsor_invitation_with_a_gift_gets_one_row(self):
        named = Invitation.objects.create(audience='sponsor', email='one@example.com',
                                          organisation=self.org, programme=self.a, code='i3-bf1')
        withdrawn = Invitation.objects.create(
            audience='sponsor', email='two@example.com', organisation=self.org,
            programme=self.b, code='i3-bf2', revoked_at=timezone.now())
        Invitation.objects.create(audience='sponsor', email='three@example.com',
                                  organisation=self.org, code='i3-bf3')          # none named
        Invitation.objects.create(audience='staff', email='four@example.com', role='reviewer',
                                  organisation=self.org, programme=self.a, code='i3-bf4')
        migration = import_module('apps.scholarship.migrations.0205_invitation_gifts')
        migration.copy_one_gift_into_rows(django_apps, None)
        migration.copy_one_gift_into_rows(django_apps, None)       # re-runnable
        self.assertEqual(
            sorted(InvitationGift.objects.values_list('invitation_id', 'programme_id')),
            sorted([(named.id, self.a.id), (withdrawn.id, self.b.id)]))
