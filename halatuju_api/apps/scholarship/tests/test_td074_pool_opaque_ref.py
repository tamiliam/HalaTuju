"""TD-074 — the sponsor pool detail, fund and my-students routes are keyed by the opaque ``ref``.

Before: ``/sponsor/pool/<raw application id>/`` (and ``.../fund/``, ``/sponsor/my-students/<id>/``),
with the raw id also on every pool card. After: the card carries only ``ref`` (S-XXXXXX), and the
server resolves a ref ONLY inside what the caller may already see — the display pool narrowed by
their programme fence, or their own sponsorships. So:

* the owner opens their own student by ref;
* another sponsor who knows (or computes) that ref gets the same 404 as a ref that never existed;
* an old raw-id link is a 404 — never a redirect, never someone else's student.
"""
from decimal import Decimal
from unittest import mock

import jwt
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import pool
from apps.scholarship.models import (
    Consent, Donation, Programme, ScholarshipApplication, ScholarshipCohort, Sponsor,
    SponsorProfile, SponsorProgrammeMembership, Sponsorship,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
NOT_FOUND = {'error': 'not_found'}


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
                       'email': f'{uid}@example.com', 'is_anonymous': False},
                      TEST_JWT_SECRET, algorithm='HS256')


def _pool_app(programme, org, *, code, uid):
    cohort = ScholarshipCohort.objects.create(
        code=code, name='Intake', year=2026, owning_organisation=org, programme=programme)
    profile = StudentProfile.objects.create(supabase_user_id=uid, name='Pooled Student')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, award_amount=Decimal('3000'), status='recommended')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.',
                                  anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors',
                           version='e', is_active=True)
    return app


