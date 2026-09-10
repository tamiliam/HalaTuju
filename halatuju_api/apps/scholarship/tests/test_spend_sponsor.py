"""What a sponsor may see about their student's spending — S5.

⚠⚠ **THE TEST THAT CARRIES THIS FILE IS `TestNothingIdentifyingReachesASponsor`.** It plants a real
merchant name, a real transaction id, a real wallet id and a real purchase DATE on the fixture and
asserts that none of them appears anywhere in the payload — the same shape that proves the
sponsor-pool serializers, and for the same reason: a guarantee that is promised rather than tested
is a guarantee until somebody adds a field.

The other two that matter:
  * `TestOtherNeverSwallowsTheHonestOnes` — `transfer` and `unsorted` must keep their own rows
    however small (owner, 2026-09-10). Folding them into "Other" is quietly dropping the two
    categories the sponsor most needs to see honestly.
  * `TestSpentCanExceedReleased` — the wallet is the student's own and a parent may top it up. The
    arithmetic must not go negative and nothing may imply the student overspent our money.
"""
import datetime
import json
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import spend_sponsor as sp
from apps.scholarship import spending_import as si
from apps.scholarship.models import (
    SPEND_CATEGORY_CHOICES, BursarySpendTxn, Programme, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_SEQ = {'n': 0}
LABELS = dict(SPEND_CATEGORY_CHOICES)


def make_app(award='2000', **profile_extra):
    _SEQ['n'] += 1
    i = _SEQ['n']
    org = PartnerOrganisation.objects.create(code=f'spn{i}', name='BrightPath')
    programme, _ = Programme.objects.get_or_create(
        organisation=org, code=f'{org.code}-prog', defaults={'name_en': 'Bursary'})
    cohort = ScholarshipCohort.objects.create(
        code=f'{org.code}-c', name='B40', year=2026, owning_organisation=org, programme=programme)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'spn-stud-{i}', nric=f'{i:06d}-18-{i:04d}',
        name=f'Student {i}', contact_phone=f'05{i:08d}', **profile_extra)
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, owning_organisation=org, status='awarded',
        chosen_pathway='matric', award_amount=D(award), vircle_id='8000400170001')


def txn(app, merchant, amount, category, *, when=None, txn_id=None, tx='SPEND'):
    _SEQ['n'] += 1
    return BursarySpendTxn.objects.create(
        application=app, txn_id=txn_id or f'V{_SEQ["n"]:08d}',
        txn_date=when or datetime.date(2026, 8, 30), wallet_id=app.vircle_id,
        merchant=si.norm_text(merchant), amount=D(str(amount)),
        duitnow_type='STATIC_MERCHANT_QR_CODE_DUITNOW', entry_type='CREDIT', tx_type=tx,
        status='00', category=category, decided_by='rule', source_file='r.xlsx')


# ── the ranked list ───────────────────────────────────────────────────────────

class TestCategoryRows(TestCase):
    """Pure — no database, nothing identifying can even reach it."""

    def test_it_ranks_by_value(self):
        rows = sp.category_rows(
            [('food', D('10')), ('groceries', D('50')), ('transport', D('30'))], LABELS)
        self.assertEqual([r['code'] for r in rows], ['groceries', 'transport', 'food'])

    def test_a_category_with_no_money_is_absent_not_zero(self):
        rows = sp.category_rows([('food', D('10')), ('phone', D('0'))], LABELS)
        self.assertEqual([r['code'] for r in rows], ['food'])

    def test_everything_past_the_top_six_folds_into_other(self):
        pairs = [(c, D(str(100 - i))) for i, c in enumerate(
            ['food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing'])]
        rows = sp.category_rows(pairs, LABELS)
        self.assertEqual(rows[-1]['code'], 'other')
        self.assertEqual(len([r for r in rows if r['code'] != 'other']), sp.TOP_SLICES)

    def test_other_carries_the_folded_total(self):
        pairs = [(c, D(str(100 - i))) for i, c in enumerate(
            ['food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing'])]
        rows = sp.category_rows(pairs, LABELS)
        other = [r for r in rows if r['code'] == 'other'][0]
        # Values run 100, 99 … 93; the top six are kept, so `health` (94) and `clothing` (93) fold.
        self.assertEqual(other['total'], D('94.00') + D('93.00'))

    def test_there_is_no_other_row_when_nothing_folded(self):
        rows = sp.category_rows([('food', D('10')), ('groceries', D('5'))], LABELS)
        self.assertEqual([r['code'] for r in rows], ['food', 'groceries'])


