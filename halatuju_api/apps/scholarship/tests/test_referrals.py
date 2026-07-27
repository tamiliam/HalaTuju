"""B40 Phase E/F (F4) — sponsor referral / invitation.

Service + endpoint coverage: invite creation (+ email + idempotency), attribution
on register via the ref code, the 60-day PDPA purge, and the approved-sponsor gate.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import jwt
from django.core import mail
from django.core.management import call_command
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

    # ── attribution by EMAIL (2026-07-28) ────────────────────────────────────────
    # The code path only fires when the invitee clicks the ?ref= link. Most don't: they
    # read the invite, then register on their own — and every one of those invitations
    # sat at "Invited" for ever, so a real conversion read as none.

    def test_attribute_by_email_closes_a_direct_signup(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='Direct@X.org')
        joiner = _sponsor('joiner', status='pending', email='direct@x.org')
        out = referrals.attribute_referral_by_email(joiner)
        self.assertIsNotNone(out)
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')
        self.assertEqual(ref.registered_sponsor_id, joiner.id)
        self.assertIsNotNone(ref.joined_at)

    def test_attribute_by_email_is_case_insensitive(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='mixed@x.org')
        joiner = _sponsor('joiner', status='pending', email='  MiXeD@X.ORG ')
        self.assertIsNotNone(referrals.attribute_referral_by_email(joiner))
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')

    def test_attribute_by_email_never_self_refers(self):
        inviter = _sponsor('inv', email='self@x.org')
        ref = referrals.create_referral(inviter, invitee_email='self@x.org')
        self.assertIsNone(referrals.attribute_referral_by_email(inviter))
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'invited')

    def test_attribute_by_email_oldest_invitation_wins(self):
        """Two sponsors invited the same person — credit the one who introduced them."""
        first = _sponsor('first', email='first@x.org')
        second = _sponsor('second', email='second@x.org')
        early = referrals.create_referral(first, invitee_email='pop@x.org')
        late = referrals.create_referral(second, invitee_email='pop@x.org')
        SponsorReferral.objects.filter(id=early.id).update(
            created_at=timezone.now() - timedelta(days=10))
        joiner = _sponsor('joiner', status='pending', email='pop@x.org')
        referrals.attribute_referral_by_email(joiner)
        early.refresh_from_db(); late.refresh_from_db()
        self.assertEqual(early.status, 'joined')
        self.assertEqual(late.status, 'invited')      # still open, not double-counted

    def test_attribute_by_email_needs_an_email(self):
        inviter = _sponsor('inv')
        referrals.create_referral(inviter, invitee_email='someone@x.org')
        self.assertIsNone(referrals.attribute_referral_by_email(
            _sponsor('joiner', status='pending', email='')))
        self.assertIsNone(referrals.attribute_referral_by_email(None))

    def test_attribute_by_email_ignores_a_closed_row(self):
        inviter = _sponsor('inv')
        ref = referrals.create_referral(inviter, invitee_email='once@x.org')
        joiner = _sponsor('joiner', status='pending', email='once@x.org')
        referrals.attribute_referral_by_email(joiner)
        ref.refresh_from_db()
        first_joined_at = ref.joined_at
        self.assertIsNone(referrals.attribute_referral_by_email(joiner))   # idempotent
        ref.refresh_from_db()
        self.assertEqual(ref.joined_at, first_joined_at)

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

    def _auth(self, uid, email=''):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, email)}')

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

    def test_register_without_ref_attributes_by_email(self):
        """The case the code path missed: they read the invite and signed up directly."""
        inviter = _sponsor('inv', status='approved')
        ref = referrals.create_referral(inviter, invitee_email='lead@x.org')
        self._auth('newbie', 'lead@x.org')
        r = self.client.post('/api/v1/sponsor/register/', {
            'name': 'Newbie', 'phone': '0123', 'source': 'friend', 'consent': True,
        }, format='json')
        self.assertEqual(r.status_code, 201)
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')
        self.assertEqual(ref.registered_sponsor.supabase_user_id, 'newbie')

    def test_register_attributes_the_code_not_the_email(self):
        """Both signals present and disagreeing → the link they actually clicked wins."""
        by_code = _sponsor('a', status='approved', email='a@x.org')
        by_email = _sponsor('b', status='approved', email='b@x.org')
        code_ref = referrals.create_referral(by_code, invitee_email='someone.else@x.org')
        email_ref = referrals.create_referral(by_email, invitee_email='lead@x.org')
        self._auth('newbie', 'lead@x.org')
        r = self.client.post('/api/v1/sponsor/register/', {
            'name': 'Newbie', 'phone': '0123', 'source': 'friend',
            'consent': True, 'ref': code_ref.code,
        }, format='json')
        self.assertEqual(r.status_code, 201)
        code_ref.refresh_from_db(); email_ref.refresh_from_db()
        self.assertEqual(code_ref.status, 'joined')
        self.assertEqual(email_ref.status, 'invited')   # exactly one invitation closed

    def test_register_survives_a_broken_attribution(self):
        """Bookkeeping must never cost someone their registration."""
        _sponsor('inv', status='approved')
        with patch('apps.scholarship.referrals.attribute_referral_by_email',
                   side_effect=RuntimeError('boom')):
            r = self.client.post('/api/v1/sponsor/register/', {
                'name': 'Newbie', 'phone': '0123', 'source': 'friend', 'consent': True,
            }, format='json', HTTP_AUTHORIZATION=f'Bearer {_token("newbie", "x@x.org")}')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Sponsor.objects.filter(supabase_user_id='newbie').exists())


class TestBackfillReferralAttribution(TestCase):
    """The one-off repair for invitations answered before attribution-by-email existed.

    Same matching as the live path plus one guard it does not need: the sponsor must have
    registered AFTER the invitation. At registration that is true by construction; reading
    history it is not, and someone who was already a sponsor is not a conversion.
    """
    def _run(self, apply=False):
        out = StringIO()
        args = ['backfill_referral_attribution'] + (['--apply'] if apply else [])
        call_command(*args, stdout=out)
        return out.getvalue()

    def test_reports_without_writing_then_applies(self):
        inviter = _sponsor('inv', email='inv@x.org')
        ref = referrals.create_referral(inviter, invitee_email='joined@x.org')
        joiner = _sponsor('joiner', status='approved', email='joined@x.org')

        self.assertIn('1 referral(s) would be attributed', self._run())
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'invited')          # report mode wrote nothing

        self.assertIn('1 referral(s) attributed', self._run(apply=True))
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'joined')
        self.assertEqual(ref.registered_sponsor_id, joiner.id)
        # `joined_at` is the sponsor's own registration date, not today — the record has to
        # stay honest about WHEN it happened.
        self.assertEqual(ref.joined_at, joiner.created_at)

    def test_leaves_a_sponsor_who_predates_the_invite(self):
        early = _sponsor('early', status='approved', email='early@x.org')
        Sponsor.objects.filter(id=early.id).update(
            created_at=timezone.now() - timedelta(days=90))
        inviter = _sponsor('inv', email='inv@x.org')
        ref = referrals.create_referral(inviter, invitee_email='early@x.org')

        out = self._run(apply=True)
        self.assertIn('BEFORE the invite', out)
        self.assertIn('0 referral(s) attributed', out)
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'invited')

    def test_leaves_a_self_referral(self):
        inviter = _sponsor('inv', email='inv@x.org')
        ref = referrals.create_referral(inviter, invitee_email='inv@x.org')
        self.assertIn('0 referral(s) attributed', self._run(apply=True))
        ref.refresh_from_db()
        self.assertEqual(ref.status, 'invited')

    def test_is_idempotent(self):
        inviter = _sponsor('inv', email='inv@x.org')
        referrals.create_referral(inviter, invitee_email='joined@x.org')
        _sponsor('joiner', status='approved', email='joined@x.org')
        self._run(apply=True)
        self.assertIn('0 referral(s) attributed', self._run(apply=True))

    def test_ignores_an_invitee_who_never_registered(self):
        inviter = _sponsor('inv', email='inv@x.org')
        referrals.create_referral(inviter, invitee_email='ghost@x.org')
        self.assertIn('0 referral(s) attributed', self._run(apply=True))