def _sponsor(uid, programme):
    s = Sponsor.objects.create(
        supabase_user_id=uid, name='Funder', email=f'{uid}@example.com', phone='0123',
        source='friend', consent_at=timezone.now(), status='approved')
    SponsorProgrammeMembership.objects.create(sponsor=s, programme=programme, status='approved')
    return s


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SPONSOR_POOL_ENABLED=True)
class TestPoolIsKeyedByOpaqueRef(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='td074-org', name='TD074 Org')
        cls.gift_a = Programme.objects.create(organisation=cls.org, code='td074-a', name_en='A')
        cls.gift_b = Programme.objects.create(organisation=cls.org, code='td074-b', name_en='B')
        cls.owner = _sponsor('td074-owner', cls.gift_a)
        cls.outsider = _sponsor('td074-outsider', cls.gift_b)
        cls.app = _pool_app(cls.gift_a, cls.org, code='td074-c1', uid='td074-s1')
        cls.ref = pool.pool_ref(cls.app.id)

    def _as(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    # ── the card ──────────────────────────────────────────────────────────────────────────────
    def test_the_card_carries_the_ref_and_no_raw_id(self):
        students = self._as('td074-owner').get('/api/v1/sponsor/pool/').json()['students']
        self.assertEqual([s['ref'] for s in students], [self.ref])
        self.assertNotIn('id', students[0])

    # ── the owner ─────────────────────────────────────────────────────────────────────────────
    def test_the_owner_opens_their_own_student_by_ref(self):
        r = self._as('td074-owner').get(f'/api/v1/sponsor/pool/{self.ref}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['ref'], self.ref)
        self.assertNotIn('id', r.json())

    def test_the_ref_is_case_insensitive_for_the_email_link(self):
        r = self._as('td074-owner').get(f'/api/v1/sponsor/pool/{self.ref.lower()}/')
        self.assertEqual(r.status_code, 200, r.content)

    def test_the_owner_funds_by_ref(self):
        Donation.objects.create(sponsor=self.owner, amount=Decimal('5000'), programme=self.gift_a)
        r = self._as('td074-owner').post(f'/api/v1/sponsor/pool/{self.ref}/fund/', {},
                                         format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Sponsorship.objects.filter(sponsor=self.owner,
                                                    application=self.app).count(), 1)

    # ── another sponsor, guessing ─────────────────────────────────────────────────────────────
    def test_another_sponsor_with_the_ref_gets_the_same_404_as_a_ref_that_never_existed(self):
        c = self._as('td074-outsider')
        known = c.get(f'/api/v1/sponsor/pool/{self.ref}/')
        never = c.get('/api/v1/sponsor/pool/S-000000/')
        self.assertEqual(known.status_code, 404)
        self.assertEqual(known.json(), NOT_FOUND)
        self.assertEqual((never.status_code, never.json()), (known.status_code, known.json()))

    def test_another_sponsor_cannot_fund_by_ref(self):
        Donation.objects.create(sponsor=self.outsider, amount=Decimal('5000'),
                                programme=self.gift_b)
        r = self._as('td074-outsider').post(f'/api/v1/sponsor/pool/{self.ref}/fund/', {},
                                            format='json')
        self.assertEqual((r.status_code, r.json()), (404, NOT_FOUND))
        self.assertEqual(Sponsorship.objects.count(), 0)

    # ── old raw-id links ──────────────────────────────────────────────────────────────────────
    def test_a_raw_id_no_longer_opens_the_detail_even_for_the_owner(self):
        r = self._as('td074-owner').get(f'/api/v1/sponsor/pool/{self.app.id}/')
        self.assertEqual((r.status_code, r.json()), (404, NOT_FOUND))

    def test_a_raw_id_no_longer_funds(self):
        Donation.objects.create(sponsor=self.owner, amount=Decimal('5000'), programme=self.gift_a)
        r = self._as('td074-owner').post(f'/api/v1/sponsor/pool/{self.app.id}/fund/', {},
                                         format='json')
        self.assertEqual((r.status_code, r.json()), (404, NOT_FOUND))
        self.assertEqual(Sponsorship.objects.count(), 0)

    def test_malformed_refs_are_404(self):
        c = self._as('td074-owner')
        for bad in ('S-12345', 'S-1234567', 'X-ABCDEF', 'S-GHIJKL', self.ref + 'A', '0'):
            with self.subTest(bad=bad):
                r = c.get(f'/api/v1/sponsor/pool/{bad}/')
                self.assertEqual((r.status_code, r.json()), (404, NOT_FOUND))

    def test_the_count_route_is_not_swallowed_by_the_ref_route(self):
        r = APIClient().get('/api/v1/sponsor/pool/count/')
        self.assertEqual(r.status_code, 200, r.content)

    # ── my-students ───────────────────────────────────────────────────────────────────────────
    def test_my_students_is_keyed_by_ref_and_fenced_to_own_sponsorships(self):
        Sponsorship.objects.create(sponsor=self.owner, application=self.app,
                                   amount=Decimal('3000'), status='active')
        owner, outsider = self._as('td074-owner'), self._as('td074-outsider')
        ok = owner.get(f'/api/v1/sponsor/my-students/{self.ref}/')
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()['student']['ref'], self.ref)
        self.assertNotIn('id', ok.json()['student'])
        # the raw application id is dead, even for the owner
        raw = owner.get(f'/api/v1/sponsor/my-students/{self.app.id}/')
        self.assertEqual((raw.status_code, raw.json()), (404, NOT_FOUND))
        # another sponsor with the exact ref: not theirs → not found
        other = outsider.get(f'/api/v1/sponsor/my-students/{self.ref}/')
        self.assertEqual((other.status_code, other.json()), (404, NOT_FOUND))


class TestResolveRef(SimpleTestCase):
    def test_resolves_only_inside_the_given_ids(self):
        self.assertEqual(pool.resolve_ref([5, 6, 7], pool.pool_ref(6)), 6)
        self.assertIsNone(pool.resolve_ref([5, 7], pool.pool_ref(6)))

    def test_a_raw_id_or_junk_never_resolves(self):
        self.assertIsNone(pool.resolve_ref([6], '6'))
        self.assertIsNone(pool.resolve_ref([6], ''))
        self.assertIsNone(pool.resolve_ref([6], None))

    def test_a_repeated_id_from_a_join_still_resolves(self):
        self.assertEqual(pool.resolve_ref([6, 6, 6], pool.pool_ref(6)), 6)

    def test_an_ambiguous_ref_resolves_to_nothing(self):
        # A 24-bit collision inside one fenced set: never open or fund either student.
        with mock.patch.object(pool, 'pool_ref', return_value='S-ABCDEF'):
            self.assertIsNone(pool.resolve_ref([1, 2], 'S-ABCDEF'))
            self.assertEqual(pool.resolve_ref([1], 'S-ABCDEF'), 1)
