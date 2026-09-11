"""Payment runs carry their programme — P2b (2026-07-26).

The guarantee: **a run pays students of ONE gift.** Before this, `PaymentRun` was fenced to an
organisation only, so once BrightPath runs two programmes a single run would have drawn from both
— paying one benefactor's students out of another's money and making per-programme reconciliation
impossible.

Pinned here: the narrowing itself; that `programme` is REQUIRED and cannot be defaulted away; the
org fence still holds ABOVE it; that the run's "skipped this run" list narrows too (a student of
another gift was never a candidate and must not read as skipped); and the backfill's invariant —
an existing run's item set does not move.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import payments
from apps.scholarship.models import (
    PaymentRun, Programme, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_PREFIX = '8000400175'
_SEQ = {'n': 0}


def _org(code='p2b-org', name='BrightPath'):
    return PartnerOrganisation.objects.create(code=code, name=name)


def _programme(org, code, name):
    return Programme.objects.create(organisation=org, code=code, name_en=name)


def _cohort(org, programme, code):
    return ScholarshipCohort.objects.create(
        code=code, name='B40', year=2026, owning_organisation=org, programme=programme)


def _app(cohort, org, suffix):
    _SEQ['n'] += 1
    i = _SEQ['n']
    prof = StudentProfile.objects.create(
        supabase_user_id=f'p2b-stud-{i}', nric=f'{i:06d}-14-{i:04d}', name=f'Student {i}')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=prof, owning_organisation=org, status='awarded',
        chosen_pathway='matric', award_amount=D('2000'), reporting_date=date(2026, 6, 1),
        vircle_id=_PREFIX + suffix)


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class _Base(TestCase):
    """ONE organisation running TWO gifts — the shape BrightPath takes the moment Sabah opens,
    and the only shape in which this sprint's bug is visible at all."""

    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.flagship = _programme(cls.org, 'p2b-flag', 'Flagship Bursary')
        cls.sabah = _programme(cls.org, 'p2b-sabah', 'Sabah Bursary')
        cls.c_flag = _cohort(cls.org, cls.flagship, 'p2b-cf')
        cls.c_sabah = _cohort(cls.org, cls.sabah, 'p2b-cs')
        cls.app_flag = _app(cls.c_flag, cls.org, '001')
        cls.app_sabah = _app(cls.c_sabah, cls.org, '002')
        cls.pay_date = date(2026, 8, 1)
        cls.period = date(2026, 8, 1)

    def _create(self, programme):
        with mock.patch('apps.scholarship.payments.timezone.localdate',
                        return_value=date(2026, 7, 20)):
            return payments.create_run(self.org, programme, self.pay_date, self.period)


class TestARunPaysOneGift(_Base):
    def test_a_run_contains_only_its_own_programmes_students(self):
        run = self._create(self.sabah)
        self.assertEqual([i.application_id for i in run.items.all()], [self.app_sabah.id])

    def test_the_other_gifts_run_is_disjoint(self):
        flag_run = self._create(self.flagship)
        sabah_run = self._create(self.sabah)
        flag_ids = {i.application_id for i in flag_run.items.all()}
        sabah_ids = {i.application_id for i in sabah_run.items.all()}
        self.assertEqual(flag_ids, {self.app_flag.id})
        self.assertEqual(sabah_ids, {self.app_sabah.id})
        self.assertEqual(flag_ids & sabah_ids, set())

    def test_the_run_records_which_gift_it_paid(self):
        run = self._create(self.sabah)
        self.assertEqual(run.programme_id, self.sabah.id)

    def test_eligible_rows_narrows_by_programme(self):
        rows = payments.eligible_rows(self.org, self.pay_date, period_month=self.period,
                                      programme=self.sabah)
        self.assertEqual([r['application'].id for r in rows], [self.app_sabah.id])

    def test_eligible_rows_without_a_programme_still_spans_the_org(self):
        """The narrowing is opt-in at this level — the funding summary wants the whole org.
        `create_run` is what makes it compulsory."""
        rows = payments.eligible_rows(self.org, self.pay_date, period_month=self.period)
        self.assertEqual({r['application'].id for r in rows},
                         {self.app_flag.id, self.app_sabah.id})


