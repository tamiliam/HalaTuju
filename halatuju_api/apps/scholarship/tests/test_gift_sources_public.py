"""Per-gift referral sources, Sprint 2 (owner, 2026-10-08) — what the STUDENT sees and may send.

1. **The public intake** (`GET /api/v1/scholarship/intake/?programme=<code>`) serves `sources`:
   `[{code, name}]` for the gift `programme_code` names — that gift's switched-on links whose
   source is still active — and `[]` whenever no gift can be named (unknown, closed, inactive,
   ambiguous). Read by a truly ANONYMOUS client. Gift B never shows gift A's links, and nothing
   but code and name leaves: a contact person, email and phone are planted and must stay out.
2. **The submit** refuses a `referral_source` the gift does not offer (400
   `referral_source_not_offered`) and writes nothing; blank, the three fixed choices and an
   offered source are accepted, and only an offered source ever links `referred_by_org` (never a
   tenant).
3. **The legacy codes migration** (courses 0077): `pushparani` / `govind` → `other`.
"""
from importlib import import_module

from django.apps import apps as live_apps
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship.models import ProgrammeReferralSource, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_cohort, make_org, make_programme,
    make_shortlistable_student, make_student,
)

INTAKE = '/api/v1/scholarship/intake/'
APPLY = '/api/v1/scholarship/applications/'
SENTINELS = ('ZZ-contact-person-9431', 'zz-sentinel-9431@example.test', '0199431943')


def _source(code, name, show=True, active=True):
    return PartnerOrganisation.objects.create(
        code=code, name=name, show_in_apply=show, is_active=active,
        contact_person=SENTINELS[0], contact_email=SENTINELS[1], phone=SENTINELS[2])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _TwoGifts(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org('gp-org')
        cls.gift_a = make_programme(organisation=cls.org, code='gp-a', is_active=True)
        cls.gift_b = make_programme(organisation=cls.org, code='gp-b', is_active=True)
        cls.round_a = make_cohort(programme=cls.gift_a, code='gp-a-2026', is_open=True, is_active=True)
        cls.round_b = make_cohort(programme=cls.gift_b, code='gp-b-2026', is_open=True, is_active=True)
        cls.smc = _source('smc', 'Sri Murugan Centre')
        cls.cumig = _source('cumig', 'Concerned UM Indian Graduates')
        cls.tara = _source('tara', 'Tara Foundation', show=False)       # switched off in Sources
        ProgrammeReferralSource.objects.create(programme=cls.gift_a, source=cls.smc)
        ProgrammeReferralSource.objects.create(programme=cls.gift_a, source=cls.cumig)
        ProgrammeReferralSource.objects.create(programme=cls.gift_a, source=cls.tara)
        ProgrammeReferralSource.objects.create(programme=cls.gift_b, source=cls.cumig)

    def _intake(self, query=''):
        resp = APIClient().get(INTAKE + query)      # no credentials at all
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()


class TestTheIntakeServesTheGiftsSources(_TwoGifts):
    def test_a_gift_lists_its_own_active_sources_by_name(self):
        body = self._intake('?programme=gp-a')
        self.assertEqual(body['programme_code'], 'gp-a')
        # Tara is linked but switched off in Sources: not offered.
        self.assertEqual(body['sources'], [
            {'code': 'cumig', 'name': 'Concerned UM Indian Graduates'},
            {'code': 'smc', 'name': 'Sri Murugan Centre'},
        ])

    def test_gift_b_never_shows_gift_as_links(self):
        self.assertEqual(self._intake('?programme=gp-b')['sources'],
                         [{'code': 'cumig', 'name': 'Concerned UM Indian Graduates'}])

    def test_only_code_and_name_leave_the_server(self):
        body = self._intake('?programme=gp-a')
        self.assertTrue(body['sources'])                      # the sentinel rows ARE in the data
        self.assertEqual({k for s in body['sources'] for k in s}, {'code', 'name'})
        raw = APIClient().get(INTAKE + '?programme=gp-a').content.decode()
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, raw)

    def test_no_nameable_gift_means_no_sources(self):
        # Unknown code; ambiguous bare visit (two rounds open).
        self.assertEqual(self._intake('?programme=nope')['sources'], [])
        bare = self._intake()
        self.assertEqual(bare['choices'] and bare['sources'], [])
        # Closed round.
        self.round_a.is_open = False
        self.round_a.save(update_fields=['is_open'])
        self.assertEqual(self._intake('?programme=gp-a')['sources'], [])

    def test_an_inactive_gift_lists_nothing(self):
        self.gift_b.is_active = False
        self.gift_b.save(update_fields=['is_active'])
        body = self._intake('?programme=gp-b')
        self.assertEqual((body['programme_code'], body['sources']), ('', []))

    def test_a_tenant_is_never_served_even_when_linked(self):
        tenant = _source('gp-tenant', 'A Tenant Org')
        make_admin('org_admin', owning_org=tenant)
        ProgrammeReferralSource.objects.create(programme=self.gift_a, source=tenant)
        codes = [s['code'] for s in self._intake('?programme=gp-a')['sources']]
        self.assertNotIn('gp-tenant', codes)