class TestOtherNeverSwallowsTheHonestOnes(TestCase):
    """⚠⚠ OWNER RULING, 2026-09-10. `transfer` is money sent to a person — the one line a careful
    sponsor most needs to see — and `unsorted` is what stops the other nine reading as complete
    when they are not. Neither may be hidden inside "Other", however small."""

    def _crowded(self, extra):
        pairs = [(c, D(str(100 - i))) for i, c in enumerate(
            ['food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing'])]
        return sp.category_rows(pairs + extra, LABELS)

    def test_a_tiny_transfer_keeps_its_own_row(self):
        rows = self._crowded([('transfer', D('0.50'))])
        self.assertIn('transfer', [r['code'] for r in rows])

    def test_a_tiny_unsorted_keeps_its_own_row(self):
        rows = self._crowded([('unsorted', D('0.50'))])
        self.assertIn('unsorted', [r['code'] for r in rows])

    def test_both_survive_together_and_other_still_exists(self):
        rows = self._crowded([('transfer', D('0.50')), ('unsorted', D('0.25'))])
        codes = [r['code'] for r in rows]
        self.assertIn('transfer', codes)
        self.assertIn('unsorted', codes)
        self.assertIn('other', codes)

    def test_the_kept_rows_are_always_ordered_by_value(self):
        """⚠ A bite-check proved an earlier post-loop re-sort could never change anything: the
        ranked list is already ordered and the loop appends in that order. The ORDER still has to
        hold, so it is asserted here - on the property, not on the line that used to claim it."""
        rows = self._crowded([('transfer', D('0.50'))])
        totals = [r['total'] for r in rows if r['code'] != 'other']
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_two_categories_on_the_same_amount_keep_a_stable_order(self):
        """The tie-break is the LABEL - what a reader sees - and it must not wobble between runs."""
        pairs = [('transport', D('50')), ('groceries', D('50')), ('food', D('50'))]
        once = [r['code'] for r in sp.category_rows(pairs, LABELS)]
        twice = [r['code'] for r in sp.category_rows(list(reversed(pairs)), LABELS)]
        self.assertEqual(once, twice)
        # Labels, not codes: 'Food & drink' < 'Groceries' < 'Transport'.
        self.assertEqual(once, ['food', 'groceries', 'transport'])

    def test_they_are_still_absent_when_they_have_no_money(self):
        rows = self._crowded([])
        self.assertNotIn('transfer', [r['code'] for r in rows])


# ── the four numbers ──────────────────────────────────────────────────────────

class TestTheFourNumbers(TestCase):

    def test_nothing_imported_means_NO_CARD_not_an_empty_one(self):
        """⚠ Four zeroes and an empty donut would claim the student has spent nothing. The likelier
        truth is that no report has reached us yet, and we may not make the first claim."""
        self.assertIsNone(sp.sponsor_card(make_app()))

    def test_spent_is_the_sum_of_the_spend_rows(self):
        app = make_app()
        txn(app, 'A SHOP', 30, 'food')
        txn(app, 'B SHOP', 70, 'groceries')
        self.assertEqual(sp.sponsor_card(app)['spent'], '100.00')

    def test_promised_is_the_award(self):
        app = make_app(award='2500')
        txn(app, 'A SHOP', 10, 'food')
        self.assertEqual(sp.sponsor_card(app)['promised'], '2500.00')

    def test_money_never_reaches_a_sponsor_as_a_float(self):
        """⚠⚠ WRITTEN IN BLOOD. A bare `Decimal` in a plain dict is rendered by DRF as a FLOAT,
        so 30.00 went out as 30.0. The values ARE Decimals inside this function, so an
        `isinstance(..., Decimal)` assertion here stayed green the whole time - only a test
        driving the real endpoint saw it. Money crosses the boundary as a STRING."""
        app = make_app()
        txn(app, 'A SHOP', '12.30', 'food')
        card = sp.sponsor_card(app)
        for key in ('promised', 'released', 'spent', 'left'):
            self.assertIsInstance(card[key], str, key)
        self.assertEqual(card['spent'], '12.30')
        # And nothing anywhere in the payload is a float, however nested.
        def floats(node):
            if isinstance(node, float):
                return [node]
            if isinstance(node, dict):
                return [f for v in node.values() for f in floats(v)]
            if isinstance(node, list):
                return [f for v in node for f in floats(v)]
            return []
        self.assertEqual(floats(card), [])

    def test_a_non_spend_row_is_not_counted_as_spending(self):
        app = make_app()
        txn(app, 'A SHOP', 30, 'food')
        txn(app, 'SOMEBODY', 500, 'transfer', tx='RECEIVED')
        self.assertEqual(sp.sponsor_card(app)['spent'], '30.00')


class TestSpentCanExceedReleased(TestCase):
    """⚠ NOT A BUG. The wallet is the student's own and a parent may top it up; we cannot tell our
    ringgit from theirs."""

    def test_left_floors_at_zero_and_never_goes_negative(self):
        app = make_app()
        txn(app, 'A SHOP', 900, 'food')          # released is 0 — no disbursements
        card = sp.sponsor_card(app)
        self.assertEqual(card['spent'], '900.00')
        self.assertEqual(card['left'], '0.00')

    def test_the_card_still_renders_every_figure(self):
        app = make_app()
        txn(app, 'A SHOP', 900, 'food')
        card = sp.sponsor_card(app)
        for key in ('promised', 'released', 'spent', 'left', 'as_at', 'categories'):
            self.assertIn(key, card)


