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
from apps.scholarship import sponsor_signup
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

    def test_an_invitation_written_before_0207_with_only_the_mirror_still_counts(self):
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
        migration = import_module('apps.scholarship.migrations.0207_invitation_gifts')
        migration.copy_one_gift_into_rows(django_apps, None)
        migration.copy_one_gift_into_rows(django_apps, None)       # re-runnable
        self.assertEqual(
            sorted(InvitationGift.objects.values_list('invitation_id', 'programme_id')),
            sorted([(named.id, self.a.id), (withdrawn.id, self.b.id)]))


class TestTheI3Review(_Case):
    """The adversarial review of I3 (2026-11-08): four findings, each pinned here."""

    # Finding 1 — another organisation's waiting invitation is not theirs to resend.
    def test_another_organisations_bare_invite_is_a_fresh_choice_not_a_resend(self):
        self._invite(programme_ids=[])                          # org A: Every gift, waiting
        other_admin = make_admin('org_admin', owning_org=self.other, uid='i3-other-oa')
        r = self._invite(other_admin)                           # org B: no gift field at all
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertEqual(inv.organisation_id, self.other.id)    # B takes the row over (kept)
        self.assertFalse(inv.every_gift)                        # A's Every gift does not survive
        self.assertIsNone(inv.every_gift_resolved_at)
        self.assertEqual(list(inv.gift_rows.values_list('programme_id', flat=True)),
                         [self.theirs.id])                      # B's sole active gift
        self.assertEqual(self._memberships(self._register()), {'i3-theirs': 'pending'})

    def test_another_organisation_with_two_gifts_is_asked_and_A_rows_never_move(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        make_programme(organisation=self.other, code='i3-theirs-2', is_active=True)
        other_admin = make_admin('org_admin', owning_org=self.other, uid='i3-other-oa2')
        r = self._invite(other_admin)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'programme_required')
        self.assertEqual(sorted(p['code'] for p in r.data['programmes']),
                         ['i3-theirs', 'i3-theirs-2'])
        inv = self._inv()
        self.assertEqual(inv.organisation_id, self.org.id)
        self.assertEqual(sorted(inv.gift_rows.values_list('programme_id', flat=True)),
                         sorted([self.a.id, self.b.id]))

    def test_a_named_re_invite_from_another_organisation_replaces_every_row(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        other_admin = make_admin('org_admin', owning_org=self.other, uid='i3-other-oa3')
        self._invite(other_admin, programme_ids=[self.theirs.id])
        inv = self._inv()
        self.assertEqual(list(inv.gift_rows.values_list('programme_id', flat=True)),
                         [self.theirs.id])
        self.assertEqual(inv.programme_id, self.theirs.id)

    # Finding 2 — Every gift resolves exactly once, even to none.
    def test_every_gift_with_no_gift_open_at_registration_stays_empty_for_good(self):
        self._invite(programme_ids=[])
        Programme.objects.filter(organisation=self.org).update(is_active=False)
        sponsor = self._register()
        self.assertEqual(self._memberships(sponsor), {})
        inv = self._inv()
        self.assertIsNotNone(inv.every_gift_resolved_at)       # resolved: to none
        self.assertFalse(inv.gift_rows.exists())
        # Two gifts open afterwards. Vetting reads the frozen answer, on every click.
        Programme.objects.filter(pk__in=[self.a.pk, self.b.pk]).update(is_active=True)
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {})
        self._review(sponsor, 'approve')                        # a repeated click
        self.assertEqual(self._memberships(sponsor), {})
        self.assertEqual(sponsor_signup.signup_programmes_for(sponsor), [])
        self.assertFalse(self._inv().gift_rows.exists())

    def test_a_gift_opened_after_an_empty_registration_is_never_joined_by_any_approve(self):
        self._invite(programme_ids=[])
        Programme.objects.filter(organisation=self.org).update(is_active=False)
        sponsor = self._register()                              # resolved to NO gift
        Programme.objects.filter(pk=self.a.pk).update(is_active=True)
        self._review(sponsor, 'approve')
        make_programme(organisation=self.org, code='i3-later-2', is_active=True)
        self._review(sponsor, 'approve')                        # a second click, another gift open
        self.assertEqual(self._memberships(sponsor), {})

    def test_an_every_gift_invitation_never_frozen_is_frozen_once_at_vetting(self):
        """Registered under the old image during a rollback: no rows, no stamp."""
        self._invite(programme_ids=[])
        sponsor = Sponsor.objects.create(supabase_user_id='i3-rollback', name='Test Giver',
                                         email=EMAIL, status='pending')
        self.assertIsNone(self._inv().every_gift_resolved_at)
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'approved'})
        self.assertIsNotNone(self._inv().every_gift_resolved_at)
        make_programme(organisation=self.org, code='i3-later-3', is_active=True)
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'approved'})

    # Finding 3 — account vetting never changes a REJECTED gift membership.
    def test_a_gift_rejected_by_hand_stays_rejected_when_the_account_is_re_vetted(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        sponsor = self._register()
        self._review(sponsor, 'approve')
        sponsorship.set_programme_membership(sponsor, self.b, 'rejected', vetted_by='x@example.com')
        self._review(sponsor, 'approve')                        # a re-click
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'rejected'})
        self._review(sponsor, 'suspend')                        # the cascade still suspends...
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'suspended', 'i3-b': 'rejected'})
        self._review(sponsor, 'approve')                        # ...and reinstates, but not B
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'rejected'})

    def test_a_rejected_account_gets_its_gifts_back_when_approved(self):
        """I3 second review: a rejection the ACCOUNT cascaded is not the organisation's refusal."""
        self._invite(programme_ids=[self.a.id, self.b.id])
        sponsor = self._register()
        self._review(sponsor, 'reject')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'rejected', 'i3-b': 'rejected'})
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'approved', 'i3-b': 'approved'})

    def test_a_hand_rejected_gift_holds_while_the_other_follows_the_account(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        sponsor = self._register()
        self._review(sponsor, 'approve')
        sponsorship.set_programme_membership(sponsor, self.a, 'rejected', vetted_by='x@example.com')
        self._review(sponsor, 'reject')
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'rejected', 'i3-b': 'approved'})

    def test_a_hand_rejection_undone_by_hand_follows_the_account_again(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        sponsor = self._register()
        self._review(sponsor, 'approve')
        sponsorship.set_programme_membership(sponsor, self.a, 'rejected', vetted_by='x@example.com')
        self.assertIsNotNone(SponsorProgrammeMembership.objects.get(
            sponsor=sponsor, programme=self.a).rejected_by_hand_at)
        sponsor.refresh_from_db()                               # the account is approved now
        sponsorship.set_programme_membership(sponsor, self.a, 'approved', vetted_by='x@example.com')
        self.assertIsNone(SponsorProgrammeMembership.objects.get(
            sponsor=sponsor, programme=self.a).rejected_by_hand_at)
        self._review(sponsor, 'suspend')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'suspended', 'i3-b': 'suspended'})

    def test_a_hand_rejection_of_a_cascaded_rejection_is_stamped(self):
        self._invite(programme_ids=[self.a.id])
        sponsor = self._register()
        self._review(sponsor, 'reject')                         # cascaded, unstamped
        sponsorship.set_programme_membership(sponsor, self.a, 'rejected', vetted_by='x@example.com')
        self._review(sponsor, 'approve')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'rejected'})

    # Finding 4 — a super with an organisation names only that organisation's gifts.
    def test_a_super_in_an_organisation_names_only_its_gifts(self):
        org_super = make_admin('super', super_admin=True, owning_org=self.org, uid='i3-org-super')
        r = self._invite(org_super, programme_ids=[self.theirs.id])
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Invitation.objects.filter(email=EMAIL).exists())
        offered = authed_client(org_super).get(f'{INVITE}?kind=sponsors').json()['programmes']
        self.assertEqual([p['code'] for p in offered], ['i3-a', 'i3-b'])
        # The organisation-less super keeps every tenant's.
        offered = authed_client(self.super).get(f'{INVITE}?kind=sponsors').json()['programmes']
        self.assertIn('i3-theirs', [p['code'] for p in offered])

    # I3 second review — ANY super's bare invite on a waiting row is a resend (the web's Resend).
    def _org_super_resend(self):
        self._invite(programme_ids=[self.a.id, self.b.id])      # org A's row, two gifts
        org_super = make_admin('super', super_admin=True, owning_org=self.other,
                               uid='i3-other-super')
        r = self._invite(org_super)                              # bare POST, as Resend sends
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertEqual(inv.organisation_id, self.org.id)
        self.assertEqual(sorted(inv.gift_rows.values_list('programme_id', flat=True)),
                         sorted([self.a.id, self.b.id]))
        self.assertEqual(Invitation.objects.filter(email=EMAIL).count(), 1)

    def test_a_super_resend_on_another_organisations_row_changes_nothing_two_gifts(self):
        make_programme(organisation=self.other, code='i3-theirs-3', is_active=True)
        self._org_super_resend()

    def test_a_super_resend_on_another_organisations_row_changes_nothing_one_gift(self):
        self._org_super_resend()                                 # their org has ONE active gift


