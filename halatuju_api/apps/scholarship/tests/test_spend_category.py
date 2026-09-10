"""The four-rung spending sorter — S3 (docs/plans/2026-09-10-sponsor-spending-roadmap.md).

⚠ **THE TESTS THAT MATTER MOST HERE ARE WRITTEN FROM THE HARM, NOT FROM THE CODE.** Two guards in
this sprint would pass a lazy test while completely broken, so each is pinned by what goes wrong
when it is deleted:

  * the RM20 per-row ceiling — `TestTheCeilingByName` names `AL HUDHA ENTERPRISE`'s RM200 and
    `TEGUH ENIGMA (MATRIK 1)`'s RM97.70, the two real payments a merchant-level verdict would have
    filed as campus meals;
  * "a merchant is asked about once" — `TestTheModelIsNeverAskedTwice` asserts the CALL COUNT of
    the Gemini seam, because a stored answer that is still re-asked is a silent bill and the
    stored value alone proves nothing.

Merchant names below are shops, not people we hold records on. The real corpus lives outside the
repo; the test that reads it SKIPS when it is absent, so CI never depends on it.
"""
import inspect
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import spend_category as sc
from apps.scholarship import spending_import as si
from apps.scholarship.models import (
    SPEND_CATEGORY_CHOICES, BursarySpendTxn, MerchantCategory, Programme,
    ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_SEQ = {'n': 0}

CORPUS_DIR = r'C:\Users\tamil\Downloads\spending'

SEAM = 'apps.scholarship.vision._call_gemini_json'
MERCHANT_QR = 'STATIC_MERCHANT_QR_CODE_DUITNOW'


def make_app(wallet='8000400170001'):
    _SEQ['n'] += 1
    i = _SEQ['n']
    org = PartnerOrganisation.objects.create(code=f'sortbp{i}', name='BrightPath')
    programme, _ = Programme.objects.get_or_create(
        organisation=org, code=f'{org.code}-prog', defaults={'name_en': 'Bursary'})
    cohort = ScholarshipCohort.objects.create(
        code=f'{org.code}-c', name='B40', year=2026, owning_organisation=org,
        programme=programme)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'sort-stud-{i}', nric=f'{i:06d}-15-{i:04d}',
        name=f'Student {i}', contact_phone=f'02{i:08d}')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, owning_organisation=org, status='awarded',
        chosen_pathway='matric', award_amount=D('2000'), vircle_id=wallet)


def txn(app, merchant, amount, *, txn_id=None, duitnow=MERCHANT_QR, tx='SPEND',
        category='', decided_by=''):
    _SEQ['n'] += 1
    return BursarySpendTxn.objects.create(
        application=app, txn_id=txn_id or f'T{_SEQ["n"]:08d}', txn_date=date(2026, 8, 30),
        wallet_id=app.vircle_id, merchant=si.norm_text(merchant), amount=D(str(amount)),
        duitnow_type=duitnow, entry_type='CREDIT', tx_type=tx, status='00',
        is_person_transfer=duitnow == si.DUITNOW_P2P,
        category=category, decided_by=decided_by, source_file='fixture.xlsx')


def answer(pairs):
    """Build a fake seam reply: `{'SHOP': 'food'}` → the JSON the model would return."""
    return {'merchants': [{'name': n, 'category': c} for n, c in pairs.items()]}


# ── the vocabulary ────────────────────────────────────────────────────────────

class TestVocabulary(TestCase):
    """The ten codes are declared twice - here and on the model - so pin them together."""

    def test_the_module_vocabulary_is_exactly_the_model_choices(self):
        self.assertEqual(sc.CATEGORY_CODES, tuple(c for c, _ in SPEND_CATEGORY_CHOICES))

    def test_the_model_may_never_answer_transfer(self):
        """⚠ 'Sent to a person' comes from duitnow_type, never from a name. Half the real
        merchants are registered under an individual's name."""
        self.assertNotIn('transfer', sc.AI_VOCABULARY)

    def test_no_keyword_rule_may_produce_transfer(self):
        self.assertEqual([k for c, k in sc.KEYWORD_RULES if c == 'transfer'], [])

    def test_every_keyword_rule_names_a_real_category(self):
        for category, keyword in sc.KEYWORD_RULES:
            self.assertIn(category, sc.CATEGORY_CODES, keyword)

    def test_no_keyword_is_listed_twice(self):
        keywords = [k for _c, k in sc.KEYWORD_RULES]
        self.assertEqual(sorted(keywords), sorted(set(keywords)),
                         'a duplicated keyword means one of the two rules is unreachable')


