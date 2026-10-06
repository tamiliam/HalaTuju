"""Request #28 follow-up (2026-10-06): flag a shop for review, with a notes log.

What each test holds, from the harm it prevents:

  * the flow — open → note → close → reopen — keeps ONE log, oldest first, and a note is required
    every time (a flag says why; so does clearing one);
  * ⚠ TENANCY: a flag is ONE organisation's. Another organisation reads exactly what it would
    read if nobody had flagged the shop, cannot write to a shop its students never used, and never
    finds a word of the notes anywhere in its own spending payload;
  * a flag moves NO money: category, chart and totals are byte-identical either side of it;
  * the page's `flagged` costs one query however many flags there are.
"""
import json
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship import spending_import as si
from apps.scholarship.models import BursarySpendTxn, MerchantCategory, MerchantFlag, MerchantFlagNote
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)

FLAG_URL = '/api/v1/admin/scholarship/spending/flag/'
READ_URL = '/api/v1/admin/scholarship/spending/'
#: No timestamp, id, amount, email or shop name can contain this.
SECRET = 'QQZX-private-note-about-the-stall-QQZX'


def txn(app, merchant, amount=5, category='unsorted'):
    return BursarySpendTxn.objects.create(
        application=app, txn_id=unique_suffix('MF'), txn_date=date(2026, 8, 30),
        wallet_id=app.vircle_id, merchant=si.norm_text(merchant), amount=Decimal(str(amount)),
        duitnow_type='STATIC_MERCHANT_QR_CODE_DUITNOW', entry_type='CREDIT', tx_type='SPEND',
        status='00', category=category, decided_by='', source_file='fixture.xlsx')


def funded_app():
    return make_application(cohort=make_cohort(), vircle_id=unique_suffix('8000'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):

    def setUp(self):
        self.app_a = funded_app()
        self.app_b = funded_app()
        self.org_a = self.app_a.owning_organisation
        self.org_b = self.app_b.owning_organisation
        txn(self.app_a, 'SHARED STALL', 4)        # both organisations' students shop here
        txn(self.app_b, 'SHARED STALL', 7)
        txn(self.app_a, 'ONLY A SHOP', 3, category='food')
        self.a = authed_client(make_admin('org_admin', owning_org=self.org_a))
        self.b = authed_client(make_admin('org_admin', owning_org=self.org_b))

    def post(self, client, action, note, merchant='SHARED STALL', url=FLAG_URL):
        return client.post(url, {'merchant': merchant, 'action': action, 'note': note},
                           format='json')

    def read(self, client, merchant='SHARED STALL'):
        return client.get(FLAG_URL, {'merchant': merchant})


class TestTheFlow(_Base):

    def test_open_note_close_reopen_is_one_log_oldest_first(self):
        r = self.post(self.a, 'open', '  Name looks like a person, not a shop.  ')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['flagged'])
        self.assertEqual(r.json()['notes'][0]['body'], 'Name looks like a person, not a shop.')
        self.assertTrue(self.post(self.a, 'note', 'Asked the student.').json()['flagged'])
        closed = self.post(self.a, 'close', 'It is her aunt\'s stall; fine.')
        self.assertEqual(closed.status_code, 200)
        self.assertFalse(closed.json()['flagged'])
        reopened = self.post(self.a, 'open', 'Seen again in September.')
        self.assertTrue(reopened.json()['flagged'])

        log = self.read(self.a).json()
        self.assertEqual(log['merchant'], 'SHARED STALL')
        self.assertTrue(log['flagged'])
        self.assertEqual([n['kind'] for n in log['notes']], ['open', 'note', 'close', 'open'])
        self.assertEqual(log['notes'][-1]['body'], 'Seen again in September.')
        self.assertTrue(all(n['author'].endswith('@example.test') and n['at']
                            for n in log['notes']))
        # Reopening continued the SAME flag; nothing was deleted.
        self.assertEqual(MerchantFlag.objects.count(), 1)
        self.assertEqual(MerchantFlagNote.objects.count(), 4)

    def test_a_note_is_required_for_all_three_and_a_blank_one_writes_nothing(self):
        for blank in ('', '   ', None):
            r = self.post(self.a, 'open', blank)
            self.assertEqual((r.status_code, r.json()['code']), (400, 'note_required'))
        self.assertFalse(MerchantFlag.objects.exists())
        self.post(self.a, 'open', 'why')
        for action in ('note', 'close'):
            r = self.post(self.a, action, ' ')
            self.assertEqual((r.status_code, r.json()['code']), (400, 'note_required'))
        self.assertTrue(self.read(self.a).json()['flagged'], 'a blank closing note cleared it')
        self.assertEqual(MerchantFlagNote.objects.count(), 1)

    def test_an_over_long_note_is_refused(self):
        r = self.post(self.a, 'open', 'x' * 2001)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'note_too_long'))
        self.assertEqual(self.post(self.a, 'open', 'x' * 2000).status_code, 200)

    def test_the_transitions(self):
        for action in ('note', 'close'):
            r = self.post(self.a, action, 'n')
            self.assertEqual((r.status_code, r.json()['code']), (409, 'not_flagged'))
        self.post(self.a, 'open', 'n')
        r = self.post(self.a, 'open', 'again')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_flagged'))
        self.post(self.a, 'close', 'done')
        r = self.post(self.a, 'note', 'after clearing')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'not_flagged'))
        r = self.post(self.a, 'delete', 'n')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'unknown_action'))

    def test_an_unflagged_shop_reads_as_an_empty_log(self):
        r = self.read(self.a)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'merchant': 'SHARED STALL', 'flagged': False, 'notes': []})
        self.assertIn(self.client.get(FLAG_URL).status_code, (401, 403))   # signed out
        self.assertEqual(self.a.get(FLAG_URL).json()['code'], 'merchant_required')

    def test_the_audit_line_names_the_shop_and_never_the_note(self):
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as cm:
            self.post(self.a, 'open', SECRET)
        line = '\n'.join(cm.output)
        self.assertIn('spend_flag_open', line)
        self.assertIn('SHARED STALL', line)
        self.assertIn(f'org={self.org_a.pk}', line)
        self.assertNotIn(SECRET, line)


