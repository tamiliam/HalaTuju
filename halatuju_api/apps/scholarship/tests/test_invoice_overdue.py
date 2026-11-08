"""Staff nudges sprint 3 (2026-11-09): the ONE overdue rule and the red banner's door.

Brief `docs/plans/2026-11-08-staff-nudges.md`, decisions 5 and 6. The rule (`invoice_overdue.py`): SENT,
not void, balance > 0, no open tenant payment declaration, and today (Kuala Lumpur) AFTER `due_on`.
Part-paid counts; no grace period. The door (`admin/scholarship/billing/overdue/`): the caller's own
organisation only, the invoices gate (`may_read_invoices`), not the super.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import invoice_overdue
from apps.scholarship.models import Invoice, InvoicePaymentDeclaration, InvoiceReceipt
from apps.scholarship.tests.test_invoice_endpoints import _Doors

#: Spelt out here, not imported: `test_endpoint_exercise.py` follows a module constant, not an import.
BASE = '/api/v1/admin/scholarship/billing'

DUE = date(2026, 10, 15)
_N = iter(range(1, 10_000))


def make_invoice(org, *, due_on=DUE, total='100.00', sent=True, void=False, issued_on=None):
    n = next(_N)
    return Invoice.objects.create(
        number=f'INV-2026-{n:04d}', organisation=org, period_month=f'2025-{(n % 12) + 1:02d}',
        issued_on=issued_on or date(2026, 9, 15), due_on=due_on,
        subtotal_myr=Decimal(total), total_myr=Decimal(total),
        sent_at=timezone.now() if sent else None, voided_at=timezone.now() if void else None)


def receipt(inv, amount):
    return InvoiceReceipt.objects.create(number=f'RCP-2026-{next(_N):04d}', invoice=inv,
                                         received_on=date(2026, 10, 1), amount_myr=Decimal(amount),
                                         reference='MBB-1')


def declaration(inv, **kw):
    return InvoicePaymentDeclaration.objects.create(invoice=inv, paid_on=date(2026, 10, 1),
                                                    reference='MBB-2', **kw)


def fresh(inv):
    return Invoice.objects.prefetch_related('receipts', 'payment_declarations').get(pk=inv.pk)


class TestTheRule(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='overdue-a', name='Tenant A')

    def test_on_the_due_date_it_is_not_overdue_and_the_day_after_it_is(self):
        inv = fresh(make_invoice(self.org))
        self.assertFalse(invoice_overdue.is_overdue(inv, today=date(2026, 10, 14)))
        self.assertFalse(invoice_overdue.is_overdue(inv, today=DUE))
        self.assertTrue(invoice_overdue.is_overdue(inv, today=date(2026, 10, 16)))
        self.assertEqual(invoice_overdue.days_overdue(inv, today=date(2026, 10, 16)), 1)
        self.assertEqual(invoice_overdue.days_overdue(inv, today=DUE), 0)

    def test_part_paid_still_counts(self):
        inv = make_invoice(self.org)
        receipt(inv, '40.00')
        inv = fresh(inv)
        self.assertEqual(inv.status, 'part_paid')
        self.assertTrue(invoice_overdue.is_overdue(inv, today=date(2026, 11, 1)))

    def test_paid_in_full_and_a_zero_balance_never_count(self):
        paid = make_invoice(self.org)
        receipt(paid, '100.00')
        self.assertFalse(invoice_overdue.is_overdue(fresh(paid), today=date(2026, 11, 1)))
        # A fully discounted month owes nothing: never late (owner, 2026-10-29).
        zero = make_invoice(self.org, total='0.00')
        self.assertFalse(invoice_overdue.is_overdue(fresh(zero), today=date(2026, 11, 1)))

    def test_an_open_declaration_does_not_count_and_a_settled_one_does_not_shield(self):
        inv = make_invoice(self.org)
        d = declaration(inv)
        self.assertFalse(invoice_overdue.is_overdue(fresh(inv), today=date(2026, 11, 1)))
        # The owner could not find it: the claim is closed and the invoice is late again.
        d.rejected_at = timezone.now()
        d.save()
        self.assertTrue(invoice_overdue.is_overdue(fresh(inv), today=date(2026, 11, 1)))

    def test_part_paid_with_an_open_declaration_for_the_rest_does_not_count(self):
        inv = make_invoice(self.org)
        receipt(inv, '40.00')
        declaration(inv)
        inv = fresh(inv)
        self.assertEqual(inv.status, 'part_paid')   # money beats a claim, for the STATUS
        self.assertFalse(invoice_overdue.is_overdue(inv, today=date(2026, 11, 1)))

    def test_void_and_unsent_never_count(self):
        self.assertFalse(invoice_overdue.is_overdue(fresh(make_invoice(self.org, void=True)),
                                                    today=date(2026, 11, 1)))
        self.assertFalse(invoice_overdue.is_overdue(fresh(make_invoice(self.org, sent=False)),
                                                    today=date(2026, 11, 1)))

    def test_today_is_the_kuala_lumpur_date_not_the_utc_one(self):
        inv = fresh(make_invoice(self.org))
        # 00:30 on 16 October in Kuala Lumpur is still 15 October in UTC: overdue already.
        with mock.patch('django.utils.timezone.now',
                        return_value=datetime(2026, 10, 15, 16, 30, tzinfo=dt_timezone.utc)):
            self.assertTrue(invoice_overdue.is_overdue(inv))
            self.assertEqual(invoice_overdue.days_overdue(inv), 1)
        # 23:30 on 15 October in Kuala Lumpur: the due date itself, not yet.
        with mock.patch('django.utils.timezone.now',
                        return_value=datetime(2026, 10, 15, 15, 30, tzinfo=dt_timezone.utc)):
            self.assertFalse(invoice_overdue.is_overdue(inv))

    def test_the_summary_names_the_oldest_and_counts_the_rest(self):
        today = date(2026, 11, 9)
        self.assertIsNone(invoice_overdue.org_summary(self.org.id, today=today))
        newer = make_invoice(self.org, due_on=date(2026, 10, 30), total='50.00')
        older = make_invoice(self.org, due_on=date(2026, 10, 15), total='120.50')
        receipt(older, '20.50')
        make_invoice(self.org, due_on=date(2026, 11, 20))            # not due yet
        declaration(make_invoice(self.org, due_on=date(2026, 9, 1)))  # declared: being checked
        make_invoice(self.org, due_on=date(2026, 9, 1), sent=False)   # never sent
        other = PartnerOrganisation.objects.create(code='overdue-b', name='Tenant B')
        make_invoice(other, due_on=date(2026, 8, 1))                  # another tenant's
        s = invoice_overdue.org_summary(self.org.id, today=today)
        self.assertEqual(s, {
            'invoice_id': older.id, 'number': older.number, 'currency': 'MYR',
            'balance_myr': '100.00', 'due_on': '2026-10-15', 'days_overdue': 25,
            'count': 2, 'more': 1,
        })
        self.assertNotEqual(s['invoice_id'], newer.id)
        self.assertIsNone(invoice_overdue.org_summary(None, today=today))


class TestTheDoor(_Doors):
    """The real endpoint. `_Doors` pins the clock at 09:00 on 15 September 2026, Kuala Lumpur."""

    def overdue_here(self):
        return make_invoice(self.org, due_on=date(2026, 9, 1), issued_on=date(2026, 8, 15))

    def test_an_org_admin_reads_its_own_oldest_overdue_invoice(self):
        inv = self.overdue_here()
        body = self.client_for('oa-a').get(f'{BASE}/overdue/').json()
        self.assertEqual(body['overdue']['number'], inv.number)
        self.assertEqual(body['overdue']['days_overdue'], 14)
        self.assertEqual(body['overdue']['balance_myr'], '100.00')
        self.assertEqual(body['overdue']['more'], 0)

    def test_nothing_overdue_answers_none(self):
        self.assertEqual(self.client_for('oa-a').get(f'{BASE}/overdue/').json(), {'overdue': None})

    def test_another_tenant_never_sees_this_tenants_bill(self):
        self.overdue_here()
        _other, _admin = self.second_tenant()
        r = self.client_for('oa-b').get(f'{BASE}/overdue/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'overdue': None})

    def test_the_super_has_no_organisation_and_is_not_nagged(self):
        self.overdue_here()
        self.assertEqual(self.client_for('super-uid').get(f'{BASE}/overdue/').json(), {'overdue': None})

    def test_reviewer_and_finance_are_refused(self):
        self.overdue_here()
        for role in ('reviewer', 'finance', 'admin'):
            with self.subTest(role=role):
                PartnerAdmin.objects.create(supabase_user_id=f'{role}-uid', role=role, is_active=True,
                                            owning_organisation=self.org, name=role, email=f'{role}@x.com')
                self.assertEqual(self.client_for(f'{role}-uid').get(f'{BASE}/overdue/').status_code, 403)

    def test_dark_billing_is_a_404_for_the_tenant(self):
        self.overdue_here()
        with self.settings(BILLING_USAGE_ENABLED=False):
            self.assertEqual(self.client_for('oa-a').get(f'{BASE}/overdue/').status_code, 404)

    def test_the_invoice_list_serves_the_same_flag_the_banner_reads(self):
        late = self.overdue_here()
        on_time = make_invoice(self.org, due_on=date(2026, 9, 30), issued_on=date(2026, 8, 15))
        rows = {i['id']: i for i in self.client_for('oa-a').get(f'{BASE}/invoices/').json()['invoices']}
        self.assertIs(rows[late.id]['is_overdue'], True)
        self.assertIs(rows[on_time.id]['is_overdue'], False)
        banner = self.client_for('oa-a').get(f'{BASE}/overdue/').json()['overdue']
        self.assertEqual([i for i, r in rows.items() if r['is_overdue']], [banner['invoice_id']])