# ── rung 2 ────────────────────────────────────────────────────────────────────

class TestKeywordRules(TestCase):
    """Rung 2, checked against merchant names that really appear in the exports."""

    def test_it_places_the_obvious_ones(self):
        for name, expected in [
            ("ENGINEER'S KITCHEN", 'food'),
            ('DELIMA MATANG CAFE', 'food'),
            ('RESTORAN NASI KANDAR BHARKAT', 'food'),
            ('99 SPEEDMART', 'groceries'),
            ('ECONSAVE PDS', 'groceries'),
            ('PASARAYA HUP KAY', 'groceries'),
            ("WATSON'S", 'health'),
            ('SAYAGIN APPAREL', 'clothing'),
        ]:
            self.assertEqual(sc.rule_category(name), expected, name)

    def test_the_two_non_obvious_rules_the_brief_asked_for(self):
        """A campus co-op is the campus shop; KTMB is the national railway. Neither name says so."""
        self.assertEqual(sc.rule_category('KOPERASI UTEM MELAKA BERHAD'), 'study')
        self.assertEqual(sc.rule_category('KTESI KOOP-QR'), 'study')
        self.assertEqual(sc.rule_category('KTMB'), 'transport')

    def test_matching_is_whole_word_not_substring(self):
        """⚠ A substring rule would file an accounting firm as groceries: SMART contains MART."""
        self.assertIsNone(
            sc.rule_category('GTB - QR POS SMART-ACC SOLUTIONS SDN BHD'))
        self.assertIsNone(sc.rule_category('GRABBIT ENTERPRISE'))
        self.assertNotEqual(sc.rule_category('919 KOPITIAM'), 'study')

    def test_order_is_load_bearing_food_outranks_the_petrol_station(self):
        """⚠ A doughnut counter inside a BHP station is food, not a bus fare."""
        self.assertEqual(sc.rule_category("DUNKIN' - BHP KARAK"), 'food')

    def test_a_personal_name_is_placed_by_nothing(self):
        for name in ('SYAHIR AZHAR', 'FAIZUL BIN HAT', 'HASLIZA BINTI ABDUL KHAIR'):
            self.assertIsNone(sc.rule_category(name), name)

    def test_it_normalises_before_matching(self):
        self.assertEqual(sc.rule_category('  delima   matang  cafe '), 'food')


# ── rung 3 ────────────────────────────────────────────────────────────────────

class TestSpendPattern(TestCase):
    """Rung 3: small amounts, visited often. Pure - no database needed."""

    def test_stats_are_per_merchant(self):
        stats = sc.merchant_stats([('A SHOP', D('2')), ('A SHOP', D('4')), ('A SHOP', D('6')),
                                   ('B SHOP', D('50'))])
        self.assertEqual(stats['A SHOP'].visits, 3)
        self.assertEqual(stats['A SHOP'].median, D('4'))
        self.assertEqual(stats['B SHOP'].visits, 1)

    def test_two_visits_is_a_coincidence_not_a_pattern(self):
        stats = sc.merchant_stats([('X', D('3')), ('X', D('3'))])
        self.assertFalse(sc.merchant_looks_like_food(stats.get('X')))

    def test_an_expensive_regular_is_not_a_food_stall(self):
        stats = sc.merchant_stats([('X', D('40'))] * 5)
        self.assertFalse(sc.merchant_looks_like_food(stats.get('X')))

    def test_a_cheap_regular_is_food(self):
        stats = sc.merchant_stats([('X', D('5'))] * 5)
        self.assertTrue(sc.merchant_looks_like_food(stats.get('X')))
        self.assertEqual(sc.inferred_category(stats['X'], D('5')), 'food')

    def test_an_unknown_merchant_is_placed_by_nothing(self):
        self.assertFalse(sc.merchant_looks_like_food(None))
        self.assertIsNone(sc.inferred_category(None, D('5')))


