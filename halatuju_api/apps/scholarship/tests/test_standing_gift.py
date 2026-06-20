"""R6 — AutoSponsor (StandingGift): matching + allocation + the config endpoint.

A standing gift auto-funds matching pool students from the sponsor's balance, each
via fund_student → an OFFERED sponsorship (no real money moves). Event-driven via an
hourly run; idempotent + balance-throttled (skip silently when low).
"""
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import standing_gift
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, Sponsorship, StandingGift,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'


def _token(uid, email='x@x.com'):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _fundable_app(cohort, *, suffix='1', award=Decimal('3000'), state='Kedah', field='Engineering'):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'stu-{suffix}', name='Zxq Student', nric=ADULT_NRIC,
        preferred_state=state, exam_type='spm', grades={'bm': 'A'},
        contact_email='student@secret.example', contact_phone='012-7776666')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='accepted', award_amount=award,
        field_of_study=field, notify_email='student@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='spon-1', status='approved', donate=Decimal('10000')):
    s = Sponsor.objects.create(
        supabase_user_id=uid, name='Jane Sponsor', email='jane@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status=status)
    if donate:
        Donation.objects.create(sponsor=s, amount=donate)
    return s


def _gift(sponsor, **kw):
    return StandingGift.objects.create(sponsor=sponsor, **kw)


@override_settings(SPONSOR_POOL_ENABLED=True)
class TestStandingGiftAllocation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_funds_a_matching_student(self):
        s = _sponsor()
        _gift(s)  # any field/state, no cap
        app = _fundable_app(self.cohort)
        result = standing_gift.run_standing_gifts()
        self.assertEqual(result['funded'], 1)
        sp = app.sponsorships.get()
        self.assertEqual(sp.status, 'offered')
        self.assertEqual(sp.sponsor_id, s.id)
        self.assertEqual(sp.amount, Decimal('3000'))

    def test_idempotent_second_run_does_not_refund(self):
        _gift(_sponsor())
        self._app = _fundable_app(self.cohort)
        standing_gift.run_standing_gifts()
        second = standing_gift.run_standing_gifts()
        self.assertEqual(second['funded'], 0)
        self.assertEqual(Sponsorship.objects.count(), 1)

    def test_low_balance_skips_silently(self):
        s = _sponsor(donate=Decimal('1000'))  # < 3000 award
        _gift(s)
        _fundable_app(self.cohort)
        result = standing_gift.run_standing_gifts()
        self.assertEqual(result['funded'], 0)
        self.assertEqual(Sponsorship.objects.count(), 0)

    def test_field_pref_filters(self):
        s = _sponsor()
        _gift(s, field_pref='Medicine')           # student is Engineering
        _fundable_app(self.cohort, field='Engineering')
        self.assertEqual(standing_gift.run_standing_gifts()['funded'], 0)

    def test_state_pref_filters(self):
        s = _sponsor()
        _gift(s, state_pref='Selangor')            # student is Kedah
        _fundable_app(self.cohort, state='Kedah')
        self.assertEqual(standing_gift.run_standing_gifts()['funded'], 0)

    def test_max_amount_cap_filters(self):
        s = _sponsor()
        _gift(s, max_amount=Decimal('2000'))       # award is 3000
        _fundable_app(self.cohort, award=Decimal('3000'))
        self.assertEqual(standing_gift.run_standing_gifts()['funded'], 0)

    def test_inactive_gift_does_nothing(self):
        _gift(_sponsor(), active=False)
        _fundable_app(self.cohort)
        self.assertEqual(standing_gift.run_standing_gifts()['funded'], 0)

    def test_fair_spread_least_recently_allocated_first(self):
        s1 = _sponsor('s1'); s2 = _sponsor('s2')
        g1 = _gift(s1); _gift(s2)
        # g1 already allocated recently → g2 (never allocated) should win the next.
        g1.last_allocated_at = timezone.now(); g1.save(update_fields=['last_allocated_at'])
        _fundable_app(self.cohort)
        standing_gift.run_standing_gifts()
        self.assertEqual(Sponsorship.objects.get().sponsor_id, s2.id)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_inert_when_flag_off(self):
        _gift(_sponsor())
        _fundable_app(self.cohort)
        self.assertEqual(standing_gift.run_standing_gifts(), {'students': 0, 'funded': 0})
        self.assertEqual(Sponsorship.objects.count(), 0)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestStandingGiftEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        _sponsor('spon-ok')
        _sponsor('spon-pending', status='pending')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_get_unconfigured_then_put_upsert(self):
        self._auth('spon-ok')
        r = self.client.get('/api/v1/sponsor/standing-gift/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['configured'])
        # upsert
        p = self.client.put('/api/v1/sponsor/standing-gift/',
                            {'field_pref': 'Engineering', 'max_amount': '5000', 'active': True},
                            format='json')
        self.assertEqual(p.status_code, 200, p.content)
        body = p.json()
        self.assertTrue(body['configured'])
        self.assertEqual(body['field_pref'], 'Engineering')
        self.assertEqual(StandingGift.objects.count(), 1)
        # a second PUT updates the same row (no duplicate)
        self.client.put('/api/v1/sponsor/standing-gift/', {'active': False}, format='json')
        self.assertEqual(StandingGift.objects.count(), 1)

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_bad_max_amount_rejected(self):
        self._auth('spon-ok')
        r = self.client.put('/api/v1/sponsor/standing-gift/', {'max_amount': '-5'}, format='json')
        self.assertEqual(r.status_code, 400)

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/standing-gift/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/standing-gift/').status_code, 404)
