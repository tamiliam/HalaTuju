"""Grouped development lines, and bug work charged at zero (owner, 2026-10-29).

The owner read the July-September previews and asked for two changes to the development half of
an invoice:

1. *"the list of items are listed as subitems under, say, feature request, instead of main items.
   And each feature request, too, include the req no in brackets."*
2. *"include bug report as well, and state the hours and rate which is zero, but these need not be
   itemised."*

The second one is not a new pricing rule — it makes an existing one visible. The owner's own note
on the 15% development margin, written 2026-09-11, says: *"The margin should help cover bug fixing
which is not billed separately."* So a bug was always meant to be free, and until this change the
invoice charged it as a feature anyway, which collected for the same work twice.

⚠ **WHICH FIELD DECIDES IS THE WHOLE RISK HERE.** A request carries three opinions about whether
it is a bug: Gemini's `ai_draft_kind`, the submitter's `kind`, and the owner's `triaged_kind`. Only
the last may move money, and these tests pin that from both sides — a bug filed and triaged as a
feature is CHARGED, and a feature filed and triaged as a bug is FREE. Getting this backwards would
let an AI guess set a customer's price.
"""
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import PartnerOrganisation
from apps.courses.models_staff import PartnerAdmin
from apps.scholarship import invoice_pdf, invoicing, platform_cost
from apps.scholarship.models import InvoiceLine, OrgBuildHours, OrgRequest
from apps.scholarship.tests.test_invoicing import SEPT_15, InvoiceWorld