class TestTheCeilingByName(TestCase):
    """⚠⚠ THE TWO REAL CASES THE CEILING EXISTS FOR.

    Both shops ARE food stalls by every other measure. A merchant-level verdict would have swept
    their one large payment along with the small ones - RM320 filed as campus meals, silently.
    Deleting `ROW_CEILING` must turn these red while the small rows stay green.
    """

    def test_al_hudha_enterprise_rm200_is_not_a_meal(self):
        stats = sc.merchant_stats([('AL HUDHA ENTERPRISE', D('7.20'))] * 8
                                  + [('AL HUDHA ENTERPRISE', D('200.00'))])
        shop = stats['AL HUDHA ENTERPRISE']
        self.assertTrue(sc.merchant_looks_like_food(shop), 'the shop still looks like food')
        self.assertEqual(sc.inferred_category(shop, D('7.20')), 'food')
        self.assertIsNone(sc.inferred_category(shop, D('200.00')))

    def test_teguh_enigma_matrik_1_rm97_70_is_not_a_meal(self):
        stats = sc.merchant_stats([('TEGUH ENIGMA (MATRIK 1)', D('0.80'))] * 4
                                  + [('TEGUH ENIGMA (MATRIK 1)', D('97.70'))])
        shop = stats['TEGUH ENIGMA (MATRIK 1)']
        self.assertTrue(sc.merchant_looks_like_food(shop))
        self.assertEqual(sc.inferred_category(shop, D('0.80')), 'food')
        self.assertIsNone(sc.inferred_category(shop, D('97.70')))

    def test_a_row_exactly_on_the_ceiling_is_still_food(self):
        stats = sc.merchant_stats([('X', D('5'))] * 5)
        self.assertEqual(sc.inferred_category(stats['X'], sc.ROW_CEILING), 'food')
        self.assertIsNone(sc.inferred_category(stats['X'], sc.ROW_CEILING + D('0.01')))


# ── rung 4 ────────────────────────────────────────────────────────────────────

class TestTheModelSeesOnlyNames(TestCase):
    """⚠⚠ THE PRIVACY WALL IS STRUCTURAL, NOT A PROMPT INSTRUCTION."""

    def test_ask_model_takes_a_list_of_names_and_nothing_else(self):
        """A wall the code cannot cross beats a prompt asking it not to. If this test is being
        changed to admit a second parameter, that parameter is the leak."""
        self.assertEqual(list(inspect.signature(sc.ask_model).parameters), ['names'])

    def test_the_prompt_carries_the_names_the_version_and_no_money(self):
        prompt = sc._build_prompt(['GLASSEYE EYEWEAR TRADING', 'IBIBO (REDBUS)'])
        self.assertIn('GLASSEYE EYEWEAR TRADING', prompt)
        self.assertIn(sc.PROMPT_VERSION, prompt)
        self.assertNotIn('RM', prompt)

    def test_the_prompt_offers_no_category_outside_the_vocabulary(self):
        prompt = sc._build_prompt(['X'])
        for code in sc.CATEGORY_CODES:
            if code in sc.AI_VOCABULARY:
                self.assertIn(code, prompt, code)
            else:
                self.assertNotIn(code, prompt, code)


class TestTheModelsAnswerIsFiltered(TestCase):
    """⚠ The vocabulary is enforced in PYTHON, after the answer returns - never re-prompted."""

    def test_a_category_outside_the_list_is_discarded(self):
        with mock.patch(SEAM, return_value=answer({'A SHOP': 'petrol', 'B SHOP': 'food'})):
            self.assertEqual(sc.ask_model(['A SHOP', 'B SHOP']), {'B SHOP': 'food'})

    def test_transfer_is_discarded_even_if_the_model_offers_it(self):
        with mock.patch(SEAM, return_value=answer({'A SHOP': 'transfer'})):
            self.assertEqual(sc.ask_model(['A SHOP']), {})

    def test_a_name_we_did_not_ask_about_is_discarded(self):
        with mock.patch(SEAM, return_value=answer({'SOMETHING ELSE': 'food'})):
            self.assertEqual(sc.ask_model(['A SHOP']), {})

    def test_a_model_failure_stores_nothing(self):
        """⚠ An outage is not a category. Filing these as `unsorted` would store the outage as an
        answer for ever and they would never be asked again."""
        with mock.patch(SEAM, return_value={'_error': 'quota'}):
            self.assertEqual(sc.ask_model(['A SHOP']), {})

    def test_names_are_sent_in_batches(self):
        names = [f'SHOP {i}' for i in range(sc.AI_BATCH_SIZE * 2 + 1)]
        with mock.patch(SEAM, return_value={'merchants': []}) as seam:
            sc.ask_model(names)
        self.assertEqual(seam.call_count, 3)


