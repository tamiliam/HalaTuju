"""Common profile S1 (2026-10-31) — `GET admin/me/`, and the reviewer profile following `review`.

`admin/me/` is the one payload the common Profile page reads about the signed-in person, for every
role and a source user alike: its own row, nothing else, and no write. The reviewer profile
(`admin/reviewer-profile/`) is now gated on the `review` PERMISSION, not the Reviewer role (owner
ruling 2026-10-31); the first-sign-in hold stays Reviewer-role only, pinned at the foot.
"""
from django.test import TestCase, override_settings

from apps.scholarship.models import ProgrammeReferralSource, ReviewerProfile
from apps.scholarship.reviewer_onboarding import reviewer_profile_complete
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme, make_source,
)

ME = '/api/v1/admin/me/'
RP = '/api/v1/admin/reviewer-profile/'
KEYS = {'id', 'name', 'email', 'role', 'is_super', 'organisation', 'source', 'referral_partner',
        'programmes', 'permissions', 'first_seen_at', 'last_seen_at'}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminMe(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(name='BrightPath')
        cls.gift = make_programme(organisation=cls.org, code='flag', name_en='Flagship',
                                  name_ta='முதன்மை')
        cls.other_gift = make_programme(organisation=cls.org, code='sabah', name_en='Sabah')

    def test_requires_an_admin(self):
        self.assertEqual(authed_client('nobody-uid').get(ME).status_code, 403)

    def test_a_reviewer_reads_its_own_row_and_resolved_permissions(self):
        me = make_admin('reviewer', owning_org=self.org, name='Priya')
        make_admin('reviewer', owning_org=self.org, name='Somebody else')
        data = authed_client(me).get(ME).json()
        self.assertEqual(set(data), KEYS)
        self.assertEqual((data['id'], data['name'], data['email']), (me.pk, 'Priya', me.email))
        self.assertEqual((data['role'], data['is_super']), ('reviewer', False))
        self.assertEqual(data['organisation'], {'id': self.org.pk, 'name': 'BrightPath'})
        self.assertIsNone(data['source'])
        self.assertIsNone(data['referral_partner'])
        self.assertEqual(data['programmes'], 'all')
        self.assertEqual(data['permissions'], ['review'])

    def test_a_custom_set_is_served_resolved(self):
        me = make_admin('admin', owning_org=self.org, permissions=['review', 'see_all', 'bogus'])
        self.assertEqual(authed_client(me).get(ME).json()['permissions'], ['review', 'see_all'])

    def test_one_gift_binding_names_the_gift_in_the_asked_language(self):
        me = make_admin('reviewer', owning_org=self.org, programme=self.gift)
        self.assertEqual(authed_client(me).get(ME + '?lang=ta').json()['programmes'],
                         [{'id': self.gift.pk, 'code': 'flag', 'name': 'முதன்மை'}])
        # A blank translation falls back to English; an unknown language is English.
        me.programme = self.other_gift
        me.save(update_fields=['programme'])
        self.assertEqual(authed_client(me).get(ME + '?lang=xx').json()['programmes'][0]['name'],
                         'Sabah')

    def test_a_super(self):
        me = make_admin('super', super_admin=True)
        data = authed_client(me).get(ME).json()
        self.assertEqual((data['role'], data['is_super'], data['programmes']), ('super', True, 'all'))
        self.assertIsNone(data['organisation'])

    def test_a_legacy_super_flag_reads_as_super(self):
        me = make_admin('reviewer', super_admin=True)
        self.assertEqual(authed_client(me).get(ME).json()['role'], 'super')

    def test_a_referral_partner(self):
        referrer = make_org(name='CUMIG')
        me = make_admin('partner', org=referrer)
        data = authed_client(me).get(ME).json()
        self.assertEqual(data['referral_partner'], {'name': 'CUMIG'})
        self.assertEqual((data['programmes'], data['permissions']), ([], []))

    def test_a_source_user_is_opted_in_and_sees_only_its_own_gifts(self):
        source = make_source(organisation=self.org, name='MUETMyWay')
        ProgrammeReferralSource.objects.create(programme=self.gift, source=source)
        me = make_admin('source_partner', owning_org=self.org, source=source)
        resp = authed_client(me).get(ME)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['role'], 'source_partner')
        self.assertEqual(data['source'], {'id': source.pk, 'name': 'MUETMyWay'})
        self.assertEqual(data['permissions'], [])
        self.assertEqual([p['code'] for p in data['programmes']], ['flag'])

    def test_sign_in_stamps_are_served(self):
        me = make_admin('reviewer', owning_org=self.org)
        authed_client(me).get('/api/v1/admin/role/')      # the console's sign-in stamp
        me.refresh_from_db()
        data = authed_client(me).get(ME).json()
        self.assertIsNotNone(me.last_seen_at)
        self.assertTrue(data['last_seen_at'] and data['first_seen_at'])

    def test_it_writes_nothing(self):
        me = make_admin('reviewer', owning_org=self.org)
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(authed_client(me), method)(ME, {}, format='json').status_code,
                             405, method)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReviewerProfileFollowsTheReviewPermission(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def test_an_admin_given_review_may_read_and_save_the_reviewer_cards(self):
        me = make_admin('admin', owning_org=self.org,
                        permissions=['review', 'see_all', 'spending', 'payments_prepare'])
        client = authed_client(me)
        self.assertEqual(client.get(RP).status_code, 200)
        resp = client.patch(RP, {'phone': '012-345 6789', 'paused': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=me).phone, '012-345 6789')
        me.refresh_from_db()
        self.assertTrue(me.is_paused)

    def test_a_preset_admin_without_review_is_refused(self):
        me = make_admin('admin', owning_org=self.org)
        self.assertEqual(authed_client(me).get(RP).status_code, 403)
        self.assertFalse(ReviewerProfile.objects.filter(partner_admin=me).exists())

    def test_a_reviewer_who_lost_review_is_refused_and_keeps_the_row(self):
        me = make_admin('reviewer', owning_org=self.org)
        ReviewerProfile.objects.create(partner_admin=me, phone='012-000 0000')
        me.permissions = []
        me.save(update_fields=['permissions'])
        self.assertEqual(authed_client(me).get(RP).status_code, 403)
        self.assertEqual(authed_client(me).patch(RP, {'phone': '1'}, format='json').status_code, 403)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=me).phone, '012-000 0000')

    def test_a_preset_reviewer_still_passes(self):
        me = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(authed_client(me).get(RP).status_code, 200)

    def test_a_super_still_passes_as_under_the_role_check(self):
        me = make_admin('super', super_admin=True)
        self.assertEqual(authed_client(me).get(RP).status_code, 200)

    def test_a_source_user_is_refused(self):
        me = make_admin('source_partner', owning_org=self.org)
        self.assertEqual(authed_client(me).get(RP).status_code, 403)
        self.assertEqual(authed_client(me).patch(RP, {}, format='json').status_code, 403)

    def test_the_first_sign_in_hold_stays_reviewer_role_only(self):
        """⚠ PINNED ON PURPOSE (owner ruling 2026-10-31): `review` widens the CARDS, never the
        hold. An org admin or admin given `review` with an empty profile is never held; a Reviewer
        with an empty profile still is."""
        for role in ('admin', 'qc', 'finance'):
            held = make_admin(role, owning_org=self.org, permissions=['review'])
            self.assertTrue(reviewer_profile_complete(held), role)
        self.assertTrue(reviewer_profile_complete(make_admin('org_admin', owning_org=self.org)))
        self.assertFalse(reviewer_profile_complete(make_admin('reviewer', owning_org=self.org)))
        role = authed_client(make_admin('admin', owning_org=self.org, permissions=['review'])
                             ).get('/api/v1/admin/role/').json()
        self.assertIs(role['reviewer_profile_complete'], True)
