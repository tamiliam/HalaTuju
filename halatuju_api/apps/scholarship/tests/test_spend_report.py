"""The officer's spending screen — S4 (docs/plans/2026-09-10-sponsor-spending-roadmap.md).

⚠ **THE TWO TESTS THAT CARRY THIS SPRINT ARE WRITTEN FROM THE HARM, NOT FROM THE CODE:**

  * `TestTheCorrectionSticks` does NOT assert "the field was written". It asserts the promise the
    screen makes to a person: **a corrected shop survives the next full `--all` re-sort, and the
    money moves with it.** A correction that a routine sweep silently undoes would make the whole
    screen a lie, and "the row saved" is true in that world too.
  * `TestNothingIdentifyingLeaks` plants a real NRIC, phone, address, email and school on the
    fixture and asserts none of them appears in the rendered JSON. The payload is built key by key
    from plain dicts, so the guarantee is allowlist-by-construction — this proves it rather than
    promising it (the sponsor-pool serializer pattern, v2.24.0).

Merchant names below are shops. Student identifiers are invented.
"""
import datetime
import json
from decimal import Decimal
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import spend_category as sc
from apps.scholarship import spend_report as sr
from apps.scholarship import spending_import as si
from apps.scholarship.models import (
    BursarySpendTxn, MerchantCategory, Programme, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_SEQ = {'n': 0}
TEST_JWT_SECRET = 'test-supabase-jwt-secret'
SEAM = 'apps.scholarship.vision._call_gemini_json'
MERCHANT_QR = 'STATIC_MERCHANT_QR_CODE_DUITNOW'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def make_org(code):
    _SEQ['n'] += 1
    org = PartnerOrganisation.objects.create(code=f'{code}-{_SEQ["n"]}', name=code)
    programme, _ = Programme.objects.get_or_create(
        organisation=org, code=f'{org.code}-prog', defaults={'name_en': 'Bursary'})
    cohort = ScholarshipCohort.objects.create(
        code=f'{org.code}-c', name='B40', year=2026, owning_organisation=org,
        programme=programme)
    return org, cohort


def make_app(org, cohort, wallet='8000400170001', *, status='awarded', **profile_extra):
    _SEQ['n'] += 1
    i = _SEQ['n']
    profile = StudentProfile.objects.create(
        supabase_user_id=f'sr-stud-{i}', nric=f'{i:06d}-16-{i:04d}',
        name=f'Student {i}', contact_phone=f'03{i:08d}', **profile_extra)
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, owning_organisation=org, status=status,
        chosen_pathway='matric', award_amount=D('2000'), vircle_id=wallet)


def txn(app, merchant, amount, *, when=None, category='', decided_by='', duitnow=MERCHANT_QR):
    _SEQ['n'] += 1
    return BursarySpendTxn.objects.create(
        application=app, txn_id=f'S{_SEQ["n"]:08d}', txn_date=when or datetime.date(2026, 8, 30),
        wallet_id=app.vircle_id, merchant=si.norm_text(merchant), amount=D(str(amount)),
        duitnow_type=duitnow, entry_type='CREDIT', tx_type='SPEND', status='00',
        category=category, decided_by=decided_by, source_file='fixture.xlsx')


# ── the figures ───────────────────────────────────────────────────────────────

class TestTotals(TestCase):

    def setUp(self):
        self.org, self.cohort = make_org('tot')
        self.app = make_app(self.org, self.cohort)

    def test_an_organisation_with_no_spending_reads_zero_not_a_crash(self):
        """⚠ A percentage over an empty set is a division by zero, and 100% would be a lie."""
        t = sr.totals(self.org)
        self.assertEqual(t['spent'], D('0.00'))
        self.assertEqual(t['placed_pct'], 0)

    def test_the_split_is_computed_and_adds_up(self):
        txn(self.app, 'DELIMA MATANG CAFE', 30, category='food', decided_by='rule')
        txn(self.app, 'EY VENTURE', 70, category='unsorted', decided_by='')
        t = sr.totals(self.org)
        self.assertEqual(t['spent'], D('100.00'))
        self.assertEqual(t['placed'], D('30.00'))
        self.assertEqual(t['unplaced'], D('70.00'))
        self.assertEqual(t['placed'] + t['unplaced'], t['spent'])
        self.assertEqual(t['placed_pct'], 30)

    def test_never_sorted_and_unsorted_both_count_as_not_placed(self):
        """They are DIFFERENT states and neither is an answer a sponsor could read."""
        txn(self.app, 'A SHOP', 10, category='', decided_by='')
        txn(self.app, 'B SHOP', 10, category='unsorted', decided_by='')
        self.assertEqual(sr.totals(self.org)['unplaced'], D('20.00'))