# ── the ladder over stored rows ───────────────────────────────────────────────

class TestTheLadder(TestCase):

    def setUp(self):
        self.app = make_app()

    def test_a_person_transfer_is_decided_by_the_bank_code_not_the_name(self):
        """⚠ The merchant here is a personal name AND the row is a P2P transfer."""
        row = txn(self.app, 'SYAHIR AZHAR', 20, duitnow=si.DUITNOW_P2P, tx='RECEIVED')
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('transfer', sc.BY_DUITNOW))
        self.assertFalse(seam.called, 'a person is never sent to the model')

    def test_a_keyword_rule_beats_everything_below_it(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('food', sc.BY_RULE))
        self.assertFalse(seam.called)

    def test_the_pattern_places_a_shop_whose_name_says_nothing(self):
        rows = [txn(self.app, 'BACHOK MAJU ENTERPRISE', 4) for _ in range(4)]
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
        for row in rows:
            row.refresh_from_db()
            self.assertEqual((row.category, row.decided_by), ('food', sc.BY_INFERENCE))
        self.assertFalse(seam.called, 'rung 3 placed it, so rung 4 must not be paid for it')

    def test_the_ceiling_applies_to_the_transaction_not_the_shop(self):
        """⚠⚠ The whole reason rung 3 is per-transaction. Same shop, two verdicts."""
        small = [txn(self.app, 'AL HUDHA ENTERPRISE', '7.20') for _ in range(8)]
        big = txn(self.app, 'AL HUDHA ENTERPRISE', '200.00')
        with mock.patch(SEAM):
            report = sc.sort_transactions(apply=True)
        for row in small:
            row.refresh_from_db()
            self.assertEqual(row.category, 'food')
        big.refresh_from_db()
        self.assertEqual((big.category, big.decided_by), ('unsorted', ''))
        self.assertEqual(report.rows_over_ceiling, 1)

    def test_a_leftover_goes_to_the_model(self):
        row = txn(self.app, 'GLASSEYE EYEWEAR TRADING', 130)
        with mock.patch(SEAM, return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})):
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('health', sc.BY_MODEL))
        stored = MerchantCategory.objects.get(merchant='GLASSEYE EYEWEAR TRADING')
        self.assertEqual(stored.reason, sc.PROMPT_VERSION,
                         'the prompt version is stamped so a redesign is visible')

    def test_a_leftover_the_model_cannot_place_is_honestly_unsorted(self):
        row = txn(self.app, 'EY VENTURE', 5.7)
        with mock.patch(SEAM, return_value=answer({'EY VENTURE': 'unsorted'})):
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual(row.category, 'unsorted')

    def test_nothing_placed_it_and_the_model_was_off(self):
        row = txn(self.app, 'EY VENTURE', 5.7)
        with mock.patch(SEAM) as seam:
            report = sc.sort_transactions(apply=True, use_ai=False)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('unsorted', ''))
        self.assertFalse(seam.called)
        self.assertEqual(report.rows_unsorted, 1)

    def test_the_pattern_is_read_from_every_row_we_hold_not_from_this_batch(self):
        """⚠ THE HARM: the weekly run sorts a handful of NEW rows. If the visit history were
        counted from that batch instead of from the whole table, a stall visited forty times would
        look like a first visit every single week and nothing would ever be inferred."""
        for _ in range(4):
            txn(self.app, 'BACHOK MAJU ENTERPRISE', 4)
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True)
        fresh = txn(self.app, 'BACHOK MAJU ENTERPRISE', 4)
        with mock.patch(SEAM) as seam:
            report = sc.sort_transactions(apply=True)
        self.assertEqual(report.rows_considered, 1, 'only the new row is in scope')
        fresh.refresh_from_db()
        self.assertEqual((fresh.category, fresh.decided_by), ('food', sc.BY_INFERENCE))
        self.assertFalse(seam.called)

    def test_a_shop_whose_typical_visit_is_large_is_not_a_food_stall(self):
        rows = [txn(self.app, 'KAJOL NSN MAJU ENTERPRISE', 40) for _ in range(4)]
        with mock.patch(SEAM, return_value={'merchants': []}):
            sc.sort_transactions(apply=True)
        for row in rows:
            row.refresh_from_db()
            self.assertEqual(row.category, 'unsorted')

    def test_every_row_lands_in_exactly_one_rung(self):
        """⚠ The counts must add up. An aggregate that does not print what it could not place
        reports a smaller, entirely plausible number - this corpus cost us RM621 that way once."""
        txn(self.app, 'DELIMA MATANG CAFE', 5)
        txn(self.app, 'SYAHIR AZHAR', 3, duitnow=si.DUITNOW_P2P)
        for _ in range(4):
            txn(self.app, 'BACHOK MAJU ENTERPRISE', 4)
        txn(self.app, 'EY VENTURE', 5.7)
        with mock.patch(SEAM, return_value={'merchants': []}):
            report = sc.sort_transactions(apply=True)
        self.assertEqual(report.rows_considered, 7)
        self.assertEqual(sum(report.by_rung.values()), report.rows_considered)


