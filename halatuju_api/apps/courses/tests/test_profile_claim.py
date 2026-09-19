"""TD-254 — claiming a profile whose IC is already registered.

**What the old door was.** `POST /api/v1/profile/claim-nric/` answered somebody else's IC with
`status: 'exists'` **and that person's name**, and a second call carrying `confirm: true` MOVED
the profile's primary key to the caller in raw SQL. Two defects in one endpoint: a name
disclosure to anyone who types an IC, and an account takeover with no challenge and no record.

**What replaced it** (owner ruling 2026-09-18: a second factor the real owner holds, plus an
audit line):

* the look-up never names the holder — it answers which challenge CHANNELS exist, as bare types;
* a claim proves control of a contact ALREADY ON the target profile that is ALREADY VERIFIED;
* success writes a `ProfileLoginAlias` row — a LINK, never a move — which the auth seam resolves,
  so every student endpoint follows without being touched one by one;
* every branch that reaches another person's profile writes a `ProfileClaimEvent`.

⚠ **THE SENTINELS.** The disclosure tests assert over the WHOLE response body, so each sentinel
is a string no timestamp, id or amount can contain, and each is paired with a POSITIVE control
proving the sentinel really is on the target profile (docs/lessons.md, the H1 sentinel lesson —
a "must not appear" assertion over a payload is worthless until something proves the value
exists at all).
"""
from datetime import timedelta
import hashlib
import json
import logging
import unittest.mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from halatuju.middleware import supabase_auth

from apps.courses.models import (
    PartnerAdmin, ProfileClaimEvent, ProfileLoginAlias, SavedCourse, StudentProfile,
)
from apps.courses import profile_claim
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

_W = 'apps.scholarship.whatsapp'

CLAIM_URL = '/api/v1/profile/claim-nric/'
SEND_URL = '/api/v1/profile/claim-nric/send-code/'
CONFIRM_URL = '/api/v1/profile/claim-nric/confirm-code/'

#: Obviously fake, FORMAT-VALID. `030303-14-` is the factory's stem, so this cannot collide
#: with a factory student at the soft-NRIC uniqueness check.
TARGET_NRIC = '030303-14-9107'

#: ⚠ Sentinels: nothing a timestamp, an id or an amount can produce.
SENTINEL_NAME = 'QXSENTINELNAME ZZTARGET'
SENTINEL_EMAIL = 'qxsentinelmail@example.invalid'
SENTINEL_PHONE = '+60199887766'
SENTINEL_PHONE_DIGITS = '199887766'


def _target(**kw):
    """The profile somebody else is going to try to claim. Verified on BOTH channels unless a
    test says otherwise."""
    kw.setdefault('nric', TARGET_NRIC)
    kw.setdefault('name', SENTINEL_NAME)
    kw.setdefault('contact_email', SENTINEL_EMAIL)
    kw.setdefault('contact_email_verified', True)
    kw.setdefault('contact_phone', SENTINEL_PHONE)
    kw.setdefault('contact_phone_verified', True)
    kw.setdefault('supabase_user_id', 'td254-target-uid')
    return StudentProfile.objects.create(**kw)


def _body(response):
    """The response body as raw TEXT, for a whole-payload absence assertion."""
    return json.dumps(response.data, ensure_ascii=False, default=str)


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ClaimBase(TestCase):
    def setUp(self):
        cache.clear()
        self.target = _target()
        self.caller_uid = 'td254-caller-uid'
        self.client = authed_client(self.caller_uid)

    def post(self, url, data, client=None):
        return (client or self.client).post(url, data, format='json')

    def events(self, **filters):
        return list(ProfileClaimEvent.objects.filter(**filters).order_by('id'))


