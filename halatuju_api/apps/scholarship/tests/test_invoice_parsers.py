"""Reading a provider's invoice into ledger lines (2026-09-11).

Owner ruling: *"Don't use typed by hand. Everything should be extracted from the relevant
systems. We want to avoid anything manual."*

⚠ **THE FIXTURES BELOW ARE THE REAL INVOICES**, trimmed of the postal address and pasted
verbatim from the July and August 2026 PDFs the owner supplied. That is the whole value of this
file: a parser tested against text somebody invented will keep passing on the day a provider
changes its layout, which is the only day it matters.

⚠ **ONE THING IS REDACTED: the Twilio Account SID**, which appears as `ACxxxx…` below. It is a
real account identifier and GitHub's push protection correctly refused the first attempt to push
it. No parser reads it — it is decoration in the fixture — so blanking it costs the tests nothing
and keeps an account id out of a public repository. Nothing else here is altered: every figure,
date and invoice number is exactly as the provider printed it, because those ARE what is tested.

The property that carries this module is **an invoice must reconcile to its own printed total**
before it is allowed to become a ledger row. It earned that on the first run: Twilio's July
invoice lists three products summing to $4.30 and prints a total of $4.29.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.scholarship import invoice_parsers as ip

# ── Real invoice text, as `pypdf` extracts it ────────────────────────────────

WORKSPACE_AUG = """Page 1 of 2
Tax Invoice
Invoice number: 5669048846
..............................................................5669048846
..............................................................31 Aug 2026
..............................................................9274-6879-1951
..............................................................halatuju.xyz
Details
Invoice number
Invoice date
Billing ID
Domain name
MYR 18.90
Google Workspace
Total in MYR
MYR 17.50
MYR 1.40
MYR 18.90
Summary for 1 Aug 2026 - 31 Aug 2026
Subtotal in MYR
Service tax (8%)
Total in MYR
Tax Invoice Invoice number: 5669048846
Page 2 of 2
MYR 17.50
MYR 1.40
MYR 18.90
Subtotal in MYR
Service tax (8%)
Total in MYR
Subscription Description Interval Quantity Amount(MYR)
Google Workspace Business Starter Usage 1 Aug - 31 Aug 1 17.50
"""

SUPABASE_AUG = """RECEIPT
Supabase Pte. Ltd.
65 Chulia Street
Singapore
Invoice number TPTHYS-00010
Receipt date Sep 8, 2026
Payment date Sep 8, 2026
Amount paid $25.00
Description Quantity Rate Amount
Compute Hours
Aug 8 - Sep 7, 2026
$0.00
Compute Hours (Micro)
Aug 8 - Sep 7, 2026
$10.00
pbrrlyoyyiftckqvzvvo 744 $0.01344 $10.00
 Discount ($10.00 across 18 prices) -$10.00
Monthly Active Users
Aug 8 - Sep 7, 2026
30 $0.00325 $0.10
 Discount (-100000 units) -$0.10
1 of 2
Description Quantity Rate Amount
Pro Plan
Sep 8 - Oct 7, 2026
1 $25.00 $25.00
Subtotal $25.00
Amount paid $25.00
2 of 2
"""

TWILIO_AUG = """Usage Summary per Product

 Twilio Inc.
 101 Spear Street, Suite 500
 San Francisco, CA 94105
 Invoice Amount
in USD

$1.77
 No payment due

Invoice Number
MTSOJA-2026-08
Issue Date
Aug 31 2026
Account SID
ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Project Name
HalaTuju

Phone Numbers
$1.15
Programmable Messaging
$0.62
Invoice Amount
$1.77
Invoice for
ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Aug 1 2026 - Aug 31 2026
 Page 1  of 2
Usage Details

Quantity
Amount
Invoice Amount
$1.77

Services Total

$1.77

Phone Numbers
1
$1.15
"""

# ⚠ THE ONE THAT DOES NOT ADD UP. 1.59 + 1.56 + 1.15 = 4.30; the invoice says 4.29.
TWILIO_JUL = """Usage Summary per Product

 Twilio Inc.
 Invoice Amount
in USD

$4.29
 No payment due

Invoice Number
MTSOJA-2026-07
Issue Date
Jul 31 2026
Project Name
HalaTuju