class TestOwnerOutranksEverything(TestCase):

    def setUp(self):
        self.app = make_app()

    def test_an_owner_row_is_left_alone_even_by_a_full_resort(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5, category='study', decided_by='owner')
        with mock.patch(SEAM):
            report = sc.sort_transactions(apply=True, resort=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('study', 'owner'),
                         'a keyword rule must not overwrite a person')
        self.assertEqual(report.owner_rows_untouched, 1)

    def test_an_owner_merchant_verdict_beats_a_keyword_rule(self):
        MerchantCategory.objects.create(
            merchant='DELIMA MATANG CAFE', category='study', decided_by='owner',
            decided_by_email='owner@example.com')
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('study', 'owner'))

    def test_an_owner_merchant_row_is_never_rewritten(self):
        MerchantCategory.objects.create(
            merchant='DELIMA MATANG CAFE', category='study', decided_by='owner',
            decided_by_email='owner@example.com')
        txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True)
        stored = MerchantCategory.objects.get(merchant='DELIMA MATANG CAFE')
        self.assertEqual((stored.category, stored.decided_by), ('study', 'owner'))


class TestTheModelIsNeverAskedTwice(TestCase):
    """⚠⚠ THE COST DESIGN. Asserted on the CALL COUNT, not on the stored value - a stored answer
    that is still re-asked is a silent bill that nothing else in the suite would notice."""

    def setUp(self):
        self.app = make_app()

    def test_a_second_run_asks_nothing(self):
        txn(self.app, 'GLASSEYE EYEWEAR TRADING', 130)
        with mock.patch(SEAM,
                        return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})) as seam:
            sc.sort_transactions(apply=True)
            self.assertEqual(seam.call_count, 1)
            sc.sort_transactions(apply=True, resort=True)
            self.assertEqual(seam.call_count, 1, 'the stored answer must be reused')

    def test_a_new_row_at_a_known_shop_asks_nothing(self):
        txn(self.app, 'GLASSEYE EYEWEAR TRADING', 130)
        with mock.patch(SEAM,
                        return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})) as seam:
            sc.sort_transactions(apply=True)
            row = txn(self.app, 'GLASSEYE EYEWEAR TRADING', 90)
            sc.sort_transactions(apply=True)
            self.assertEqual(seam.call_count, 1)
        row.refresh_from_db()
        self.assertEqual(row.category, 'health')

    def test_a_new_keyword_rule_is_re_derived_over_a_stored_answer(self):
        """A rule is deterministic and free, so it is recomputed every run - which is how a newly
        added rule reaches merchants an earlier run had already stored."""
        MerchantCategory.objects.create(
            merchant='DELIMA MATANG CAFE', category='clothing', decided_by='ai')
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('food', sc.BY_RULE))
        self.assertFalse(seam.called)


