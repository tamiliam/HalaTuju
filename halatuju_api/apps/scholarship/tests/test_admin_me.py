"""Common profile S1 (2026-10-31) — `GET admin/me/`, and the reviewer profile following `review`.

`admin/me/` is the one payload the common Profile page reads about the signed-in person, for every
role and a source user alike: its own row, nothing else, and no write. The reviewer profile
(`admin/reviewer-profile/`) is now gated on the `review` PERMISSION, not the Reviewer role (owner
ruling 2026-10-31); the first-sign-in hold stays Reviewer-role only, pinned at the foot.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship.models import ProgrammeReferralSource, ReviewerProfile
from apps.scholarship.reviewer_onboarding import reviewer_profile_complete
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme, make_source,
)

ME = '/api/v1/admin/me/'
RP = '/api/v1/admin/reviewer-profile/'
KEYS = {'id', 'name', 'email', 'role', 'is_super', 'organisation', 'source', 'referral_partner',
        'programmes', 'permissions', 'first_seen_at', 'last_seen_at',
        # Common profile S2: the person's own card.
        'job_title', 'about', 'phone', 'share_phone_with_team', 'share_phone_with_students',
        'photo_url'}


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

    def test_it_takes_no_post_put_or_delete(self):
        # PATCH writes the card since S2 (`test_staff_profile_card.py`); nothing else is served.
        me = make_admin('reviewer', owning_org=self.org)
        for method in ('post', 'put', 'delete'):
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
        resp = client.patch(RP, {'university': 'Universiti Malaya', 'paused': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=me).university, 'Universiti Malaya')
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


class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code, self._body, self.text = status_code, body or {}, ''

    def json(self):
        return self._body


PW = '/api/v1/admin/me/password/'
SUPA = dict(SUPABASE_URL='https://supa.test', SUPABASE_SERVICE_ROLE_KEY='service-key')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, **SUPA)
class TestOwnPasswordChange(TestCase):
    """`POST admin/me/password/` — the Sign-in card's change, checked by the CURRENT password."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()                      # the throttle counts in the cache
        self.me = make_admin('reviewer', owning_org=make_org(), uid='me-uid', email='me@example.test')
        self.account = {'id': 'me-uid', 'email': 'me@example.test',
                        'app_metadata': {'providers': ['email']}}
        patcher = mock.patch('apps.courses.supabase_admin.http_requests')
        self.http = patcher.start()
        self.addCleanup(patcher.stop)
        self.http.get.return_value = _Resp(200, self.account)
        self.http.post.return_value = _Resp(200, {'access_token': 'check-session'})
        self.http.put.return_value = _Resp(200, {'id': 'me-uid'})

    def _post(self, body, admin=None):
        return authed_client(admin or self.me).post(PW, body, format='json')

    def _grant_calls(self):
        return [c for c in self.http.post.call_args_list if 'grant_type=password' in c.args[0]]

    def test_the_right_current_password_sets_the_new_one_on_the_callers_own_account(self):
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        self.assertEqual((resp.status_code, resp.json()), (200, {'ok': True, 'others_signed_out': True}))
        self.assertEqual(self._grant_calls()[0].kwargs['json'],
                         {'email': 'me@example.test', 'password': 'old-secret'})
        self.assertEqual(self.http.put.call_args.args[0], 'https://supa.test/auth/v1/admin/users/me-uid')
        # The password ONLY: no metadata, so `must_change_password` and its clock are untouched.
        self.assertEqual(self.http.put.call_args.kwargs['json'], {'password': 'new-secret-1'})
        # The check's own session is signed out (scope=local), with the CHECK session's token.
        local = [c for c in self.http.post.call_args_list if 'logout?scope=local' in c.args[0]]
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0].kwargs['headers']['Authorization'], 'Bearer check-session')

    def test_review_m2_every_other_session_ends_with_the_callers_own_token(self):
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        others = [c for c in self.http.post.call_args_list if 'logout?scope=others' in c.args[0]]
        self.assertEqual(len(others), 1)
        # The caller's OWN bearer token (this tab keeps its session: scope=others, not global).
        self.assertEqual(others[0].kwargs['headers']['Authorization'],
                         authed_client(self.me)._credentials['HTTP_AUTHORIZATION'])
        self.assertIs(resp.json()['others_signed_out'], True)

    def test_review_m2_a_failed_sign_out_of_the_others_is_said_not_hidden(self):
        def post(url, **kw):
            if 'scope=others' in url:
                return _Resp(500)
            return _Resp(200, {'access_token': 'check-session'})
        self.http.post.side_effect = post
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        self.assertEqual(resp.status_code, 200)               # the password IS changed
        self.assertIs(resp.json()['others_signed_out'], False)

    def test_review_h1_a_temporary_password_still_owed_is_cleared_in_the_same_write(self):
        from apps.courses import password_change_flag
        self.account['app_metadata'] = {'providers': ['email'], 'must_change_password': True,
                                        'temp_password_issued_at': '2026-10-30T00:00:00+00:00'}
        self.account['user_metadata'] = {'name': 'Me', 'must_change_password': True}
        self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        self.assertEqual(self.http.put.call_count, 1)                         # ONE write
        body = self.http.put.call_args.kwargs['json']
        self.assertEqual(body['password'], 'new-secret-1')
        self.assertEqual(body['app_metadata'], password_change_flag.cleared_fields())
        self.assertEqual(body['user_metadata'],
                         password_change_flag.scrubbed_user_metadata(self.account['user_metadata']))

    def test_a_wrong_current_password_is_400_and_nothing_is_set(self):
        self.http.post.return_value = _Resp(400, {'error': 'invalid_grant'})
        resp = self._post({'current_password': 'guess', 'new_password': 'new-secret-1'})
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'wrong_current_password'))
        self.assertEqual(set(resp.json()), {'error', 'code'})       # nothing said about the account
        self.http.put.assert_not_called()

    def test_newer_gotrue_wrong_password_code_is_also_a_wrong_password(self):
        self.http.post.return_value = _Resp(400, {'error_code': 'invalid_credentials'})
        resp = self._post({'current_password': 'guess', 'new_password': 'new-secret-1'})
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'wrong_current_password'))
        self.http.put.assert_not_called()

    def test_a_captcha_refusal_is_503_never_a_wrong_password(self):
        """Lead check before deploy: if the project's Auth captcha guards the password grant, the
        check cannot run — the person must not be told their (right) password is wrong."""
        self.http.post.return_value = _Resp(400, {'error_code': 'captcha_failed'})
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        self.assertEqual((resp.status_code, resp.json()['error']), (503, 'supabase_unavailable'))
        self.http.put.assert_not_called()

    def test_an_email_or_user_id_in_the_body_is_ignored(self):
        make_admin('reviewer', uid='victim-uid', email='victim@example.test')
        self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1',
                    'email': 'victim@example.test', 'user_id': 'victim-uid'})
        self.assertEqual(self.http.get.call_args.args[0], 'https://supa.test/auth/v1/admin/users/me-uid')
        self.assertEqual(self._grant_calls()[0].kwargs['json']['email'], 'me@example.test')
        self.assertTrue(self.http.put.call_args.args[0].endswith('/me-uid'))

    def test_the_shared_minimum_length_and_same_password_rules(self):
        from apps.courses.supabase_admin import MIN_PASSWORD_LENGTH
        short = 'x' * (MIN_PASSWORD_LENGTH - 1)
        self.assertEqual(self._post({'current_password': 'old', 'new_password': short}).json()['error'],
                         'password_too_short')
        self.assertEqual(self._post({'current_password': 'same-secret', 'new_password': 'same-secret'}
                                    ).json()['error'], 'same_password')
        self.assertEqual(self._post({'new_password': 'new-secret-1'}).json()['error'],
                         'current_password_required')
        self.http.get.assert_not_called()
        self.http.post.assert_not_called()

    def test_a_password_the_project_policy_refuses_is_400_weak_password(self):
        self.http.put.return_value = _Resp(422, {'error_code': 'weak_password'})
        resp = self._post({'current_password': 'old-secret', 'new_password': 'aaaaaaaa'})
        self.assertEqual((resp.status_code, resp.json()['error']), (400, 'weak_password'))

    def test_a_google_only_account_has_no_password_to_change(self):
        self.account['app_metadata'] = {'providers': ['google']}
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
        self.assertEqual(resp.json()['error'], 'no_password_sign_in')
        self.http.post.assert_not_called()

    def test_supabase_down_is_503_never_500(self):
        cases = [
            ('get', Exception('down'), None),           # the account cannot be read
            ('post', Exception('down'), None),          # the password grant cannot be made
            ('post', None, _Resp(500)),                 # the grant answers oddly
            ('put', Exception('down'), None),           # the new password cannot be written
        ]
        for method, raises, answer in cases:
            self.http.reset_mock(return_value=False, side_effect=True)
            self.http.get.return_value = _Resp(200, self.account)
            self.http.post.return_value = _Resp(200, {'access_token': 'check-session'})
            self.http.put.return_value = _Resp(200, {'id': 'me-uid'})
            fn = getattr(self.http, method)
            if raises:
                fn.side_effect = raises
            else:
                fn.return_value = answer
            resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'})
            self.assertEqual((resp.status_code, resp.json()['error']), (503, 'supabase_unavailable'),
                             method)
            self.assertNotIn('Traceback', resp.content.decode())

    def test_the_sixth_attempt_in_fifteen_minutes_is_429_and_never_reaches_supabase(self):
        self.http.post.return_value = _Resp(400, {'error': 'invalid_grant'})
        body = {'current_password': 'g', 'new_password': 'new-secret-1'}
        for _ in range(5):
            self.assertEqual(self._post(body).status_code, 400)
        grants = len(self._grant_calls())
        resp = self._post(body)
        self.assertEqual((resp.status_code, resp.json()['error']), (429, 'too_many_attempts'))
        self.assertEqual(len(self._grant_calls()), grants)                  # refused BEFORE the check
        # Per person: somebody else is not held by my attempts.
        other = make_admin('reviewer', uid='other-uid')
        self.assertEqual(self._post(body, admin=other).status_code, 400)

    def test_review_m3_the_attempt_slots_are_claimed_with_add_and_free_themselves(self):
        from django.core.cache import cache
        from apps.courses import supabase_admin
        self.assertEqual([supabase_admin.take_password_attempt('edge') for _ in range(6)],
                         [True] * 5 + [False])
        cache.delete('pwchange:edge:2')                                    # one slot's window ends
        self.assertEqual([supabase_admin.take_password_attempt('edge') for _ in range(2)], [True, False])
        with mock.patch('django.core.cache.cache.add', return_value=False) as add:
            self.assertFalse(supabase_admin.take_password_attempt('someone'))   # every insert lost
        self.assertEqual(add.call_count, supabase_admin.PASSWORD_ATTEMPTS)
        self.assertEqual(add.call_args.args[2], 15 * 60)

    def test_a_source_user_may_change_its_own_password(self):
        source_user = make_admin('source_partner', uid='src-uid', email='src@example.test')
        self.http.get.return_value = _Resp(200, {**self.account, 'id': 'src-uid', 'email': 'src@example.test'})
        resp = self._post({'current_password': 'old-secret', 'new_password': 'new-secret-1'},
                          admin=source_user)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.http.put.call_args.args[0].endswith('/src-uid'))

    def test_a_non_admin_is_refused_before_supabase_is_asked(self):
        resp = authed_client('stranger-uid').post(
            PW, {'current_password': 'a', 'new_password': 'new-secret-1'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.http.get.assert_not_called()

    def test_a_body_that_is_not_an_object_is_a_400_not_a_500(self):
        resp = authed_client(self.me).post(PW, ['x'], format='json')
        self.assertEqual(resp.status_code, 400)

    def test_get_is_not_served(self):
        self.assertEqual(authed_client(self.me).get(PW).status_code, 405)
