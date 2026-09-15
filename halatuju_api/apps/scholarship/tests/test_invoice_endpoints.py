"""Tenant invoices through the REAL endpoints and the REAL cron door (2026-09-14).

The service tests prove the arithmetic. These prove the doors, which is where the lessons say the
damage happens:

* **The fence is asserted AT THE DOOR, from the widening side** (TD-241): a second tenant naming
  the first tenant's invoice and receipt ids, and getting the same 404 as for a missing one.
* **"Sent" is part of the fence.** Owner, 2026-09-14: nothing leaves the building until a super
  presses Send — so an issued invoice is invisible to the tenant until then.
* **Money crosses as strings**, walked through the whole payload (the sponsor-card lesson).
* **The door can actually issue** with no arguments (the verdict-engine lesson: registered is not
  runnable), and a refusal reaches a person through the LOG and an email, not stdout.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

import jwt
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import invoicing
from apps.scholarship.models import (
    Invoice, InvoiceIssuer, OrgBillingDetails, PlatformCost,
)
from apps.scholarship.tests.test_invoicing import SEPT_15, InvoiceWorld

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/billing'
# 09:00 on 15 September 2026 in Kuala Lumpur, pinned. Every endpoint below reads the real clock
# through `timezone.localdate()`, so the world has to be pinned at the door, not in the service.
SEPT_15_0900_MYT = datetime(2026, 9, 15, 1, 0, tzinfo=dt_timezone.utc)


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BILLING_USAGE_ENABLED=True, CRON_SECRET='test-cron-secret',
                   ADMIN_NOTIFY_EMAIL='ops@halatuju.xyz', DEFAULT_FROM_EMAIL='noreply@halatuju.xyz',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class _Doors(InvoiceWorld):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OA', email='oa@x.com')

    def setUp(self):
        patcher = mock.patch('django.utils.timezone.now', return_value=SEPT_15_0900_MYT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def client_for(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c

    def issued(self):
        return invoicing.issue_invoice(self.org, '2026-08', today=SEPT_15)

    def sent(self):
        inv = self.issued()
        invoicing.send_invoice(inv)
        mail.outbox.clear()
        return inv

    def second_tenant(self):
        """A REAL second tenant — an organisation with an active org_admin — and its admin."""
        other = PartnerOrganisation.objects.create(code='other-tenant', name='Other Tenant')
        admin = PartnerAdmin.objects.create(
            supabase_user_id='oa-b', role='org_admin', is_active=True,
            owning_organisation=other, name='OB', email='ob@x.com')
        return other, admin


def _walk_for_floats(testcase, value, path='payload'):
    if isinstance(value, float):
        testcase.fail(f'A float reached the wire at {path}: {value!r}')
    if isinstance(value, dict):
        for k, v in value.items():
            _walk_for_floats(testcase, v, f'{path}.{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk_for_floats(testcase, v, f'{path}[{i}]')


class TestWhatATenantSees(_Doors):

    def test_an_issued_invoice_is_invisible_to_the_tenant_until_it_is_sent(self):
        inv = self.issued()
        oa = self.client_for('oa-a')
        self.assertEqual(oa.get(f'{BASE}/invoices/').json()['invoices'], [])
        self.assertEqual(oa.get(f'{BASE}/invoices/{inv.id}/pdf/').status_code, 404)

        invoicing.send_invoice(inv)
        listed = oa.get(f'{BASE}/invoices/').json()['invoices']
        self.assertEqual([i['number'] for i in listed], ['INV-2026-0001'])
        r = oa.get(f'{BASE}/invoices/{inv.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_the_tenant_payload_carries_no_internal_fields_and_no_floats(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        inv = invoicing.issue_invoice(self.org, '2026-08', today=SEPT_15,
                                      override_reason='Supabase cancelled.',
                                      issued_by_email='super@x.com')
        invoicing.send_invoice(inv)
        invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr='10.00',
                                 reference='MBB9', today=SEPT_15)
        body = self.client_for('oa-a').get(f'{BASE}/invoices/').json()
        _walk_for_floats(self, body)
        row = body['invoices'][0]
        for internal in ('override_reason', 'issued_by_email', 'sent_to', 'sent_by_email',
                         'voided_by_email', 'bill_to_emails'):
            self.assertNotIn(internal, row)
        self.assertNotIn('readiness', body)
        # No Supabase row in August: infrastructure 0.00 + metered 23.00 + development 718.75.
        self.assertEqual(row['total_myr'], '741.75')
        self.assertEqual(row['balance_myr'], '731.75')
        self.assertEqual(row['receipts'][0]['amount_myr'], '10.00')
        self.assertEqual(row['status'], 'part_paid')

    def test_a_sent_invoice_that_is_later_voided_still_shows_as_void(self):
        """The tenant was told about it, so the tenant is told it was withdrawn."""
        inv = self.sent()
        invoicing.void_invoice(inv, reason='Hours belonged to September')
        row = self.client_for('oa-a').get(f'{BASE}/invoices/').json()['invoices'][0]
        self.assertEqual(row['status'], 'void')
        self.assertEqual(row['void_reason'], 'Hours belonged to September')


class TestTheFenceFromTheWideningSide(_Doors):

    def test_another_tenant_cannot_list_download_or_reach_a_receipt(self):
        inv = self.sent()
        receipt = invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr='50.00',
                                           reference='MBB1', today=SEPT_15)
        _, _ = self.second_tenant()
        ob = self.client_for('oa-b')
        self.assertEqual(ob.get(f'{BASE}/invoices/').json()['invoices'], [])
        self.assertEqual(ob.get(f'{BASE}/invoices/{inv.id}/pdf/').status_code, 404)
        self.assertEqual(ob.get(f'{BASE}/receipts/{receipt.id}/pdf/').status_code, 404)
        # ...and the owning tenant, through the same routes, can.
        oa = self.client_for('oa-a')
        self.assertEqual(oa.get(f'{BASE}/receipts/{receipt.id}/pdf/').status_code, 200)

    def test_a_tenant_cannot_issue_send_void_pay_or_edit_settings(self):
        inv = self.sent()
        oa = self.client_for('oa-a')
        self.assertEqual(oa.post(f'{BASE}/invoices/', {'organisation_id': self.org.id,
                                                       'period_month': '2026-08'},
                                 format='json').status_code, 403)
        for action in ('send', 'void', 'receipt'):
            with self.subTest(action=action):
                self.assertEqual(oa.post(f'{BASE}/invoices/{inv.id}/{action}/', {},
                                         format='json').status_code, 403)
        self.assertEqual(oa.get(f'{BASE}/invoice-settings/').status_code, 403)
        self.assertEqual(oa.post(f'{BASE}/invoice-settings/', {'issuer': {'legal_name': 'X'}},
                                 format='json').status_code, 403)
        self.assertEqual(InvoiceIssuer.objects.get().legal_name, 'HalaTuju Platform')

    @override_settings(BILLING_USAGE_ENABLED=False)
    def test_while_billing_is_dark_a_tenant_gets_the_same_404_and_a_super_still_works(self):
        self.sent()
        self.assertEqual(self.client_for('oa-a').get(f'{BASE}/invoices/').status_code, 404)
        self.assertEqual(self.client_for('super-uid').get(f'{BASE}/invoices/').status_code, 200)

    def test_a_reviewer_is_refused(self):
        PartnerAdmin.objects.create(supabase_user_id='rev', role='reviewer', is_active=True,
                                    owning_organisation=self.org, name='R', email='r@x.com')
        self.assertEqual(self.client_for('rev').get(f'{BASE}/invoices/').status_code, 403)


class TestWhatASuperDoes(_Doors):

    def test_the_list_carries_readiness_for_last_month_by_default(self):
        body = self.client_for('super-uid').get(f'{BASE}/invoices/').json()
        self.assertEqual(body['month'], '2026-08')
        self.assertEqual(body['issue_day'], 15)
        self.assertEqual(body['readiness'],
                         [{'organisation_id': self.org.id, 'organisation': self.org.name,
                           'problems': []}])

    def test_issue_then_send_then_record_payment_then_download_the_receipt(self):
        su = self.client_for('super-uid')
        r = su.post(f'{BASE}/invoices/', {'organisation_id': self.org.id,
                                          'period_month': '2026-08'}, format='json')
        self.assertEqual(r.status_code, 201)
        inv = r.json()
        _walk_for_floats(self, inv)
        self.assertEqual((inv['number'], inv['total_myr'], inv['status']),
                         ('INV-2026-0001', '856.75', 'issued'))
        self.assertEqual(inv['issued_by_email'], 'super@x.com')

        r = su.post(f'{BASE}/invoices/{inv["id"]}/send/', {}, format='json')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'sent'))
        self.assertEqual(len(mail.outbox), 1)

        r = su.post(f'{BASE}/invoices/{inv["id"]}/receipt/',
                    {'received_on': '2026-09-15', 'amount_myr': '856.75',
                     'reference': 'MBB-0915', 'method': 'bank_transfer'}, format='json')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'paid'))
        receipt_id = r.json()['receipts'][0]['id']
        pdf = su.get(f'{BASE}/receipts/{receipt_id}/pdf/')
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_a_refusal_is_a_409_carrying_every_reason(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        InvoiceIssuer.objects.update(bank_name='')
        r = self.client_for('super-uid').post(
            f'{BASE}/invoices/', {'organisation_id': self.org.id, 'period_month': '2026-08'},
            format='json')
        self.assertEqual(r.status_code, 409)
        codes = {p['code'] for p in r.json()['problems']}
        self.assertEqual(codes, {'supplier_missing', 'issuer_incomplete'})
        self.assertFalse(Invoice.objects.exists())

    def test_issue_anyway_with_a_reason(self):
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        r = self.client_for('super-uid').post(
            f'{BASE}/invoices/', {'organisation_id': self.org.id, 'period_month': '2026-08',
                                  'override_reason': 'Supabase was cancelled.'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIn('Supabase was cancelled.', r.json()['override_reason'])

    def test_void_needs_a_reason_and_an_unknown_action_is_404(self):
        inv = self.issued()
        su = self.client_for('super-uid')
        r = su.post(f'{BASE}/invoices/{inv.id}/void/', {'reason': ''}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
        self.assertEqual(su.post(f'{BASE}/invoices/{inv.id}/delete/', {},
                                 format='json').status_code, 404)
        r = su.post(f'{BASE}/invoices/{inv.id}/void/', {'reason': 'Wrong'}, format='json')
        self.assertEqual(r.json()['status'], 'void')

    def test_the_pdf_route_is_not_swallowed_by_the_action_route(self):
        """`/invoices/<id>/<action>/` would match `/invoices/<id>/pdf/` if it were listed first,
        and a GET would then answer 405 rather than a document."""
        inv = self.issued()
        r = self.client_for('super-uid').get(f'{BASE}/invoices/{inv.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('INV-2026-0001.pdf', r['Content-Disposition'])

    def test_settings_save_the_issuer_and_a_tenants_billing_details(self):
        su = self.client_for('super-uid')
        r = su.post(f'{BASE}/invoice-settings/',
                    {'issuer': {'legal_name': 'New Name Berhad', 'payment_terms_days': 14}},
                    format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['issuer']['legal_name'], 'New Name Berhad')
        self.assertEqual(InvoiceIssuer.objects.get().payment_terms_days, 14)

        r = su.post(f'{BASE}/invoice-settings/',
                    {'organisation_id': self.org.id, 'bill_to_name': 'BP Berhad',
                     'address': 'KL', 'emails': 'a@bp.example; b@bp.example'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(OrgBillingDetails.objects.get(organisation=self.org).emails,
                         ['a@bp.example', 'b@bp.example'])

    def test_settings_refuse_a_bad_email_and_a_non_tenant(self):
        su = self.client_for('super-uid')
        r = su.post(f'{BASE}/invoice-settings/', {'issuer': {'email': 'not-an-email'}},
                    format='json')
        self.assertEqual(r.status_code, 400)
        r = su.post(f'{BASE}/invoice-settings/', {'organisation_id': self.org.id,
                                                  'emails': ['ok@x.com', 'broken']}, format='json')
        self.assertEqual(r.status_code, 400)
        school = PartnerOrganisation.objects.create(code='school', name='School')
        r = su.post(f'{BASE}/invoice-settings/', {'organisation_id': school.id,
                                                  'emails': ['ok@x.com']}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_the_first_day_in_production_nothing_is_set_and_the_screen_says_so(self):
        """No issuer row exists on the day this ships. The settings read must not create one."""
        InvoiceIssuer.objects.all().delete()
        body = self.client_for('super-uid').get(f'{BASE}/invoice-settings/').json()
        self.assertIn('legal_name', body['issuer']['missing'])
        self.assertFalse(InvoiceIssuer.objects.exists())


class TestTheDoor(_Doors):
    """`CronRunView` calls the command with NO arguments. That call must be the real run."""

    def door(self):
        return self.client.post('/api/v1/internal/cron/issue-monthly-invoices/',
                                HTTP_X_CRON_SECRET='test-cron-secret')

    def test_the_door_with_no_arguments_issues_last_months_invoices(self):
        r = self.door()
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('error', r.json())
        self.assertEqual(list(Invoice.objects.values_list('number', 'period_month')),
                         [('INV-2026-0001', '2026-08')])
        self.assertEqual(mail.outbox, [])   # issuing sends NOTHING

    def test_a_second_call_the_same_day_doubles_nothing(self):
        self.door()
        self.door()
        self.assertEqual(Invoice.objects.count(), 1)

    def test_a_refusal_is_logged_and_emailed_not_just_printed(self):
        """Under cron, stdout lands in a response body Cloud Scheduler throws away."""
        PlatformCost.objects.filter(period_month='2026-08', source='supabase').delete()
        with self.assertLogs('apps.scholarship.invoicing', level='WARNING') as logs:
            self.door()
        self.assertTrue(any('supabase' in line for line in logs.output))
        self.assertFalse(Invoice.objects.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ops@halatuju.xyz'])
        self.assertIn('supabase', mail.outbox[0].body)
        self.assertIn('Nothing has been sent', mail.outbox[0].body)

    def test_a_clean_run_sends_no_all_clear(self):
        self.door()
        self.assertEqual(mail.outbox, [])

    def test_dry_run_writes_nothing_and_a_bad_month_is_refused(self):
        call_command('issue_monthly_invoices', '--dry-run')
        self.assertFalse(Invoice.objects.exists())
        with self.assertRaises(CommandError):
            call_command('issue_monthly_invoices', '--month', '2026-00')