class TestMerchantRows(TestCase):

    def setUp(self):
        self.org, self.cohort = make_org('mer')
        self.app = make_app(self.org, self.cohort)

    def test_one_row_per_shop_with_the_money_and_the_visits(self):
        txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
        txn(self.app, 'DELIMA MATANG CAFE', 7, category='food', decided_by='rule')
        txn(self.app, '99 SPEEDMART', 40, category='groceries', decided_by='rule')
        rows = {r['merchant']: r for r in sr.merchant_rows(self.org)}
        self.assertEqual(rows['DELIMA MATANG CAFE']['visits'], 2)
        self.assertEqual(rows['DELIMA MATANG CAFE']['total'], D('12.00'))
        self.assertEqual(rows['99 SPEEDMART']['visits'], 1)

    def test_the_biggest_spend_is_first(self):
        txn(self.app, 'SMALL', 5, category='food', decided_by='rule')
        txn(self.app, 'BIG', 500, category='food', decided_by='rule')
        self.assertEqual([r['merchant'] for r in sr.merchant_rows(self.org)][0], 'BIG')

    def test_last_seen_is_a_date_and_can_never_carry_a_time(self):
        """⚠ The hour was discarded at import, deliberately and for ever. No sponsor may ever be
        able to see what time a student ate, so the column is a DateField and this is structural."""
        txn(self.app, 'A SHOP', 5, when=datetime.date(2026, 7, 1), category='food',
            decided_by='rule')
        txn(self.app, 'A SHOP', 5, when=datetime.date(2026, 8, 30), category='food',
            decided_by='rule')
        row = sr.merchant_rows(self.org)[0]
        self.assertEqual(row['last_seen'], datetime.date(2026, 8, 30))
        self.assertNotIsInstance(row['last_seen'], datetime.datetime)

    def test_the_stored_merchant_verdict_wins_over_the_rows(self):
        MerchantCategory.objects.create(
            merchant='A SHOP', category='study', decided_by='owner', decided_by_email='o@x.com')
        txn(self.app, 'A SHOP', 5, category='food', decided_by='rule')
        row = sr.merchant_rows(self.org)[0]
        self.assertEqual((row['category'], row['decided_by']), ('study', 'owner'))

    def test_held_back_counts_the_rows_the_ceiling_kept_out_of_food(self):
        """⚠ The RM424 across six real payments. Surfacing it is the point: those rows are honestly
        unsorted and an officer is the only one who can place them."""
        MerchantCategory.objects.create(
            merchant='AL HUDHA ENTERPRISE', category='food', decided_by='inferred')
        for _ in range(8):
            txn(self.app, 'AL HUDHA ENTERPRISE', '7.20', category='food', decided_by='inferred')
        txn(self.app, 'AL HUDHA ENTERPRISE', '200.00', category='unsorted', decided_by='')
        row = sr.merchant_rows(self.org)[0]
        self.assertEqual(row['held_back'], 1)

    def test_held_back_is_silent_for_a_shop_the_ceiling_had_nothing_to_do_with(self):
        """Repeating the count for a plainly-unknown shop would read as "the ceiling did this",
        which is a claim about a mechanism that never ran."""
        MerchantCategory.objects.create(
            merchant='EY VENTURE', category='unsorted', decided_by='ai')
        txn(self.app, 'EY VENTURE', 5, category='unsorted', decided_by='ai')
        row = sr.merchant_rows(self.org)[0]
        self.assertEqual(row['held_back'], 0)


