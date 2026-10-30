"""Student maintenance Sprint 5b — HER Funds and Contract tabs on My Bursary (`views_bursary`,
`scholar_money.student_funds` / `student_contract`).

Pinned from the harm:
  * HER OWN FILE ONLY — another student's, no file at all and a pre-award case all answer 404
    `no_file`; a closed file still reads;
  * ONE TRUTH FOR MONEY — her Funds tab, her S3 summary, the officer's Money tab and her sponsor's card
    hold the same received / remaining / released / left, every amount a STRING;
  * OWNER RULING (a), 2026-10-30 — totals plus categories, EVERY category by code: no merchant, no
    transaction, no transaction date; `left` floors at zero; no report yet is `spending: null`;
  * the contract is the platform-signed one (the witness optional), with no IC number, no recording
    officer, and a 300-second link only on request.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import spend_sponsor
from apps.scholarship.models import BursaryAgreement, BursarySpendTxn, Disbursement
from apps.scholarship.storage import build_doc_key
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student, unique_suffix,
)
from apps.scholarship.views_bursary import summary_payload

FUNDS = '/api/v1/scholarship/bursary/funds/'
CONTRACT = '/api/v1/scholarship/bursary/contract/'
SIGNED = 'https://storage.example/signed/agreement.pdf?token=abc'
IC = '010203-14-5678'


def _release(app, amount, days_ago):
    return Disbursement.objects.create(application=app, amount=Decimal(amount), status='released', sequence=1,
                                       released_at=timezone.now() - timedelta(days=days_ago), reference='RUN-1')


def _spend(app, amount, category='food'):
    return BursarySpendTxn.objects.create(
        application=app, txn_id=unique_suffix('TX'), txn_date=date(2026, 9, 14), wallet_id=app.vircle_id or 'W1',
        merchant='KEDAI RAHSIA SDN BHD', amount=Decimal(amount), duitnow_type='', entry_type='CREDIT',
        tx_type='SPEND', status='00', category=category, decided_by='', source_file='fixture.xlsx')


def _signed(app, **over):
    now = timezone.now()
    fields = dict(application=app, version='2026-v1',
                  pdf_storage_path=build_doc_key(app, app.id, 'bursary_agreement_2026-v1_1767225600.pdf'),
                  student_signed_name='NUR AISYAH', student_signed_nric=IC, student_signed_at=now,
                  guarantor_name='SITI', guarantor_nric=IC, guarantor_relationship='mother', guarantor_signed_at=now,
                  foundation_signatory_name='DR KUMAR', foundation_signatory_nric=IC, foundation_signed_at=now,
                  witness_signed_by='super@halatuju.test')
    fields.update(over)
    return BursaryAgreement.objects.create(**fields)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.student = make_student()
        self.app = make_application('maintenance', cohort=self.cohort, student=self.student,
                                    award_amount=Decimal('2000'), vircle_id=unique_suffix('8000'),
                                    active_at=timezone.now() - timedelta(days=60))

    def _funds(self, student=None):
        return authed_client((student or self.student).supabase_user_id).get(FUNDS)

    def _contract(self, student=None):
        return authed_client((student or self.student).supabase_user_id).get(CONTRACT)

    def _contract_link(self):
        return authed_client(self.student.supabase_user_id).get(f'{CONTRACT}?link=1')


class TestHerOwnFileOnly(_Base):
    def test_another_student_no_file_and_pre_award_are_404_closed_reads(self):
        stranger = make_student()
        make_application('submitted', cohort=self.cohort, student=stranger)            # no file
        for r in (self._funds(stranger), self._contract(stranger)):
            self.assertEqual((r.status_code, r.json()['code']), (404, 'no_file'))
        type(self.app).objects.filter(pk=self.app.pk).update(status='closed', closure_reason='completed')
        self.assertEqual(self._funds().status_code, 200)
        self.assertEqual(self._contract().status_code, 200)


class TestOneTruthForHerMoney(_Base):
    def test_her_tab_her_summary_the_officers_tab_and_the_sponsor_card_agree(self):
        _release(self.app, '300.00', 40)
        _release(self.app, '250.50', 10)
        _spend(self.app, '100.00')
        body = self._funds().json()
        app = type(self.app).objects.get(pk=self.app.pk)
        hub = summary_payload(app)['funds']
        admin = make_admin('org_admin', owning_org=self.cohort.owning_organisation)
        officer = authed_client(admin).get(f'/api/v1/admin/scholarship/scholars/{app.id}/money/').json()
        sponsor = spend_sponsor.sponsor_card(app)
        self.assertEqual({body['received'], hub['received'], officer['paid_to_date'], sponsor['released'],
                          body['spending']['released']}, {'550.50'})
        self.assertEqual({body['remaining'], hub['remaining'], officer['remaining']}, {'1449.50'})
        self.assertEqual((body['spending']['spent'], body['spending']['left']), (sponsor['spent'], sponsor['left']))
        self.assertEqual([r['amount'] for r in body['releases']], ['250.50', '300.00'])
        self.assertNotRegex(self._funds().content.decode(),
                            r'"(amount|received|remaining|award_amount|spent|left|released|promised|total)":\s*\d')


class TestOwnerRulingA(_Base):
    def test_totals_and_every_category_by_code_no_merchant_no_transaction_no_date(self):
        codes = ['food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing']
        for i, code in enumerate(codes):
            _spend(self.app, f'{10 + i}.00', category=code)
        raw = self._funds().content.decode()
        cats = json.loads(raw)['spending']['categories']
        self.assertEqual(sorted(c['code'] for c in cats), sorted(codes))         # all eight, unfolded
        self.assertTrue(all(set(c) == {'code', 'total'} for c in cats))
        for leak in ('KEDAI', 'RAHSIA', 'txn', '2026-09-14', 'merchant', 'wallet', self.app.vircle_id):
            self.assertNotIn(leak, raw)

    def test_left_floors_at_zero_and_no_report_is_null_not_zeroes(self):
        self.assertIsNone(self._funds().json()['spending'])
        _release(self.app, '100.00', 5)
        _spend(self.app, '250.00')                                                # a parent's top-up
        self.assertEqual(self._funds().json()['spending']['left'], '0.00')


class TestHerContract(_Base):
    @mock.patch('apps.scholarship.storage.create_signed_download_url', return_value=SIGNED)
    def test_countersigned_without_witness_no_ic_no_officer_link_on_request_only(self, signed):
        self.assertEqual(self._contract().json(), {'exists': False})
        _signed(self.app)
        with override_settings(BURSARY_AGREEMENT_ENABLED=False):
            first = self._contract()
        body = first.json()
        self.assertTrue(body['exists'])
        self.assertIsNone(body['pdf_url'])
        signed.assert_not_called()
        self.assertEqual([p['role'] for p in body['parties']], ['student', 'guarantor', 'foundation'])
        for leak in (IC, IC.replace('-', ''), 'nric', 'super@halatuju.test', 'version'):
            self.assertNotIn(leak, first.content.decode())
        linked = self._contract_link().json()
        self.assertEqual(linked['pdf_url'], SIGNED)
        self.assertEqual(signed.call_args.kwargs['expires_in'], 300)

    def test_before_the_organisation_signs_it_is_no_contract_on_file(self):
        _signed(self.app, foundation_signed_at=None)
        self.assertEqual(self._contract().json(), {'exists': False})
