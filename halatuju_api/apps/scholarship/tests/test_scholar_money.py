"""Student maintenance Sprint 5a — the scholar file's Money and Contract tabs (`scholar_money.py`).

Pinned from the harm:
  * ONE TRUTH FOR MONEY: the file's Overview card, her My Bursary summary (S3), this Money tab, the
    Payments funding summary and the sponsor card's "released" agree for the same student — award,
    paid, remaining — with and without an award, and every amount is a STRING on the wire;
  * the spending block exists only for a viewer holding `spending`; otherwise the KEY IS ABSENT;
  * "this term" starts at her current S4b term's STORED start, else the day she was funded;
  * the contract is shown only when EXECUTED (the platform-signed rule), whatever the signing flag
    says; the PDF link is minted for 300 seconds and refused for another organisation's path; no IC
    number appears anywhere in the payload;
  * the fence is the Applications rule (finance and an unassigned reviewer refused, another
    organisation 404), and a closed file reads the same (read-only).
"""
import datetime
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import scholar_money, spend_sponsor
from apps.scholarship.models import (
    BursaryAgreement, BursarySpendTxn, Disbursement, ResultsExpectation,
)
from apps.scholarship.scholars import file_payload
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)
from apps.scholarship.views_bursary import summary_payload

FUNDING = '/api/v1/admin/scholarship/payments/funding-summary/'
SIGNED = 'https://storage.example/signed/agreement.pdf?token=abc'
IC = '010203-14-5678'


def _release(app, amount, days_ago, ref='RUN-1'):
    return Disbursement.objects.create(application=app, amount=Decimal(amount), status='released', sequence=1,
                                       released_at=timezone.now() - timedelta(days=days_ago), reference=ref)


def _spend(app, amount, on, category='food'):
    return BursarySpendTxn.objects.create(
        application=app, txn_id=unique_suffix('TX'), txn_date=on, wallet_id=app.vircle_id or 'W1',
        merchant='KEDAI SECRET MERCHANT', amount=Decimal(amount), duitnow_type='', entry_type='CREDIT',
        tx_type='SPEND', status='00', category=category, decided_by='', source_file='fixture.xlsx')


def _executed(app, **over):
    from apps.scholarship.storage import build_doc_key
    now = timezone.now()
    # The REAL key shape (`bursary.py`): `<org>/<app>/bursary_agreement_<version>_<ts>.pdf`.
    path = build_doc_key(app, app.id, 'bursary_agreement_2026-v1_1767225600.pdf')
    fields = dict(application=app, version='2026-v1', pdf_storage_path=path,
                  student_signed_name='NUR AISYAH', student_signed_nric=IC, student_signed_at=now,
                  guarantor_name='SITI', guarantor_nric=IC, guarantor_relationship='mother', guarantor_signed_at=now,
                  foundation_signatory_name='DR KUMAR', foundation_signatory_title='Chair',
                  foundation_signatory_nric=IC, foundation_signed_at=now,
                  witness_name='MS LEE', witness_signed_at=now)
    fields.update(over)
    return BursaryAgreement.objects.create(**fields)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        org = self.cohort.owning_organisation
        self.org_admin = make_admin('org_admin', owning_org=org)
        self.qc = make_admin('qc', owning_org=org)
        self.reviewer = make_admin('reviewer', owning_org=org)
        self.finance = make_admin('finance', owning_org=org)
        self.app = make_application('maintenance', cohort=self.cohort, reviewer=self.reviewer,
                                    award_amount=Decimal('2000'), vircle_id=unique_suffix('8000'),
                                    active_at=timezone.now() - timedelta(days=60))

    def _money_url(self, pk):
        return f'/api/v1/admin/scholarship/scholars/{pk}/money/'

    def _contract_url(self, pk):
        return f'/api/v1/admin/scholarship/scholars/{pk}/contract/'

    def _link(self, admin):
        return authed_client(admin).get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/contract/?link=1')

    def _get(self, admin, what, app=None):
        pk = (app or self.app).id
        if what == 'money':
            return authed_client(admin).get(self._money_url(pk))
        return authed_client(admin).get(self._contract_url(pk))