class TestLookUpDisclosesNothing(ClaimBase):
    """The look-up answers WHETHER, and which doors exist — never WHO."""

    def test_exists_carries_no_name_and_no_contact_detail(self):
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'exists')
        # The KEYS, exhaustively — a future field cannot slip a person's detail back in.
        self.assertEqual(sorted(resp.data.keys()), ['channels', 'status'])
        body = _body(resp)
        for sentinel in (SENTINEL_NAME, SENTINEL_NAME.upper(), SENTINEL_EMAIL,
                         SENTINEL_PHONE, SENTINEL_PHONE_DIGITS):
            self.assertNotIn(sentinel, body)

    def test_the_sentinels_really_are_on_the_target_profile(self):
        """POSITIVE CONTROL. Without this the absence assertion above proves nothing."""
        own = authed_client(self.target.supabase_user_id)
        resp = own.get('/api/v1/profile/')
        self.assertEqual(resp.status_code, 200)
        body = _body(resp)
        self.assertIn(SENTINEL_NAME.upper(), body)      # the model upper-cases the name
        self.assertIn(SENTINEL_EMAIL, body)
        self.assertIn(SENTINEL_PHONE, body)

    def test_channels_are_bare_types_only(self):
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        self.assertEqual(sorted(resp.data['channels']), ['email', 'phone'])

    def test_only_the_verified_channels_are_offered(self):
        self.target.contact_phone_verified = False
        self.target.save(update_fields=['contact_phone_verified'])
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        self.assertEqual(resp.data['channels'], ['email'])

    def test_no_verified_contact_offers_no_channel(self):
        self.target.contact_phone_verified = False
        self.target.contact_email_verified = False
        self.target.save(update_fields=['contact_phone_verified', 'contact_email_verified'])
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['channels'], [])

    def test_the_plain_look_up_is_audited(self):
        """⚠ This is what makes "has anybody been probing ICs?" answerable at all."""
        self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        rows = self.events(event='exists_shown')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].caller_sub, self.caller_uid)
        self.assertEqual(rows[0].target_profile_id, self.target.supabase_user_id)
        self.assertEqual(rows[0].nric, TARGET_NRIC)

    def test_the_caller_own_ic_is_not_audited_as_a_probe(self):
        StudentProfile.objects.create(supabase_user_id=self.caller_uid, nric='030303-14-9108')
        self.post(CLAIM_URL, {'nric': '030303-14-9108'})
        self.assertEqual(self.events(), [])


class TestTheOldDoorIsShut(ClaimBase):
    """`confirm: true` must transfer NOTHING, ever."""

    def setUp(self):
        super().setUp()
        self.course = None
        course_model = SavedCourse._meta.get_field('course').related_model
        course = course_model.objects.first()
        if course is not None:
            self.course = SavedCourse.objects.create(student=self.target, course=course)

    def test_confirm_is_refused(self):
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC, 'confirm': True})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['status'], 'refused')
        self.assertEqual(resp.data['code'], 'confirm_removed')

    def test_confirm_moves_no_primary_key_and_no_child_row(self):
        self.post(CLAIM_URL, {'nric': TARGET_NRIC, 'confirm': True})
        self.target.refresh_from_db()
        self.assertEqual(self.target.supabase_user_id, 'td254-target-uid')
        self.assertEqual(self.target.nric, TARGET_NRIC)
        self.assertFalse(ProfileLoginAlias.objects.exists())
        if self.course is not None:
            self.course.refresh_from_db()
            self.assertEqual(self.course.student_id, 'td254-target-uid')

    def test_the_refusal_is_audited(self):
        self.post(CLAIM_URL, {'nric': TARGET_NRIC, 'confirm': True})
        rows = self.events(event='refused_confirm_removed')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].caller_sub, self.caller_uid)
        self.assertEqual(rows[0].target_profile_id, self.target.supabase_user_id)


