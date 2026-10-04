"""TD-239 — a better prompt can re-ask what an older prompt answered, and ONLY that.

`PROMPT_VERSION` is stamped on every `ai` answer. Until 2026-10-04 nothing read it, so a redesigned
prompt applied only to merchants nobody had asked about yet. `sort_transactions(reask_version=…)`
(`sort_spending --reask-version`) re-asks exactly the merchants whose stored answer carries another
version — never one of today's, never an owner's, never on a bump by itself.

Every test mocks the Gemini seam; nothing here makes a paid call. The cost claims are asserted on
the seam's CALL ARGUMENTS, because a stored value alone cannot prove what was billed.
"""
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.scholarship import spend_category as sc
from apps.scholarship.models import MerchantCategory
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_spend_category import SEAM, answer, txn

OLD = 'spend-cat-v0'


def asked_names(seam):
    """Every merchant name the mocked model was asked about, across all calls."""
    names = []
    for call in seam.call_args_list:
        prompt = call.args[0] if call.args else call.kwargs.get('prompt', '')
        names += [n for n in ('GLASSEYE EYEWEAR TRADING', 'EY VENTURE', 'NEW SHOP SDN BHD')
                  if n in str(prompt)]
    return sorted(set(names))


class TestReaskVersion(TestCase):

    def setUp(self):
        self.app = make_application(stage='awarded', vircle_id='8000400170001')
        # An answer from an OLDER prompt, and one from today's.
        MerchantCategory.objects.create(merchant='GLASSEYE EYEWEAR TRADING', category='clothing',
                                        decided_by=sc.BY_MODEL, reason=OLD)
        MerchantCategory.objects.create(merchant='EY VENTURE', category='food',
                                        decided_by=sc.BY_MODEL, reason=sc.PROMPT_VERSION)
        self.stale_row = txn(self.app, 'GLASSEYE EYEWEAR TRADING', 130,
                             category='clothing', decided_by=sc.BY_MODEL)
        self.fresh_row = txn(self.app, 'EY VENTURE', 6, category='food', decided_by=sc.BY_MODEL)

    def test_a_bump_alone_re_asks_nothing(self):
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
            sc.sort_transactions(apply=True, resort=True)
        self.assertFalse(seam.called, 'never automatic: an old answer is reused until asked')

    def test_it_re_asks_only_the_older_prompts_answer(self):
        with mock.patch(SEAM, return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})) as seam:
            report = sc.sort_transactions(apply=True, reask_version=sc.PROMPT_VERSION)
        self.assertEqual(asked_names(seam), ['GLASSEYE EYEWEAR TRADING'],
                         "today's answer (EY VENTURE) must not be paid for again")
        self.assertEqual(report.merchants_reasked, 1)
        stored = MerchantCategory.objects.get(merchant='GLASSEYE EYEWEAR TRADING')
        self.assertEqual((stored.category, stored.reason), ('health', sc.PROMPT_VERSION))
        self.stale_row.refresh_from_db()
        self.assertEqual((self.stale_row.category, self.stale_row.decided_by), ('health', sc.BY_MODEL))
        self.fresh_row.refresh_from_db()
        self.assertEqual(self.fresh_row.category, 'food')

    def test_a_second_re_ask_asks_nothing(self):
        with mock.patch(SEAM, return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})) as seam:
            sc.sort_transactions(apply=True, reask_version=sc.PROMPT_VERSION)
            sc.sort_transactions(apply=True, reask_version=sc.PROMPT_VERSION)
        self.assertEqual(seam.call_count, 1)

    def test_an_owner_verdict_is_never_re_asked(self):
        MerchantCategory.objects.filter(merchant='GLASSEYE EYEWEAR TRADING').update(
            decided_by='owner', reason=OLD)
        with mock.patch(SEAM) as seam:
            report = sc.sort_transactions(apply=True, reask_version=sc.PROMPT_VERSION)
        self.assertFalse(seam.called)
        self.assertEqual(report.merchants_reasked, 0)

    def test_a_merchant_the_new_prompt_does_not_answer_keeps_its_old_verdict(self):
        with mock.patch(SEAM, return_value={'_error': 'quota'}):
            sc.sort_transactions(apply=True, reask_version=sc.PROMPT_VERSION)
        self.stale_row.refresh_from_db()
        self.assertEqual((self.stale_row.category, self.stale_row.decided_by), ('clothing', sc.BY_MODEL))
        stored = MerchantCategory.objects.get(merchant='GLASSEYE EYEWEAR TRADING')
        self.assertEqual(stored.reason, OLD, 'an unanswered merchant is not re-stamped as new')

    def test_a_report_run_writes_nothing(self):
        with mock.patch(SEAM, return_value=answer({'GLASSEYE EYEWEAR TRADING': 'health'})):
            report = sc.sort_transactions(apply=False, reask_version=sc.PROMPT_VERSION)
        self.assertEqual(report.merchants_reasked, 1)
        self.assertEqual(MerchantCategory.objects.get(merchant='GLASSEYE EYEWEAR TRADING').reason, OLD)

    def test_a_typo_or_the_model_off_is_refused_before_anything_is_asked(self):
        with mock.patch(SEAM) as seam:
            with self.assertRaises(ValueError):
                sc.sort_transactions(apply=True, reask_version='spend-cat-v1x')
            with self.assertRaises(ValueError):
                sc.sort_transactions(apply=True, use_ai=False, reask_version=sc.PROMPT_VERSION)
            with self.assertRaises(CommandError):
                call_command('sort_spending', '--reask-version', 'nope', stdout=StringIO())
        self.assertFalse(seam.called)


class TestAReusedAnswerKeepsItsVersion(TestCase):
    """Found while building TD-239: the apply loop re-wrote every reused `ai` answer with TODAY's
    `PROMPT_VERSION`, so a new row at an old shop silently re-stamped the old answer as new — and
    the version is exactly what a re-ask reads."""

    def test_a_new_row_at_an_old_shop_does_not_re_stamp_its_answer(self):
        app = make_application(stage='awarded', vircle_id='8000400170002')
        MerchantCategory.objects.create(merchant='GLASSEYE EYEWEAR TRADING', category='clothing',
                                        decided_by=sc.BY_MODEL, reason=OLD)
        row = txn(app, 'GLASSEYE EYEWEAR TRADING', 90)
        with mock.patch(SEAM) as seam:
            sc.sort_transactions(apply=True)
        self.assertFalse(seam.called)
        row.refresh_from_db()
        self.assertEqual(row.category, 'clothing')
        self.assertEqual(MerchantCategory.objects.get(merchant='GLASSEYE EYEWEAR TRADING').reason, OLD)