class TestReportModeCannotWrite(TestCase):

    def setUp(self):
        self.app = make_app()

    def test_a_report_run_changes_nothing(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            report = sc.sort_transactions(apply=False)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('', ''))
        self.assertEqual(MerchantCategory.objects.count(), 0)
        self.assertFalse(report.applied)
        self.assertEqual(report.rows_considered, 1)

    def test_a_second_run_only_looks_at_undecided_rows(self):
        done = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            sc.sort_transactions(apply=True)
        fresh = txn(self.app, '99 SPEEDMART', 12)
        with mock.patch(SEAM):
            report = sc.sort_transactions(apply=True)
        self.assertEqual(report.rows_considered, 1)
        fresh.refresh_from_db()
        done.refresh_from_db()
        self.assertEqual(fresh.category, 'groceries')
        self.assertEqual(done.category, 'food')


# ── the commands ──────────────────────────────────────────────────────────────

class TestCommandWiring(TestCase):

    def setUp(self):
        self.app = make_app()

    def test_sort_spending_is_report_only_by_default(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            call_command('sort_spending')
        row.refresh_from_db()
        self.assertEqual(row.category, '')

    def test_sort_spending_apply_writes(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5)
        with mock.patch(SEAM):
            call_command('sort_spending', '--apply')
        row.refresh_from_db()
        self.assertEqual(row.category, 'food')

    def test_sort_spending_no_ai_makes_no_model_call(self):
        txn(self.app, 'EY VENTURE', 5.7)
        with mock.patch(SEAM) as seam:
            call_command('sort_spending', '--apply', '--no-ai')
        self.assertFalse(seam.called)

    def test_sort_spending_all_reconsiders_a_decided_row(self):
        row = txn(self.app, 'DELIMA MATANG CAFE', 5, category='unsorted', decided_by='ai')
        with mock.patch(SEAM):
            call_command('sort_spending', '--apply', '--all')
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('food', sc.BY_RULE))


class TestIngestRunsTheSorter(TestCase):
    """⚠ The daily job must stay ONE Cloud Scheduler entry, so `ingest_spending --apply` finishes
    by running the ladder. A report run must still be unable to write."""

    def setUp(self):
        self.app = make_app()

    def _values(self):
        header = ['transaction_date', 'wallet_id', 'transaction_id', 'Wallet User', 'Child User',
                  'Merchant Name', 'duitnow_type', 'Entry Type', 'TX Type', 'amount', 'Status']
        row = ['30 Aug 2026', self.app.vircle_id, 'TX-SORT-1', 'Test Holder', 'null',
               'DELIMA MATANG CAFE', MERCHANT_QR, 'CREDIT', 'SPEND', 5, '00']
        return [header, row]

    def _run(self, *flags):
        values = self._values()
        with mock.patch('apps.scholarship.sheets.spending_reports_in',
                        return_value=[('f1', 'r.xlsx', None)]), \
             mock.patch('apps.scholarship.sheets.read_spending_report', return_value=values), \
             mock.patch(SEAM):
            call_command('ingest_spending', '--drive', '--no-email', *flags)

    def test_an_apply_run_sorts_what_it_stored(self):
        self._run('--apply')
        stored = BursarySpendTxn.objects.get(txn_id='TX-SORT-1')
        self.assertEqual((stored.category, stored.decided_by), ('food', sc.BY_RULE))

    def test_no_sort_opts_out(self):
        self._run('--apply', '--no-sort')
        stored = BursarySpendTxn.objects.get(txn_id='TX-SORT-1')
        self.assertEqual((stored.category, stored.decided_by), ('', ''))

    def test_a_report_run_stores_nothing_and_sorts_nothing(self):
        existing = txn(self.app, 'DELIMA MATANG CAFE', 5)
        self._run()
        self.assertFalse(BursarySpendTxn.objects.filter(txn_id='TX-SORT-1').exists())
        existing.refresh_from_db()
        self.assertEqual(existing.category, '', 'a report run must not write a category either')