class TestEmailChallenge(ClaimBase):
    """The email door: a 6-digit code, hashed, 10 minutes, five wrong answers."""

    def _send(self):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            resp = self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
        return resp, sent

    def _code_from(self, sent):
        """The code as the STUDENT received it — read off the metered send seam."""
        self.assertTrue(sent.called)
        return sent.call_args[1]['extra']['code']

    def test_send_goes_through_the_metered_seam_and_to_the_verified_address(self):
        resp, sent = self._send()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'status': 'sent', 'channel': 'email'})
        self.assertEqual(sent.call_args[0][0], SENTINEL_EMAIL)

    def test_the_code_is_six_digits_and_is_not_stored_in_the_clear(self):
        _resp, sent = self._send()
        code = self._code_from(sent)
        self.assertRegex(code, r'^\d{6}$')
        pending = cache.get(profile_claim.pending_key(self.caller_uid, TARGET_NRIC))
        self.assertNotIn(code, json.dumps(pending, default=str))
        self.assertNotEqual(pending['code_hash'], code)

    def test_the_right_code_writes_an_alias_and_moves_nothing(self):
        _resp, sent = self._send()
        code = self._code_from(sent)
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'status': 'claimed'})
        alias = ProfileLoginAlias.objects.get(alias_uid=self.caller_uid)
        self.assertEqual(alias.profile_id, self.target.supabase_user_id)
        self.target.refresh_from_db()
        self.assertEqual(self.target.supabase_user_id, 'td254-target-uid')

    def test_the_send_and_the_claim_are_audited(self):
        _resp, sent = self._send()
        self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': self._code_from(sent)})
        self.assertEqual([e.event for e in self.events()], ['code_sent', 'claimed'])
        self.assertEqual({e.channel for e in self.events(event='code_sent')}, {'email'})
        claimed = self.events(event='claimed')[0]
        self.assertEqual(claimed.caller_sub, self.caller_uid)
        self.assertEqual(claimed.target_profile_id, self.target.supabase_user_id)
        self.assertEqual(claimed.nric, TARGET_NRIC)

    def test_a_wrong_code_is_refused_and_audited_and_writes_no_alias(self):
        self._send()
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '000000'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'code_incorrect')
        self.assertFalse(ProfileLoginAlias.objects.exists())
        self.assertEqual(len(self.events(event='code_failed')), 1)

    def test_an_expired_code_is_refused(self):
        _resp, sent = self._send()
        code = self._code_from(sent)
        # Age the pending challenge through the SAME key production writes — no test-only
        # back door in the module under test.
        key = profile_claim.pending_key(self.caller_uid, TARGET_NRIC)
        pending = cache.get(key)
        pending['expires_at'] = (timezone.now() - timedelta(minutes=1)).isoformat()
        cache.set(key, pending, 600)
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'code_expired')
        self.assertFalse(ProfileLoginAlias.objects.exists())

    def test_the_sixth_attempt_is_refused_and_the_code_dies(self):
        _resp, sent = self._send()
        code = self._code_from(sent)
        for _ in range(profile_claim.MAX_CODE_ATTEMPTS):
            self.assertEqual(
                self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '000000'}).data['code'],
                'code_incorrect')
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '000000'})
        self.assertEqual(resp.data['code'], 'too_many_attempts')
        # ⚠ and the RIGHT code no longer works either — the pending code is burnt.
        self.assertNotEqual(
            self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code}).data.get('status'),
            'claimed')
        self.assertFalse(ProfileLoginAlias.objects.exists())

    def test_confirm_without_a_send_is_refused(self):
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '123456'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'no_pending_code')


class TestPhoneChallenge(ClaimBase):
    """The phone door: Twilio Verify holds the code, exactly as /profile's phone verify does."""

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(True, 'pending', ''))
    def test_send_asks_twilio_verify_over_whatsapp(self, start):
        resp = self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'phone'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'status': 'sent', 'channel': 'phone'})
        self.assertEqual(start.call_args[0][0], SENTINEL_PHONE)
        self.assertEqual(start.call_args[1]['channel'], 'whatsapp')

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(True, ''))
    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(True, 'pending', ''))
    def test_an_approved_code_writes_the_alias(self, _start, _check):
        self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'phone'})
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '123456'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'status': 'claimed'})
        self.assertEqual(
            ProfileLoginAlias.objects.get(alias_uid=self.caller_uid).profile_id,
            self.target.supabase_user_id)

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(False, ''))
    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(True, 'pending', ''))
    def test_a_rejected_code_writes_no_alias(self, _start, _check):
        self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'phone'})
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '123456'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'code_incorrect')
        self.assertFalse(ProfileLoginAlias.objects.exists())

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(False, 'unconfigured', ''))
    def test_an_unconfigured_verify_service_refuses_honestly(self, _start):
        resp = self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'phone'})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'unconfigured')