class TestOneTruthForMoney(_Base):
    def _readings(self, app):
        app = type(app).objects.get(pk=app.pk)
        tab = self._get(self.org_admin, 'money', app).json()
        card = file_payload(app)['money']
        hub = summary_payload(app)['funds']
        rows = authed_client(self.org_admin).get(FUNDING).json()['rows']
        funding = next(r for r in rows if r['application_id'] == app.id)
        _spend(app, '1.00', timezone.localdate())                      # the sponsor card needs a report
        sponsor = spend_sponsor.sponsor_card(app)
        return tab, card, hub, funding, sponsor

    def test_every_reader_agrees_with_and_without_an_award(self):
        _release(self.app, '300.00', 40)
        _release(self.app, '250.50', 10)
        Disbursement.objects.create(application=self.app, amount=Decimal('999'), status='scheduled', sequence=3)
        no_award = make_application('maintenance', cohort=self.cohort, award_amount=None,
                                    vircle_id=unique_suffix('8001'), active_at=timezone.now())
        _release(no_award, '100.00', 5)
        for app, paid, remaining in ((self.app, '550.50', '1449.50'), (no_award, '100.00', '0.00')):
            with self.subTest(app=app.id):
                tab, card, hub, funding, sponsor = self._readings(app)
                # The same NUMBER on every screen (each screen's own string format aside — the
                # funding summary prints `str(Decimal)` as it always has).
                self.assertEqual({Decimal(v) for v in (tab['paid_to_date'], card['paid_to_date'], hub['received'],
                                                       funding['paid_to_date'], sponsor['released'])}, {Decimal(paid)})
                self.assertEqual({Decimal(v) for v in (tab['remaining'], card['remaining'], hub['remaining'],
                                                       funding['remaining'])}, {Decimal(remaining)})
                self.assertEqual(tab['paid_to_date'], paid)                 # the tab: two places, always

    def test_money_is_a_string_on_the_wire_and_the_last_three_releases_newest_first(self):
        for i, amt in enumerate(('10.00', '20.00', '30.00', '40.00')):
            _release(self.app, amt, 40 - i * 10, ref=f'RUN-{i}')
        r = self._get(self.org_admin, 'money')
        raw = json.loads(r.content)
        self.assertEqual([x['amount'] for x in raw['releases']], ['40.00', '30.00', '20.00'])
        for key in ('award_amount', 'paid_to_date', 'remaining'):
            self.assertIsInstance(raw[key], str)
        self.assertNotRegex(r.content.decode(), r'"(amount|paid_to_date|remaining|award_amount|spent|total)":\s*\d')


class TestSpendingBlock(_Base):
    def test_present_only_with_the_spending_permission_otherwise_absent(self):
        _spend(self.app, '12.00', timezone.localdate())
        self.assertIn('spending', self._get(self.org_admin, 'money').json())
        for admin in (self.qc, self.reviewer):
            with self.subTest(role=admin.role):
                body = self._get(admin, 'money').json()
                self.assertNotIn('spending', body)                       # absent, not null
                self.assertIn('paid_to_date', body)

    def test_this_term_starts_at_her_stored_term_start_else_since_funded(self):
        today = timezone.localdate()
        _spend(self.app, '5.00', today - timedelta(days=200))
        _spend(self.app, '7.00', today - timedelta(days=50), category='transport')
        _spend(self.app, '9.00', today - timedelta(days=5))
        funded = self._get(self.org_admin, 'money').json()['spending']
        self.assertEqual((funded['basis'], funded['since'], funded['spent']),
                         ('funded', (today - timedelta(days=60)).isoformat(), '16.00'))
        ResultsExpectation.objects.create(application=self.app, term_index=1, term_starts_on=today - timedelta(days=20),
                                          term_ends_on=today + timedelta(days=160), due_on=today + timedelta(days=205))
        term = self._get(self.org_admin, 'money').json()['spending']
        self.assertEqual((term['basis'], term['since'], term['spent']),
                         ('term', (today - timedelta(days=20)).isoformat(), '9.00'))
        self.assertEqual([c['code'] for c in term['categories']], ['food'])
        self.assertNotIn('KEDAI', json.dumps(term))                     # categories and totals only

    def test_a_lapsed_term_is_not_this_term(self):
        """Review L5: only a term that has begun AND not yet ended is "this term"."""
        today = timezone.localdate()
        ResultsExpectation.objects.create(application=self.app, term_index=1, term_starts_on=today - timedelta(days=200),
                                          term_ends_on=today - timedelta(days=20), due_on=today + timedelta(days=25))
        self.assertEqual(scholar_money.spending_since(self.app)[1], 'funded')

    def test_every_category_unfolded_by_code_with_no_english_label(self):
        """Review M2: the officer sees EVERY category (the Spending page's view, not the sponsor
        card's top six + "other"), keyed by code for the screen to translate."""
        codes = ['food', 'groceries', 'transport', 'study', 'phone', 'hostel', 'health', 'clothing']
        for i, code in enumerate(codes):
            _spend(self.app, f'{10 + i}.00', timezone.localdate(), category=code)
        cats = self._get(self.org_admin, 'money').json()['spending']['categories']
        self.assertEqual(sorted(c['code'] for c in cats), sorted(codes))
        self.assertNotIn('other', [c['code'] for c in cats])
        self.assertTrue(all(set(c) == {'code', 'total'} for c in cats))


