"""B40 Phase E/F (F4) — sponsor referral / invitation.

Service + endpoint coverage: invite creation (+ email + idempotency), attribution
on register via the ref code, the 60-day PDPA purge, and the approved-sponsor gate.
"""
from datetime import timedelta

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import referrals
from apps.scholarship.models import Sponsor, SponsorReferral

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid, email=''):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _sponsor(uid='inviter', status='approved', email='inviter@x.org'):
    return Sponsor.objects.create(supabase_user_id=uid, name='Aisha', email=email, status=status)


class TestReferralService(TestCase):
    def test_create_records_and_emails(self):
        inviter = _sponsor()
        ref = referrals.create_referral(inviter, invitee_email='Friend@Example.com',
                                        invitee_name='Ben', note='Join me!')
        self.assertEqual(ref.status, 'invited')
        self.assertEqual(ref.invitee_email, 'friend@example.com')   # normalised
        self.assertTrue(ref.code)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(ref.code, mail.outbox[0].body)                # the ?ref= link

    def test_bad_email_rejected(self):
        inviter = _sponsor()
        for bad in ('', 'not-an-email', 'a@b'):
            with self.assertRaises(referrals.ReferralError) as ctx:
                referrals.create_referral(inviter, invitee_email=bad)
            self.assertEqual(ctx.exception.code, 'bad_email')

    def test_duplicate_pending_is_idempotent(self):
        inviter = _sponsor()
        a = referrals.create_referral(inviter, invitee_email='dup@x.org')
        mail.outbox.clear()
        b = referrals.create_referral(inviter, invitee_email='dup@x.org')
        self.assertEqual(a.id, b.id)                                # no second row
        self.assertEqual(len(mail.outbox), 0)                       # no second email
        self.assertEqual(inviter.referrals_sent.count(), 1)

    def test_attribute_on_join(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='new@x.org')
        joiner = _sponsor('joiner', status='pending', email='new@x.org')
        out = referrals.attribute_referral(ref.code, joiner)
        self.assertIsNotNone(out)
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')
        self.assertEqual(ref.registered_sponsor_id, joiner.id)
        self.assertIsNotNone(ref.joined_at)

    def test_attribute_self_referral_noop(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='x@x.org')
        self.assertIsNone(referrals.attribute_referral(ref.code, inviter))   # can't refer yourself
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'invited')

    def test_attribute_unknown_code_noop(self):
        joiner = _sponsor('j')
        self.assertIsNone(referrals.attribute_referral('nope', joiner))

    def test_purge_scrubs_old_pii_only(self):
        inviter = _sponsor()
        old = referrals.create_referral(inviter, invitee_email='old@x.org', invitee_name='Old')
        recent = referrals.create_referral(inviter, invitee_email='recent@x.org')
        # age `old` past the window
        SponsorReferral.objects.filter(id=old.id).update(
            created_at=timezone.now() - timedelta(days=referrals.RETENTION_DAYS + 1))
        purged = referrals.purge_expired_referrals()
        self.assertEqual(purged, 1)
        old.refresh_from_db(); recent.refresh_from_db()
        self.assertEqual(old.status, 'expired')
        self.assertEqual(old.invitee_email, '')
        self.assertEqual(old.invitee_name, '')
        self.assertEqual(recent.status, 'invited')      # within window, untouched
        self.assertEqual(recent.invitee_email, 'recent@x.org')

    def test_purge_leaves_joined_alone(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='j@x.org')
        joiner = _sponsor('joiner', email='j@x.org')
        referrals.attribute_referral(ref.code, joiner)
        SponsorReferral.objects.filter(id=ref.id).update(
            created_at=timezone.now() - timedelta(days=referrals.RETENTION_DAYS + 5))
        self.assertEqual(referrals.purge_expired_referrals(), 0)   # joined never purged
        ref.refresh_from_db()
        self.assertEqual(ref.invitee_email, 'j@x.org')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReferralEndpoints(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_create_and_list(self):
        _sponsor('a1', status='approved')
        self._auth('a1')
        r = self.client.post('/api/v1/sponsor/referrals/',
                             {'invitee_email': 'pal@x.org', 'note': 'Come help!'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['status'], 'invited')
        r2 = self.client.get('/api/v1/sponsor/referrals/')
        self.assertEqual(len(r2.json()['referrals']), 1)

    def test_non_approved_403(self):
        _sponsor('p1', status='pending')
        self._auth('p1')
        r = self.client.post('/api/v1/sponsor/referrals/', {'invitee_email': 'x@x.org'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_bad_email_400(self):
        _sponsor('a2', status='approved')
        self._auth('a2')
        r = self.client.post('/api/v1/sponsor/referrals/', {'invitee_email': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_email')

    def test_register_with_ref_attributes(self):
        inviter = _sponsor('inv', status='approved')
        ref = referrals.create_referral(inviter, invitee_email='lead@x.org')
        self._auth('newbie')
        r = self.client.post('/api/v1/sponsor/register/', {
            'name': 'Newbie', 'phone': '0123', 'source': 'friend',
            'consent': True, 'ref': ref.code,
        }, format='json')
        self.assertEqual(r.status_code, 201)
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')
        self.assertEqual(ref.registered_sponsor.supabase_user_id, 'newbie')