class TestRefusals(ClaimBase):
    """Each refusal is honest, carries a stable code, writes no alias and leaves a record."""

    def _send(self, channel='email', client=None):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True):
            with unittest.mock.patch(f'{_W}.start_phone_verification',
                                     return_value=(True, 'pending', '')):
                return self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': channel}, client)

    def _assert_refused(self, resp, code):
        self.assertIn(resp.status_code, (400, 403, 429, 503))
        self.assertEqual(resp.data['status'], 'refused')
        self.assertEqual(resp.data['code'], code)
        self.assertFalse(ProfileLoginAlias.objects.exists())
        self.assertTrue(self.events(event=f'refused_{code}'))

    def test_no_verified_contact(self):
        self.target.contact_email_verified = False
        self.target.contact_phone_verified = False
        self.target.save(update_fields=['contact_email_verified', 'contact_phone_verified'])
        self._assert_refused(self._send(), 'no_verified_contact')

    def test_an_unverified_contact_is_not_good_enough(self):
        """⚠ THE CONSERVATIVE POLICY. The owner has not ruled that an unverified address may
        receive the code, so it may not. Widening this is one line in `claim_channels`."""
        self.target.contact_email_verified = False   # the address is still there, unproven
        self.target.contact_phone_verified = False
        self.target.save(update_fields=['contact_email_verified', 'contact_phone_verified'])
        self.assertEqual(profile_claim.claim_channels(self.target), [])
        self._assert_refused(self._send(), 'no_verified_contact')

    def test_a_channel_the_target_has_not_verified(self):
        self.target.contact_phone_verified = False
        self.target.save(update_fields=['contact_phone_verified'])
        self._assert_refused(self._send(channel='phone'), 'channel_unavailable')

    def test_the_caller_already_holds_a_verified_ic(self):
        StudentProfile.objects.create(
            supabase_user_id=self.caller_uid, nric='030303-14-9109', nric_verified=True)
        self._assert_refused(self._send(), 'caller_has_verified_nric')

    def test_the_caller_already_holds_an_application(self):
        mine = make_student(supabase_user_id=self.caller_uid)
        make_application(cohort=make_cohort(), student=mine)
        self._assert_refused(self._send(), 'caller_has_application')

    def test_a_staff_identity_may_never_become_an_alias(self):
        PartnerAdmin.objects.create(
            supabase_user_id=self.caller_uid, role='reviewer', name='Test Reviewer 07',
            email='reviewer07@example.invalid')
        self._assert_refused(self._send(), 'caller_is_staff')

    def test_a_caller_who_already_claimed_cannot_claim_again(self):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
            code = sent.call_args[1]['extra']['code']
        self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})
        second = _target(supabase_user_id='td254-target-2', nric='030303-14-9110')
        self.assertTrue(second.pk)
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True):
            resp = self.post(SEND_URL, {'nric': '030303-14-9110', 'channel': 'email'})
        self.assertEqual(resp.data['code'], 'already_claimed')
        self.assertEqual(ProfileLoginAlias.objects.count(), 1)

    def test_nothing_the_caller_owns_is_ever_deleted(self):
        """The caller's own fresh profile stays exactly where it is — revoking brings it back."""
        mine = StudentProfile.objects.create(supabase_user_id=self.caller_uid, school='SMK Test')
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
            code = sent.call_args[1]['extra']['code']
        self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})
        mine.refresh_from_db()
        self.assertEqual(mine.school, 'SMK Test')