class RequestWorld(InvoiceWorld):
    """`InvoiceWorld`, plus real requests behind the hours so a kind can be looked up.

    ⚠ `InvoiceWorld`'s own two hours rows carry NO request tag ('Payments module', 'Monthly
    report'), which is deliberate here: they hold the untagged case in place in every test below.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = PartnerAdmin.objects.create(
            owning_organisation=cls.org, role='org_admin', is_active=True,
            email='finance@brightpath.example')

    def a_request(self, request_id, *, filed, triaged, hours, title, month='2026-08'):
        """One finished request and the billable-hours row that names it.

        ⚠ QUOTED AND ACCEPTED by default, because that is the only state a finished request should
        ever be in: since 2026-10-29 a feature with no quote or no acceptance is an ABSOLUTE
        refusal to issue. `TestEveryFeatureNeedsAQuoteAndAnAcceptance` strips these back off to
        test the refusal; every other test here wants a request that can actually be billed.
        """
        from django.utils import timezone

        OrgRequest.objects.create(
            pk=request_id, organisation=self.org, submitted_by=self.admin, kind=filed,
            title=title, description=title, status='done', triaged_kind=triaged,
            quote_hours=Decimal(hours), quoted_at=timezone.now(), approved_at=timezone.now())
        return OrgBuildHours.objects.create(
            organisation=self.org, period_month=month,
            module=f'{platform_cost.request_module_tag(request_id)} {title}',
            hours=Decimal(hours), basis='quoted on the request')


# ── Which opinion sets the price ──────────────────────────────────────────────

class TestWhichFieldDecidesTheKind(RequestWorld):

    def test_the_owners_triage_wins_over_what_was_filed(self):
        """Both directions, because only testing one would pass on a coin flip."""
        filed_bug = self.a_request(5, filed='bug', triaged='feature', hours='1.0',
                                   title='Only the date in the last paid column')
        filed_feature = self.a_request(10, filed='feature', triaged='bug', hours='2.0',
                                       title='A new page to review reviewers')
        self.assertEqual(platform_cost.billable_kind(filed_bug.module), 'feature')
        self.assertEqual(platform_cost.billable_kind(filed_feature.module), 'bug')

    def test_an_untriaged_request_falls_back_to_what_was_filed(self):
        row = self.a_request(12, filed='bug', triaged='', hours='1.0', title='show year SPM')
        self.assertEqual(platform_cost.billable_kind(row.module), 'bug')

    def test_hours_with_no_request_behind_them_are_a_feature(self):
        """A super typed the row by hand, so the decision to bill it was already made. Reading it
        as free would silently discard work nobody waived."""
        self.assertEqual(platform_cost.billable_kind('Payments module'), 'feature')
        self.assertEqual(platform_cost.billable_kind(''), 'feature')
        self.assertEqual(platform_cost.billable_kind(None), 'feature')

    def test_a_tag_naming_a_request_that_does_not_exist_is_a_feature(self):
        """A dangling tag must not quietly zero a line. Same reason as the untagged case."""
        self.assertEqual(platform_cost.billable_kind('[REQ-9999] vanished'), 'feature')

    def test_the_id_is_read_back_out_of_the_module(self):
        self.assertEqual(platform_cost.request_id_from_module('[REQ-12] show year SPM'), 12)
        self.assertEqual(platform_cost.request_id_from_module('no tag here'), None)
        self.assertEqual(platform_cost.request_id_from_module(''), None)
        self.assertEqual(platform_cost.request_id_from_module(None), None)


# ── What the money does ───────────────────────────────────────────────────────

class TestBugHoursAreFree(RequestWorld):

    def test_a_bug_adds_hours_and_no_money(self):
        self.a_request(14, filed='bug', triaged='bug', hours='4.0', title='STPM tagged as SPM')
        dev = platform_cost.development_charge(self.org, '2026-08')
        # InvoiceWorld's own 12.5 untagged hours stay billable; only the bug is free.
        self.assertEqual(dev['hours'], Decimal('16.5'))
        self.assertEqual(dev['feature_hours'], Decimal('12.5'))
        self.assertEqual(dev['bug_hours'], Decimal('4.0'))
        self.assertEqual(dev['charge_myr'], Decimal('718.75'))      # 12.5 x 57.50, bug at zero
        bug = [ln for ln in dev['lines'] if ln['kind'] == 'bug'][0]
        self.assertEqual(bug['amount_myr'], Decimal('0.00'))
        self.assertEqual(bug['unit_amount_myr'], Decimal('0.00'))

    def test_the_cost_of_the_time_still_counts_the_free_hours(self):
        """`subtotal_myr` answers "is the rate enough?". Dropping unbilled hours out of it would
        make the margin look better than it is — a month of bug-fixing really did cost us time."""
        self.a_request(14, filed='bug', triaged='bug', hours='4.0', title='STPM tagged as SPM')
        dev = platform_cost.development_charge(self.org, '2026-08')
        self.assertEqual(dev['subtotal_myr'], Decimal('825.00'))    # 16.5 hours x RM50
        self.assertLess(dev['charge_myr'], dev['subtotal_myr'])

    def test_a_month_of_nothing_but_bugs_charges_nothing_for_development(self):
        OrgBuildHours.objects.filter(organisation=self.org, period_month='2026-08').delete()
        self.a_request(14, filed='bug', triaged='bug', hours='9.0', title='STPM tagged as SPM')
        charge = platform_cost.charge_for(self.org, '2026-08')
        dev = [ln for ln in charge['lines'] if ln['category'] == 'development'][0]
        self.assertEqual(dev['amount_myr'], Decimal('0.00'))
        self.assertEqual(dev['bug_hours'], Decimal('9.0'))
        # The two cost lines still stand, so the month is not "nothing to bill".
        self.assertEqual(charge['subtotal_myr'], Decimal('138.00'))

    def test_the_invoice_prints_the_bug_line_with_hours_and_a_zero_rate(self):
        """Exactly what the owner asked for: the hours and the rate, which is zero."""
        self.a_request(14, filed='bug', triaged='bug', hours='4.0', title='STPM tagged as SPM')
        inv = self.issue()
        bug = InvoiceLine.objects.get(invoice=inv, description='Bug reports, August 2026')
        self.assertEqual(bug.quantity, Decimal('4.0'))
        self.assertEqual(bug.unit_amount_myr, Decimal('0.00'))
        self.assertEqual(bug.amount_myr, Decimal('0.00'))
        self.assertFalse(bug.children.exists(), 'bug reports are deliberately NOT itemised')

    def test_no_bug_line_at_all_when_nothing_was_a_bug(self):
        """A standing RM0.00 row on every invoice would read as something having been waived."""
        inv = self.issue()
        self.assertFalse(
            [ln for ln in inv.lines.all() if ln.description.startswith('Bug reports')])


# ── What the paper looks like ─────────────────────────────────────────────────

class TestTheGroupedLayout(RequestWorld):

    def setUp(self):
        self.a_request(12, filed='feature', triaged='feature', hours='6.0',
                       title='show year SPM was taken')
        self.a_request(14, filed='bug', triaged='bug', hours='2.0',
                       title='STPM tagged as SPM')

    def test_the_group_carries_the_money_and_the_sub_items_carry_the_hours(self):
        inv = self.issue()
        group = InvoiceLine.objects.get(invoice=inv, description='Feature requests, August 2026')
        self.assertEqual(group.quantity, Decimal('18.5'))           # 10.0 + 2.5 + 6.0
        self.assertEqual(group.unit_amount_myr, Decimal('57.50'))
        self.assertEqual(group.amount_myr, Decimal('1063.75'))
        children = list(group.children.order_by('position'))
        self.assertEqual(len(children), 3)
        for child in children:
            with self.subTest(line=child.description):
                self.assertEqual(child.amount_myr, Decimal('0.00'))
                self.assertIsNone(child.unit_amount_myr)
        self.assertEqual(sum(c.quantity for c in children), group.quantity)

    def test_a_sub_item_names_its_request_number_in_round_brackets(self):
        inv = self.issue()
        printed = [ln.description for ln in inv.lines.all()]
        self.assertIn('show year SPM was taken (REQ-12)', printed)
        # The square-bracket tag is still never printed, and the hours row still holds it.
        self.assertFalse([d for d in printed if '[REQ-' in d])

    def test_an_untagged_row_gets_no_number(self):
        """There is nothing to put in the brackets, and inventing one would be a lie."""
        self.assertIn('Payments module', [ln.description for ln in self.issue().lines.all()])

    def test_a_very_long_title_keeps_its_number(self):
        """The number is the part a reader needs to look the job up, so the wording is truncated
        around it rather than the number being pushed off the end of the column."""
        words = 'x' * 400
        self.a_request(31, filed='feature', triaged='feature', hours='1.0', title=words[:200])
        line = [ln for ln in self.issue().lines.all() if '(REQ-31)' in ln.description]
        self.assertEqual(len(line), 1)
        self.assertLessEqual(len(line[0].description), 300)

    def test_the_position_numbers_keep_a_child_under_its_parent(self):
        inv = self.issue()
        ordered = list(inv.lines.order_by('position'))
        group_at = [i for i, ln in enumerate(ordered) if ln.parent_id is None
                    and ln.description.startswith('Feature requests')][0]
        for child in ordered[group_at + 1:group_at + 4]:
            with self.subTest(line=child.description):
                self.assertEqual(child.parent_id, ordered[group_at].pk)

    def test_the_pdf_prints_a_sub_item_without_an_amount(self):
        html = invoice_pdf.render_invoice_html(self.issue())
        self.assertIn('show year SPM was taken (REQ-12)', html)
        self.assertIn('padding-left:18px', html)          # the indent that marks a sub-item
        self.assertIn('Bug reports, August 2026', html)

    def test_the_pdf_still_renders(self):
        self.assertTrue(invoice_pdf.invoice_pdf(self.issue()).startswith(b'%PDF'))


# ── The invariant the grouping could have broken ──────────────────────────────

class TestTheAmountColumnStillAddsUp(RequestWorld):

    def test_the_lines_reach_the_subtotal_with_a_group_and_a_bug_line(self):
        self.a_request(12, filed='feature', triaged='feature', hours='6.0', title='show year')
        self.a_request(14, filed='bug', triaged='bug', hours='2.0', title='STPM tagged')
        inv = self.issue()
        self.assertEqual(sum(ln.amount_myr for ln in inv.lines.all()), inv.subtotal_myr)
        self.assertEqual(inv.subtotal_myr,
                         platform_cost.charge_for(self.org, '2026-08')['subtotal_myr'])

    def test_build_lines_refuses_a_group_that_double_counts(self):
        """The guard is not decorative. If a sub-item ever carried money, the check must catch it
        rather than let an invoice that does not add up reach a customer."""
        charge = platform_cost.charge_for(self.org, '2026-08')
        charge['subtotal_myr'] = Decimal('1.00')
        with self.assertRaises(invoicing.InvoicingError) as caught:
            invoicing.build_lines(charge, '2026-08')
        self.assertEqual(caught.exception.code, 'lines_do_not_add_up')


class TestTheTenantNeverSeesACost(RequestWorld):
    """The oldest rule on this surface, re-checked because a new column was added to the model."""

    def test_no_invoice_line_field_carries_a_cost_or_a_margin(self):
        self.a_request(14, filed='bug', triaged='bug', hours='2.0', title='STPM tagged')
        fields = {f.name for f in InvoiceLine._meta.get_fields()}
        for leak in ('cost_myr', 'margin_pct', 'tool_cost_myr', 'rate_myr'):
            with self.subTest(field=leak):
                self.assertNotIn(leak, fields)

    def test_the_printed_document_names_no_supplier_and_no_margin(self):
        """⚠ Checked on the document BODY, not the raw file. The stylesheet legitimately contains
        the word 'margin' (`@page { margin: ... }`), so searching the whole file finds a leak that
        is not one — a false alarm that would train somebody to ignore this test."""
        import re

        self.a_request(14, filed='bug', triaged='bug', hours='2.0', title='STPM tagged')
        html = invoice_pdf.render_invoice_html(self.issue(today=SEPT_15))
        body = re.sub(r'<style\b.*?</style>', '', html, flags=re.S | re.I)
        body = re.sub(r'<[^>]+>', ' ', body).lower()
        for leak in ('anthropic', 'claude', 'supabase', 'margin', 'markup', 'what it cost'):
            with self.subTest(word=leak):
                self.assertNotIn(leak, body)


# ── A feature must be quoted AND accepted before it can be billed ─────────────

class TestEveryFeatureNeedsAQuoteAndAnAcceptance(RequestWorld):
    """Owner, 2026-10-29: *"Make sure every feature has a quote and acceptance from BrightPath
    (including me signed in as BrightPath org admin)."*

    ⚠ Every bound is tested from the side that WIDENS it — a quote with no acceptance, an
    acceptance with no quote, hours with no quote_hours, a tag naming nothing. A test that only
    proves a fully-approved request issues proves nothing: that already worked.
    """

    def test_a_quoted_and_accepted_feature_bills(self):
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Agreed')
        self.assertEqual(platform_cost.consent_gaps(self.org, '2026-08'), [])
        self.assertNotIn('feature_not_accepted', self.codes())

    def test_a_feature_never_accepted_is_refused(self):
        from django.utils import timezone
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Unaccepted')
        OrgRequest.objects.filter(pk=12).update(quoted_at=timezone.now(), approved_at=None)
        gaps = platform_cost.consent_gaps(self.org, '2026-08')
        self.assertEqual([g['missing'] for g in gaps], ['an acceptance'])
        self.assertIn('feature_not_accepted', self.codes())

    def test_a_feature_never_quoted_is_refused(self):
        from django.utils import timezone
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Unquoted')
        OrgRequest.objects.filter(pk=12).update(quoted_at=None, approved_at=timezone.now())
        self.assertEqual([g['missing'] for g in platform_cost.consent_gaps(self.org, '2026-08')],
                         ['a quote'])

    def test_neither_names_both(self):
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Neither')
        OrgRequest.objects.filter(pk=12).update(quoted_at=None, approved_at=None)
        self.assertEqual([g['missing'] for g in platform_cost.consent_gaps(self.org, '2026-08')],
                         ['a quote and an acceptance'])

    def test_a_timestamp_without_hours_is_still_not_a_quote(self):
        """`quoted_at` set and `quote_hours` empty is a half-written quote, not an agreed price."""
        from django.utils import timezone
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Half quoted')
        OrgRequest.objects.filter(pk=12).update(
            quoted_at=timezone.now(), approved_at=timezone.now(), quote_hours=None)
        self.assertEqual([g['missing'] for g in platform_cost.consent_gaps(self.org, '2026-08')],
                         ['a quote'])

    def test_the_refusal_is_ABSOLUTE_and_cannot_be_overridden(self):
        """The whole point. An overridable warning is a button somebody presses at 11pm."""
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Unaccepted')
        OrgRequest.objects.filter(pk=12).update(quoted_at=None, approved_at=None)
        problem = [p for p in invoicing.readiness(self.org, '2026-08', today=SEPT_15)
                   if p['code'] == 'feature_not_accepted'][0]
        self.assertFalse(problem['overridable'])
        with self.assertRaises(invoicing.InvoiceRefused) as caught:
            self.issue(override_reason='I am in a hurry', issued_by_email='x@y.z')
        self.assertIn('feature_not_accepted', [p['code'] for p in caught.exception.problems])

    def test_a_BUG_needs_no_quote_or_acceptance(self):
        """It is free, so there is nothing to agree to. Blocking a month over paperwork for
        RM0.00 would make the bug rule unusable."""
        self.a_request(14, filed='bug', triaged='bug', hours='4.0', title='A bug')
        OrgRequest.objects.filter(pk=14).update(quoted_at=None, approved_at=None)
        self.assertEqual(platform_cost.consent_gaps(self.org, '2026-08'), [])
        self.assertNotIn('feature_not_accepted', self.codes())

    def test_hand_typed_hours_with_no_request_are_left_alone(self):
        """`InvoiceWorld`'s own two rows carry no tag. A super typed them and meant them."""
        self.assertEqual(platform_cost.consent_gaps(self.org, '2026-08'), [])

    def test_a_tag_naming_a_request_that_does_not_exist_is_reported_not_ignored(self):
        OrgBuildHours.objects.create(
            organisation=self.org, period_month='2026-08',
            module=f'{platform_cost.request_module_tag(9999)} vanished',
            hours=Decimal('1.0'), basis='x')
        gaps = platform_cost.consent_gaps(self.org, '2026-08')
        self.assertEqual([g['request_id'] for g in gaps], [9999])
        self.assertIn('feature_not_accepted', self.codes())

    def test_only_the_billed_month_is_checked(self):
        """A gap in September must not block August. The check is per month, like the charge."""
        from django.utils import timezone
        self.a_request(12, filed='feature', triaged='feature', hours='4.0', title='Sept gap',
                       month='2026-09')
        OrgRequest.objects.filter(pk=12).update(quoted_at=timezone.now(), approved_at=None)
        self.assertEqual(platform_cost.consent_gaps(self.org, '2026-08'), [])
        self.assertEqual(len(platform_cost.consent_gaps(self.org, '2026-09')), 1)
