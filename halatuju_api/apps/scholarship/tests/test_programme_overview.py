"""Programme Overview — the page you land on inside a gift, and the two gates that shape it.

Four claims carry this file:

1. **Role shaping is a GATE, not a layout.** The key set is chosen server-side, so a reviewer's
   payload has no money key to hide and a finance admin's has no funnel.
   `test_the_key_set_per_role_is_exact` pins every role's exact set — a section arriving by
   accident fails here rather than reaching a screen.

2. **The fence is one queryset, and it is tested FROM THE WIDENING SIDE.** A non-super naming
   another tenant's gift gets 404 (never 403 — a 403 would confirm the gift exists), and cannot
   count that tenant's rows by any route; a super with no organisation of their own sees the
   platform.

3. **The headline money is the SAME money the neighbouring screens show.** Two reconciliation
   tests call the Payments funding summary and the Spending endpoint on this one fixture and
   assert byte equality. A page that quietly disagreed with the screen one click away would be
   worse than no page.

4. **TD-209 — a test that reads the same clock as the code cannot see a clock bug.** The
   timezone test pins a 23:30 UTC instant and a fixed `now`, and asserts the case lands in the
   NEXT Malaysian week. Nothing in it is derived from `timezone.now()`.
"""
import datetime
from decimal import Decimal
from io import StringIO