class TestModelDecisions(TestCase):

    def setUp(self):
        self.org, self.cohort = make_org('mod')
        self.app = make_app(self.org, self.cohort)

    def test_it_lists_what_the_model_decided_lately(self):
        MerchantCategory.objects.create(
            merchant='EY VENTURE', category='groceries', decided_by='ai', reason='spend-cat-v1')
        txn(self.app, 'EY VENTURE', 5, category='groceries', decided_by='ai')
        rows = sr.model_decisions(self.org)
        self.assertEqual([r['merchant'] for r in rows], ['EY VENTURE'])
        self.assertEqual(rows[0]['reason'], 'spend-cat-v1')

    def test_a_rule_or_an_owner_verdict_is_not_the_model_s_work(self):
        MerchantCategory.objects.create(
            merchant='DELIMA MATANG CAFE', category='food', decided_by='rule')
        txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
        self.assertEqual(sr.model_decisions(self.org), [])

    def test_an_old_decision_falls_out_of_the_window(self):
        m = MerchantCategory.objects.create(
            merchant='EY VENTURE', category='groceries', decided_by='ai')
        txn(self.app, 'EY VENTURE', 5, category='groceries', decided_by='ai')
        MerchantCategory.objects.filter(pk=m.pk).update(
            decided_at=timezone.now() - datetime.timedelta(days=sr.MODEL_REVIEW_DAYS + 1))
        self.assertEqual(sr.model_decisions(self.org), [])


class TestWalletGaps(TestCase):

    def setUp(self):
        self.org, self.cohort = make_org('wal')

    def test_a_funded_student_with_no_wallet_is_named(self):
        app = make_app(self.org, self.cohort, '')
        self.assertEqual(sr.wallet_gaps(self.org)['students_without_wallet'], [app.id])

    def test_a_finished_student_needs_no_wallet(self):
        make_app(self.org, self.cohort, '', status='closed')
        self.assertEqual(sr.wallet_gaps(self.org)['students_without_wallet'], [])

    def test_a_wallet_claimed_by_two_students_is_named(self):
        a = make_app(self.org, self.cohort, '8000400170001')
        b = make_app(self.org, self.cohort, '8000400170001')
        gaps = sr.wallet_gaps(self.org)
        self.assertEqual(gaps['shared_wallets'], {'8000400170001': sorted([a.id, b.id])})


# ── the correction ────────────────────────────────────────────────────────────