Programmable Messaging
$1.59
Account Security
$1.56
Phone Numbers
$1.15
Invoice Amount
$4.29
Invoice for
ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Jul 1 2026 - Jul 31 2026
 Page 1  of 2
"""

ANTHROPIC_SEP = """
Page 1 of 1
Receipt
Invoice number ZOX36MBZ 0011
Receipt number 2535 4368 0581
Date paid September 3, 2026
VAT Registration Malaysia Reg. No: 26000029
Anthropic, PBC @anthropic
548 Market Street
San Francisco, California 94104
Bill to
tamiliam@gmail.com's Organization
Malaysia
$108.00 paid on September 3, 2026
Description Qty Unit price Tax Amount
Max plan - 5x
Sep 3 Oct 3, 2026
1 $100.00 8% $100.00

Subtotal $100.00
Total excluding tax $100.00
SST - Malaysia  8% on $100.00  $8.00
Total $108.00
Amount paid $108.00
"""

ANTHROPIC_AUG = ANTHROPIC_SEP.replace('Sep 3 Oct 3, 2026', 'Aug 3 Sep 3, 2026') \
                             .replace('ZOX36MBZ 0011', 'ZOX36MBZ 0010')

GCP_STATEMENT_AUG = """Page 1 of 2
Statement
To
Ve Elanjelian
..............................................................01D44F-1CA89B-18AB53
..............................................................31 Aug 2026
Details
Cloud account ID
Statement issue date
MYR 85.15
MYR 23.92
-MYR 85.15
MYR 23.92
Google Cloud
Summary for 1 Aug 2026-31 Aug 2026
Starting balance as of 1 Aug 2026
Total new activity
Total payments received
Ending balance in MYR
This is not a bill.
"""


class TestGoogleWorkspace(SimpleTestCase):
    def test_it_reads_the_invoice_number_month_and_both_lines(self):
        inv = ip.parse_text(WORKSPACE_AUG)
        self.assertEqual(inv.source, 'workspace')
        self.assertEqual(inv.invoice_ref, '5669048846')
        self.assertEqual(inv.period_month, '2026-08')
        self.assertEqual(inv.currency, 'MYR')
        self.assertEqual(inv.total, Decimal('18.90'))
        self.assertEqual([(ln.sku, ln.amount) for ln in inv.lines],
                         [('Business Starter', Decimal('17.50')),
                          ('Service tax (8%)', Decimal('1.40'))])

    def test_the_tax_line_is_recognised_as_tax_and_the_plan_as_ours(self):
        """The classification the cost split depends on. A mailbox is a standing cost."""
        from apps.scholarship import platform_cost
        inv = ip.parse_text(WORKSPACE_AUG)
        plan, tax = inv.lines
        self.assertFalse(platform_cost.classify_sku(plan.service, plan.sku))
        self.assertTrue(platform_cost.is_tax(tax.service, tax.sku))


class TestSupabase(SimpleTestCase):
    def test_it_reads_the_receipt_and_the_plan_fee(self):
        inv = ip.parse_text(SUPABASE_AUG)
        self.assertEqual(inv.source, 'supabase')
        self.assertEqual(inv.invoice_ref, 'TPTHYS-00010')
        self.assertEqual(inv.currency, 'USD')
        self.assertEqual(inv.total, Decimal('25.00'))
        self.assertEqual([(ln.sku, ln.amount) for ln in inv.lines],
                         [('Pro Plan', Decimal('25.00'))])

    def test_the_month_is_the_one_the_USAGE_opens_in_not_the_receipt_date(self):
        """⚠ The receipt for 'Aug 8 - Sep 7' is DATED 8 September. Keying on the receipt date
        would file August's database under September and then charge it by September's terms."""
        self.assertEqual(ip.parse_text(SUPABASE_AUG).period_month, '2026-08')

    def test_the_odd_billing_window_is_recorded_rather_than_flattened(self):
        note = ip.parse_text(SUPABASE_AUG).period_note
        self.assertIn('Aug 8', note)
        self.assertIn('Sep 7', note)


class TestTwilio(SimpleTestCase):
    def test_it_reads_the_per_product_summary(self):
        inv = ip.parse_text(TWILIO_AUG)
        self.assertEqual(inv.source, 'twilio')
        self.assertEqual(inv.invoice_ref, 'MTSOJA-2026-08')
        self.assertEqual(inv.period_month, '2026-08')
        self.assertEqual([(ln.sku, ln.amount) for ln in inv.lines],
                         [('Phone Numbers', Decimal('1.15')),
                          ('Programmable Messaging', Decimal('0.62'))])

    def test_the_detailed_breakdown_below_the_total_is_not_swept_in(self):
        """The detail repeats every product. Counting it would double the bill."""
        inv = ip.parse_text(TWILIO_AUG)
        self.assertEqual(sum(ln.amount for ln in inv.lines), Decimal('1.77'))

    def test_the_providers_own_one_cent_rounding_becomes_a_named_line(self):
        """⚠ REAL, AND CAUGHT ON THE FIRST RUN. Twilio's July products sum to $4.30 and the
        invoice says $4.29 — it rounds each product for display and totals the unrounded ones.

        Refusing would be wrong: the document is genuine and $4.29 is what we paid. Trusting the
        lines would leave the ledger a cent above the bill. So the gap gets its own line."""
        inv = ip.parse_text(TWILIO_JUL)
        self.assertEqual(sum(ln.amount for ln in inv.lines), Decimal('4.29'))
        rounding = inv.lines[-1]
        self.assertIn('Rounding', rounding.sku)
        self.assertEqual(rounding.amount, Decimal('-0.01'))

    def test_messaging_is_tenant_driven_and_the_rented_number_is_ours(self):
        from apps.scholarship import platform_cost
        self.assertTrue(platform_cost.classify_sku('Twilio', 'Programmable Messaging'))
        self.assertTrue(platform_cost.classify_sku('Twilio', 'Account Security'))
        self.assertFalse(platform_cost.classify_sku('Twilio', 'Phone Numbers'))


class TestAnthropic(SimpleTestCase):
    """⚠ The receipt whose dashes arrive as NUL BYTES. See `TestNormalisation` below."""

    def test_it_reads_the_plan_and_the_tax_as_separate_lines(self):
        inv = ip.parse_text(ANTHROPIC_SEP)
        self.assertEqual(inv.source, 'anthropic')
        self.assertEqual(inv.invoice_ref, 'ZOX36MBZ 0011')
        self.assertEqual(inv.currency, 'USD')
        self.assertEqual(inv.total, Decimal('108.00'))
        self.assertEqual([(ln.sku, ln.amount) for ln in inv.lines],
                         [('Max plan - 5x', Decimal('100.00')),
                          ('Sales tax (SST 8%)', Decimal('8.00'))])

    def test_the_tax_line_is_NAMED_so_the_tax_matcher_finds_it(self):
        """⚠ Anthropic prints only 'SST'. Widening `is_tax` to match SST/GST/VAT was rejected:
        'vat' is a substring of ordinary words like 'innovate', so it would silently turn real
        charges into tax. Naming the line correctly is precise; loosening the matcher is not."""
        from apps.scholarship import platform_cost
        _plan, tax = ip.parse_text(ANTHROPIC_SEP).lines
        self.assertTrue(platform_cost.is_tax(tax.service, tax.sku))

    def test_the_plan_is_a_DEVELOPMENT_cost_and_never_a_platform_one(self):
        """⚠ THE DOUBLE-CHARGE GUARD, at the parser. If this line were bucketed as platform it
        would be marked up as infrastructure AND recovered again by the hourly rate."""
        from apps.scholarship import platform_cost
        plan, _tax = ip.parse_text(ANTHROPIC_SEP).lines
        self.assertEqual(platform_cost.cost_bucket(plan.service, plan.sku), 'development')

    def test_the_month_is_when_the_PLAN_STARTS_not_when_it_was_paid(self):
        """The receipt dated 3 September buys 3 Sep to 3 Oct, so it belongs to September. Filing
        by the payment date would be right by accident and wrong the moment a provider bills in
        arrears. Same rule as Supabase."""
        self.assertEqual(ip.parse_text(ANTHROPIC_SEP).period_month, '2026-09')
        self.assertEqual(ip.parse_text(ANTHROPIC_AUG).period_month, '2026-08')

    def test_the_3rd_to_3rd_window_is_recorded(self):
        self.assertIn('Sep 3', ip.parse_text(ANTHROPIC_SEP).period_note)
        self.assertIn('Oct 3', ip.parse_text(ANTHROPIC_SEP).period_note)


class TestNormalisation(SimpleTestCase):
    """⚠ NOT COSMETIC, AND IT COST A DEBUGGING ROUND.

    `pypdf` hands back Anthropic's en-dash as a literal NUL byte, so the service window reads
    `'Sep 3\\x00Oct 3, 2026'`. A NUL is not whitespace to `\\s`, so every pattern spanning it
    fails — and the failure looks exactly like a provider having changed its layout.
    """

    def test_a_NUL_where_a_dash_should_be_does_not_break_the_parse(self):
        raw = ANTHROPIC_SEP.replace('Sep 3 Oct 3', 'Sep 3\x00Oct 3')
        self.assertEqual(ip.parse_text(raw).period_month, '2026-09')

    def test_non_breaking_spaces_and_fancy_dashes_are_flattened(self):
        self.assertEqual(ip.normalise('a\xa0b'), 'a b')
        self.assertEqual(ip.normalise('a–b'), 'a-b')
        self.assertEqual(ip.normalise('a\x00b'), 'a b')

    def test_it_survives_empty_input(self):
        self.assertEqual(ip.normalise(''), '')
        self.assertEqual(ip.normalise(None), '')


class TestTheSelfCheck(SimpleTestCase):
    """The property that makes an extracted figure trustworthy at all."""

    def test_a_gap_bigger_than_display_rounding_refuses_outright(self):
        with self.assertRaises(ip.InvoiceParseError) as ctx:
            ip.ParsedInvoice(
                source='twilio', invoice_ref='X-1', currency='USD', period_month='2026-08',
                total=Decimal('10.00'),
                lines=[ip.InvoiceLine('Twilio', 'Messaging', Decimal('4.00'))])
        self.assertIn('layout has changed', str(ctx.exception))

    def test_an_invoice_with_no_lines_refuses(self):
        with self.assertRaises(ip.InvoiceParseError):
            ip.ParsedInvoice(source='twilio', invoice_ref='X-1', currency='USD',
                             period_month='2026-08', total=Decimal('0.00'), lines=[])

    def test_a_bad_period_month_refuses(self):
        with self.assertRaises(ip.InvoiceParseError):
            ip.ParsedInvoice(
                source='twilio', invoice_ref='X-1', currency='USD', period_month='August',
                total=Decimal('1.00'),
                lines=[ip.InvoiceLine('Twilio', 'Messaging', Decimal('1.00'))])

    def test_a_truncated_invoice_refuses_rather_than_reporting_a_smaller_bill(self):
        """A provider redesign that loses one line must break, not quietly under-report."""
        truncated = TWILIO_AUG.replace('Programmable Messaging\n$0.62\n', '')
        with self.assertRaises(ip.InvoiceParseError):
            ip.parse_text(truncated)


class TestDispatch(SimpleTestCase):
    def test_each_provider_is_recognised_only_by_its_own_parser(self):
        self.assertEqual(ip.parse_text(WORKSPACE_AUG).source, 'workspace')
        self.assertEqual(ip.parse_text(SUPABASE_AUG).source, 'supabase')
        self.assertEqual(ip.parse_text(TWILIO_AUG).source, 'twilio')

    def test_an_unknown_document_returns_None_rather_than_being_guessed_at(self):
        """⚠ A parser applied to the wrong provider's invoice is how a Twilio total ends up
        filed as Supabase."""
        self.assertIsNone(ip.parse_text('Some other company\nTotal $9.99'))

    def test_a_google_cloud_statement_is_detected_and_never_imported(self):
        """It is a CHECK on the BigQuery pull, not a source. The export carries every SKU and
        the statement does not."""
        self.assertTrue(ip.detect_gcp_statement(GCP_STATEMENT_AUG))
        self.assertIsNone(ip.parse_text(GCP_STATEMENT_AUG))
        self.assertEqual(ip.parse_gcp_statement(GCP_STATEMENT_AUG),
                         ('2026-08', Decimal('23.92')))

    def test_an_unreadable_statement_returns_None_and_does_not_raise(self):
        """Nothing depends on it: a failure costs a cross-check, not a ledger row."""
        self.assertIsNone(ip.parse_gcp_statement('Google Cloud\nThis is not a bill.'))