import jwt
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import programme_overview
from apps.scholarship.models import (
    BursarySpendTxn, Disbursement, Programme, ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/programme-overview/'
FUNDING = '/api/v1/admin/scholarship/payments/funding-summary/'
SPENDING = '/api/v1/admin/scholarship/spending/'

#: ⚠ THE MONEY FIXTURE LIVES IN JULY AND AUGUST 2026 — deliberately in the PAST of any run, so
#: "the spend series stops at `data_to`, not at today" stays a real assertion for ever rather
#: than one that happens to hold on the day it was written.


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _local(y, m, d, hh=12, mm=0):
    """An aware instant at a MALAYSIAN wall-clock time — the fixtures speak the owner's clock."""
    naive = datetime.datetime(y, m, d, hh, mm)
    return timezone.make_aware(naive, timezone.get_default_timezone())


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REVIEW_SLA_DAYS=10, REVIEW_NUDGE_SOON_DAYS=2, REVIEW_ESCALATE_GRACE_DAYS=3)
class _Base(TestCase):
    """One world, shared by every class here — which is what makes the reconciliation tests
    meaningful: they compare three endpoints reading the same rows."""

    @classmethod
    def setUpTestData(cls):
        # ⚠ THE SEEDED ORGANISATION, not a new one. A data migration creates the platform's one
        # tenant; creating a second here would give this world TWO tenants where production has
        # one, and every "a non-super sees only their own" assertion would still pass while
        # proving less. The SECOND tenant below is created deliberately, to be excluded.
        cls.org = PartnerOrganisation.objects.get(code='brightpath')
        cls.other_org = PartnerOrganisation.objects.create(
            code='ov-other', name='Other Tenant')

        cls.gift = Programme.objects.create(
            organisation=cls.org, code='ov-gift', name_en='Overview Gift')
        cls.gift2 = Programme.objects.create(
            organisation=cls.org, code='ov-gift2', name_en='Second Gift')
        cls.other_gift = Programme.objects.create(
            organisation=cls.other_org, code='ov-other-gift', name_en='Other Gift')

        cls.cohort = ScholarshipCohort.objects.create(
            code='ov-2026', name='Overview 2026', year=2026, owning_organisation=cls.org,
            programme=cls.gift, is_open=True,
            opens_on=datetime.date(2026, 1, 15), closes_on=datetime.date(2026, 6, 30))
        # An older round of the SAME gift — the intake block must pick the highest year.
        cls.old_cohort = ScholarshipCohort.objects.create(
            code='ov-2025', name='Overview 2025', year=2025, owning_organisation=cls.org,
            programme=cls.gift, is_open=False)
        cls.cohort2 = ScholarshipCohort.objects.create(
            code='ov2-2026', name='Second 2026', year=2026, owning_organisation=cls.org,
            programme=cls.gift2)
        cls.other_cohort = ScholarshipCohort.objects.create(
            code='ov-other-2026', name='Other 2026', year=2026,
            owning_organisation=cls.other_org, programme=cls.other_gift)

        def staff(uid, role, org=cls.org, **kw):
            return PartnerAdmin.objects.create(
                supabase_user_id=uid, role=role, is_active=True, owning_organisation=org,
                name=uid, email=f'{uid}@ov.test', **kw)

        cls.su = PartnerAdmin.objects.create(
            supabase_user_id='ov-su', is_super_admin=True, is_active=True,
            name='Super', email='ov-su@ov.test')
        cls.oa = staff('ov-oa', 'org_admin')
        cls.adm = staff('ov-adm', 'admin')
        cls.fin = staff('ov-fin', 'finance')
        cls.qc = staff('ov-qc', 'qc')
        cls.rev = staff('ov-rev', 'reviewer')
        cls.rev2 = staff('ov-rev2', 'reviewer')
        cls.ptr = staff('ov-ptr', 'partner')
        cls.other_oa = staff('ov-other-oa', 'org_admin', org=cls.other_org)
        cls.homeless_oa = PartnerAdmin.objects.create(
            supabase_user_id='ov-homeless', role='org_admin', is_active=True,
            name='Homeless', email='homeless@ov.test')

        now = timezone.now()
        cls.now = now

        # ── the money students (the three PAYABLE states) ───────────────────────────────
        cls.m1 = cls._app('m1', status='awarded', award_amount=Decimal('3000.00'),
                          awarded_at=_local(2026, 7, 20))
        cls.m2 = cls._app('m2', status='active', award_amount=Decimal('2000.00'))
        cls.m3 = cls._app('m3', status='maintenance', award_amount=Decimal('1000.00'))
        cls._released(cls.m1, '1000.00', _local(2026, 7, 5, 10))
        cls._released(cls.m2, '500.00', _local(2026, 8, 10, 10))

        # ── the review queue ────────────────────────────────────────────────────────────
        cls.r_soon = cls._app('r1', status='interviewing', assigned_to=cls.rev,
                              assigned_at=now - datetime.timedelta(days=9))
        cls.r_over = cls._app('r2', status='interviewing', assigned_to=cls.rev,
                              assigned_at=now - datetime.timedelta(days=11))
        cls.r_open = cls._app('r3', status='profile_complete', assigned_to=cls.rev,
                              assigned_at=now - datetime.timedelta(days=1))
        cls.r_other = cls._app('r4', status='interviewing', assigned_to=cls.rev2,
                               assigned_at=now - datetime.timedelta(days=11))
        cls.unassigned = cls._app('u1', status='submitted')

        # ── the QC queue and two cases this QC decided ──────────────────────────────────
        cls.q_waiting = cls._app('q1', status='interviewed', assigned_to=cls.rev,
                                 assigned_at=now - datetime.timedelta(days=12),
                                 verdict_decided_at=now - datetime.timedelta(days=4))
        cls.q_done_rec = cls._app(
            'q2', status='recommended', assigned_to=cls.rev,
            assigned_at=now - datetime.timedelta(days=20),
            verdict_decided_at=now - datetime.timedelta(days=10),
            recommended_at=now - datetime.timedelta(days=9), recommended_by=cls.qc.email)
        cls.q_done_rej = cls._app(
            'q3', status='rejected', assigned_to=cls.rev,
            assigned_at=now - datetime.timedelta(days=20),
            verdict_decided_at=now - datetime.timedelta(days=10),
            rejected_at=now - datetime.timedelta(days=8), rejected_by=cls.qc.email)
        # Decided by somebody ELSE — must never land on this QC's pace.
        cls.q_not_mine = cls._app(
            'q4', status='recommended', assigned_to=cls.rev2,
            assigned_at=now - datetime.timedelta(days=20),
            verdict_decided_at=now - datetime.timedelta(days=10),
            recommended_at=now - datetime.timedelta(days=9),
            recommended_by='somebody@else.test')

        # ── the SAME reviewer, in a DIFFERENT gift of the same organisation ─────────────
        cls.other_gift_case = cls._app(
            'g2', status='recommended', cohort=cls.cohort2, assigned_to=cls.rev,
            assigned_at=now - datetime.timedelta(days=30),
            verdict_decided_at=now - datetime.timedelta(days=25))

        # ── the other tenant ────────────────────────────────────────────────────────────
        cls.foreign_a = cls._app('f1', cohort=cls.other_cohort, status='submitted')
        cls.foreign_b = cls._app('f2', cohort=cls.other_cohort, status='awarded',
                                 award_amount=Decimal('9999.00'))
        cls._released(cls.foreign_b, '9999.00', _local(2026, 8, 1, 10))
        cls._txn(cls.foreign_b, 'f-1', datetime.date(2026, 8, 4), '77.00', 'food')

        # ── spending (this organisation) ────────────────────────────────────────────────
        cls._txn(cls.m1, 'a-1', datetime.date(2026, 8, 3), '12.50', 'food')
        cls._txn(cls.m1, 'a-2', datetime.date(2026, 8, 5), '30.00', 'groceries')
        cls._txn(cls.m2, 'a-3', datetime.date(2026, 8, 12), '100.00', '')
        cls._txn(cls.m2, 'a-4', datetime.date(2026, 8, 13), '20.00', 'unsorted')
        # A NON-spend row: it extends how far the data reaches and is not spending.
        cls._txn(cls.m2, 'a-5', datetime.date(2026, 8, 20), '50.00', '', tx_type='RECEIVED')

        # ⚠ `submitted_at` IS `auto_now_add`, so it can only be set by an UPDATE. Pinning it
        # makes `applications_per_week` deterministic without freezing the whole clock.
        ScholarshipApplication.objects.filter(
            owning_organisation=cls.org).update(submitted_at=_local(2026, 8, 4))

    # ── fixture helpers ────────────────────────────────────────────────────────────────
    #: ⚠ A COUNTER, NOT `hash(tag)`. Python's string hash is randomised per process, so a
    #: hash-derived NRIC is a different (and occasionally COLLIDING) value on every run — a
    #: unique-constraint flake that would show up once a month and look like anything but this.
    _seq = 0

    @classmethod
    def _app(cls, tag, *, cohort=None, **kw):
        _Base._seq += 1
        n = _Base._seq
        profile = StudentProfile.objects.create(
            supabase_user_id=f'ov-{tag}', nric=f'0101{n + 10:02d}-14-{n + 1000:04d}',
            name=f'Student {tag.upper()}')
        return ScholarshipApplication.objects.create(
            cohort=cohort or cls.cohort, profile=profile, **kw)

    @classmethod
    def _released(cls, app, amount, released_at):
        return Disbursement.objects.create(
            application=app, amount=Decimal(amount), status='released', sequence=1,
            released_at=released_at)

    @classmethod
    def _txn(cls, app, txn_id, txn_date, amount, category, tx_type='SPEND'):
        return BursarySpendTxn.objects.create(
            application=app, txn_id=txn_id, txn_date=txn_date, wallet_id='8000400170001',
            merchant='SHOP', amount=Decimal(amount), tx_type=tx_type, category=category)

    # ── request helpers ────────────────────────────────────────────────────────────────
    def _client(self, uid=None):
        c = APIClient()
        if uid:
            c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def _get(self, uid, query='?programme=ov-gift'):
        return self._client(uid).get(URL + query)

    def _body(self, uid, query='?programme=ov-gift'):
        r = self._get(uid, query)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()