class TestTheCorrectionSticks(TestCase):
    """⚠⚠ THE PROMISE THE SCREEN MAKES: what you change is kept for good.

    Asserting "the row saved" would pass in a world where the next nightly sweep quietly undoes
    it. These tests assert the thing a person actually relies on."""

    def setUp(self):
        self.org, self.cohort = make_org('cor')
        self.app = make_app(self.org, self.cohort)

    def test_a_correction_moves_every_payment_at_that_shop(self):
        rows = [txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
                for _ in range(3)]
        changed, err = sr.set_owner_category('DELIMA MATANG CAFE', 'study', 'o@x.com', self.org)
        self.assertIsNone(err)
        self.assertEqual(changed, 3)
        for row in rows:
            row.refresh_from_db()
            self.assertEqual((row.category, row.decided_by), ('study', 'owner'))

    def test_a_correction_survives_a_full_resort(self):
        """⚠ THE WHOLE POINT. A keyword rule says this shop is food; the officer says study.
        Running the sorter over everything must leave the officer's answer standing."""
        row = txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
        sr.set_owner_category('DELIMA MATANG CAFE', 'study', 'o@x.com', self.org)
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True, resort=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('study', 'owner'))

    def test_a_correction_also_claims_the_payments_THAT_HAVE_NOT_ARRIVED_YET(self):
        """⚠⚠ FOUND BY A SILENT BITE-CHECK, 2026-09-10.

        Setting only the ROWS looks identical in every other test: the existing payments move and
        they survive a re-sort, because `decided_by='owner'` takes them out of the sweep. But the
        shop is visited every week. If the MERCHANT verdict is not also `owner`, next week's
        payment arrives undecided, the ladder re-decides it from a keyword rule, and the officer's
        answer quietly stops applying — to a shop they have already fixed, with nothing failing
        and nothing to see.

        This is the promise the screen actually makes, and it was the half nothing asserted.
        """
        # A shop can only be corrected once it has been visited — that is the fence on the write.
        txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
        _, err = sr.set_owner_category('DELIMA MATANG CAFE', 'study', 'o@x.com', self.org)
        self.assertIsNone(err)
        later = txn(self.app, 'DELIMA MATANG CAFE', 5)      # arrives next week, undecided
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True)
        later.refresh_from_db()
        self.assertEqual((later.category, later.decided_by), ('study', 'owner'),
                         'a new payment at a corrected shop must inherit the correction')
        stored = MerchantCategory.objects.get(merchant='DELIMA MATANG CAFE')
        self.assertEqual(stored.decided_by, 'owner',
                         "the MERCHANT verdict is what makes that true - not the rows")

    def test_the_totals_move_with_it(self):
        txn(self.app, 'DELIMA MATANG CAFE', 40, category='unsorted', decided_by='')
        self.assertEqual(sr.totals(self.org)['unplaced'], D('40.00'))
        sr.set_owner_category('DELIMA MATANG CAFE', 'study', 'o@x.com', self.org)
        after = sr.totals(self.org)
        self.assertEqual(after['unplaced'], D('0.00'))
        self.assertEqual(after['placed_pct'], 100)

    def test_the_email_is_recorded_so_a_correction_has_an_author(self):
        txn(self.app, 'A SHOP', 5)
        sr.set_owner_category('A SHOP', 'study', 'officer@example.com', self.org)
        stored = MerchantCategory.objects.get(merchant='A SHOP')
        self.assertEqual(stored.decided_by_email, 'officer@example.com')

    def test_an_over_long_email_is_capped_to_its_column(self):
        """⚠ A plain Serializer does not inherit a model's max_length, and an over-long value is
        an atomic rollback ("could not save"), not a clean refusal."""
        txn(self.app, 'A SHOP', 5)
        sr.set_owner_category('A SHOP', 'study', 'x' * 400, self.org)
        self.assertEqual(len(MerchantCategory.objects.get(merchant='A SHOP').decided_by_email), 254)

    def test_an_unknown_category_is_refused_not_silently_ignored(self):
        txn(self.app, 'A SHOP', 5)
        changed, err = sr.set_owner_category('A SHOP', 'petrol', 'o@x.com', self.org)
        self.assertEqual((changed, err), (0, 'unknown_category'))
        self.assertFalse(MerchantCategory.objects.exists())

    def test_a_blank_merchant_is_refused(self):
        self.assertEqual(sr.set_owner_category('  ', 'food', 'o@x.com', self.org)[1],
                         'merchant_required')


# ── the fence ─────────────────────────────────────────────────────────────────

class TestTheFenceIsOnTheQuery(TestCase):
    """⚠ A ROW question, not a field question. An allowlist protects a column and does nothing
    about a row (TD-201)."""

    def setUp(self):
        self.org_a, self.cohort_a = make_org('fen-a')
        self.org_b, self.cohort_b = make_org('fen-b')
        self.app_a = make_app(self.org_a, self.cohort_a, '8000400170001')
        self.app_b = make_app(self.org_b, self.cohort_b, '8000400170002')
        txn(self.app_a, 'SHOP A', 10, category='food', decided_by='rule')
        txn(self.app_b, 'SHOP B', 99, category='food', decided_by='rule')

    def test_one_tenant_never_sees_the_other_s_money(self):
        self.assertEqual(sr.totals(self.org_a)['spent'], D('10.00'))
        self.assertEqual(sr.totals(self.org_b)['spent'], D('99.00'))

    def test_one_tenant_never_sees_the_other_s_shops(self):
        self.assertEqual([r['merchant'] for r in sr.merchant_rows(self.org_a)], ['SHOP A'])

    def test_one_tenant_never_sees_the_other_s_students(self):
        self.assertEqual([r['application_id'] for r in sr.student_rows(self.org_a)],
                         [self.app_a.id])

    def test_a_tenant_cannot_correct_a_shop_it_has_never_used(self):
        """⚠ The verdict is GLOBAL by design, so the fence has to be on who may SET it — otherwise
        any tenant's admin could write a verdict for any shop on the platform by guessing a name."""
        changed, err = sr.set_owner_category('SHOP B', 'study', 'a@x.com', self.org_a)
        self.assertEqual((changed, err), (0, 'unknown_merchant'))
        self.assertFalse(MerchantCategory.objects.filter(merchant='SHOP B').exists())

    def test_the_model_decision_list_is_fenced_even_though_the_table_is_global(self):
        MerchantCategory.objects.create(merchant='SHOP B', category='food', decided_by='ai')
        self.assertEqual(sr.model_decisions(self.org_a), [])
        self.assertEqual([r['merchant'] for r in sr.model_decisions(self.org_b)], ['SHOP B'])