class TestProgrammeCannotBeSkipped(_Base):
    def test_programme_is_positional_and_has_no_default(self):
        """A default would compile, pass every pre-P2b test, and silently pay across gifts —
        the P2a lesson applied to runs. Forgetting it must be a TypeError, not a wrong answer."""
        with self.assertRaises(TypeError):
            payments.create_run(self.org, self.pay_date, self.period)

    def test_an_explicit_none_is_refused(self):
        with self.assertRaises(payments.PaymentsError) as ctx:
            self._create(None)
        self.assertEqual(ctx.exception.code, 'programme_required')

    def test_a_programme_from_another_organisation_is_refused(self):
        """The organisation stays the fence; the programme narrows INSIDE it and can never be
        used to reach across."""
        other_org = _org(code='p2b-other', name='Other Org')
        foreign = _programme(other_org, 'p2b-foreign', 'Foreign Bursary')
        with self.assertRaises(payments.PaymentsError) as ctx:
            self._create(foreign)
        self.assertEqual(ctx.exception.code, 'programme_not_in_org')


class TestSkippedListNarrowsToo(_Base):
    """The channel lesson: narrowing the ITEMS is not narrowing the RUN. The detail payload also
    lists 'skipped this run' students, computed live from the same choke-point."""

    def test_another_gifts_student_is_not_listed_as_skipped(self):
        from apps.scholarship.views_admin import _payment_run_detail
        # Make the OTHER gift's student ineligible-but-listable (no eWallet → greyed, not hidden).
        self.app_flag.vircle_id = ''
        self.app_flag.save(update_fields=['vircle_id'])
        run = self._create(self.sabah)
        detail = _payment_run_detail(run)
        skipped_ids = {s['application_id'] for s in detail['skipped']}
        self.assertNotIn(self.app_flag.id, skipped_ids)

    def test_a_legacy_run_with_no_programme_keeps_the_whole_org_view(self):
        """A pre-P2b run has no gift recorded; it must keep reading exactly as it did."""
        from apps.scholarship.views_admin import _payment_run_detail
        self.app_flag.vircle_id = ''
        self.app_flag.save(update_fields=['vircle_id'])
        run = self._create(self.sabah)
        PaymentRun.objects.filter(pk=run.pk).update(programme=None)
        run.refresh_from_db()
        detail = _payment_run_detail(run)
        self.assertIn(self.app_flag.id, {s['application_id'] for s in detail['skipped']})

    def test_the_detail_payload_names_the_gift(self):
        from apps.scholarship.views_admin import _payment_run_detail
        run = self._create(self.sabah)
        self.assertEqual(_payment_run_detail(run)['programme'],
                         {'id': self.sabah.id, 'name': 'Sabah Bursary'})