_ALWAYS = {'programme', 'generated_at', 'data_to', 'sections'}
_FULL = _ALWAYS | {'funnel', 'money', 'attention', 'applications_series',
                   'money_series', 'intake'}


class RolesAndShapeTests(_Base):
    def test_every_console_role_is_admitted(self):
        for uid in ('ov-su', 'ov-oa', 'ov-adm', 'ov-fin', 'ov-qc', 'ov-rev'):
            with self.subTest(uid=uid):
                self.assertEqual(self._get(uid).status_code, 200)

    def test_a_partner_is_refused(self):
        """A referral organisation is attribution, never a scope — and a role with no sections
        at all is refused rather than served an empty page."""
        self.assertEqual(self._get('ov-ptr').status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertEqual(self._client().get(URL).status_code, 401)

    def test_the_key_set_per_role_is_exact(self):
        """⚠ THE ROLE GATE, PINNED. A section arriving by accident fails HERE, not on a screen."""
        expected = {
            'ov-su': _FULL,
            'ov-oa': _FULL,
            'ov-adm': _FULL,
            'ov-fin': _ALWAYS | {'money', 'money_series', 'intake'},
            'ov-qc': _ALWAYS | {'qc', 'intake'},
            'ov-rev': _ALWAYS | {'mine', 'intake'},
        }
        for uid, keys in expected.items():
            with self.subTest(uid=uid):
                body = self._body(uid)
                self.assertEqual(set(body), keys)
                # `sections` must DESCRIBE the payload, not merely accompany it.
                self.assertEqual(set(body['sections']), keys - _ALWAYS)

    def test_a_reviewer_gets_no_money_and_no_programme_wide_funnel(self):
        body = self._body('ov-rev')
        self.assertNotIn('money', body)
        self.assertNotIn('money_series', body)
        self.assertNotIn('funnel', body)
        self.assertNotIn('attention', body)
        self.assertIn('mine', body)

    def test_finance_gets_no_applicant_counts_and_no_names(self):
        r = self._get('ov-fin')
        body = r.json()
        self.assertNotIn('funnel', body)
        self.assertNotIn('attention', body)
        self.assertNotIn('mine', body)
        self.assertNotIn('qc', body)
        # Aggregates only: no student's name may appear anywhere in the rendered payload.
        self.assertNotIn(b'Student M1', r.content)

    def test_qc_gets_the_queue_and_their_own_pace_only(self):
        body = self._body('ov-qc')
        self.assertEqual(set(body['qc']), {'awaiting', 'oldest_waiting_days', 'cases', 'pace'})
        self.assertNotIn('money', body)
        self.assertNotIn('funnel', body)


class FenceTests(_Base):
    def test_another_tenants_gift_is_404_never_403(self):
        """A 403 would confirm the gift exists. Unknown and cross-tenant must be the same answer."""
        r = self._get('ov-oa', '?programme=ov-other-gift')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self._get('ov-oa', '?programme=no-such-gift').status_code, 404)

    def test_a_non_super_never_counts_another_tenants_rows(self):
        """Tested from the WIDENING side: no gift named is the WIDEST this caller can ask for,
        and it must still stop at the tenant wall."""
        body = self._body('ov-oa', '')
        mine = ScholarshipApplication.objects.filter(owning_organisation=self.org).count()
        self.assertEqual(body['funnel']['total'], mine)
        self.assertNotEqual(body['funnel']['total'], ScholarshipApplication.objects.count())
        # The other tenant's RM9,999 award may never reach this organisation's money strip.
        self.assertNotIn('9999', body['money']['committed'])

    def test_a_super_with_no_organisation_sees_the_platform(self):
        body = self._body('ov-su', '')
        self.assertEqual(body['funnel']['total'], ScholarshipApplication.objects.count())

    def test_no_gift_named_returns_everything_the_fence_allows(self):
        body = self._body('ov-oa', '')
        self.assertIsNone(body['programme'])
        # Both of this organisation's gifts are counted, and nothing else.
        self.assertEqual(
            body['funnel']['total'],
            ScholarshipApplication.objects.filter(owning_organisation=self.org).count())

    def test_the_gift_narrowing_reaches_through_the_cohort(self):
        """The Applications list's own pair, so the funnel agrees with the list one click away."""
        body = self._body('ov-oa', '?programme=ov-gift2')
        self.assertEqual(body['funnel']['total'], 1)
        self.assertEqual(body['programme'], {'code': 'ov-gift2', 'name': 'Second Gift'})

    def test_an_org_admin_with_no_organisation_is_refused_no_org(self):
        r = self._get('ov-homeless', '')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_org')