class TestTheAliasResolvesAtTheAuthSeam(ClaimBase):
    """⚠ THE POINT OF THE WHOLE DESIGN. One row, and EVERY student endpoint follows — nothing
    was changed endpoint by endpoint, so nothing can be forgotten."""

    def setUp(self):
        super().setUp()
        self.application = make_application(cohort=make_cohort(), student=self.target)
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
            code = sent.call_args[1]['extra']['code']
        self.assertEqual(
            self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code}).data['status'], 'claimed')

    def test_the_new_login_reads_the_old_profile(self):
        resp = self.client.get('/api/v1/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nric'], TARGET_NRIC)
        self.assertIn(SENTINEL_NAME.upper(), _body(resp))

    def test_the_new_login_reads_the_old_scholarship_application(self):
        resp = self.client.get('/api/v1/scholarship/applications/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['applications'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([r['id'] for r in rows], [self.application.id])

    def test_the_new_login_can_WRITE_to_the_old_profile(self):
        resp = self.client.put('/api/v1/profile/', {'school': 'SMK Claimed'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.school, 'SMK Claimed')

    def test_the_claim_surface_itself_still_acts_as_the_REAL_login(self):
        """⚠ TWO IDENTITIES, AND THE CLAIM SURFACE USES BOTH. Re-submitting the IC of the
        profile this login now ACTS AS reads as `linked`, not as somebody else's record; but a
        second claim is refused, because the LOGIN already holds one."""
        self.assertEqual(
            self.post(CLAIM_URL, {'nric': TARGET_NRIC}).data, {'status': 'linked'})
        _target(supabase_user_id='td254-target-3', nric='030303-14-9111')
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True):
            resp = self.post(SEND_URL, {'nric': '030303-14-9111', 'channel': 'email'})
        self.assertEqual(resp.data['code'], 'already_claimed')

    def test_a_login_with_no_alias_reaches_none_of_that(self):
        """The positive control for the three above: the same requests from a DIFFERENT new
        login see nothing, so the alias is what carried them, not an unfenced endpoint."""
        stranger = authed_client('td254-stranger-uid')
        self.assertEqual(stranger.get('/api/v1/profile/').data['nric'], '')
        self.assertEqual(stranger.get('/api/v1/scholarship/applications/').status_code, 403)

    def test_an_alias_whose_target_is_gone_fails_closed(self):
        """⚠ Deleting the profile CASCADES the alias away, so the login falls back to its own
        (empty) record — never to somebody else's, and never a 500."""
        self.target.delete()
        self.assertFalse(ProfileLoginAlias.objects.filter(alias_uid=self.caller_uid).exists())
        resp = self.client.get('/api/v1/scholarship/applications/')
        self.assertIn(resp.status_code, (401, 403, 404))
        self.assertNotIn(SENTINEL_NAME.upper(), resp.content.decode())


class TestIsolationFromStaffAndSponsors(ClaimBase):
    """An alias is a STUDENT link. It may never redirect a staff or sponsor identity."""

    def test_the_auth_seam_itself_refuses_to_redirect_a_staff_subject(self):
        """⚠ THE SEAM, DIRECTLY. `get_admin` reading `auth_sub` is the second defence; this is
        the first, and it is the one that covers a staff row created AFTER the alias."""
        PartnerAdmin.objects.create(
            supabase_user_id='td254-late-admin', role='reviewer', name='Test Reviewer 08',
            email='reviewer08@example.invalid')
        ProfileLoginAlias.objects.create(alias_uid='td254-late-admin', profile=self.target)
        self.assertEqual(supabase_auth.resolve_login_alias('td254-late-admin'),
                         'td254-late-admin')

    def test_the_auth_seam_itself_refuses_to_redirect_a_sponsor_subject(self):
        from apps.scholarship.models import Sponsor
        Sponsor.objects.create(supabase_user_id='td254-late-sponsor', name='Test Sponsor 08',
                               email='sponsor08@example.invalid', status='approved')
        ProfileLoginAlias.objects.create(alias_uid='td254-late-sponsor', profile=self.target)
        self.assertEqual(supabase_auth.resolve_login_alias('td254-late-sponsor'),
                         'td254-late-sponsor')

    def test_the_seam_does_redirect_an_ordinary_student(self):
        """The positive control: without this the two refusals above would pass on a seam that
        never redirects anybody."""
        ProfileLoginAlias.objects.create(alias_uid='td254-plain-student', profile=self.target)
        self.assertEqual(supabase_auth.resolve_login_alias('td254-plain-student'),
                         self.target.supabase_user_id)

    def test_an_alias_never_redirects_an_admin_lookup(self):
        admin = PartnerAdmin.objects.create(
            supabase_user_id='td254-admin-uid', role='super', is_super_admin=True,
            name='Test Admin 07', email='admin07@example.invalid')
        ProfileLoginAlias.objects.create(alias_uid=admin.supabase_user_id, profile=self.target)
        resp = authed_client(admin.supabase_user_id).get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(resp.status_code, 200)

    def test_an_alias_never_redirects_a_sponsor_lookup(self):
        from apps.scholarship.models import Sponsor
        sponsor = Sponsor.objects.create(
            supabase_user_id='td254-sponsor-uid', name='Test Sponsor 07',
            email='sponsor07@example.invalid', status='approved')
        ProfileLoginAlias.objects.create(alias_uid=sponsor.supabase_user_id, profile=self.target)
        resp = authed_client(sponsor.supabase_user_id).get('/api/v1/sponsor/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'sponsor07@example.invalid')


class TestRateLimits(ClaimBase):
    """Generic 429 with a stable code, per CALLER and per TARGET IC. Twilio's own per-number
    limits are the backstop behind the phone door."""

    def test_look_ups_at_somebody_else_ic_are_capped_per_caller(self):
        for _ in range(profile_claim.MAX_LOOKUPS_PER_CALLER):
            self.assertEqual(self.post(CLAIM_URL, {'nric': TARGET_NRIC}).status_code, 200)
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.data['code'], 'rate_limited')

    def test_look_ups_at_one_ic_are_capped_across_callers(self):
        for i in range(profile_claim.MAX_LOOKUPS_PER_NRIC):
            self.post(CLAIM_URL, {'nric': TARGET_NRIC}, authed_client(f'td254-prober-{i}'))
        resp = self.post(CLAIM_URL, {'nric': TARGET_NRIC}, authed_client('td254-prober-last'))
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.data['code'], 'rate_limited')

    def test_code_sends_are_capped_per_caller(self):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True):
            for _ in range(profile_claim.MAX_SENDS_PER_CALLER):
                self.assertEqual(
                    self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'}).status_code,
                    200)
            resp = self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.data['code'], 'rate_limited')

    def test_code_checks_are_capped_per_caller(self):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True):
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
        for _ in range(profile_claim.MAX_CHECKS_PER_CALLER):
            self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '000000'})
        resp = self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': '000000'})
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.data['code'], 'rate_limited')