class TestBackfillLeavesRunsAlone(_Base):
    """The migration's invariant, expressed as behaviour rather than as a migration test: giving
    an existing run its programme must not change WHO is in it or WHAT it pays. Prod holds an
    open draft run of 30 items on the live payout path — this is the property that protects it."""

    def _backfill(self):
        """The same derivation `0127` performs."""
        for run in PaymentRun.objects.filter(programme__isnull=True):
            ids = set(run.items.exclude(application__programme__isnull=True)
                      .values_list('application__programme_id', flat=True))
            if len(ids) == 1:
                run.programme_id = ids.pop()
                run.save(update_fields=['programme'])

    def test_item_set_and_total_are_unchanged(self):
        run = self._create(self.sabah)
        before_items = sorted(i.application_id for i in run.items.all())
        before_total = sum((i.amount for i in run.items.all()), D('0'))
        PaymentRun.objects.filter(pk=run.pk).update(programme=None)

        self._backfill()

        run.refresh_from_db()
        self.assertEqual(sorted(i.application_id for i in run.items.all()), before_items)
        self.assertEqual(sum((i.amount for i in run.items.all()), D('0')), before_total)
        self.assertEqual(run.programme_id, self.sabah.id)

    def test_a_run_is_never_assigned_a_gift_its_students_do_not_share(self):
        """An ambiguous run is left unassigned rather than guessed — guessing would attribute
        one gift's students to another."""
        run = self._create(self.sabah)
        # Force a cross-gift run of the kind P2b makes impossible, to prove the backfill's guard.
        run.items.create(application=self.app_flag, included=True, amount=D('200'),
                         award_amount_snapshot=D('2000'), paid_to_date_snapshot=D('0'))
        PaymentRun.objects.filter(pk=run.pk).update(programme=None)

        self._backfill()

        run.refresh_from_db()
        self.assertIsNone(run.programme_id)

    def test_a_run_with_no_items_is_left_alone(self):
        run = self._create(self.sabah)
        run.items.all().delete()
        PaymentRun.objects.filter(pk=run.pk).update(programme=None)

        self._backfill()

        run.refresh_from_db()
        self.assertIsNone(run.programme_id)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET='test-supabase-jwt-secret')