class FiguresTests(_Base):
    def test_the_funnel_names_every_status_and_sums_to_total(self):
        funnel = self._body('ov-oa')['funnel']
        self.assertEqual(set(funnel['by_status']),
                         {c for c, _ in ScholarshipApplication.STATUS_CHOICES})
        self.assertEqual(len(funnel['by_status']), 13)
        self.assertEqual(sum(funnel['by_status'].values()), funnel['total'])
        self.assertEqual(funnel['by_status']['interviewing'], 3)
        self.assertEqual(funnel['by_status']['submitted'], 1)
        # A stage nobody is in is present AT ZERO, never absent.
        self.assertEqual(funnel['by_status']['withdrawn'], 0)

    def test_the_money_headline_equals_the_payments_footer(self):
        """⚠ RECONCILIATION. Two endpoints, one fixture, byte equality."""
        overview = self._body('ov-oa')['money']
        footer = self._client('ov-oa').get(
            FUNDING + '?programme=ov-gift').json()['totals']
        self.assertEqual(overview['students'], footer['students'])
        self.assertEqual(overview['committed'], footer['award_total'])
        self.assertEqual(overview['paid'], footer['paid_total'])
        self.assertEqual(overview['remaining'], footer['remaining_total'])
        # ⚠ THE RECONCILIATION ABOVE IS ON THE STRING; THE VALUES BELOW ARE ON THE NUMBER, and
        # the difference is deliberate. What must never differ between two screens is the
        # rendered text — hence the string comparison. What the figure IS does not depend on the
        # database, but its SCALE does: SQLite's `Sum` over a numeric(10,2) returns
        # `Decimal('1500')` where Postgres returns `Decimal('1500.00')`. Pinning the literal
        # string here would pin a SQLite artefact into a production assertion.
        self.assertEqual(Decimal(overview['committed']), Decimal('6000.00'))
        self.assertEqual(Decimal(overview['paid']), Decimal('1500.00'))
        self.assertEqual(Decimal(overview['remaining']), Decimal('4500.00'))

    def test_the_spent_figure_equals_the_spending_total(self):
        """⚠ RECONCILIATION, the other neighbour."""
        overview = self._body('ov-oa')['money']
        spending = self._client('ov-oa').get(
            SPENDING + '?programme=ov-gift').json()['totals']
        self.assertEqual(overview['spent'], spending['spent'])
        self.assertEqual(overview['spent'], '162.50')

    def test_every_money_value_is_a_string(self):
        """⚠ A bare Decimal is rendered by DRF as a FLOAT — that is how 30.00 became 30.0."""
        body = self._body('ov-oa')
        for key in ('committed', 'paid', 'remaining', 'spent'):
            self.assertIsInstance(body['money'][key], str)
        for row in body['money_series']['money_per_month']:
            for key in ('released', 'spent', 'released_cum', 'spent_cum', 'gap'):
                self.assertIsInstance(row[key], str)
        for row in body['money_series']['per_student_per_week']:
            for key in ('spent', 'spent_per_transaction', 'transactions_per_student'):
                self.assertIsInstance(row[key], str)
        overall = body['money_series']['per_student_overall']
        for key in ('spent', 'spent_per_transaction', 'weekly_transactions_per_student'):
            self.assertIsInstance(overall[key], str)
        for slice_ in body['money_series']['by_category']:
            self.assertIsInstance(slice_['total'], str)

    def test_released_and_spent_by_month_carry_a_running_gap(self):
        months = {r['month']: r for r in
                  self._body('ov-oa')['money_series']['money_per_month']}
        self.assertEqual(months['2026-07']['released'], '1000.00')
        self.assertEqual(months['2026-07']['spent'], '0.00')
        self.assertEqual(months['2026-07']['gap'], '1000.00')
        self.assertEqual(months['2026-08']['released'], '500.00')
        self.assertEqual(months['2026-08']['spent'], '162.50')
        self.assertEqual(months['2026-08']['released_cum'], '1500.00')
        self.assertEqual(months['2026-08']['spent_cum'], '162.50')
        self.assertEqual(months['2026-08']['gap'], '1337.50')
        # Contiguous, and running to the CURRENT month (a month with no money is a real zero).
        today = timezone.localtime(timezone.now()).date()
        self.assertEqual(
            max(months), f'{today.year:04d}-{today.month:02d}')

    def test_a_case_submitted_at_2330_utc_lands_in_the_next_malaysian_week(self):
        """⚠⚠ TD-209, WITH A PINNED CLOCK. 2026-03-01 23:30 UTC is a SUNDAY in London and a
        MONDAY in Kuala Lumpur, so the case belongs to the week beginning 2 March — not the one
        beginning 23 February that `.date()` on the UTC instant would give. Nothing below reads
        `timezone.now()`, so this cannot pass by agreeing with the bug."""
        gift = Programme.objects.create(
            organisation=self.org, code='ov-tz', name_en='Timezone Gift')
        cohort = ScholarshipCohort.objects.create(
            code='ov-tz-2026', name='TZ', year=2026,
            owning_organisation=self.org, programme=gift)
        app = self._app('tz', cohort=cohort, status='submitted')
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            submitted_at=datetime.datetime(2026, 3, 1, 23, 30,
                                           tzinfo=datetime.timezone.utc))
        pinned = datetime.datetime(2026, 3, 9, 4, 0, tzinfo=datetime.timezone.utc)
        weeks = [w['week'] for w in programme_overview.build(
            self.oa, self.org, gift, now=pinned)['applications_series'][
                'applications_per_week']]
        self.assertEqual(weeks[0], '2026-03-02')
        self.assertNotIn('2026-02-23', weeks)

    def test_the_student_denominator_counts_only_wallets_that_were_live_that_week(self):
        """The denominator is students with a RELEASED disbursement on or before the week's end —
        not every student in the gift, and not only the ones who spent."""
        weeks = {w['week']: w for w in
                 self._body('ov-oa')['money_series']['per_student_per_week']}
        # M1's wallet went live on 5 July; M2's on 10 August.
        self.assertEqual(weeks['2026-08-03']['students'], 1)
        self.assertEqual(weeks['2026-08-03']['spent'], '42.50')
        self.assertEqual(weeks['2026-08-10']['students'], 2)
        self.assertEqual(weeks['2026-08-10']['spent'], '120.00')
        self.assertNotIn('average', weeks['2026-08-03'])

    def test_spent_per_transaction_is_ringgit_over_rows_each_week(self):
        """⚠ Owner, 2026-09-18: the line is what a card payment COST, on average — ringgit over
        rows, not over students. A week with no rows is '0.00', not a crash."""
        weeks = {w['week']: w for w in
                 self._body('ov-oa')['money_series']['per_student_per_week']}
        self.assertEqual(weeks['2026-08-03']['spent_per_transaction'], '21.25')   # 42.50 / 2
        self.assertEqual(weeks['2026-08-10']['spent_per_transaction'], '60.00')   # 120.00 / 2
        self.assertEqual(weeks['2026-08-17']['spent_per_transaction'], '0.00')    # no rows

    def test_transactions_are_rows_not_items(self):
        """⚠ A Vircle row is one card transaction and carries no item count. `transactions` is a
        ROW COUNT; summing anything here would be inventing a quantity."""
        weeks = {w['week']: w for w in
                 self._body('ov-oa')['money_series']['per_student_per_week']}
        self.assertEqual(weeks['2026-08-03']['transactions'], 2)
        self.assertEqual(weeks['2026-08-03']['transactions_per_student'], '2.0')
        self.assertEqual(weeks['2026-08-10']['transactions'], 2)
        self.assertEqual(weeks['2026-08-10']['transactions_per_student'], '1.0')
        self.assertNotIn('purchases', weeks['2026-08-03'])

    def test_the_whole_period_figures_name_their_denominators(self):
        """The two figures the page prints beneath the weekly lines. RM162.50 over four rows is
        RM40.625 a transaction — HALF-UP to 40.63, not banker's 40.62. Four rows over the two
        students whose wallets were live by `data_to` (20 Aug), over the three weeks the series
        spans (3, 10, 17 Aug), is 0.67 a week — one decimal, 0.7."""
        overall = self._body('ov-oa')['money_series']['per_student_overall']
        self.assertEqual(overall, {
            'students': 2, 'weeks': 3, 'spent': '162.50', 'transactions': 4,
            'spent_per_transaction': '40.63', 'weekly_transactions_per_student': '0.7'})

    def test_the_whole_period_figure_is_null_when_nothing_was_spent(self):
        body = self._body('ov-oa', '?programme=ov-gift2')
        self.assertIsNone(body['money_series']['per_student_overall'])

    def test_a_release_on_or_after_the_27th_is_next_months_payment(self):
        """⚠ Owner, 2026-09-15: July's money goes out on 30 June, so it must sit beside JULY's
        spending. The rule is on the day: 27th or later → next month; the 26th → this month.
        And a late payment (July's, released in September) lands in September."""
        gift = Programme.objects.create(
            organisation=self.org, code='ov-cut', name_en='Cutoff Gift')
        cohort = ScholarshipCohort.objects.create(
            code='ov-cut-2026', name='Cutoff', year=2026,
            owning_organisation=self.org, programme=gift)
        app = self._app('cut', cohort=cohort, status='awarded',
                        award_amount=Decimal('3000.00'))
        self._released(app, '100.00', _local(2026, 6, 26, 9))   # June, plainly
        self._released(app, '200.00', _local(2026, 6, 27, 9))   # the cutoff → July
        self._released(app, '300.00', _local(2026, 6, 30, 23))  # July's money, sent 30 June
        self._released(app, '400.00', _local(2026, 9, 3, 9))    # late: July's, sent in Sept
        pinned = datetime.datetime(2026, 9, 15, 4, 0, tzinfo=datetime.timezone.utc)
        months = {r['month']: r for r in programme_overview.build(
            self.oa, self.org, gift, now=pinned)['money_series']['money_per_month']}
        self.assertEqual(months['2026-06']['released'], '100.00')
        self.assertEqual(months['2026-07']['released'], '500.00')
        self.assertEqual(months['2026-08']['released'], '0.00')
        self.assertEqual(months['2026-09']['released'], '400.00')

    def test_a_release_after_the_cutoff_this_month_extends_the_series_into_next_month(self):
        """Cutting the span at today's month would DROP a release dated the 28th of this month.
        Pinned: 15 August; a release on 28 August is September's bar, so September must exist."""
        gift = Programme.objects.create(
            organisation=self.org, code='ov-cut2', name_en='Cutoff Gift 2')
        cohort = ScholarshipCohort.objects.create(
            code='ov-cut2-2026', name='Cutoff 2', year=2026,
            owning_organisation=self.org, programme=gift)
        app = self._app('cut2', cohort=cohort, status='awarded',
                        award_amount=Decimal('3000.00'))
        self._released(app, '250.00', _local(2026, 8, 28, 9))
        pinned = datetime.datetime(2026, 8, 15, 4, 0, tzinfo=datetime.timezone.utc)
        rows = programme_overview.build(
            self.oa, self.org, gift, now=pinned)['money_series']['money_per_month']
        self.assertEqual([r['month'] for r in rows], ['2026-09'])
        self.assertEqual(rows[0]['released'], '250.00')
        self.assertEqual(rows[0]['gap'], '250.00')

    def test_the_cutoff_rule_never_touches_the_money_strip(self):
        """`paid` on the strip is the Payments footer's figure, read by the release date as-is."""
        gift = Programme.objects.create(
            organisation=self.org, code='ov-cut3', name_en='Cutoff Gift 3')
        cohort = ScholarshipCohort.objects.create(
            code='ov-cut3-2026', name='Cutoff 3', year=2026,
            owning_organisation=self.org, programme=gift)
        app = self._app('cut3', cohort=cohort, status='awarded',
                        award_amount=Decimal('3000.00'))
        self._released(app, '250.00', _local(2026, 8, 28, 9))
        body = self._body('ov-oa', '?programme=ov-cut3')
        # ⚠ `Decimal`, not the string: SQLite and Postgres disagree about the places `Sum` hands
        # back (see `test_the_money_headline_equals_the_payments_footer`).
        self.assertEqual(Decimal(body['money']['paid']), Decimal('250.00'))
        footer = self._client('ov-oa').get(FUNDING + '?programme=ov-cut3').json()['totals']
        self.assertEqual(body['money']['paid'], footer['paid_total'])

    def test_the_spend_weeks_stop_at_data_to(self):
        """⚠ Extending to today would draw zeros for weeks whose file has not been imported —
        a chart that reports "they stopped spending" when it means "we stopped importing"."""
        body = self._body('ov-oa')
        self.assertEqual(body['data_to'], '2026-08-20')
        weeks = [w['week'] for w in body['money_series']['per_student_per_week']]
        self.assertEqual(weeks, ['2026-08-03', '2026-08-10', '2026-08-17'])
        this_week = timezone.localtime(timezone.now()).date()
        this_monday = this_week - datetime.timedelta(days=this_week.weekday())
        self.assertLess(datetime.date.fromisoformat(weeks[-1]), this_monday)

    def test_the_application_weeks_run_to_this_week(self):
        weeks = [w['week'] for w in
                 self._body('ov-oa')['applications_series']['applications_per_week']]
        today = timezone.localtime(timezone.now()).date()
        self.assertEqual(weeks[0], '2026-08-03')
        self.assertEqual(weeks[-1],
                         (today - datetime.timedelta(days=today.weekday())).isoformat())
        for earlier, later in zip(weeks, weeks[1:]):
            self.assertEqual(datetime.date.fromisoformat(later)
                             - datetime.date.fromisoformat(earlier),
                             datetime.timedelta(days=7))

    def test_awards_are_grouped_by_month(self):
        months = {m['month']: m['count'] for m in
                  self._body('ov-oa')['applications_series']['awards_per_month']}
        self.assertEqual(months['2026-07'], 1)

    def test_all_eleven_category_slices_are_present_and_the_blank_one_is_its_own(self):
        """⚠⚠ `unsorted` (the sorter looked and could not place it) and `none` (nothing has
        looked yet) are DIFFERENT STATES. Neither is folded into the other and neither is
        hidden at zero."""
        slices = self._body('ov-oa')['money_series']['by_category']
        codes = [s['code'] for s in slices]
        self.assertEqual(len(slices), 11)
        self.assertEqual(codes[-2:], ['unsorted', 'none'])
        self.assertEqual(len(set(codes)), 11)
        by_code = {s['code']: s for s in slices}
        self.assertEqual(by_code['none']['total'], '100.00')
        self.assertEqual(by_code['none']['transactions'], 1)
        self.assertEqual(by_code['unsorted']['total'], '20.00')
        self.assertEqual(by_code['food']['total'], '12.50')
        # A category nobody spent in is present at zero.
        self.assertEqual(by_code['hostel']['total'], '0.00')
        self.assertEqual(by_code['hostel']['transactions'], 0)

    def test_the_attention_strip_counts_the_nudge_population(self):
        attention = self._body('ov-oa')['attention']
        # Three of this reviewer's cases plus one of another reviewer's; due_soon and overdue
        # are SUBSETS of with_reviewer, never a partition of it.
        self.assertEqual(attention, {
            'unassigned': 1, 'with_reviewer': 4,
            'due_soon': 1, 'overdue': 2, 'awaiting_qc': 1})

    def test_the_intake_block_describes_the_gifts_newest_active_round(self):
        intake = self._body('ov-oa')['intake']
        self.assertEqual(intake['code'], 'ov-2026')
        self.assertTrue(intake['is_open'])
        self.assertEqual(intake['opens_on'], '2026-01-15')
        self.assertEqual(intake['closes_on'], '2026-06-30')
        self.assertIsNone(intake['finished_at'])

    def test_intake_is_null_when_no_gift_is_named(self):
        """Present and null, never quietly missing: with several gifts there is no one round."""
        body = self._body('ov-oa', '')
        self.assertIn('intake', body)
        self.assertIsNone(body['intake'])