class TestTheI3ThirdReview(_Case):
    """The third review of I3 (2026-11-08): the stamp backfill, the waiting row's organisation, the lock."""

    def _account(self, uid, status):
        return Sponsor.objects.create(supabase_user_id=uid, name='Test Giver',
                                      email=f'{uid}@example.com', status=status)

    def _member(self, sponsor, status, **extra):
        return SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=self.a,
                                                         status=status, **extra)

    # 1 — every existing hand rejection is stamped by 0207, so vetting never re-approves it.
    def test_the_backfill_stamps_a_rejection_on_an_account_that_is_not_rejected(self):
        then = timezone.now() - timezone.timedelta(days=3)
        earlier = timezone.now() - timezone.timedelta(days=9)
        dated = self._member(self._account('i3-bf-dated', 'approved'), 'rejected', vetted_at=then)
        undated = self._member(self._account('i3-bf-undated', 'suspended'), 'rejected')
        cascaded = self._member(self._account('i3-bf-cascaded', 'rejected'), 'rejected', vetted_at=then)
        accepted = self._member(self._account('i3-bf-accepted', 'approved'), 'approved', vetted_at=then)
        stamped = self._member(self._account('i3-bf-stamped', 'approved'), 'rejected',
                               vetted_at=then, rejected_by_hand_at=earlier)
        migration = import_module('apps.scholarship.migrations.0207_invitation_gifts')
        migration.stamp_hand_rejections(django_apps, None)
        first = {m.pk: m.rejected_by_hand_at for m in SponsorProgrammeMembership.objects.all()}
        migration.stamp_hand_rejections(django_apps, None)       # re-runnable: changes nothing
        again = {m.pk: m.rejected_by_hand_at for m in SponsorProgrammeMembership.objects.all()}
        self.assertEqual(first, again)
        self.assertEqual(first[dated.pk], then)
        self.assertIsNotNone(first[undated.pk])
        self.assertIsNone(first[cascaded.pk])                    # reads as cascaded
        self.assertIsNone(first[accepted.pk])
        self.assertEqual(first[stamped.pk], earlier)              # never re-stamped
        # The money side: reinstating the account leaves the backfilled refusal alone.
        sponsor = undated.sponsor
        sponsor.status = 'approved'
        sponsor.save(update_fields=['status'])
        sponsorship.sync_account_membership(sponsor, self.a, vetted_by='x@example.com')
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'rejected'})

    # 2 — an organisation-less super's gifts must be the waiting row's organisation's.
    def test_an_orgless_super_cannot_file_another_organisations_gift_on_a_waiting_row(self):
        self._invite(programme_ids=[self.a.id, self.b.id])      # org A's row
        for body in ({'programme_ids': [self.theirs.id]}, {'programme_id': self.theirs.id}):
            r = self._invite(self.super, **body)
            self.assertEqual(r.status_code, 400, r.content)
            self.assertEqual(r.json()['code'], 'gift_not_in_invitation_org')
        inv = self._inv()
        self.assertEqual(inv.organisation_id, self.org.id)
        self.assertEqual(sorted(inv.gift_rows.values_list('programme_id', flat=True)),
                         sorted([self.a.id, self.b.id]))

    def test_an_orgless_super_may_correct_the_gifts_within_the_rows_organisation(self):
        self._invite(programme_ids=[self.a.id, self.b.id])
        r = self._invite(self.super, programme_ids=[self.b.id])
        self.assertIn(r.status_code, (201, 502), r.content)
        inv = self._inv()
        self.assertEqual(inv.organisation_id, self.org.id)
        self.assertEqual(list(inv.gift_rows.values_list('programme_id', flat=True)), [self.b.id])

    def test_an_orgless_super_on_a_new_row_keeps_the_one_organisation_rule(self):
        r = self._invite(self.super, programme_ids=[self.theirs.id])
        self.assertIn(r.status_code, (201, 502), r.content)
        r = self._invite(self.super, email='other.giver@example.com',
                         programme_ids=[self.a.id, self.theirs.id])
        self.assertEqual(r.json()['code'], 'gifts_span_organisations')

    # 3 — both membership writers read the row FOR UPDATE (SQLite drops the clause, so pin the call).
    def test_both_membership_writers_lock_the_row(self):
        from unittest import mock
        from django.db.models import QuerySet
        sponsor = self._account('i3-lock', 'approved')
        self._member(sponsor, 'approved')
        real = QuerySet.select_for_update
        with mock.patch.object(QuerySet, 'select_for_update', autospec=True,
                               side_effect=real) as lock:
            sponsorship.set_programme_membership(sponsor, self.a, 'rejected', vetted_by='x@example.com')
            sponsorship.sync_account_membership(sponsor, self.a, vetted_by='x@example.com')
        self.assertEqual([c.args[0].model for c in lock.call_args_list],
                         [SponsorProgrammeMembership, SponsorProgrammeMembership])
        self.assertEqual(self._memberships(sponsor), {'i3-a': 'rejected'})