class TestWhoMayFlag(_Base):

    def test_finance_and_reviewer_are_refused_both_ways(self):
        for role in ('finance', 'reviewer', 'qc'):
            c = authed_client(make_admin(role, owning_org=self.org_a))
            self.assertEqual(self.read(c).status_code, 403, role)
            self.assertEqual(self.post(c, 'open', 'n').status_code, 403, role)
        self.assertFalse(MerchantFlag.objects.exists())

    def test_a_plain_admin_may(self):
        c = authed_client(make_admin('admin', owning_org=self.org_a))
        self.assertEqual(self.post(c, 'open', 'n').status_code, 200)

    def test_a_super_flags_for_the_gift_s_organisation(self):
        sup = authed_client(make_admin('super', super_admin=True))
        url = f'{FLAG_URL}?programme={self.app_a.programme.code}'
        self.assertEqual(self.post(sup, 'open', 'from the platform', url=url).status_code, 200)
        flag = MerchantFlag.objects.get()
        self.assertEqual(flag.organisation_id, self.org_a.pk)
        self.assertTrue(self.read(self.a).json()['flagged'])
        self.assertFalse(self.read(self.b).json()['flagged'])

    def test_a_super_with_no_gift_is_refused_rather_than_guessed_for(self):
        # An org-less super is stopped at the door (TD-334); a super WITH an organisation passes
        # the door as ALL_ORGS, and a flag still has no single organisation to belong to.
        orgless = authed_client(make_admin('super', super_admin=True))
        self.assertEqual(self.read(orgless).json()['code'], 'programme_required')
        homed = authed_client(make_admin('super', super_admin=True, owning_org=self.org_a))
        for r in (self.read(homed), self.post(homed, 'open', 'n')):
            self.assertEqual((r.status_code, r.json()['code']), (400, 'programme_required'))
        self.assertFalse(MerchantFlag.objects.exists())

    def test_a_shop_our_students_never_used_is_unknown(self):
        r = self.post(self.a, 'open', 'n', merchant='NOBODY SHOPS HERE')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'unknown_merchant'))


