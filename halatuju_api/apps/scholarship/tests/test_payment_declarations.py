"""The tenant declares a payment; the owner checks the bank (2026-10-29).

The owner signed in as BrightPath's org_admin, read the billing page and said: *"there doesn't
seem to be a way for the client to enter anything to claim settlement."*

⚠ **THE ONE RULE THESE TESTS GUARD: A DECLARATION IS NOT MONEY.** If a tenant's claim could mint
a receipt, a customer could mark their own invoice paid. So every test below that exercises the
tenant's side also asserts that no receipt exists and the balance has not moved.

What else is held:

1. **Date and bank reference only** — the owner's choice. No amount is accepted from the tenant,
   and no file. A test asserts the endpoint ignores an amount if one is sent anyway.
2. **The fence is asserted AT THE DOOR, from the widening side** (TD-241): a second tenant naming
   this tenant's invoice, and a declaration id belonging to another invoice.
3. **Each side may only do its own act.** A super may not declare for a customer; an org_admin may
   not confirm its own claim.
4. **A refused confirmation leaves the claim OPEN**, so an overpayment typo does not quietly close
   a claim against nothing.
"""
from decimal import Decimal

from apps.scholarship import invoicing, payment_declarations
from apps.scholarship.models import InvoicePaymentDeclaration
from apps.scholarship.tests.test_invoicing import SEPT_15
from apps.scholarship.tests.test_invoice_endpoints import _Doors, _walk_for_floats

#: ⚠ SPELT OUT HERE rather than imported from `test_invoice_endpoints`, which also defines it.
#: `test_endpoint_exercise.py` proves every wired route is driven by reading test modules with
#: the AST — it follows a module-level constant but cannot follow an IMPORTED name, so an
#: imported `BASE` leaves every URL below unreconstructable and the new route reads as never
#: exercised. The duplication is the price of being watched by that guard.
BASE = '/api/v1/admin/scholarship/billing'

PAID_ON = '2026-09-15'
REF = 'MBB-FT-77421'


class _World(_Doors):

    def declared(self, inv=None, reference=REF, paid_on=PAID_ON):
        inv = inv or self.sent()
        d = payment_declarations.declare_payment(
            inv, paid_on=paid_on, reference=reference, declared_by_email='oa@x.com')
        return inv, d

    def reread(self, inv):
        from apps.scholarship.models import Invoice
        return Invoice.objects.get(pk=inv.pk)


# ── The service ──────────────────────────────────────────────────────────────

