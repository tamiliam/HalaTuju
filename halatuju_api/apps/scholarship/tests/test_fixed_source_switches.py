"""Request #44 (BrightPath, 2026-10-25) — a gift can switch off Facebook / WhatsApp and Halatuju.xyz.

What is pinned here:

1. **Default ON**: an existing gift and a new gift both offer all three fixed choices.
2. **Configuration**: GET lists `fixed_sources` as `{code, on, switchable}`; PUT switches
   `social` / `halatuju` in the same `sources` map, writes only the change, and audits it with the
   existing `programme_source_set` line. `other` is refused (`fixed_source_locked`) and a refusal
   writes nothing. The org fence is unchanged (cross-org 404).
3. **The student**: a switched-off choice leaves that gift's public intake (`fixed_sources`) and
   is REFUSED at submit for that gift only, with the code the form already handles.
4. **Past answers**: an application already holding the code keeps it, and the admin Source
   filter still finds it.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.scholarship import gift_sources
from apps.scholarship.models import Programme, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_shortlistable_student,
)

CONFIG = '/api/v1/admin/scholarship/programme/configuration/'
INTAKE = '/api/v1/scholarship/intake/'
APPLY = '/api/v1/scholarship/applications/'
ADMIN_APPS = '/api/v1/admin/scholarship/applications/'
AUDIT_LOGGER = 'apps.scholarship.views_admin'
ALL_ON = [{'code': 'halatuju', 'on': True, 'switchable': True},
          {'code': 'social', 'on': True, 'switchable': True},
          {'code': 'other', 'on': True, 'switchable': False}]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _TwoGifts(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)
        cls.org = make_org('fx-org')
        cls.gift_a = make_programme(organisation=cls.org, code='fx-a', is_active=True)
        cls.gift_b = make_programme(organisation=cls.org, code='fx-b', is_active=True)
        cls.round_a = make_cohort(programme=cls.gift_a, code='fx-a-2026', is_open=True, is_active=True)
        cls.round_b = make_cohort(programme=cls.gift_b, code='fx-b-2026', is_open=True, is_active=True)
        cls.foreign = make_programme(organisation=make_org('fx-other'), code='fx-foreign',
                                     is_active=True)
        cls.oa = make_admin('org_admin', owning_org=cls.org)

    def _put(self, sources, gift='fx-a'):
        return authed_client(self.oa).put(f'{CONFIG}?programme={gift}', {'sources': sources},
                                          format='json')

    def _switch_off(self, gift, *codes):
        Programme.objects.filter(pk=gift.pk).update(
            **{gift_sources.SWITCHABLE_FIXED[c]: False for c in codes})


class TestDefaultOn(_TwoGifts):
    def test_an_existing_and_a_new_gift_offer_all_three(self):
        fresh = Programme.objects.create(organisation=self.org, code='fx-new', name_en='New')
        for gift in (self.gift_a, fresh):
            gift.refresh_from_db()
            self.assertEqual(gift_sources.offered_fixed_codes(gift), ['halatuju', 'social', 'other'])
        self.assertEqual(gift_sources.offered_fixed_codes(None), ['halatuju', 'social', 'other'])

    def test_the_configuration_lists_the_three_with_other_locked(self):
        resp = authed_client(self.oa).get(f'{CONFIG}?programme=fx-a')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['fixed_sources'], ALL_ON)

    def test_the_intake_serves_all_three(self):
        body = APIClient().get(INTAKE + '?programme=fx-a').json()
        self.assertEqual(body['fixed_sources'], ['halatuju', 'social', 'other'])


class TestTheConfigurationSwitches(_TwoGifts):
    def test_switching_off_writes_only_that_gift_and_audits_each(self):
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            resp = self._put({'social': False, 'halatuju': False})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual([(r['code'], r['on']) for r in resp.json()['fixed_sources']],
                         [('halatuju', False), ('social', False), ('other', True)])
        self.gift_a.refresh_from_db()
        self.gift_b.refresh_from_db()
        self.assertEqual((self.gift_a.offers_social, self.gift_a.offers_halatuju), (False, False))
        self.assertEqual((self.gift_b.offers_social, self.gift_b.offers_halatuju), (True, True))
        lines = ' | '.join(r.getMessage() for r in logs.records)
        self.assertIn('AUDIT programme_source_set programme=fx-a source=social was=on now=off', lines)
        self.assertIn('AUDIT programme_source_set programme=fx-a source=halatuju was=on now=off', lines)

    def test_switching_back_on_and_a_no_op_is_not_audited(self):
        self._switch_off(self.gift_a, 'social')
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            self._put({'social': True, 'halatuju': True})
        lines = [r.getMessage() for r in logs.records if 'programme_source_set' in r.getMessage()]
        self.assertEqual(lines, [
            f'AUDIT programme_source_set programme=fx-a source=social was=off now=on by={self.oa.email}'])

    def test_other_can_never_be_switched_off_and_nothing_is_written(self):
        resp = self._put({'social': False, 'other': False})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual((resp.json()['code'], resp.json()['source']), ('fixed_source_locked', 'other'))
        self.gift_a.refresh_from_db()
        self.assertTrue(self.gift_a.offers_social)          # the whole request was refused

    def test_a_non_boolean_is_refused(self):
        resp = self._put({'social': 'off'})
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_source_value'))

    def test_the_org_fence_is_unchanged(self):
        self.assertEqual(self._put({'social': False}, gift='fx-foreign').status_code, 404)
        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.offers_social)

    def test_a_plain_admin_is_refused(self):
        resp = authed_client(make_admin('admin', owning_org=self.org)).put(
            f'{CONFIG}?programme=fx-a', {'sources': {'social': False}}, format='json')
        self.assertEqual(resp.status_code, 403)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheStudentSide(_TwoGifts):
    def setUp(self):
        self.student = make_shortlistable_student()

    def _apply(self, code, programme):
        return authed_client(self.student).post(APPLY, {
            'household_income': 2500, 'receives_str': True, 'consent_to_contact': True,
            'programme_code': programme, 'referral_source': code,
        }, format='json')

    def test_a_switched_off_choice_leaves_that_gifts_intake_only(self):
        self._switch_off(self.gift_a, 'social')
        self.assertEqual(APIClient().get(INTAKE + '?programme=fx-a').json()['fixed_sources'],
                         ['halatuju', 'other'])
        self.assertEqual(APIClient().get(INTAKE + '?programme=fx-b').json()['fixed_sources'],
                         ['halatuju', 'social', 'other'])

    def test_the_submit_refuses_it_for_that_gift_only(self):
        self._switch_off(self.gift_a, 'social', 'halatuju')
        for code in ('social', 'halatuju'):
            with self.subTest(code=code):
                resp = self._apply(code, 'fx-a')
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertEqual(resp.json()['code'], 'referral_source_not_offered')
                self.assertFalse(ScholarshipApplication.objects.filter(profile=self.student).exists())
        # `other` and blank still go through on the switched-off gift.
        self.assertEqual(self._apply('other', 'fx-a').status_code, 201)
        # Gift B is untouched.
        self.student = make_shortlistable_student()
        self.assertEqual(self._apply('social', 'fx-b').status_code, 201)

    def test_blank_is_still_accepted_with_both_off(self):
        self._switch_off(self.gift_a, 'social', 'halatuju')
        self.assertEqual(self._apply('', 'fx-a').status_code, 201)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestPastAnswers(_TwoGifts):
    def test_an_old_social_answer_is_kept_and_still_filterable(self):
        app = make_application('submitted', cohort=self.round_a, referral_code='social')
        self._switch_off(self.gift_a, 'social')
        app.refresh_from_db()
        self.assertEqual(app.referral_code, 'social')
        rows = authed_client(self.oa).get(ADMIN_APPS + '?source=social').json()
        self.assertEqual([r['id'] for r in rows['applications']], [app.pk])
        self.assertEqual(rows['applications'][0]['referral_source'], 'social')
