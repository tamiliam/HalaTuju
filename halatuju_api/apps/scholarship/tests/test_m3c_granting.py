"""Sprint M3c (decisions A9, A12, D1, D3, D5, E2, E5 and the sponsor fence, 2026-11-15): granting.

Done-when:
- An organisation admin gives a team member any key of its own set; `manage_team` stays `lead_tier`, the
  NEVER_GRANTABLE keys stay refused, and a key the giver does not hold is refused `not_held` (A9 / A12).
- A super edits an organisation admin's card (D1): the payment seats are refused `money_by_role` (by role
  until M4), the withdrawal "ask" may be given (E2), `manage_team` stays, the row stays a list. An
  organisation admin may not edit a fellow one, and their own card is read-only to them.
- A new organisation admin's invitation stores the full set (D3).
- A GRANTED team member: give a power and its door opens; take it away and it closes; they can never give
  themselves a key.
- The sponsor fence: a granted team member, of the same organisation or another, may not vet a sponsor
  ACCOUNT or publish the sponsor TERMS (both reach every organisation); they accept a sponsor into their
  own organisation's gift only. Every organisation admin keeps what they had.
- The gift pages (`programmes.edit`): a granted team member reaches their own organisation's gifts only.
- The senior letters open on `scholars.approve` (D5).
- E5 (owner 2026-11-15): whoever may open Invitations reads its Mentor kind, with no actions.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions as sp
from apps.courses import staff_permissions_v2 as v2
from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import surface_gates
from apps.scholarship.models import Sponsor, SponsorProgrammeMembership, StaffPermissionChange
from apps.scholarship.tests.factories import (
    ORG_ADMIN_MIGRATED, TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org,
    make_programme,
)
from apps.scholarship.tests.test_mentors import _Base as _MentorsBase
from apps.scholarship.tests.test_sponsor_terms import _draft

#: Every key an organisation admin may give a team member: its whole set (none is an alias or never
#: grantable — `test_the_set_holds_no_alias_and_nothing_never_grantable`).
LEAD_GIVES = tuple(v2.ORG_ADMIN_SET)
TERMS = '/api/v1/admin/scholarship/sponsor-terms/'
PROGRAMMES = '/api/v1/admin/scholarship/programmes/'
LETTERS = '/api/v1/admin/scholarship/scholars/{}/letters/'


def _url(target):
    return f'/api/v1/admin/admins/{target.pk}/permissions/'


def _patch(who, target, keys):
    return authed_client(who).patch(_url(target), {'permissions': list(keys), 'v2': True}, format='json')


def _stored(a):
    return PartnerAdmin.objects.get(pk=a.pk).permissions


def give(lead, target, *keys):
    r = _patch(lead, target, [*_stored(target), *keys])
    assert r.status_code == 200, r.content[:300]
    return r


def take(lead, target, *keys):
    r = _patch(lead, target, [k for k in _stored(target) if k not in keys])
    assert r.status_code == 200, r.content[:300]
    return r


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _World(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.other_org = make_org(), make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.other_lead = make_admin('org_admin', owning_org=cls.other_org)
        cls.member = make_admin('admin', owning_org=cls.org)
        cls.other_member = make_admin('admin', owning_org=cls.other_org)
        cls.gift = make_programme(organisation=cls.org)
        cls.other_gift = make_programme(organisation=cls.other_org)
        PartnerAdmin.objects.update(first_seen_at=timezone.now())


class TheOrganisationAdminGives(_World):
    def test_the_set_holds_no_alias_and_nothing_never_grantable(self):
        for key in LEAD_GIVES:
            self.assertNotIn(key, v2.ALIAS_V2)
            self.assertNotIn(key, v2.NEVER_GRANTABLE)
        self.assertNotIn('manage_team', LEAD_GIVES)

    def test_each_key_of_its_set_saves_for_a_team_member(self):
        for key in LEAD_GIVES:
            with self.subTest(key=key):
                rev = make_admin('reviewer', owning_org=self.org)
                r = _patch(self.lead, rev, ['review', key])
                self.assertEqual(r.status_code, 200, r.content[:300])
                self.assertIn(key, _stored(rev))

    def test_manage_team_and_the_never_grantable_keys_stay_refused(self):
        rev = make_admin('reviewer', owning_org=self.org)
        for key, code in (('manage_team', 'lead_tier'), ('billing.edit', 'never_grantable'),
                          ('requests.approve', 'never_grantable')):
            with self.subTest(key=key):
                r = _patch(self.lead, rev, ['review', key])
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertIsNone(_stored(rev))
        self.assertFalse(StaffPermissionChange.objects.exists())

    def test_a_key_the_giver_does_not_hold_is_refused_not_held(self):
        # A super took `scholars.approve` from this organisation admin: they can no longer give it.
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(
            permissions=[k for k in ORG_ADMIN_MIGRATED if k != 'scholars.approve'])
        rev = make_admin('reviewer', owning_org=self.org)
        r = _patch(self.lead, rev, ['review', 'scholars.approve'])
        self.assertEqual((r.status_code, r.json()['code'], r.json()['keys']), (403, 'not_held', ['scholars.approve']))
        self.assertIsNone(_stored(rev))
        keys = {k['key']: k for g in authed_client(self.lead).get(_url(rev)).json()['v2_keys'] for k in g['keys']}
        self.assertEqual((keys['scholars.approve']['reason'], keys['scholars.approve']['grantable']),
                         ('not_held', False))
        self.assertEqual((keys['settings.edit']['reason'], keys['settings.edit']['grantable']), (None, True))

    def test_a_new_organisation_admins_invitation_stores_the_full_set(self):
        self.assertEqual(st.invite_permissions('org_admin'), list(v2.ORG_ADMIN_SET))


class TheLeadsOwnCard(_World):
    def test_a_super_edits_an_organisation_admin(self):
        body = authed_client(self.super).get(_url(self.lead)).json()
        self.assertTrue(body['editable'])
        r = _patch(self.super, self.lead, [*_stored(self.lead), 'award_withdraw_request'])   # E2: the "ask"
        self.assertEqual(r.status_code, 200, r.content[:300])
        stored = _stored(self.lead)
        self.assertIsInstance(stored, list)
        self.assertIn('award_withdraw_request', stored)
        self.assertNotIn('manage_team', stored)                    # by role, never stored
        self.assertTrue(PartnerAdmin.objects.get(pk=self.lead.pk).has_perm('manage_team'))
        took = _patch(self.super, self.lead, [k for k in stored if k != 'scholars.approve'])
        self.assertEqual(took.status_code, 200, took.content[:300])
        self.assertNotIn('scholars.approve', _stored(self.lead))

    def test_the_payment_seats_stay_by_role(self):
        before = _stored(self.lead)
        for seat in ('payments_prepare', 'payments_check', 'payments_approve'):
            with self.subTest(seat=seat):
                r = _patch(self.super, self.lead, [*before, seat])
                self.assertEqual((r.status_code, r.json()['code'], r.json()['keys']), (400, 'money_by_role', [seat]))
        self.assertEqual(_stored(self.lead), before)

    def test_an_organisation_admin_may_not_edit_a_fellow_one_nor_their_own_card(self):
        fellow = make_admin('org_admin', owning_org=self.org)
        self.assertEqual(_patch(self.lead, fellow, ['review']).status_code, 404)
        own = authed_client(self.lead).get(_url(self.lead))
        self.assertEqual(own.status_code, 200)
        self.assertFalse(own.json()['editable'])
        before = _stored(self.lead)
        self.assertIn(_patch(self.lead, self.lead, [*before, 'award_withdraw_request']).status_code, (403, 404))
        self.assertEqual(_stored(self.lead), before)
        self.assertFalse(StaffPermissionChange.objects.exists())


class AGrantedTeamMember(_World):
    def test_give_a_power_and_it_opens_take_it_away_and_it_closes(self):
        for door, key in (('settings', 'settings.edit'), ('assign', 'students.edit'),
                          ('decide', 'students.approve'), ('programme_settings', 'programmes.edit'),
                          ('billing_read', 'billing.view'), ('contracts_write', 'contracts.edit'),
                          ('senior_letters', 'scholars.approve'), ('sponsor_vet', 'sponsors.approve')):
            with self.subTest(key=key):
                self.assertFalse(st.opens_door(PartnerAdmin.objects.get(pk=self.member.pk), door))
                give(self.lead, self.member, key)
                self.assertTrue(st.opens_door(PartnerAdmin.objects.get(pk=self.member.pk), door))
                take(self.lead, self.member, key)
                self.assertFalse(st.opens_door(PartnerAdmin.objects.get(pk=self.member.pk), door))

    def test_through_the_endpoint_the_gift_page_opens_and_closes(self):
        self.assertEqual(authed_client(self.member).get(PROGRAMMES).status_code, 403)
        give(self.lead, self.member, 'programmes.edit')
        self.assertEqual(authed_client(self.member).get(PROGRAMMES).status_code, 200)
        take(self.lead, self.member, 'programmes.edit')
        self.assertEqual(authed_client(self.member).get(PROGRAMMES).status_code, 403)

    def test_they_can_never_give_themselves_a_key(self):
        give(self.lead, self.member, *LEAD_GIVES)
        before = _stored(self.member)
        r = _patch(self.member, self.member, ['manage_team', *before])
        self.assertEqual(r.status_code, 403)
        self.assertEqual(_stored(self.member), before)
        rev = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(_patch(self.member, rev, ['review', 'settings.edit']).status_code, 403)   # no manage_team
        self.assertIsNone(_stored(rev))

    def test_manage_team_is_never_theirs(self):
        r = _patch(self.lead, self.member, [*_stored(self.member), 'manage_team'])
        self.assertEqual((r.status_code, r.json()['code']), (400, 'lead_tier'))


class TheSponsorFence(_World):
    """`sponsors.approve` on a team row opens the per-gift acceptance only; the account and the terms
    stay with organisation admins and supers (`surface_gates.may_approve_platform_sponsors`)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sponsor = Sponsor.objects.create(supabase_user_id='m3c-sp', name='Funder', email='funder@example.test',
                                             status='approved')
        cls.pending = Sponsor.objects.create(supabase_user_id='m3c-sp2', name='New', email='new@example.test',
                                             status='pending')

    def setUp(self):
        give(self.lead, self.member, 'sponsors.approve')
        give(self.other_lead, self.other_member, 'sponsors.approve')
        self.member.refresh_from_db()
        self.other_member.refresh_from_db()

    def review(self, who):
        return authed_client(who).post(f'/api/v1/admin/sponsors/{self.pending.pk}/review/', {'action': 'approve'},
                                       format='json')

    def accept(self, who, gift):
        return authed_client(who).post(f'/api/v1/admin/sponsors/{self.sponsor.pk}/membership/',
                                       {'programme_id': gift.pk, 'status': 'approved'}, format='json')

    def test_the_gates(self):
        for who, vets, platform in ((self.member, True, False), (self.other_member, True, False),
                                    (self.lead, True, True), (self.super, True, True)):
            with self.subTest(who=who.role):
                self.assertEqual(surface_gates.may_vet_sponsors(who), vets)
                self.assertEqual(surface_gates.may_approve_platform_sponsors(who), platform)

    def test_a_granted_team_member_may_not_vet_a_sponsor_account(self):
        for who in (self.member, self.other_member):
            with self.subTest(org=who.owning_organisation_id):
                self.assertEqual(self.review(who).status_code, 403)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'pending')
        self.assertEqual(self.review(self.lead).status_code, 200)             # the org admin, unchanged

    def test_a_granted_team_member_may_not_publish_the_sponsor_terms(self):
        give(self.lead, self.member, 'sponsors.edit')                         # the authoring door
        terms = _draft('m3c-terms-1')
        r = authed_client(self.member).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual((r.status_code, r.json()['error']), (403, 'publish_forbidden'))
        r = authed_client(self.lead).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_the_sponsor_list_says_who_may_vet(self):
        give(self.lead, self.member, 'sponsors.view')
        self.assertFalse(authed_client(self.member).get('/api/v1/admin/sponsors/').json()['may_vet'])
        self.assertTrue(authed_client(self.lead).get('/api/v1/admin/sponsors/').json()['may_vet'])

    def test_they_accept_a_sponsor_into_their_own_organisations_gift_only(self):
        self.assertEqual(self.accept(self.member, self.other_gift).status_code, 404)
        self.assertEqual(self.accept(self.other_member, self.gift).status_code, 404)
        self.assertFalse(SponsorProgrammeMembership.objects.exists())
        r = self.accept(self.member, self.gift)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(SponsorProgrammeMembership.objects.get().programme_id, self.gift.pk)