class TestThePlatformScope(TestCase):
    """`ALL_ORGS` — the second scope, added S6 (2026-09-11) because a super was refused by their
    own console. Everything here is about the ONE property that makes it safe to exist."""

    def setUp(self):
        self.org_a, self.cohort_a = make_org('all-a')
        self.org_b, self.cohort_b = make_org('all-b')
        self.app_a = make_app(self.org_a, self.cohort_a, '8000400170001')
        self.app_b = make_app(self.org_b, self.cohort_b, '8000400170002')
        txn(self.app_a, 'SHOP A', 10, category='food', decided_by='rule')
        txn(self.app_b, 'SHOP B', 99, category='food', decided_by='rule')

    def test_it_pools_every_tenant(self):
        self.assertEqual(sr.totals(sr.ALL_ORGS)['spent'], D('109.00'))
        self.assertEqual(sorted(r['merchant'] for r in sr.merchant_rows(sr.ALL_ORGS)),
                         ['SHOP A', 'SHOP B'])
        self.assertEqual(sorted(r['application_id'] for r in sr.student_rows(sr.ALL_ORGS)),
                         sorted([self.app_a.id, self.app_b.id]))

    def test_it_pools_the_wallet_gaps_too(self):
        """The gaps read a DIFFERENT queryset from `_txns`, so widening one and forgetting the
        other would give a super a platform table above a single tenant's fault list."""
        make_app(self.org_a, self.cohort_a, wallet='')
        make_app(self.org_b, self.cohort_b, wallet='')
        self.assertEqual(len(sr.wallet_gaps(sr.ALL_ORGS)['students_without_wallet']), 2)
        self.assertEqual(len(sr.wallet_gaps(self.org_a)['students_without_wallet']), 1)

    def test_a_super_may_correct_a_shop_from_any_tenant(self):
        changed, err = sr.set_owner_category('SHOP B', 'study', 's@x.com', sr.ALL_ORGS)
        self.assertEqual((changed, err), (1, None))
        self.assertEqual(MerchantCategory.objects.get(merchant='SHOP B').decided_by, 'owner')

    def test_a_super_still_cannot_invent_a_shop(self):
        """The platform scope widens WHOSE shops are listed. It is not a free-text write."""
        self.assertEqual(sr.set_owner_category('NO SUCH SHOP', 'food', 's@x.com', sr.ALL_ORGS),
                         (0, 'unknown_merchant'))

    def test_None_is_NOT_the_platform_scope_and_still_reads_nothing(self):
        """⚠⚠ THE WHOLE REASON `ALL_ORGS` IS A SENTINEL OBJECT AND NOT `None`.

        Every accident that loses an organisation — an unset attribute, a missed keyword, a
        `.get()` on a dict — hands `None` to these functions. That must stay an EMPTY read
        (`owning_organisation=None` matches applications belonging to no organisation), never a
        silent widening to every tenant. If somebody ever "simplifies" the sentinel away to
        `None`, this test is what fails.
        """
        self.assertEqual(sr.totals(None)['spent'], D('0.00'))
        self.assertEqual(sr.merchant_rows(None), [])
        self.assertEqual(sr.student_rows(None), [])
        self.assertEqual(sr.wallet_gaps(None)['students_without_wallet'], [])
        self.assertEqual(sr.set_owner_category('SHOP A', 'food', 's@x.com', None),
                         (0, 'unknown_merchant'))


# ── the endpoints ─────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _EndpointBase(TestCase):
    URL = '/api/v1/admin/scholarship/spending/'
    WRITE_URL = '/api/v1/admin/scholarship/spending/category/'

    def setUp(self):
        self.org, self.cohort = make_org('ep')
        self.app = make_app(self.org, self.cohort)
        self.client = APIClient()
        self.admin = PartnerAdmin.objects.create(
            supabase_user_id='ep-admin', role='admin', is_active=True,
            owning_organisation=self.org, name='Admin', email='adm@x.com')

    def auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