class MineTests(_Base):
    def test_a_reviewer_sees_only_their_own_cases(self):
        mine = self._body('ov-rev')['mine']
        ids = {c['id'] for c in mine['cases']}
        self.assertEqual(ids, {self.r_soon.id, self.r_over.id, self.r_open.id})
        self.assertNotIn(self.r_other.id, ids)
        self.assertEqual(mine['open'], 3)
        self.assertEqual(mine['due_soon'], 1)
        self.assertEqual(mine['overdue'], 1)

    def test_a_case_carries_its_own_clock_and_nothing_about_the_person(self):
        cases = {c['id']: c for c in self._body('ov-rev')['mine']['cases']}
        self.assertEqual(set(cases[self.r_soon.id]),
                         {'id', 'ref', 'applicant_name', 'status',
                          'assigned_at', 'due_at', 'band'})
        self.assertEqual(cases[self.r_soon.id]['band'], 'due_soon')
        self.assertEqual(cases[self.r_over.id]['band'], 'overdue')
        self.assertEqual(cases[self.r_open.id]['band'], 'open')

    @override_settings(REVIEW_NUDGES_ENABLED=True)
    def test_the_bands_agree_with_the_nudge_sweep(self):
        """⚠ ONE FIXTURE, BOTH READERS. A case the page calls overdue is a case the sweep
        emails about — if these ever part company, a reviewer reads one story on screen and
        another in their inbox."""
        out = StringIO()
        call_command('send_review_nudges', stdout=out)
        printed = out.getvalue()
        cases = {c['id']: c['band'] for c in self._body('ov-rev')['mine']['cases']}
        self.assertEqual(cases[self.r_over.id], 'overdue')
        self.assertEqual(cases[self.r_soon.id], 'due_soon')
        soon_printed, overdue_printed = printed.split('overdue=')
        self.assertIn(str(self.r_over.id), overdue_printed)
        self.assertNotIn(str(self.r_over.id), soon_printed.split('soon=')[1])
        self.assertIn(str(self.r_soon.id), soon_printed.split('soon=')[1])
        # The untroubled case is in neither list, on the page or in the sweep.
        self.assertEqual(cases[self.r_open.id], 'open')
        self.assertNotIn(str(self.r_open.id), printed)

    def test_the_pace_is_narrowed_to_the_gift(self):
        """The same reviewer has a decided case in ANOTHER gift of the same organisation — it
        counts when no gift is named and must not when one is."""
        self.assertEqual(self._body('ov-rev')['mine']['pace']['completed'], 3)
        self.assertEqual(self._body('ov-rev', '')['mine']['pace']['completed'], 4)

    def test_the_pace_reports_a_turnaround_and_never_a_score(self):
        pace = self._body('ov-rev')['mine']['pace']
        self.assertEqual(set(pace), {'completed', 'turnaround_days'})
        self.assertIsNotNone(pace['turnaround_days'])


class QcTests(_Base):
    def test_awaiting_is_interviewed_only(self):
        qc = self._body('ov-qc')['qc']
        self.assertEqual(qc['awaiting'], 1)
        self.assertEqual([c['id'] for c in qc['cases']], [self.q_waiting.id])
        self.assertEqual(qc['cases'][0]['status'], 'interviewed')
        self.assertEqual(qc['oldest_waiting_days'], 4)

    def test_the_pace_reads_recommended_by_and_rejected_by_for_this_admin(self):
        """⚠ KEYED ON EMAIL — there is no QC stamp column, so `recommended_by` / `rejected_by`
        are the only record of who checked. A case decided by somebody else is not theirs."""
        pace = self._body('ov-qc')['qc']['pace']
        self.assertEqual(pace['completed'], 2)
        self.assertEqual(pace['turnaround_days'], 1.5)

    def test_another_checkers_work_is_not_counted(self):
        self.qc.email = 'nobody@ov.test'
        self.qc.save(update_fields=['email'])
        self.assertEqual(self._body('ov-qc')['qc']['pace']['completed'], 0)
