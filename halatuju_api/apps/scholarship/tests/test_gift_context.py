"""The console never forgets which gift you are in — the SERVER half (2026-09-28).

A payment run belongs to exactly one gift, and so does an application. The run page and the
applicant page now tell the breadcrumb which gift they are showing, so the crumb cannot name one
gift over a record of another (owner, 2026-09-28: *"since we access the payment run by first
selecting the gift programme, that question shouldn't even arise"*). For that the client needs
the gift's CODE — the crumb speaks in codes — from the server, never from a guess.

Pinned here, and every one of these is ADDITIVE:
  * the run payload's `programme` gains `code` beside the `id` and `name` it always carried;
  * the applicant payload gains `programme: {id, code, name}` — THE GIFT, `application.programme`,
    and not `chosen_programme`, which is the student's COURSE (the fixture makes them differ);
  * a record with no gift answers `null` rather than a 500;
  * the organisation fence is untouched: another tenant's run and applicant are still 404;
  * the payload is still an allowlist — the ONE key outside `Meta.fields` is `programme`.
The query budget for the applicant GET is held by `test_query_budgets.py`, unchanged.
"""
from datetime import date

from django.test import TestCase, override_settings

from apps.scholarship.models import PaymentRun
from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

RUN_URL = '/api/v1/admin/scholarship/payment-runs/{}/'
APP_URL = '/api/v1/admin/scholarship/applications/{}/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class _TwoGifts(TestCase):
    """BrightPath's shape since Sabah opened: ONE organisation, TWO live gifts."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(code='gc-bp', name='BrightPath')
        cls.flagship = make_programme(cls.org, code='gc-flagship', name_en='BrightPath Bursary')
        cls.sabah = make_programme(cls.org, code='gc-sabah', name_en='  BPB Sabah 2026  ')
        cls.admin = make_admin('admin', owning_org=cls.org)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        # The other tenant — the fence must still answer 404 for everything it owns.
        cls.other_org = make_org(code='gc-other', name='Other')
        cls.other_gift = make_programme(cls.other_org, code='gc-other-gift')

    def _run(self, programme, org=None, ref='PR-GC-1'):
        return PaymentRun.objects.create(
            organisation=org or self.org, programme=programme, reference=ref,
            payment_date=date(2026, 10, 1), period_month=date(2026, 10, 1))


class TestTheRunNamesItsGiftByCode(_TwoGifts):
    def test_the_run_payload_carries_the_code_beside_the_id_and_name(self):
        run = self._run(self.sabah)
        r = authed_client(self.admin).get(RUN_URL.format(run.id))
        self.assertEqual(r.status_code, 200)
        # `name` is still stripped exactly as it always was; `code` is the addition.
        self.assertEqual(r.json()['programme'],
                         {'id': self.sabah.id, 'code': 'gc-sabah', 'name': 'BPB Sabah 2026'})

    def test_the_run_LIST_carries_it_too(self):
        # One helper builds both payloads, so they cannot disagree about the shape.
        self._run(self.flagship)
        r = authed_client(self.admin).get('/api/v1/admin/scholarship/payment-runs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['runs'][0]['programme']['code'], 'gc-flagship')

    def test_a_pre_P2b_run_with_no_gift_is_null_not_a_500(self):
        run = self._run(None)
        r = authed_client(self.admin).get(RUN_URL.format(run.id))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['programme'])

    def test_the_fence_still_refuses_another_tenants_run(self):
        run = self._run(self.other_gift, org=self.other_org, ref='PR-GC-X')
        r = authed_client(self.admin).get(RUN_URL.format(run.id))
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('gc-other-gift', r.content.decode())


class TestTheApplicationNamesItsGift(_TwoGifts):
    def _app(self, programme):
        # A gift-less cohort must still be BrightPath's, or the fence (not the gift) answers.
        cohort = (make_cohort(programme=programme) if programme is not None
                  else make_cohort(programme=None, owning_organisation=self.org))
        # ⚠ THE TRAP, BUILT IN: the COURSE is a thing called a "programme" too, and it names a
        # code that is NOT the gift's. A pin wired to the wrong field reads this and fails.
        return make_application('shortlisted', cohort=cohort, chosen_programme={
            'code': 'gc-sabah', 'course_id': 'DIPLOMA-X', 'name': 'Diploma in Accounting',
            'programme': 'gc-sabah'})

    def test_the_detail_payload_names_THE_GIFT_not_the_course(self):
        app = self._app(self.flagship)
        r = authed_client(self.admin).get(APP_URL.format(app.id))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['programme'], {'id': self.flagship.id, 'code': 'gc-flagship',
                                             'name': 'BrightPath Bursary'})
        # …and it agrees with the `programme_id` the payload has always carried.
        self.assertEqual(body['programme']['id'], body['programme_id'])
        # The course is untouched and still says what it said.
        self.assertEqual(body['chosen_programme']['course_id'], 'DIPLOMA-X')

    def test_an_application_with_no_gift_is_null_not_a_500(self):
        app = self._app(None)
        r = authed_client(self.admin).get(APP_URL.format(app.id))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['programme'])
        self.assertIsNone(r.json()['programme_id'])

    def test_an_ACTION_response_carries_it_as_well(self):
        # Every officer action answers with the same serializer, and the cockpit replaces its
        # whole state with that answer — so a gift present on the GET and absent on a PATCH would
        # un-pin the crumb halfway through a case.
        app = self._app(self.sabah)
        r = authed_client(self.org_admin).patch(
            APP_URL.format(app.id), {'mentoring_candidate': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['programme']['code'], 'gc-sabah')

    def test_the_fence_still_refuses_another_tenants_application(self):
        app = self._app(self.other_gift)
        r = authed_client(self.admin).get(APP_URL.format(app.id))
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('gc-other-gift', r.content.decode())


class TestThePayloadIsStillAnAllowlist(_TwoGifts):
    """`test_admin_detail_payload.py` pins that the serializer NAMES its fields. The gift is
    appended outside `Meta.fields` (the host file may not grow), so this pins the other half: the
    one key the payload carries beyond the named list is `programme`, and nothing else."""

    def test_the_only_key_beyond_meta_fields_is_programme(self):
        app = make_application('shortlisted', cohort=make_cohort(programme=self.flagship))
        data = AdminApplicationDetailSerializer(app).data
        extra = set(data) - set(AdminApplicationDetailSerializer.Meta.fields)
        self.assertEqual(extra, {'programme'})
        # …and it is the LAST key, so every existing key kept its position.
        self.assertEqual(list(data)[-1], 'programme')