class TestTheEndpointServesTheScreen(_EndpointBase):

    def test_it_returns_every_section_the_page_draws(self):
        txn(self.app, 'DELIMA MATANG CAFE', 5, category='food', decided_by='rule')
        self.auth('ep-admin')
        body = self.client.get(self.URL).json()
        for key in ('totals', 'merchants', 'students', 'model_decisions', 'wallet_gaps',
                    'categories'):
            self.assertIn(key, body, key)

    def test_money_is_a_string_never_a_float(self):
        """⚠ It is summed, compared against a released total and shown to a person."""
        txn(self.app, 'A SHOP', '12.30', category='food', decided_by='rule')
        self.auth('ep-admin')
        body = self.client.get(self.URL).json()
        self.assertEqual(body['totals']['spent'], '12.30')
        self.assertIsInstance(body['merchants'][0]['total'], str)

    def test_the_category_list_comes_from_the_model_so_the_dropdown_cannot_drift(self):
        self.auth('ep-admin')
        codes = [c['code'] for c in self.client.get(self.URL).json()['categories']]
        self.assertEqual(codes, list(sc.CATEGORY_CODES))

    def test_a_correction_through_the_endpoint_moves_the_rows(self):
        row = txn(self.app, 'A SHOP', 5, category='food', decided_by='rule')
        self.auth('ep-admin')
        res = self.client.post(self.WRITE_URL, {'merchant': 'A SHOP', 'category': 'study'},
                               format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['rows_changed'], 1)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('study', 'owner'))

    def test_the_correction_records_the_signed_in_officer(self):
        txn(self.app, 'A SHOP', 5)
        self.auth('ep-admin')
        self.client.post(self.WRITE_URL, {'merchant': 'A SHOP', 'category': 'study'},
                         format='json')
        self.assertEqual(MerchantCategory.objects.get(merchant='A SHOP').decided_by_email,
                         'adm@x.com')

    def test_a_bad_category_is_a_400_with_a_code(self):
        txn(self.app, 'A SHOP', 5)
        self.auth('ep-admin')
        res = self.client.post(self.WRITE_URL, {'merchant': 'A SHOP', 'category': 'petrol'},
                               format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 'unknown_category')


