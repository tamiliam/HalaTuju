"""Request #28 (2026-10-06): a person-only "Micro stall" category, and "checked, still unknown".

The organisation's approved proposal, pinned from the harm each part prevents:

  * ``micro_stall`` is a REAL category, and ONLY A PERSON may assign it. If the model could answer
    it, every shop whose name says nothing would drift into it — which is exactly the "Other" the
    organisation rejected. So the model's vocabulary, prompt and schema stay byte-identical and
    ``PROMPT_VERSION`` does not move.
  * a person may deliberately mark a shop ``unsorted`` through the ordinary correction. That stores
    ``decided_by='owner'``, which is what lets the screen tell "nobody has looked" (``''``) from
    "a person looked and could not place it" (``owner``) — and the nightly sorter must leave both
    owner answers alone for ever.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.scholarship import spend_category as sc
from apps.scholarship import spend_report as sr
from apps.scholarship import spending_import as si
from apps.scholarship.models import SPEND_CATEGORY_CHOICES, BursarySpendTxn, MerchantCategory
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)

SEAM = 'apps.scholarship.vision._call_gemini_json'
WRITE_URL = '/api/v1/admin/scholarship/spending/category/'
READ_URL = '/api/v1/admin/scholarship/spending/'

#: What the model was allowed to answer BEFORE this request, written out rather than derived — a
#: derived expectation would follow the vocabulary wherever it went and prove nothing.
MODEL_ANSWERS_BEFORE = {'food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health',
                        'clothing', 'unsorted'}


def txn(app, merchant, amount, *, category='', decided_by=''):
    return BursarySpendTxn.objects.create(
        application=app, txn_id=unique_suffix('MS'), txn_date=date(2026, 8, 30),
        wallet_id=app.vircle_id, merchant=si.norm_text(merchant), amount=Decimal(str(amount)),
        duitnow_type='STATIC_MERCHANT_QR_CODE_DUITNOW', entry_type='CREDIT', tx_type='SPEND',
        status='00', category=category, decided_by=decided_by, source_file='fixture.xlsx')


def funded_app():
    return make_application(cohort=make_cohort(), vircle_id=unique_suffix('8000'))


class TestOnlyAPersonMaySayMicroStall(TestCase):

    def test_it_is_a_real_category_on_both_sides_of_the_drift_pin(self):
        self.assertIn('micro_stall', sc.CATEGORY_CODES)
        self.assertIn('micro_stall', dict(SPEND_CATEGORY_CHOICES))
        self.assertEqual(dict(SPEND_CATEGORY_CHOICES)['micro_stall'],
                         'Micro stall – no online info')

    def test_the_model_may_not_answer_it(self):
        self.assertNotIn('micro_stall', sc.AI_VOCABULARY)
        self.assertNotIn('micro_stall', sc._AI_SCHEMA['properties']['merchants']['items']
                         ['properties']['category']['enum'])

    def test_the_model_vocabulary_prompt_and_version_are_unchanged(self):
        """⚠ Byte-identical prompt and schema, so the stored `ai` answers stay current and nothing
        is re-asked (or re-billed)."""
        self.assertEqual(sc.AI_VOCABULARY, frozenset(MODEL_ANSWERS_BEFORE))
        self.assertEqual(sc._AI_SCHEMA['properties']['merchants']['items']['properties']
                         ['category']['enum'], sorted(MODEL_ANSWERS_BEFORE))
        self.assertEqual(sc.PROMPT_VERSION, 'spend-cat-v1')
        self.assertNotIn('micro', sc._build_prompt(['A SHOP']).lower())

    def test_no_keyword_rule_names_it(self):
        self.assertEqual([k for c, k in sc.KEYWORD_RULES if c == 'micro_stall'], [])

    def test_it_is_discarded_if_the_model_offers_it_anyway(self):
        with mock.patch(SEAM, return_value={'merchants': [
                {'name': 'A SHOP', 'category': 'micro_stall'}]}):
            self.assertEqual(sc.ask_model(['A SHOP']), {})


class TestTheSorterNeverOverwritesAPersonsAnswer(TestCase):
    """⚠ It already skips `owner`; this pins it for the two answers request #28 is about.

    Bite-checked 2026-10-06: TWO guards hold this — `sort_transactions` excludes owner rows, and
    `merchant_verdicts` returns a stored owner verdict first — so removing either ALONE stays green
    (each covers the other); removing both turns this test, and only this test, red."""

    def setUp(self):
        self.app = funded_app()

    def _owner(self, merchant, category):
        MerchantCategory.objects.create(merchant=merchant, category=category,
                                        decided_by=sc.BY_OWNER, decided_by_email='o@example.test')
        return txn(self.app, merchant, 5, category=category, decided_by=sc.BY_OWNER)

    def test_unsorted_and_micro_stall_survive_a_full_resort_with_the_model_on(self):
        # A keyword rule (CAFE → food) AND a model answer both stand ready to overrule them.
        checked = self._owner('DELIMA MATANG CAFE', 'unsorted')
        stall = self._owner('MAK LIMAH ENTERPRISE', 'micro_stall')
        fresh = txn(self.app, 'MAK LIMAH ENTERPRISE', 3)   # a new row at the stall, undecided
        reply = {'merchants': [{'name': 'DELIMA MATANG CAFE', 'category': 'food'},
                               {'name': 'MAK LIMAH ENTERPRISE', 'category': 'groceries'}]}
        for resort in (False, True):
            with mock.patch(SEAM, return_value=reply) as seam:
                sc.sort_transactions(apply=True, resort=resort)
            self.assertFalse(seam.called, 'an owner answer is never sent to the model')
        for row, category in ((checked, 'unsorted'), (stall, 'micro_stall'),
                              (fresh, 'micro_stall')):
            row.refresh_from_db()
            self.assertEqual((row.category, row.decided_by), (category, sc.BY_OWNER))
        self.assertEqual(
            set(MerchantCategory.objects.values_list('merchant', 'category', 'decided_by')),
            {('DELIMA MATANG CAFE', 'unsorted', 'owner'),
             ('MAK LIMAH ENTERPRISE', 'micro_stall', 'owner')})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAPersonMarksAShop(TestCase):
    """Through the EXISTING correction endpoint — no new write path."""

    def setUp(self):
        self.app = funded_app()
        self.org = self.app.owning_organisation
        self.client = authed_client(make_admin('admin', owning_org=self.org))

    def _post(self, merchant, category):
        return self.client.post(WRITE_URL, {'merchant': merchant, 'category': category},
                                format='json')

    def _merchant(self, name):
        rows = self.client.get(READ_URL).json()['merchants']
        return next(r for r in rows if r['merchant'] == name)

    def test_checked_still_unknown_is_told_apart_from_untouched(self):
        txn(self.app, 'NOBODY LOOKED', 4, category='unsorted')
        txn(self.app, 'SOMEBODY LOOKED', 4, category='unsorted')
        res = self._post('SOMEBODY LOOKED', 'unsorted')
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.json()['category'], res.json()['decided_by']), ('unsorted', 'owner'))
        untouched, checked = self._merchant('NOBODY LOOKED'), self._merchant('SOMEBODY LOOKED')
        self.assertEqual((untouched['category'], untouched['decided_by']), ('unsorted', ''))
        self.assertEqual((checked['category'], checked['decided_by']), ('unsorted', 'owner'))
        # The payoff: a shop a person has checked leaves the "to check" queue…
        self.assertEqual(sr.merchants_to_check(self.org), ['NOBODY LOOKED'])
        # …but its money is still honestly not placed.
        self.assertEqual(sr.totals(self.org)['unplaced'], Decimal('8.00'))

    def test_a_person_may_assign_micro_stall_and_it_counts_as_placed(self):
        row = txn(self.app, 'MAK LIMAH ENTERPRISE', '6.50', category='unsorted')
        res = self._post('MAK LIMAH ENTERPRISE', 'micro_stall')
        self.assertEqual(res.status_code, 200)
        row.refresh_from_db()
        self.assertEqual((row.category, row.decided_by), ('micro_stall', 'owner'))
        self.assertEqual(self._merchant('MAK LIMAH ENTERPRISE')['decided_by'], 'owner')
        self.assertEqual(sr.totals(self.org)['unplaced'], Decimal('0.00'))

    def test_the_dropdown_offers_micro_stall_and_still_offers_transfer(self):
        """Transfer stays exactly as available to a person as it was; nothing else changed."""
        codes = [c['code'] for c in self.client.get(READ_URL).json()['categories']]
        self.assertEqual(codes, list(sc.CATEGORY_CODES))
        self.assertIn('micro_stall', codes)
        self.assertIn('transfer', codes)

    def test_another_organisation_cannot_mark_this_shop(self):
        txn(self.app, 'MAK LIMAH ENTERPRISE', 4)
        other = funded_app()
        outsider = authed_client(make_admin('admin', owning_org=other.owning_organisation))
        res = outsider.post(WRITE_URL, {'merchant': 'MAK LIMAH ENTERPRISE',
                                        'category': 'micro_stall'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['code'], 'unknown_merchant')
        self.assertFalse(MerchantCategory.objects.filter(merchant='MAK LIMAH ENTERPRISE').exists())