class TestTheRunLISTNarrowsByGift(_Base):
    """TD-241 (2026-09-11) — Payments moved to the PROGRAMME section, so the list narrows.

    ⚠⚠ **THIS CLASS EXISTS BECAUSE A BITE-CHECK FOUND ITS ABSENCE.** Deleting the narrowing from
    `AdminPaymentRunListView` failed NOTHING: the create path was covered from three directions
    and the READ path from none. A list that ignored the gift would show a reader every run in
    the organisation under a breadcrumb naming one gift — two funds' money on one screen, each
    row looking like it belonged there.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.reader = PartnerAdmin.objects.create(
            supabase_user_id='p2b-rd', role='admin', is_active=True,
            owning_organisation=cls.org, name='Reader', email='rd@x.com')
        cls.run_flag = PaymentRun.objects.create(
            organisation=cls.org, programme=cls.flagship, reference='PR-FLAG-01',
            payment_date=date(2026, 8, 1), period_month=date(2026, 8, 1))
        cls.run_sabah = PaymentRun.objects.create(
            organisation=cls.org, programme=cls.sabah, reference='PR-SABAH-01',
            payment_date=date(2026, 8, 2), period_month=date(2026, 8, 1))

    def _get(self, query=''):
        import jwt
        from rest_framework.test import APIClient
        c = APIClient()
        token = jwt.encode({'sub': 'p2b-rd', 'aud': 'authenticated', 'role': 'authenticated'},
                           'test-supabase-jwt-secret', algorithm='HS256')
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return c.get(f'/api/v1/admin/scholarship/payment-runs/{query}')

    def test_naming_a_gift_lists_only_that_gifts_runs(self):
        r = self._get(f'?programme={self.sabah.code}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x['reference'] for x in r.json()['runs']], ['PR-SABAH-01'])

    def test_naming_no_gift_still_lists_the_whole_organisation(self):
        """⚠ An absent gift means DO NOT NARROW. A client that never learned about the parameter
        reaches exactly what it always did — the narrowing can only ever subtract."""
        r = self._get()
        self.assertEqual(sorted(x['reference'] for x in r.json()['runs']),
                         ['PR-FLAG-01', 'PR-SABAH-01'])

    def test_another_tenants_gift_is_404_and_lists_nothing(self):
        """⚠ 404, never 403, and never another tenant's runs. A cross-tenant code must not
        confirm that gift exists, and must certainly not widen what this reader can see."""
        other = _org(code='p2b-o3', name='Other Org 3')
        foreign = _programme(other, 'p2b-f3', 'Foreign Bursary')
        PaymentRun.objects.create(
            organisation=other, programme=foreign, reference='PR-FOREIGN-01',
            payment_date=date(2026, 8, 3), period_month=date(2026, 8, 1))
        r = self._get(f'?programme={foreign.code}')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('PR-FOREIGN-01', r.content.decode())

    def test_an_unknown_gift_is_the_same_answer(self):
        self.assertEqual(self._get('?programme=no-such-gift').status_code, 404)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET='test-supabase-jwt-secret',
                   BURSARY_AGREEMENT_ENABLED=False)
class TestCreateEndpointChoosesTheGift(_Base):
    """Owner decision (2026-07-26): the OPERATOR states which gift a run pays from. The endpoint
    preselects when there is only one — which is BrightPath today, so nothing visibly changes —
    and refuses to guess when there are two.

    ⚠ **THE GIFT IS NAMED BY CODE SINCE TD-241 (2026-09-11), NOT BY `programme_id`.** These two
    tests were REVERSED IN PLACE: Payments moved to the Programme section and the page's own
    gift picker was removed, so the breadcrumb is the only control that answers "which gift",
    and it carries a CODE. **The rules themselves did not change** — preselect one, refuse to
    guess between two, 404 another tenant's gift — only the spelling of the parameter. Do not
    "restore" `programme_id`: a second way to name the gift is a second way to create a run
    against one you are not looking at.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maker = PartnerAdmin.objects.create(
            supabase_user_id='p2b-mk', role='admin', is_active=True,
            owning_organisation=cls.org, name='Maker One', email='mk@x.com')

    def _client(self):
        import jwt
        from rest_framework.test import APIClient
        c = APIClient()
        token = jwt.encode({'sub': 'p2b-mk', 'aud': 'authenticated', 'role': 'authenticated'},
                           'test-supabase-jwt-secret', algorithm='HS256')
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return c

    def _post(self, body):
        with mock.patch('apps.scholarship.payments.timezone.localdate',
                        return_value=date(2026, 7, 20)):
            return self._client().post('/api/v1/admin/scholarship/payment-runs/',
                                       body, format='json')

    def test_two_gifts_and_no_choice_is_refused(self):
        r = self._post({'payment_date': '2026-08-01'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'programme_required')
        self.assertEqual(PaymentRun.objects.count(), 0)

    def test_the_named_gift_is_used(self):
        r = self._post({'payment_date': '2026-08-01', 'programme': self.sabah.code})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['programme'], {'id': self.sabah.id, 'name': 'Sabah Bursary'})
        self.assertEqual([i['application_id'] for i in r.json()['items']], [self.app_sabah.id])

    def test_the_code_may_ride_as_a_QUERY_parameter_too(self):
        """The breadcrumb sends `?programme=<code>` on every other Programme-scope call, so
        the create endpoint accepts it there as well as in the body. One spelling of the
        VALUE (a code); two places it may sit, because the page already had both habits."""
        with mock.patch('apps.scholarship.payments.timezone.localdate',
                        return_value=date(2026, 7, 20)):
            r = self._client().post(
                f'/api/v1/admin/scholarship/payment-runs/?programme={self.sabah.code}',
                {'payment_date': '2026-08-01'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['programme']['id'], self.sabah.id)

    def test_another_tenants_programme_is_404_not_403(self):
        """⚠ 404, never 403 — a cross-tenant code must not confirm that gift exists."""
        other_org = _org(code='p2b-o2', name='Other Org 2')
        foreign = _programme(other_org, 'p2b-f2', 'Foreign Bursary')
        r = self._post({'payment_date': '2026-08-01', 'programme': foreign.code})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(PaymentRun.objects.count(), 0)

    def test_a_single_gift_org_needs_no_choice(self):
        """BrightPath today. The operator sees a preselected picker and the API accepts the
        omission — so this sprint changes nothing visible until a second gift exists."""
        self.sabah.is_active = False
        self.sabah.save(update_fields=['is_active'])
        r = self._post({'payment_date': '2026-08-01'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['programme'], {'id': self.flagship.id,
                                                 'name': 'Flagship Bursary'})