class TestWhoMayOpenIt(_EndpointBase):
    """⚠ `finance` is absent BY DECISION. `_b40_scope` promises a finance admin never sees student
    data beyond the Payments allowlist, and this screen carries names beside purchases."""

    def _admin(self, uid, role):
        PartnerAdmin.objects.create(
            supabase_user_id=uid, role=role, is_active=True,
            owning_organisation=self.org, name=role, email=f'{uid}@x.com')

    def test_an_officer_may(self):
        for uid, role in (('ep-oa', 'org_admin'),):
            self._admin(uid, role)
            self.auth(uid)
            self.assertEqual(self.client.get(self.URL).status_code, 200, role)

    def test_a_reviewer_a_qc_a_partner_and_finance_may_not(self):
        for uid, role in (('ep-rev', 'reviewer'), ('ep-qc', 'qc'),
                          ('ep-part', 'partner'), ('ep-fin', 'finance')):
            self._admin(uid, role)
            self.auth(uid)
            self.assertEqual(self.client.get(self.URL).status_code, 403, role)
            self.assertEqual(
                self.client.post(self.WRITE_URL, {'merchant': 'A SHOP', 'category': 'food'},
                                 format='json').status_code, 403, role)

    def test_a_stranger_may_not(self):
        """401, not 403: no token is "who are you?", a wrong role is "not you"."""
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_a_super_with_no_organisation_sees_the_platform(self):
        """⚠ **REVERSED IN PLACE, 2026-09-11 (S6).** This test used to assert the opposite — a
        super with no organisation got `400 no_org` — on the S4a reasoning that "defaulting to
        unfenced is how every tenant's students happens by accident". That reasoning is about a
        DEFAULT, and the scope is now an explicit sentinel that `_spending_admin` alone hands out.
        The owner opened their own console as super, was refused, and asked for the platform view
        (`docs/decisions.md`, 2026-09-11). **Do not "restore" the refusal** — the property that
        replaced it is `test_None_is_NOT_the_platform_scope_and_still_reads_nothing`.
        """
        PartnerAdmin.objects.create(
            supabase_user_id='ep-super', is_super_admin=True, is_active=True,
            name='Super', email='s@x.com')
        self.auth('ep-super')
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertIn('totals', res.json())

    def test_a_tenant_admin_sees_ONLY_their_own_tenant_through_the_endpoint(self):
        """⚠⚠ **THIS TEST EXISTS BECAUSE A BITE-CHECK FOUND ITS ABSENCE (S6, 2026-09-11).**

        `TestTheFenceIsOnTheQuery` proves `spend_report` fences a scope it is GIVEN. Nothing
        proved the VIEW gives it the right one. Widening `_spending_admin` to hand every caller
        `ALL_ORGS` failed only the orphan-account test above — an org_admin WITH an organisation
        would have seen every tenant's students' purchases, through the endpoint, silently, with
        a green suite. That is the exact fault adding a second scope can introduce, so the
        property is now asserted where it lives: at the door.
        """
        other_org, other_cohort = make_org('ep-other')
        other_app = make_app(other_org, other_cohort, '8000400179999')
        StudentProfile.objects.filter(pk=other_app.profile_id).update(
            name='SOMEBODY ELSES STUDENT')
        txn(other_app, 'ANOTHER TENANTS SHOP', 500, category='food', decided_by='rule')
        txn(self.app, 'MY OWN SHOP', 7, category='food', decided_by='rule')

        self.auth('ep-admin')
        body = self.client.get(self.URL).json()
        self.assertEqual(body['totals']['spent'], '7.00')
        self.assertEqual([m['merchant'] for m in body['merchants']], ['MY OWN SHOP'])
        rendered = json.dumps(body)
        self.assertNotIn('ANOTHER TENANTS SHOP', rendered)
        self.assertNotIn('SOMEBODY ELSES STUDENT', rendered)

    def test_an_org_admin_with_no_organisation_still_gets_no_org(self):
        """⚠ THE HALF THAT DID NOT CHANGE. Widening the super's scope must not turn a broken
        account — an org_admin whose organisation was never set — into a platform reader."""
        PartnerAdmin.objects.create(
            supabase_user_id='ep-orphan', role='org_admin', is_active=True,
            name='Orphan', email='o@x.com')
        self.auth('ep-orphan')
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 'no_org')


class TestNothingIdentifyingLeaks(_EndpointBase):
    """⚠⚠ PROVEN, NOT PROMISED. A real NRIC, phone, address, email and school are planted and
    asserted ABSENT from the rendered JSON. The student NAME is present on purpose — this is the
    officer's own organisation's students on an admin-only surface."""

    PLANTED = {
        'nric': '880101-14-5501',
        'contact_phone': '0139998888',
        'address': '12 Jalan Rahsia, Taman Sulit',
        'contact_email': 'secret.student@example.com',
        'school': 'SMK Sangat Sulit',
    }

    def test_no_planted_identifier_reaches_the_payload(self):
        import json

        profile = self.app.profile
        for field, value in self.PLANTED.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        profile.name = 'Nurul Test'
        profile.save()
        txn(self.app, 'A SHOP', 5, category='food', decided_by='rule')

        self.auth('ep-admin')
        body = json.dumps(self.client.get(self.URL).json())
        for field, value in self.PLANTED.items():
            self.assertNotIn(value, body, f'{field} leaked into the officer payload')
        # `StudentProfile` normalises the name to upper case on save, so match that, not my typing.
        self.assertIn('NURUL TEST', body.upper(),
                      'the student name is shown to the officer on purpose')

    def test_the_wallet_id_never_reaches_the_payload_either(self):
        """The screen answers "what was bought", never "which account". The wallet is an alert's
        business, and an alert goes to staff by email, not onto a page."""
        import json

        txn(self.app, 'A SHOP', 5, category='food', decided_by='rule')
        self.auth('ep-admin')
        body = json.dumps(self.client.get(self.URL).json())
        self.assertNotIn('8000400170001', body)