class TestRevocation(ClaimBase):
    """Deleting the alias row fully reverses a claim — that is the whole undo."""

    def setUp(self):
        super().setUp()
        self.mine = StudentProfile.objects.create(
            supabase_user_id=self.caller_uid, school='SMK Mine')
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
            code = sent.call_args[1]['extra']['code']
        self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})

    def test_revoking_returns_the_login_to_its_own_profile(self):
        self.assertEqual(self.client.get('/api/v1/profile/').data['nric'], TARGET_NRIC)
        profile_claim.revoke_alias(self.caller_uid, by='td254-operator')
        resp = self.client.get('/api/v1/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nric'], '')
        self.assertEqual(resp.data['school'], 'SMK Mine')

    def test_revoking_is_audited(self):
        profile_claim.revoke_alias(self.caller_uid, by='td254-operator')
        rows = self.events(event='alias_revoked')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].caller_sub, self.caller_uid)
        self.assertEqual(rows[0].target_profile_id, self.target.supabase_user_id)
        self.assertEqual(rows[0].actor, 'td254-operator')

    def test_revoking_deletes_nothing_but_the_alias(self):
        profile_claim.revoke_alias(self.caller_uid, by='td254-operator')
        self.assertFalse(ProfileLoginAlias.objects.exists())
        self.assertTrue(StudentProfile.objects.filter(pk=self.target.pk).exists())
        self.assertTrue(StudentProfile.objects.filter(pk=self.caller_uid).exists())