class TestAnotherOrganisationSeesNothing(_Base):
    """⚠ THE CORE RULE. Organisation A flags; organisation B must not be able to tell."""

    def test_b_reads_the_same_bytes_before_and_after_a_flags(self):
        before = self.read(self.b).content
        self.post(self.a, 'open', SECRET)
        self.post(self.a, 'note', SECRET)
        after = self.read(self.b).content
        self.assertEqual(before, after)
        self.assertEqual(json.loads(after), {'merchant': 'SHARED STALL', 'flagged': False,
                                              'notes': []})
        # Positive half: the sentinel IS in A's own log, so its absence above means something.
        self.assertIn(SECRET, self.read(self.a).content.decode())

    def test_b_writes_get_the_same_answer_with_or_without_a_s_flag(self):
        before = [self.post(self.b, a, 'n').json() for a in ('note', 'close')]
        self.post(self.a, 'open', SECRET)
        after = [self.post(self.b, a, 'n').json() for a in ('note', 'close')]
        self.assertEqual(before, after)
        self.assertEqual([r['code'] for r in after], ['not_flagged', 'not_flagged'])
        # A shop only A's students used is unknown to B — the category correction's code.
        r = self.post(self.b, 'open', 'n', merchant='ONLY A SHOP')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'unknown_merchant'))
        self.assertEqual(self.read(self.b, 'ONLY A SHOP').json(),
                         {'merchant': 'ONLY A SHOP', 'flagged': False, 'notes': []})

    def test_b_opening_its_own_flag_is_a_separate_flag(self):
        self.post(self.a, 'open', SECRET)
        r = self.post(self.b, 'open', 'our own reason')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([n['body'] for n in r.json()['notes']], ['our own reason'])
        self.assertEqual(MerchantFlag.objects.count(), 2)
        self.post(self.b, 'close', 'done')
        self.assertTrue(self.read(self.a).json()['flagged'], "B's clearing reached A's flag")

    def test_the_spending_payload_carries_only_the_caller_s_flags(self):
        self.post(self.a, 'open', SECRET)
        a_rows = {r['merchant']: r['flagged'] for r in self.a.get(READ_URL).json()['merchants']}
        self.assertEqual(a_rows, {'SHARED STALL': True, 'ONLY A SHOP': False})
        b_res = self.b.get(READ_URL)
        b_rows = {r['merchant']: r['flagged'] for r in b_res.json()['merchants']}
        self.assertEqual(b_rows, {'SHARED STALL': False})
        self.assertNotIn(SECRET, b_res.content.decode())
        self.assertNotIn(SECRET, self.a.get(READ_URL).content.decode(),
                         'the page carries the flag, never the notes')


class TestAFlagMovesNoMoney(_Base):

    def _page(self):
        data = self.a.get(READ_URL).json()
        for r in data['merchants']:
            r.pop('flagged')
        return data

    def test_category_chart_and_totals_are_unchanged(self):
        MerchantCategory.objects.create(merchant='ONLY A SHOP', category='food', decided_by='rule')
        before = self._page()
        txns_before = list(BursarySpendTxn.objects.values_list('id', 'category', 'decided_by'))
        self.post(self.a, 'open', 'n', merchant='ONLY A SHOP')
        self.post(self.a, 'open', 'n')
        self.assertEqual(self._page(), before)
        self.assertEqual(list(BursarySpendTxn.objects.values_list('id', 'category', 'decided_by')),
                         txns_before)
        self.assertEqual(list(MerchantCategory.objects.values_list('merchant', 'category',
                                                                   'decided_by')),
                         [('ONLY A SHOP', 'food', 'rule')])

    def test_the_page_costs_the_same_with_more_shops_and_more_flags(self):
        """ONE query for the page's flags, never one per row: two shops and no flags cost exactly
        what four shops and three flags cost (a per-row lookup would add one per shop)."""
        def cost():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.a.get(READ_URL).status_code, 200)
            return len(ctx.captured_queries)

        none = cost()
        for name in ('THIRD SHOP', 'FOURTH SHOP'):
            txn(self.app_a, name)
        for name in ('SHARED STALL', 'THIRD SHOP', 'FOURTH SHOP'):
            self.post(self.a, 'open', 'n', merchant=name)
        self.assertEqual(sum(r['flagged'] for r in self.a.get(READ_URL).json()['merchants']), 3)
        self.assertEqual(cost(), none)