class TestContract(_Base):
    @mock.patch('apps.scholarship.storage.create_signed_download_url', return_value=SIGNED)
    def test_executed_shows_dates_parties_and_a_300_second_link_with_no_ic(self, signed):
        _executed(self.app)
        with override_settings(BURSARY_AGREEMENT_ENABLED=False):       # the signing flag is not read
            r = self._link(self.org_admin)
        body = r.json()
        self.assertTrue(body['exists'] and body['witnessed'])
        self.assertEqual(body['pdf_url'], SIGNED)
        self.assertEqual(signed.call_args.kwargs['expires_in'], 300)
        self.assertEqual([p['role'] for p in body['parties']], ['student', 'guarantor', 'foundation', 'witness'])
        self.assertNotIn(IC, r.content.decode())
        self.assertNotIn(IC.replace('-', ''), r.content.decode())
        self.assertNotIn('nric', r.content.decode())

    @mock.patch('apps.scholarship.storage.create_signed_download_url', return_value=SIGNED)
    def test_countersigned_without_a_witness_is_on_file(self, _signed):
        """Review H1: the witness is NON-BLOCKING (`bursary._maybe_activate`) — a countersigned
        agreement is the platform-signed contract; its date is the organisation's and there is no
        witness row."""
        self.assertEqual(self._get(self.org_admin, 'contract').json(), {'exists': False})
        ag = _executed(self.app, witness_signed_at=None, witness_name='')
        body = self._get(self.org_admin, 'contract').json()
        self.assertTrue(body['exists'])
        self.assertFalse(body['witnessed'])
        self.assertEqual(body['executed_on'], timezone.localtime(ag.foundation_signed_at).date().isoformat())
        self.assertNotIn('witness', [p['role'] for p in body['parties']])

    def test_before_the_organisation_signs_it_is_no_contract_on_file(self):
        _executed(self.app, foundation_signed_at=None)
        self.assertEqual(self._get(self.org_admin, 'contract').json(), {'exists': False})

    @mock.patch('apps.scholarship.storage.create_signed_download_url', return_value=SIGNED)
    def test_the_first_load_mints_no_link_only_a_request_does(self, signed):
        """Review L6: the tab's first read carries no link; `?link=1` (a click) mints one."""
        _executed(self.app)
        self.assertIsNone(self._get(self.org_admin, 'contract').json()['pdf_url'])
        signed.assert_not_called()
        self.assertEqual(self._link(self.org_admin).json()['pdf_url'], SIGNED)

    @mock.patch('apps.scholarship.storage.create_signed_download_url', return_value=SIGNED)
    def test_a_pdf_path_that_is_not_this_applications_gets_no_link(self, signed):
        """Review L3: the real key is 3 segments (`<org>/<app>/file`), which `resolve_org_for_path`
        cannot read an org from — so the check is on the first two segments themselves."""
        other_org = make_cohort().owning_organisation_id
        for path in (f'{other_org}/{self.app.id}/bursary_agreement_x.pdf',
                     f'{self.app.owning_organisation_id}/{self.app.id + 999}/bursary_agreement_x.pdf',
                     f'{self.app.id}/bursary_agreement_x.pdf'):
            with self.subTest(path=path):
                BursaryAgreement.objects.filter(application=self.app).delete()
                _executed(self.app, pdf_storage_path=path)
                body = self._link(self.org_admin).json()
                self.assertTrue(body['exists'])
                self.assertIsNone(body['pdf_url'])
        signed.assert_not_called()

    def test_the_witness_is_never_named_after_the_recording_officer(self):
        """Review L4: `witness_signed_by` is the super who RECORDED the attestation."""
        from apps.scholarship.models import ReferralSource
        org = ReferralSource.objects.create(code=unique_suffix('ws'), name='Kuil Sri Murugan',
                                            organisation=self.cohort.owning_organisation)
        _executed(self.app, witness_name='', witness_signed_by='super@halatuju.test', witness_org=org)
        body = self._get(self.org_admin, 'contract').json()
        witness = next(p for p in body['parties'] if p['role'] == 'witness')
        self.assertEqual(witness['name'], 'Kuil Sri Murugan')
        self.assertNotIn('super@halatuju.test', json.dumps(body))


class TestTheFence(_Base):
    def test_finance_refused_unassigned_reviewer_refused_other_org_404_closed_reads(self):
        for what in ('money', 'contract'):
            with self.subTest(what=what):
                self.assertEqual(self._get(self.finance, what).status_code, 403)
                stranger = make_admin('reviewer', owning_org=self.cohort.owning_organisation)
                self.assertEqual(self._get(stranger, what).status_code, 403)
                outsider = make_admin('org_admin', owning_org=make_cohort().owning_organisation)
                self.assertEqual(self._get(outsider, what).status_code, 404)
                self.assertEqual(self._get(self.reviewer, what).status_code, 200)   # assigned
        type(self.app).objects.filter(pk=self.app.pk).update(status='closed', closure_reason='completed')
        for what in ('money', 'contract'):
            self.assertEqual(self._get(self.org_admin, what).status_code, 200)       # read-only, still readable


class TestPureHelpers(TestCase):
    def test_since_falls_back_to_all_when_never_funded(self):
        app = make_application('awarded', award_amount=Decimal('100'))
        type(app).objects.filter(pk=app.pk).update(awarded_at=None, active_at=None, vircle_activated_at=None)
        app.refresh_from_db()
        self.assertEqual(scholar_money.spending_since(app, datetime.date(2026, 10, 30)), (None, 'all'))
