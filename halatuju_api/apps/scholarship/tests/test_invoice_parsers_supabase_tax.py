"""Supabase's first receipt with a TAX line (TPTHYS-00012, dated 8 November 2026).

Every Supabase document before it printed `Subtotal` and `Amount paid` as the same figure. This
one adds Malaysian service tax on the line between them — 'MY (8%) $2.00' — and the parser
refused it ("subtotal 25.00 and amount paid/due 27 disagree"), which left October without a
Supabase row and would have refused every tenant's October invoice on the 15 November run.

⚠ **THE FIXTURE IS THE TEXT `invoice_parsers.pdf_text` RETURNS FOR THE REAL RECEIPT**, cut down to
labels, amounts, the receipt number and dates. Removed: the billing name, address and email,
Supabase's own address and registration numbers, and the project reference on each usage line
(shown as `xxxx…`, as `test_invoice_parsers.py` does for the Twilio SID). Nothing a parser reads
was changed — including `$27 .00`, which is how `pypdf` really hands back the total, stray space
and all. The em spaces before each 'Discount' are real too.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.scholarship import invoice_parsers as ip
from apps.scholarship import platform_cost
from apps.scholarship.tests.test_invoice_parsers import SUPABASE_AUG, SUPABASE_SEP_INVOICE

SUPABASE_OCT_TAXED = """RECEIPT
Supabase Pte. Ltd.
Invoice number TPTHYS-00012
Receipt date Nov 8, 2026
Payment date Nov 8, 2026
Amount paid $27 .00
Description Quantity Rate Amount
Compute Hours
Oct 8 - Nov 7, 2026
$0.00
Compute Hours (Micro)
Oct 8 - Nov 7, 2026
$10.00
xxxxxxxxxxxxxxxxxxxx 744 $0.01344 $10.00
 Discount ($10.00 across 18 prices) -$10.00
Cached Egress GB
Oct 8 - Nov 7, 2026
$0.86
xxxxxxxxxxxxxxxxxxxx 28.82889 $0.03 $0.86
 Discount (-250 units) -$0.86
Egress GB
Oct 8 - Nov 7, 2026
$0.93
xxxxxxxxxxxxxxxxxxxx 10.284916 $0.09 $0.93
 Discount (-250 units) -$0.93
Function Invocations
Oct 8 - Nov 7, 2026
$2.00
$2.00 per 1,000,000 6 1 × $2.00 $2.00
 Discount (-2000000 units) -$2.00
Monthly Active Users
Oct 8 - Nov 7, 2026
1,023 $0.00325 $3.32
1 of 2
Description Quantity Rate Amount
 Discount (-100000 units) -$3.32
Storage Size GB-Hrs
Oct 8 - Nov 7, 2026
$0.04
xxxxxxxxxxxxxxxxxxxx 1,478.900522 $0.00002919 $0.04
 Discount (-74400 units) -$0.04
Pro Plan
Nov 8 - Dec 7, 2026
1 $25.00 $25.00
Memo:
For Singapore: GST is applied
For other countries: Prices are Net
Reverse charge: Customer to account for VAT/GST to their relevant authority
Subtotal $25.00
MY (8%) $2.00
Amount paid $27 .00
2 of 2"""


class TestSupabaseTaxLine(SimpleTestCase):
    def test_the_taxed_receipt_reads_as_the_plan_plus_a_separate_tax_line(self):
        inv = ip.parse_text(SUPABASE_OCT_TAXED)
        self.assertEqual(inv.source, 'supabase')
        self.assertEqual(inv.invoice_ref, 'TPTHYS-00012')
        self.assertEqual(inv.currency, 'USD')
        self.assertEqual(inv.period_month, '2026-10')
        self.assertEqual(inv.total, Decimal('27.00'))
        self.assertEqual([(ln.service, ln.sku, ln.amount) for ln in inv.lines],
                         [('Supabase', 'Pro Plan', Decimal('25.00')),
                          ('Invoice', 'Service tax (MY 8%)', Decimal('2.00'))])

    def test_the_tax_line_lands_in_the_tax_bucket_and_the_plan_where_it_always_did(self):
        """The Google Workspace pattern: tax is its own line, so `is_tax` recognises it and it
        lands in neither cost bucket. The plan keeps the bucket the tax-free receipts give it."""
        plan, tax = ip.parse_text(SUPABASE_OCT_TAXED).lines
        (old_plan,) = ip.parse_text(SUPABASE_AUG).lines
        self.assertEqual(platform_cost.cost_bucket(tax.service, tax.sku), 'tax')
        self.assertEqual(platform_cost.cost_bucket(plan.service, plan.sku),
                         platform_cost.cost_bucket(old_plan.service, old_plan.sku))

    def test_the_stray_space_pypdf_puts_in_the_total_is_read_as_one_figure(self):
        """`$27 .00` must read as 27.00, not stop at 27."""
        self.assertEqual(str(ip.parse_text(SUPABASE_OCT_TAXED).total), '27.00')

    def test_a_tax_free_receipt_still_parses_exactly_as_before(self):
        for text, ref in ((SUPABASE_AUG, 'TPTHYS-00010'), (SUPABASE_SEP_INVOICE, 'TPTHYS-00011')):
            with self.subTest(ref=ref):
                inv = ip.parse_text(text)
                self.assertEqual(inv.invoice_ref, ref)
                self.assertEqual(inv.total, Decimal('25.00'))
                self.assertEqual([(ln.service, ln.sku, ln.amount) for ln in inv.lines],
                                 [('Supabase', 'Pro Plan', Decimal('25.00'))])

    def test_the_same_receipt_without_its_tax_line_reads_as_one_plan_line(self):
        untaxed = SUPABASE_OCT_TAXED.replace('MY (8%) $2.00\n', '') \
                                    .replace('Amount paid $27 .00', 'Amount paid $25.00')
        inv = ip.parse_text(untaxed)
        self.assertEqual([(ln.sku, ln.amount) for ln in inv.lines],
                         [('Pro Plan', Decimal('25.00'))])

    def test_a_wrong_total_is_still_refused(self):
        wrong = SUPABASE_OCT_TAXED.replace('Amount paid $27 .00', 'Amount paid $28.00')
        with self.assertRaises(ip.InvoiceParseError) as caught:
            ip.parse_text(wrong)
        self.assertIn('subtotal 25.00 plus tax 2.00 and amount paid/due 28.00 disagree',
                      str(caught.exception))

    def test_a_wrong_tax_figure_is_refused(self):
        with self.assertRaises(ip.InvoiceParseError):
            ip.parse_text(SUPABASE_OCT_TAXED.replace('MY (8%) $2.00', 'MY (8%) $1.50'))

    def test_a_tax_line_in_a_shape_it_cannot_read_is_refused_not_ignored(self):
        """An unread tax line leaves subtotal != amount, so the receipt refuses loudly."""
        with self.assertRaises(ip.InvoiceParseError) as caught:
            ip.parse_text(SUPABASE_OCT_TAXED.replace('MY (8%) $2.00', 'Sales levy $2.00'))
        self.assertIn('subtotal 25.00 and amount paid/due 27.00 disagree', str(caught.exception))

    def test_a_dollar_figure_elsewhere_on_the_page_is_never_read_as_tax(self):
        """Only the line directly under the subtotal can be tax."""
        moved = SUPABASE_OCT_TAXED.replace('Subtotal $25.00\nMY (8%) $2.00\n', 'Subtotal $25.00\n')
        moved = moved.replace('Memo:\n', 'Memo:\nMY (8%) $2.00\n')
        with self.assertRaises(ip.InvoiceParseError):
            ip.parse_text(moved)