class TestDeclaring(_World):

    def test_a_declaration_records_the_claim_and_mints_nothing(self):
        inv, d = self.declared()
        self.assertEqual(d.reference, REF)
        self.assertEqual(d.declared_by_email, 'oa@x.com')
        self.assertTrue(d.is_open)
        # ⚠ THE WHOLE POINT. Nothing was received, so nothing is owed any less.
        fresh = self.reread(inv)
        self.assertEqual(fresh.receipts.count(), 0)
        self.assertEqual(fresh.amount_paid(), Decimal('0.00'))
        self.assertEqual(fresh.balance(), Decimal(fresh.total_myr))
        self.assertEqual(fresh.status, 'payment_declared')

    def test_a_blank_reference_is_refused(self):
        inv = self.sent()
        for blank in ('', '   ', None):
            with self.subTest(blank=repr(blank)):
                with self.assertRaises(invoicing.InvoicingError) as cm:
                    payment_declarations.declare_payment(inv, paid_on=PAID_ON, reference=blank)
                self.assertEqual(cm.exception.code, 'reference_required')

    def test_a_date_that_is_not_a_date_or_is_in_the_future_is_refused(self):
        inv = self.sent()
        for bad, code in (('yesterday', 'bad_date'), ('', 'bad_date'),
                          ('2026-09-16', 'bad_date'), ('2026-13-01', 'bad_date')):
            with self.subTest(bad=bad):
                with self.assertRaises(invoicing.InvoicingError) as cm:
                    payment_declarations.declare_payment(inv, paid_on=bad, reference=REF)
                self.assertEqual(cm.exception.code, code)

    def test_a_payment_dated_before_the_invoice_is_refused(self):
        """Money cannot leave an account for a bill that does not exist yet. The back-dated
        invoices make this reachable: August's is dated 15 September."""
        inv = self.sent()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.declare_payment(inv, paid_on='2026-08-20', reference=REF)
        self.assertEqual(cm.exception.code, 'paid_before_issued')

    def test_an_unsent_invoice_cannot_be_declared_against(self):
        """The tenant cannot SEE it, so the claim cannot be theirs."""
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.declare_payment(self.issued(), paid_on=PAID_ON, reference=REF)
        self.assertEqual(cm.exception.code, 'not_sent')

    def test_a_voided_invoice_cannot_be_declared_against(self):
        inv = self.sent()
        invoicing.void_invoice(inv, reason='Wrong month.')
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.declare_payment(
                self.reread(inv), paid_on=PAID_ON, reference=REF)
        self.assertEqual(cm.exception.code, 'invoice_void')

    def test_a_settled_invoice_cannot_be_declared_against(self):
        inv = self.sent()
        invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr=inv.total_myr,
                                 reference='MBB1', today=SEPT_15)
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.declare_payment(
                self.reread(inv), paid_on=PAID_ON, reference=REF)
        self.assertEqual(cm.exception.code, 'already_paid')

    def test_only_one_claim_may_be_open_at_a_time(self):
        inv, _ = self.declared()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.declare_payment(
                self.reread(inv), paid_on=PAID_ON, reference='MBB-OTHER')
        self.assertEqual(cm.exception.code, 'already_declared')

    def test_the_database_itself_refuses_a_second_open_claim(self):
        """⚠ THE CONSTRAINT IS THE REAL GUARD. Two org_admins pressing the button together both
        pass the read in `declare_payment` and one must lose the write. This writes straight past
        that read to prove the partial unique index, not the `if`, is what holds."""
        from django.db import IntegrityError, transaction

        inv, _ = self.declared()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InvoicePaymentDeclaration.objects.create(
                    invoice=inv, paid_on='2026-09-15', reference='MBB-RACE')

    def test_the_losing_racer_gets_the_ordinary_refusal_not_a_500(self):
        """⚠ THE RACE ITSELF, with the read blinded so the write has to do the refusing. Without
        this the `except IntegrityError` branch is never exercised, and a real second clicker
        would get a 500 instead of being told a claim is already waiting."""
        from unittest import mock

        inv, _ = self.declared()
        with mock.patch.object(payment_declarations, 'open_declaration', return_value=None):
            with self.assertRaises(invoicing.InvoicingError) as cm:
                payment_declarations.declare_payment(
                    self.reread(inv), paid_on=PAID_ON, reference='MBB-RACE')
        self.assertEqual(cm.exception.code, 'already_declared')
        self.assertEqual(self.reread(inv).payment_declarations.count(), 1)

    def test_a_settled_claim_does_not_block_the_next_one(self):
        inv, d = self.declared()
        payment_declarations.reject_declaration(d, reason='Nothing on the 15th.')
        again = payment_declarations.declare_payment(
            self.reread(inv), paid_on=PAID_ON, reference='MBB-RIGHT')
        self.assertTrue(again.is_open)
        self.assertEqual(self.reread(inv).payment_declarations.count(), 2)