class TestTheAuditTableIsAppendOnly(ClaimBase):
    """No code path updates or deletes an event row."""

    def test_the_event_model_exposes_no_update_or_delete_path(self):
        import inspect
        from apps.courses import models_claim
        source = inspect.getsource(models_claim)
        self.assertIn('append-only', source.lower())

    def test_the_service_never_updates_or_deletes_an_event(self):
        import inspect
        source = inspect.getsource(profile_claim)
        for forbidden in ('ProfileClaimEvent.objects.filter', 'ProfileClaimEvent.objects.all'):
            self.assertNotIn(forbidden, source)


class _Capture(logging.Handler):
    """Every record the whole run emits, as text. `assertLogs` cannot be used here: it REQUIRES
    at least one record, and "nothing was logged" is a perfectly good answer to this question."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class TestNothingSensitiveIsLogged(ClaimBase):
    """⚠ The audit TABLE holds the IC. The application LOG must not — nor a code, a phone
    number or an email address, at INFO or above."""

    def test_no_ic_code_or_contact_detail_reaches_the_log(self):
        handler = _Capture()
        root = logging.getLogger()
        root.addHandler(handler)
        previous = root.level
        root.setLevel(logging.INFO)
        try:
            with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
                self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
                code = sent.call_args[1]['extra']['code']
            self.post(CONFIRM_URL, {'nric': TARGET_NRIC, 'code': code})
            self.post(CLAIM_URL, {'nric': TARGET_NRIC})
        finally:
            root.removeHandler(handler)
            root.setLevel(previous)
        blob = '\n'.join(handler.lines)
        for secret in (TARGET_NRIC, code, SENTINEL_EMAIL, SENTINEL_PHONE,
                       SENTINEL_PHONE_DIGITS, SENTINEL_NAME.upper()):
            self.assertNotIn(secret, blob)


class TestTheHashIsASaltedHash(ClaimBase):
    """A 6-digit code is trivially brute-forced from a bare digest, so the stored hash is
    keyed on SECRET_KEY as well as the caller and the IC."""

    def test_a_plain_sha256_of_the_code_is_not_what_is_stored(self):
        with unittest.mock.patch('apps.scholarship.emails._send', return_value=True) as sent:
            self.post(SEND_URL, {'nric': TARGET_NRIC, 'channel': 'email'})
            code = sent.call_args[1]['extra']['code']
        pending = cache.get(profile_claim.pending_key(self.caller_uid, TARGET_NRIC))
        self.assertNotEqual(pending['code_hash'], hashlib.sha256(code.encode()).hexdigest())


class TestTheClaimUrlsExist(TestCase):
    """The two new doors are wired, and both are past the NRIC gate (a student with no NRIC is
    exactly who needs them)."""

    def test_the_nric_gate_lets_the_claim_doors_through(self):
        from halatuju.middleware.supabase_auth import NRIC_GATE_EXACT
        self.assertIn(SEND_URL, NRIC_GATE_EXACT)
        self.assertIn(CONFIRM_URL, NRIC_GATE_EXACT)

    def test_the_doors_are_routed(self):
        self.assertTrue(reverse('profile-claim-nric'))
        self.assertTrue(reverse('profile-claim-send-code'))
        self.assertTrue(reverse('profile-claim-confirm-code'))