class TheGiftPages(_World):
    def setUp(self):
        give(self.lead, self.member, 'programmes.edit')
        give(self.other_lead, self.other_member, 'programmes.edit')

    def test_the_list_holds_their_own_organisations_gifts_only(self):
        for who, gift, other in ((self.member, self.gift, self.other_gift),
                                 (self.other_member, self.other_gift, self.gift)):
            with self.subTest(org=who.owning_organisation_id):
                ids = {p['id'] for p in authed_client(who).get(PROGRAMMES).json()['programmes']}
                self.assertIn(gift.pk, ids)
                self.assertNotIn(other.pk, ids)

    def test_another_organisations_gift_is_404_and_their_own_saves(self):
        for who, other in ((self.member, self.other_gift), (self.other_member, self.gift)):
            with self.subTest(org=who.owning_organisation_id):
                for url in (f'{PROGRAMMES}{other.pk}/', f'{PROGRAMMES}{other.pk}/years/'):
                    method = 'patch' if url.endswith(f'{other.pk}/') else 'get'
                    r = getattr(authed_client(who), method)(url, {'name_en': 'Taken'}, format='json')
                    self.assertEqual(r.status_code, 404, url)
        other_name = type(self.gift).objects.get(pk=self.other_gift.pk).name_en
        self.assertNotEqual(other_name, 'Taken')
        r = authed_client(self.member).patch(f'{PROGRAMMES}{self.gift.pk}/', {'name_en': 'Renamed'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(type(self.gift).objects.get(pk=self.gift.pk).name_en, 'Renamed')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheSeniorLetters(TestCase):
    def setUp(self):
        self.app = make_application('maintenance', active_at=timezone.now() - datetime.timedelta(days=60),
                                    notify_email='scholar@example.test')
        org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=org)
        self.member = make_admin('admin', owning_org=org)          # holds `scholars`, not the senior letters
        PartnerAdmin.objects.update(first_seen_at=timezone.now())

    def tab(self, who):
        body = authed_client(who).get(LETTERS.format(self.app.id)).json()
        return 'suspension' in body['can_issue'], body['can_withdraw']

    def test_they_open_on_the_key(self):
        self.assertEqual(self.tab(self.lead), (True, True))
        self.assertEqual(self.tab(self.member), (False, False))
        give(self.lead, self.member, 'scholars.approve')
        self.assertEqual(self.tab(self.member), (True, True))
        take(self.lead, self.member, 'scholars.approve')
        self.assertEqual(self.tab(self.member), (False, False))

    def test_an_organisation_admin_without_the_key_loses_them(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(
            permissions=[k for k in ORG_ADMIN_MIGRATED if k != 'scholars.approve'])
        self.assertEqual(self.tab(self.lead), (False, False))


INVITE = '/api/v1/admin/invitations/'


class TheMentorKind(_MentorsBase):
    """E5 (owner 2026-11-15): "if an admin could view invitations, it should be able view mentor as well"."""

    def test_an_invitations_viewer_reads_the_mentor_kind_with_no_actions(self):
        self.invite()
        viewer = make_admin('reviewer', owning_org=self.org, permissions=['review', 'invitations.view', 'team.view'])
        self.assertFalse(st.opens(viewer, 'invitations.edit'))
        body = authed_client(viewer).get(INVITE + '?kind=mentor').json()
        self.assertEqual((len(body['invitations']), body['waiting']['mentor']), (1, 1))
        self.assertEqual([m['manageable'] for m in body['mentors']], [False])

    def test_without_invitations_view_the_page_is_refused(self):
        self.invite()
        # (Any admin page key seats a row at Admins, whose table grants `invitations.view`: a reviewer.)
        other = make_admin('reviewer', owning_org=self.org, permissions=['review'])
        self.assertFalse(st.opens(other, 'invitations.view'))
        self.assertEqual(authed_client(other).get(INVITE + '?kind=mentor').status_code, 403)

    def test_an_admin_role_reads_it_too(self):
        self.invite()
        with patch('apps.courses.supabase_admin.read_auth_user', return_value=None):
            body = authed_client(self.viewer).get(INVITE + '?kind=mentor').json()
        self.assertEqual(body['waiting']['mentor'], 1)
        self.assertEqual([m['manageable'] for m in body['mentors']], [False])

    def test_finance_gets_only_the_tab_fields(self):
        """M3c review F1: the Mentor kind is an ALLOWLIST of what `MentorRoster` reads — never the Mentors
        page's full record (work, scholars, last seen, languages, area, gifts, delete flags)."""
        self.invite()
        finance = make_admin('finance', owning_org=self.org)
        body = authed_client(finance).get(INVITE + '?kind=mentor&all=1').json()
        self.assertEqual(len(body['mentors']), 1)
        self.assertEqual(set(body['mentors'][0]), {'id', 'name', 'email', 'status', 'manageable'})

    def test_a_mentors_reader_gets_the_same_fields(self):
        self.invite()
        body = authed_client(self.lead).get(INVITE + '?kind=mentor&all=1').json()
        self.assertEqual(set(body['mentors'][0]), {'id', 'name', 'email', 'status', 'manageable'})
        self.assertEqual(body['mentors'][0]['manageable'], True)