class TestConfirming(_World):

    def test_confirming_mints_the_receipt_and_closes_the_claim(self):
        inv, d = self.declared()
        receipt = payment_declarations.confirm_payment(
            d, amount_myr=inv.total_myr, confirmed_by_email='super@x.com')
        d.refresh_from_db()
        self.assertFalse(d.is_open)
        self.assertEqual(d.receipt_id, receipt.pk)
        self.assertEqual(d.confirmed_by_email, 'super@x.com')
        self.assertEqual(receipt.recorded_by_email, 'super@x.com')
        fresh = self.reread(inv)
        self.assertEqual(fresh.status, 'paid')
        self.assertEqual(fresh.balance(), Decimal('0.00'))

    def test_the_declared_date_and_reference_are_used_unless_corrected(self):
        inv, d = self.declared()
        receipt = payment_declarations.confirm_payment(d, amount_myr='10.00')
        self.assertEqual(receipt.received_on.isoformat(), PAID_ON)
        self.assertEqual(receipt.reference, REF)

    def test_the_owner_may_correct_the_date_and_the_reference(self):
        """⚠ THE OWNER'S FIGURES WIN. The correction goes on the RECEIPT, which is the document
        that counts; the tenant's claim is left as they wrote it.

        The invoice is BACK-DATED to the 10th so that a correction has somewhere to land: an
        invoice issued today can only have been paid today, and `record_receipt` rightly refuses
        anything earlier than the bill itself.
        """
        inv = invoicing.issue_invoice(self.org, '2026-08', today=SEPT_15, issued_on='2026-09-10')
        invoicing.send_invoice(inv)
        _, d = self.declared(inv=inv)
        receipt = payment_declarations.confirm_payment(
            d, amount_myr='10.00', received_on='2026-09-12', reference='MBB-REAL-99')
        self.assertEqual(receipt.received_on.isoformat(), '2026-09-12')
        self.assertEqual(receipt.reference, 'MBB-REAL-99')
        d.refresh_from_db()
        self.assertEqual(d.reference, REF)
        self.assertEqual(d.paid_on.isoformat(), PAID_ON)

    def test_a_refused_amount_leaves_the_claim_open_and_mints_nothing(self):
        """An overpayment typo must not quietly close a claim against nothing."""
        inv, d = self.declared()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.confirm_payment(d, amount_myr='99999.00')
        self.assertEqual(cm.exception.code, 'overpayment')
        d.refresh_from_db()
        self.assertTrue(d.is_open)
        self.assertEqual(self.reread(inv).receipts.count(), 0)

    def test_a_claim_already_dealt_with_cannot_be_confirmed_or_rejected_again(self):
        inv, d = self.declared()
        payment_declarations.confirm_payment(d, amount_myr='10.00')
        d.refresh_from_db()
        for call in (lambda: payment_declarations.confirm_payment(d, amount_myr='10.00'),
                     lambda: payment_declarations.reject_declaration(d, reason='Changed my mind')):
            with self.subTest(call=call.__name__):
                with self.assertRaises(invoicing.InvoicingError) as cm:
                    call()
                self.assertEqual(cm.exception.code, 'declaration_settled')


    def test_a_second_confirmation_cannot_slip_past_the_first_check(self):
        """⚠ THE RACE, and the reason the row is LOCKED and re-read inside the transaction. Two
        supers confirming at once both pass the `is_open` check on their own copy of the object;
        the second would mint a SECOND receipt, which `record_receipt` only catches when the first
        already covered the whole balance. A partial confirmation would be recorded twice.

        The stale object is the second super's copy, held from before the first confirmed.
        """
        inv, stale = self.declared()
        fresh = InvoicePaymentDeclaration.objects.get(pk=stale.pk)
        payment_declarations.confirm_payment(fresh, amount_myr='10.00')
        self.assertTrue(stale.is_open)                       # the stale copy still says open
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.confirm_payment(stale, amount_myr='10.00')
        self.assertEqual(cm.exception.code, 'declaration_settled')
        self.assertEqual(self.reread(inv).receipts.count(), 1)

    def test_a_rejection_cannot_slip_past_a_confirmation(self):
        inv, stale = self.declared()
        payment_declarations.confirm_payment(
            InvoicePaymentDeclaration.objects.get(pk=stale.pk), amount_myr='10.00')
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.reject_declaration(stale, reason='Could not find it.')
        self.assertEqual(cm.exception.code, 'declaration_settled')
        stale.refresh_from_db()
        self.assertIsNone(stale.rejected_at)
        self.assertEqual(stale.reject_reason, '')