class TestTheSubmitRefusesAnUnofferedCode(_TwoGifts):
    def setUp(self):
        self.student = make_shortlistable_student()

    def _apply(self, code, programme='gp-a'):
        return authed_client(self.student).post(APPLY, {
            'household_income': 2500, 'receives_str': True, 'consent_to_contact': True,
            'programme_code': programme, 'referral_source': code,
        }, format='json')

    def test_an_offered_source_is_accepted_and_links_the_org(self):
        resp = self._apply('smc')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.student.refresh_from_db()
        self.assertEqual((self.student.referral_source, self.student.referred_by_org_id),
                         ('smc', self.smc.id))

    def test_blank_and_the_three_fixed_choices_are_always_accepted(self):
        for code in ('', 'halatuju', 'social', 'other'):
            with self.subTest(code=code):
                self.student = make_shortlistable_student()
                self.assertEqual(self._apply(code).status_code, 201)

    def test_another_gifts_source_a_switched_off_one_and_a_legacy_code_are_refused(self):
        for code, gift in (('smc', 'gp-b'),            # gift A's source, submitted to gift B
                           ('tara', 'gp-a'),           # linked, but switched off in Sources
                           ('pushparani', 'gp-a'),     # legacy, off every form
                           ('nope', 'gp-a')):
            with self.subTest(code=code, gift=gift):
                resp = self._apply(code, gift)
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertEqual(resp.json()['code'], 'referral_source_not_offered')
                self.assertFalse(ScholarshipApplication.objects.filter(profile=self.student).exists())
                self.student.refresh_from_db()
                self.assertNotEqual(self.student.referral_source, code)
                self.assertIsNone(self.student.referred_by_org_id)

    def test_a_tenant_code_is_never_linked(self):
        """Even if a tenant row were somehow linked to the gift, the submit refuses it and the
        profile never points at the organisation that runs the gift."""
        make_admin('org_admin', owning_org=self.org)
        PartnerOrganisation.objects.filter(pk=self.org.pk).update(show_in_apply=True)
        ProgrammeReferralSource.objects.create(programme=self.gift_a, source=self.org)
        self.assertEqual(self._apply('gp-org').status_code, 400)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.referred_by_org_id)


class TestTheProfileLinkIsOnlyEverAnActiveSource(_TwoGifts):
    """`sync_profile_fields` on its own — the second line behind the view's refusal. A bite-check
    found the submit tests could not see this half: the view refuses a tenant code before the sync
    runs. So the sync is asked directly."""

    def test_only_an_active_non_tenant_source_is_linked(self):
        from apps.scholarship.services import sync_profile_fields
        make_admin('org_admin', owning_org=self.org)                    # gp-org is a tenant
        PartnerOrganisation.objects.filter(pk=self.org.pk).update(show_in_apply=True)
        for code in ('gp-org', 'tara'):                                 # a tenant; a switched-off source
            with self.subTest(code=code):
                student = make_student()
                sync_profile_fields(student, {'referral_source': code})
                student.refresh_from_db()
                self.assertIsNone(student.referred_by_org_id)
        student = make_student()
        sync_profile_fields(student, {'referral_source': 'smc'})
        student.refresh_from_db()
        self.assertEqual(student.referred_by_org_id, self.smc.id)

    def test_a_fixed_choice_never_links_even_if_a_row_carries_its_code(self):
        """Review fix: the Sources POST now refuses a reserved code, but a row from before (or
        written another way) must still never collect the "Other" students."""
        from apps.scholarship.services import sync_profile_fields
        squatter = _source('other', 'A Row Called Other')
        ProgrammeReferralSource.objects.create(programme=self.gift_a, source=squatter)
        student = make_student()
        sync_profile_fields(student, {'referral_source': 'other'})
        student.refresh_from_db()
        self.assertIsNone(student.referred_by_org_id)
        self.assertEqual(student.referral_source, 'other')


class TestTheLegacyCodesMigration(TestCase):
    def test_pushparani_and_govind_move_to_other_and_nothing_else_moves(self):
        mig = import_module('apps.courses.migrations.0077_retire_legacy_referral_codes')
        rows = {code: make_student(referral_source=code)
                for code in ('pushparani', 'govind', 'smc', 'other', 'halatuju')}
        blank = make_student()
        mig.retire_legacy_codes(live_apps, None)
        got = {code: StudentProfile.objects.get(pk=p.pk).referral_source for code, p in rows.items()}
        self.assertEqual(got, {'pushparani': 'other', 'govind': 'other', 'smc': 'smc',
                               'other': 'other', 'halatuju': 'halatuju'})
        self.assertEqual(StudentProfile.objects.get(pk=blank.pk).referral_source,
                         blank.referral_source)