# ── the stamp ─────────────────────────────────────────────────────────────────

class TestTheAsAtStampIsTheImportNotThePurchase(TestCase):
    """⚠⚠ They look interchangeable and are not. The newest `txn_date` is *the day this student
    last bought something* — a transaction date wearing a different hat. `imported_at` answers the
    question the stamp actually asks: how fresh is this?"""

    def test_it_does_not_track_the_newest_purchase_date(self):
        app = make_app()
        txn(app, 'A SHOP', 10, 'food', when=datetime.date(2026, 7, 4))
        card = sp.sponsor_card(app)
        self.assertNotEqual(card['as_at'], '2026-07-04')

    def test_it_is_the_date_of_the_newest_import(self):
        from django.utils import timezone
        app = make_app()
        txn(app, 'A SHOP', 10, 'food', when=datetime.date(2026, 7, 4))
        self.assertEqual(sp.sponsor_card(app)['as_at'], timezone.localtime().date().isoformat())

    def test_the_stamp_is_the_date_in_MALAYSIA_not_in_UTC(self):
        """⚠⚠ FOUND BY THE CLOCK ROLLING PAST MIDNIGHT MID-DEPLOY, 2026-09-11.

         is stored UTC. A bare  on it is YESTERDAY for the eight hours
        between midnight MYT and 08:00 MYT - so a sponsor opening the card over breakfast would be
        told the figures were "as at" the day before, every single morning. Nothing else would
        ever have caught it; the suite happened to run at 00:0x MYT.
        """
        from django.utils import timezone
        from apps.scholarship.models import BursarySpendTxn
        app = make_app()
        row = txn(app, 'A SHOP', 10, 'food')
        # 16:30 UTC = 00:30 the NEXT day in Malaysia (UTC+8).
        utc_evening = datetime.datetime(2026, 9, 10, 16, 30, tzinfo=datetime.timezone.utc)
        BursarySpendTxn.objects.filter(pk=row.pk).update(imported_at=utc_evening)
        stamp = sp.sponsor_card(app)['as_at']
        self.assertEqual(stamp, timezone.localtime(utc_evening).date().isoformat())
        self.assertEqual(stamp, '2026-09-11', 'the Malaysian date, not the UTC one')


# ── the wall ──────────────────────────────────────────────────────────────────

class TestNothingIdentifyingReachesASponsor(TestCase):
    """⚠⚠ PROVEN, NOT PROMISED. A real merchant, transaction id, wallet id and purchase date are
    planted and asserted ABSENT. The payload is built one aggregate at a time, so a field added to
    `BursarySpendTxn` tomorrow cannot reach a sponsor unless somebody writes a line for it — and
    if they do, this fails."""

    MERCHANT = 'DELIMA MATANG CAFE'
    TXN_ID = 'VIRCLE-TXN-7788991'
    WALLET = '8000400170001'
    PURCHASE_DATE = datetime.date(2026, 7, 4)

    def setUp(self):
        self.app = make_app()
        txn(self.app, self.MERCHANT, 30, 'food',
            when=self.PURCHASE_DATE, txn_id=self.TXN_ID)
        txn(self.app, 'PALANI MINI MART', 70, 'groceries', when=self.PURCHASE_DATE)
        self.card = sp.sponsor_card(self.app)
        self.blob = json.dumps(self.card, default=str)

    def test_no_merchant_name(self):
        self.assertNotIn(self.MERCHANT, self.blob)
        self.assertNotIn('PALANI', self.blob)

    def test_no_transaction_id(self):
        self.assertNotIn(self.TXN_ID, self.blob)

    def test_no_wallet_id(self):
        self.assertNotIn(self.WALLET, self.blob)

    def test_no_purchase_date(self):
        self.assertNotIn(self.PURCHASE_DATE.isoformat(), self.blob)

    def test_no_student_name_and_no_application_id(self):
        self.assertNotIn(self.app.profile.name, self.blob)
        self.assertNotIn(f'"{self.app.id}"', self.blob)

    def test_no_payment_COUNT_per_category(self):
        """A count is a shape of the week — how often they shopped — and the ruling is categories
        and TOTALS. The officer screen has counts; this one may not."""
        for row in self.card['categories']:
            self.assertEqual(set(row), {'code', 'label', 'total'}, row)

    def test_the_keys_are_exactly_the_agreed_ones(self):
        """⚠ A new key here is a decision, not an accident. If this fails because a field was
        added, the question to answer is whether a SPONSOR may see it."""
        self.assertEqual(set(self.card),
                         {'promised', 'released', 'spent', 'left', 'as_at', 'categories'})