class TestRejecting(_World):

    def test_rejecting_needs_a_reason_and_the_tenant_is_shown_it(self):
        inv, d = self.declared()
        with self.assertRaises(invoicing.InvoicingError) as cm:
            payment_declarations.reject_declaration(d, reason='  ')
        self.assertEqual(cm.exception.code, 'reason_required')

        payment_declarations.reject_declaration(
            d, reason='No credit on the 15th or 16th.', rejected_by_email='super@x.com')
        d.refresh_from_db()
        self.assertFalse(d.is_open)
        self.assertEqual(d.reject_reason, 'No credit on the 15th or 16th.')
        self.assertEqual(d.rejected_by_email, 'super@x.com')
        # Back to simply unpaid. Nothing was ever received, so nothing changes about the money.
        fresh = self.reread(inv)
        self.assertEqual(fresh.status, 'sent')
        self.assertEqual(fresh.receipts.count(), 0)


class TestTheStatusItself(_World):

    def test_money_beats_a_claim(self):
        """A receipt exists, so `part_paid` is the honest word even with a claim open. The STATUS
        says what the bank says, never what somebody told us about the bank."""
        inv = self.sent()
        invoicing.record_receipt(inv, received_on=SEPT_15, amount_myr='10.00',
                                 reference='MBB1', today=SEPT_15)
        payment_declarations.declare_payment(
            self.reread(inv), paid_on=PAID_ON, reference=REF)
        self.assertEqual(self.reread(inv).status, 'part_paid')

    def test_a_void_invoice_with_an_open_claim_still_reads_void(self):
        inv, _ = self.declared()
        invoicing.void_invoice(self.reread(inv), reason='Wrong month.')
        self.assertEqual(self.reread(inv).status, 'void')


# ── The doors ────────────────────────────────────────────────────────────────