class TestTheSorterHasADoor(TestCase):
    """⚠ A command that can only run on a laptop with no database is finished and unreachable,
    which from the outside looks exactly like finished (BrightPath #20). Tuning a keyword rule is
    worth nothing if the re-sort cannot reach production."""

    def test_the_resort_job_is_registered_with_its_flags(self):
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['spending-sort'],
                         ('sort_spending', ('--all', '--apply')))

    def test_the_cron_endpoint_can_actually_invoke_it(self):
        """Checking the registry entry is not the same as checking it RUNS."""
        with self.settings(CRON_SECRET='test-secret'):
            with mock.patch(SEAM):
                res = self.client.post('/api/v1/internal/cron/spending-sort/',
                                       data='{}', content_type='application/json',
                                       HTTP_X_CRON_SECRET='test-secret')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('error', res.json())

    def test_the_door_never_touches_an_owner_row(self):
        """⚠ The registered flags include `--all`. If that ever came to mean "everything", a
        person's correction would be erased by a routine re-sort."""
        app = make_app()
        row = txn(app, 'DELIMA MATANG CAFE', 5, category='study', decided_by='owner')
        with self.settings(CRON_SECRET='test-secret'):
            with mock.patch(SEAM):
                self.client.post('/api/v1/internal/cron/spending-sort/',
                                 data='{}', content_type='application/json',
                                 HTTP_X_CRON_SECRET='test-secret')
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('study', 'owner'))


# ── the real corpus ───────────────────────────────────────────────────────────

class TestRealCorpusSorting(TestCase):
    """The acceptance criterion, over the eight real exports when this machine has them.

    ⚠ SKIPS when the folder is absent - the corpus carries student names and wallet ids and is
    never committed. The figures below were measured with the shipped rules on 2026-09-10.
    """

    def _rows(self):
        import glob
        paths = sorted(p for p in glob.glob(os.path.join(CORPUS_DIR, '*.xlsx'))
                       if not os.path.basename(p).startswith('~$'))
        seen = {}
        for path in paths:
            rows, _ = si.rows_from_xlsx(path)
            for row in rows:
                if row.amount is not None and row.txn_date is not None:
                    seen.setdefault(row.txn_id, row)
        return list(seen.values())

    def test_the_ladder_places_what_it_measured(self):
        if not os.path.isdir(CORPUS_DIR):
            self.skipTest('real corpus not present on this machine')
        rows = self._rows()
        if not rows:
            self.skipTest('no .xlsx in the corpus folder')

        stats = sc.merchant_stats([(r.merchant, r.amount) for r in rows if r.is_spend])
        merchants = sorted({r.merchant for r in rows if not r.is_person_transfer and r.merchant})

        by_rule = [m for m in merchants if sc.rule_category(m)]
        by_pattern = [m for m in merchants
                      if not sc.rule_category(m) and sc.merchant_looks_like_food(stats.get(m))]
        leftover = [m for m in merchants
                    if m not in set(by_rule) and m not in set(by_pattern)]

        self.assertEqual(len(merchants), 288, 'distinct merchants')
        self.assertEqual(len(by_rule), 126, 'rung 2 - keyword rules')
        self.assertEqual(len(by_pattern), 60, 'rung 3 - spend pattern')
        self.assertEqual(len(leftover), 102, 'rung 4 - what the model is asked')
        self.assertEqual(len(by_rule) + len(by_pattern) + len(leftover), len(merchants))

    def test_the_two_real_outliers_are_kept_out_of_food(self):
        """⚠⚠ Not a synthetic fixture - these are the actual payments in the actual exports."""
        if not os.path.isdir(CORPUS_DIR):
            self.skipTest('real corpus not present on this machine')
        rows = self._rows()
        if not rows:
            self.skipTest('no .xlsx in the corpus folder')
        stats = sc.merchant_stats([(r.merchant, r.amount) for r in rows if r.is_spend])

        for name, big in (('AL HUDHA ENTERPRISE', D('200.00')),
                          ('TEGUH ENIGMA (MATRIK 1)', D('97.70'))):
            shop = stats.get(name)
            self.assertIsNotNone(shop, name)
            self.assertTrue(sc.merchant_looks_like_food(shop), f'{name} does look like food')
            self.assertIsNone(sc.inferred_category(shop, big),
                              f'{name} RM{big} must never be filed as a meal')