class TestTheDoors(_World):

    def url(self, inv, action):
        return f'{BASE}/invoices/{inv.id}/declaration/{action}/'

    def test_an_org_admin_declares_its_own_payment_and_the_payload_comes_back(self):
        inv = self.sent()
        r = self.client_for('oa-a').post(
            self.url(inv, 'declare'), {'paid_on': PAID_ON, 'reference': REF}, format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        _walk_for_floats(self, body)
        self.assertEqual(body['status'], 'payment_declared')
        self.assertEqual(len(body['payment_declarations']), 1)
        decl = body['payment_declarations'][0]
        self.assertEqual(decl['state'], 'open')
        self.assertEqual(decl['reference'], REF)
        self.assertEqual(decl['paid_on'], PAID_ON)
        self.assertEqual(decl['receipt_number'], '')
        # ⚠ Still a tenant payload: the internal fields stay out, and no receipt was minted.
        self.assertNotIn('override_reason', body)
        self.assertEqual(body['receipts'], [])
        self.assertEqual(body['balance_myr'], body['total_myr'])

    def test_an_amount_sent_by_a_tenant_is_ignored(self):
        """⚠ DATE AND REFERENCE ONLY. A tenant-typed amount must not reach the money side even if
        somebody puts one in the request by hand."""
        inv = self.sent()
        r = self.client_for('oa-a').post(
            self.url(inv, 'declare'),
            {'paid_on': PAID_ON, 'reference': REF, 'amount_myr': '1.00'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.reread(inv).receipts.count(), 0)
        self.assertNotIn('amount_myr', r.json()['payment_declarations'][0])

    def test_a_super_may_not_declare_for_a_customer(self):
        inv = self.sent()
        r = self.client_for('super-uid').post(
            self.url(inv, 'declare'), {'paid_on': PAID_ON, 'reference': REF}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.reread(inv).payment_declarations.count(), 0)

    def test_an_org_admin_may_not_confirm_or_reject_its_own_claim(self):
        inv, d = self.declared()
        oa = self.client_for('oa-a')
        for action, data in (('confirm', {'declaration_id': d.id, 'amount_myr': '10.00'}),
                             ('reject', {'declaration_id': d.id, 'reason': 'let me off'})):
            with self.subTest(action=action):
                self.assertEqual(oa.post(self.url(inv, action), data, format='json').status_code,
                                 403)
        d.refresh_from_db()
        self.assertTrue(d.is_open)

    def test_the_owner_confirms_through_the_door(self):
        inv, d = self.declared()
        r = self.client_for('super-uid').post(
            self.url(inv, 'confirm'),
            {'declaration_id': d.id, 'amount_myr': inv.total_myr}, format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'paid')
        self.assertEqual(body['payment_declarations'][0]['state'], 'confirmed')
        self.assertEqual(body['payment_declarations'][0]['receipt_number'], 'RCP-2026-0001')

    def test_the_owner_rejects_through_the_door(self):
        inv, d = self.declared()
        r = self.client_for('super-uid').post(
            self.url(inv, 'reject'),
            {'declaration_id': d.id, 'reason': 'Nothing credited that week.'}, format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'sent')
        self.assertEqual(body['payment_declarations'][0]['state'], 'rejected')
        self.assertEqual(body['payment_declarations'][0]['reject_reason'],
                         'Nothing credited that week.')

    def test_a_second_tenant_naming_this_invoice_gets_the_missing_answer(self):
        """THE FENCE, from the widening side. Not 403 — 404, the same answer as an invoice that
        does not exist, so the id itself leaks nothing."""
        inv = self.sent()
        self.second_tenant()
        r = self.client_for('oa-b').post(
            self.url(inv, 'declare'), {'paid_on': PAID_ON, 'reference': REF}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.reread(inv).payment_declarations.count(), 0)

    def test_an_unsent_invoice_is_not_even_visible_to_declare_against(self):
        inv = self.issued()
        r = self.client_for('oa-a').post(
            self.url(inv, 'declare'), {'paid_on': PAID_ON, 'reference': REF}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_a_declaration_id_from_another_invoice_is_not_found(self):
        """⚠ The declaration is reached THROUGH the invoice, never by its own id. September's
        claim cannot be confirmed against August's bill."""
        aug, d_aug = self.declared()
        # September needs its own supplier rows before it can be issued at all — the same
        # `supplier_missing` / `no_costs` refusals every other month answers to.
        self._cost('2026-09', 'gcp', 'Cloud Run', 'Services CPU', '20.00', attributable=True)
        self._cost('2026-09', 'supabase', 'Supabase', 'Pro Plan', '100.00', attributable=False)
        oct_15 = SEPT_15.replace(month=10)
        sept = invoicing.issue_invoice(self.org, '2026-09', today=oct_15)
        invoicing.send_invoice(sept)
        r = self.client_for('super-uid').post(
            f'{BASE}/invoices/{sept.id}/declaration/confirm/',
            {'declaration_id': d_aug.id, 'amount_myr': '1.00'}, format='json')
        self.assertEqual(r.status_code, 404)
        d_aug.refresh_from_db()
        self.assertTrue(d_aug.is_open)

    def test_a_declaration_id_that_is_not_an_id_is_refused_not_a_500(self):
        inv, d = self.declared()
        sup = self.client_for('super-uid')
        for bad in ('abc', 1.5, True, None, '', [1]):
            with self.subTest(bad=repr(bad)):
                r = sup.post(self.url(inv, 'confirm'),
                             {'declaration_id': bad, 'amount_myr': '1.00'}, format='json')
                self.assertEqual(r.status_code, 404)

    def test_an_unknown_action_is_not_found(self):
        inv = self.sent()
        self.assertEqual(
            self.client_for('oa-a').post(self.url(inv, 'cancel'), {}, format='json').status_code,
            404)

    def test_a_json_array_body_is_a_refusal_not_a_500(self):
        inv = self.sent()
        r = self.client_for('oa-a').post(self.url(inv, 'declare'), [1, 2], format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'reference_required')

    def test_a_refusal_carries_its_code(self):
        inv, _ = self.declared()
        r = self.client_for('oa-a').post(
            self.url(inv, 'declare'), {'paid_on': PAID_ON, 'reference': 'MBB2'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'already_declared')
