"""Bill the hours we TOLD them, not the hours we planned (2026-10-29).

The owner audited every billed request on 2026-10-29 — 3, 5, 10, 12, 14, 18, 27, 28, 29, 30, 31,
33, 38, 39, 42, 44 — and found five wrong: **10, 14, 28, 30 and 31**. The cause was not
arithmetic. Development billing read `quote_hours`, the PLAN, while the closing report had already
published a different number to BrightPath:

  * #10 — quoted 15.0, re-scoped downward, spent 11.5, **billed 15.0**;
  * #14 — *"2.0 hours estimated, approximately 5 hours spent … None of it is charged"*, **billed 2.0**;
  * #30 — *"Planned: 7 hours. Actual: about 4 hours"*, **billed 7.0**.

The owner's ruling, verbatim: *"It is not what is calculated internally. What matters is, what was
communicated back to the requester."*

So these tests hold the code to four claims:

1. **The published actual is a COLUMN, typed by a person.** Nothing here parses prose, and nothing
   should: a machine guessing a number that lands on an invoice is how the five got through.
2. **No actual recorded REFUSES the month.** Absolutely — not a warning somebody can click past.
   Falling back to the quote is the defect itself.
3. **`charged_hours = 0.0` is a real answer and is not "unknown".** It is how #14's *"none of it is
   charged"* is written down, and a reader must be able to tell it from a blank.
4. **Recording a figure late changes no invoice already sent.** The five audited requests are
   ALREADY billed; the record has to be correctable, and the money remedy is a correction row
   (`OrgBillingCorrection`), never an edit to a document the customer has read.
"""
from datetime import date
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import org_requests, platform_cost, request_hours
from apps.scholarship.models import Invoice, InvoiceLine, OrgBuildHours, OrgRequest

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'

#: A real path in this repo. The analysis record requires a citation, and a test citing a fictional
#: file would drift from what production stores.
A_REAL_FILE = 'apps/scholarship/request_hours.py'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='ah', name='Actual Hours Org')
        cls.other = PartnerOrganisation.objects.create(code='ah2', name='Other Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='ah-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@ah.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='ah-su', is_super_admin=True, is_active=True,
            name='Super', email='su@ah.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _req(self, *, status='scheduled', quote_hours='7.0', organisation=None,
             scheduled_for=date(2026, 10, 3)):
        """A quoted, accepted, scheduled FEATURE — the shape that reaches an invoice.

        ⚠ NOT `done` yet, and that is how production works: `can_comment` refuses a terminal
        request, so the closing report is written and approved WHILE the work is still open, and
        the request is marked done afterwards. `_finish` is the second step.
        """
        return OrgRequest.objects.create(
            organisation=organisation or self.org, submitted_by=self.oa, kind='feature',
            triaged_kind='feature', title='Invite engine', description='d', status=status,
            quote_hours=Decimal(quote_hours) if quote_hours is not None else None,
            quoted_at=timezone.now(), approved_at=timezone.now(), scheduled_for=scheduled_for)

    def _finish(self, req):
        """Mark the work done — what makes it reach the unbilled panel."""
        req.status = 'done'
        req.save(update_fields=['status'])
        return req

    def _draft(self, req, *, body='Planned 7 hours; it took about 4.'):
        return org_requests.record_analysis(
            req, self.super, body=body, estimated_hours='7.0', cited_files=[A_REAL_FILE],
            authored_by='claude-opus-5', repo_sha='a' * 40)

    def _approved(self, req, **kw):
        return org_requests.approve_analysis(self._draft(req, **kw), self.super)


# ── The service: a transcription, with guards ────────────────────────────────

class TestRecordingTheActual(_Base):

    def test_the_actual_is_written_down_and_charged_follows_it(self):
        """The ordinary case: we spent four hours and we charge four hours."""
        analysis = self._approved(self._req())
        request_hours.record_hours(analysis, self.super, actual_hours='4.0')
        analysis.refresh_from_db()
        self.assertEqual(analysis.actual_hours, Decimal('4.0'))
        self.assertEqual(analysis.charged_hours, Decimal('4.0'))
        # No note, because there is nothing to explain.
        self.assertIsNone(analysis.charge_note)

    def test_charging_nothing_for_work_that_was_done_is_recordable(self):
        """Request #14, exactly: *"approximately 5 hours spent … None of it is charged"*.

        ⚠ `org_requests._clean_hours` REFUSES zero, correctly — a quote of nothing is meaningless.
        Reusing it here would have refused the very figure this sprint exists to record.
        """
        analysis = self._approved(self._req())
        request_hours.record_hours(analysis, self.super, actual_hours='5.0', charged_hours='0',
                                   charge_note='Our overrun, not theirs. Absorbed in full.')
        analysis.refresh_from_db()
        self.assertEqual(analysis.actual_hours, Decimal('5.0'))
        self.assertEqual(analysis.charged_hours, Decimal('0.0'))
        self.assertIn('Absorbed', analysis.charge_note)

    def test_charging_MORE_than_we_spent_is_allowed_when_it_is_explained(self):
        """Request #38: quoted high, the organisation accepted the extra, and we kept it.

        The owner on the five wrong requests: *"In certain cases, we may have accepted the extra,
        as in the case of #38."* So the guard is a NOTE, not a ceiling.
        """
        analysis = self._approved(self._req())
        request_hours.record_hours(analysis, self.super, actual_hours='2.5', charged_hours='4.0',
                                   charge_note='Quoted 4.0 and accepted; scope held.')
        analysis.refresh_from_db()
        self.assertEqual(analysis.charged_hours, Decimal('4.0'))

    def test_a_difference_with_no_reason_is_refused(self):
        """An unexplained write-off is money moved with nothing on the record — the same defect
        `OrgBuildHours.basis` exists to prevent."""
        analysis = self._approved(self._req())
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(analysis, self.super, actual_hours='5.0', charged_hours='0')
        self.assertEqual(caught.exception.code, 'charge_note_required')
        analysis.refresh_from_db()
        self.assertIsNone(analysis.actual_hours)        # refused, so NOTHING was written

    def test_an_unapproved_draft_was_never_sent_so_it_carries_no_authority(self):
        """The authority is what was COMMUNICATED. A draft nobody approved was communicated to
        nobody, so its figures are not the published actual."""
        analysis = self._draft(self._req())
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(analysis, self.super, actual_hours='4.0')
        self.assertEqual(caught.exception.code, 'analysis_not_approved')

    def test_a_superseded_analysis_is_refused(self):
        analysis = self._approved(self._req())
        analysis.superseded_at = timezone.now()
        analysis.save(update_fields=['superseded_at'])
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(analysis, self.super, actual_hours='4.0')
        self.assertEqual(caught.exception.code, 'analysis_superseded')

    def test_only_a_super_may_write_the_figure_that_sets_a_price(self):
        analysis = self._approved(self._req())
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(analysis, self.oa, actual_hours='4.0')
        self.assertEqual(caught.exception.code, 'forbidden')

    def test_unreadable_or_impossible_hours_are_refused_rather_than_coerced(self):
        analysis = self._approved(self._req())
        for value, code in (('abc', 'bad_actual_hours'), (None, 'bad_actual_hours'),
                            ('-1', 'bad_actual_hours'), ('100001', 'bad_actual_hours')):
            with self.subTest(value=str(value)):
                with self.assertRaises(org_requests.OrgRequestError) as caught:
                    request_hours.record_hours(analysis, self.super, actual_hours=value)
                self.assertEqual(caught.exception.code, code)

    def test_an_unreadable_charged_figure_is_named_as_its_own_problem(self):
        """Two fields, two codes — so the screen can put the error on the right box."""
        analysis = self._approved(self._req())
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(analysis, self.super, actual_hours='4.0',
                                       charged_hours='abc')
        self.assertEqual(caught.exception.code, 'bad_charged_hours')

    def test_hours_are_held_to_one_decimal_place(self):
        analysis = self._approved(self._req())
        request_hours.record_hours(analysis, self.super, actual_hours='4.26')
        analysis.refresh_from_db()
        self.assertEqual(analysis.actual_hours, Decimal('4.3'))

    def test_a_note_longer_than_a_comment_may_be_is_refused_not_truncated(self):
        """Same rule as the analysis body, and for the same reason: a silent slice is how 2,015
        characters of an engineer's analysis were lost on 2026-08-01."""
        analysis = self._approved(self._req())
        with self.assertRaises(org_requests.OrgRequestError) as caught:
            request_hours.record_hours(
                analysis, self.super, actual_hours='5.0', charged_hours='0',
                charge_note='x' * (org_requests.COMMENT_MAX_CHARS + 1))
        self.assertEqual(caught.exception.code, 'charge_note_too_long')

    def test_recording_it_late_is_allowed_and_rewrites_no_invoice(self):
        """⚠ THE BACKFILL DEPENDS ON THIS. All five audited requests are already billed; refusing
        the edit would mean the record could never be made right at all. An `InvoiceLine` is a
        frozen snapshot, so the document the customer read cannot move."""
        req = self._req()
        analysis = self._approved(req)
        OrgBuildHours.objects.create(
            organisation=self.org, period_month='2026-10',
            module=f'{request_hours.request_module_tag(req.id)} Invite engine',
            hours=Decimal('7.0'), basis=f'Quoted on request #{req.id}')
        invoice = Invoice.objects.create(
            number='INV-2026-9001', organisation=self.org, period_month='2026-10',
            issued_on=date(2026, 11, 15), due_on=date(2026, 11, 29),
            subtotal_myr=Decimal('161.00'), total_myr=Decimal('161.00'))
        line = InvoiceLine.objects.create(
            invoice=invoice, position=1, category='development', description='Feature requests',
            quantity=Decimal('7.0'), unit_amount_myr=Decimal('23.00'),
            amount_myr=Decimal('161.00'))

        request_hours.record_hours(analysis, self.super, actual_hours='4.0')

        line.refresh_from_db()
        self.assertEqual(line.quantity, Decimal('7.0'))
        self.assertEqual(line.amount_myr, Decimal('161.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_myr, Decimal('161.00'))


# ── The readers: what the invoice is allowed to believe ──────────────────────

class TestWhatTheInvoiceReads(_Base):

    def test_with_nothing_recorded_there_is_no_closing_figure_at_all(self):
        """⚠ NOT the quote. This is the bug: a blank used to fall through to `quote_hours`."""
        req = self._req(quote_hours='7.0')
        self._approved(req)
        self.assertIsNone(request_hours.closing_report(req))
        self.assertIsNone(request_hours.billable_hours(req))

    def test_zero_charged_hours_is_an_answer_and_is_not_a_blank(self):
        req = self._req()
        request_hours.record_hours(self._approved(req), self.super, actual_hours='5.0',
                                   charged_hours='0', charge_note='Absorbed.')
        self.assertEqual(request_hours.billable_hours(req), Decimal('0.0'))
        self.assertIsNotNone(request_hours.closing_report(req))

    def test_the_LATEST_closing_report_wins(self):
        """A request can be re-reported. The newest approved figure is the published one."""
        req = self._req()
        first = self._approved(req, body='It took about 6 hours.')
        request_hours.record_hours(first, self.super, actual_hours='6.0')
        second = self._approved(req, body='Correction: 4 hours, not 6.')
        request_hours.record_hours(second, self.super, actual_hours='4.0')
        self.assertEqual(request_hours.closing_report(req).id, second.id)
        self.assertEqual(request_hours.billable_hours(req), Decimal('4.0'))

    def test_a_report_with_no_hours_on_it_is_not_a_closing_report(self):
        """Every October completion report is prose with no figure. Picking the latest analysis
        blindly is how `bug_reports_fixed` once reported "ten bugs, no hours"."""
        req = self._req()
        with_hours = self._approved(req, body='It took 4 hours.')
        request_hours.record_hours(with_hours, self.super, actual_hours='4.0')
        self._approved(req, body='Shipped and verified in production.')   # no figures recorded
        self.assertEqual(request_hours.closing_report(req).id, with_hours.id)


class TestTheUnbilledPanel(_Base):
    """The panel the owner read on 2026-10-29, which proposed 7h for #30 and 8h for #31 — the
    PLANS — while the closing reports had told BrightPath 4 and 5. Pressing Record filed the wrong
    number, and the invoice then billed it."""

    def test_it_proposes_the_published_actual_and_shows_the_quote_beside_it(self):
        req = self._req(quote_hours='7.0')
        request_hours.record_hours(self._approved(req), self.super, actual_hours='4.0')
        self._finish(req)
        row = [r for r in platform_cost.unbilled_request_hours(self.org)
               if r['request_id'] == req.id][0]
        self.assertEqual(row['hours'], Decimal('4.0'))          # what gets recorded
        self.assertEqual(row['actual_hours'], Decimal('4.0'))
        self.assertEqual(row['quoted_hours'], Decimal('7.0'))   # shown, never billed
        self.assertIsNone(row['blocked'])

    def test_a_row_with_no_published_actual_says_WHY_it_cannot_be_recorded(self):
        """It offers no number at all, so the screen can offer no Record button."""
        req = self._req(quote_hours='7.0')
        self._approved(req)
        self._finish(req)
        row = [r for r in platform_cost.unbilled_request_hours(self.org)
               if r['request_id'] == req.id][0]
        self.assertIsNone(row['hours'])
        self.assertEqual(row['blocked'], 'no_actual_reported')


# ── The endpoint ────────────────────────────────────────────────────────────

class TestTheHoursEndpoint(_Base):

    def _url(self, req, analysis):
        return f'{BASE}{req.id}/analysis/{analysis.id}/hours/'

    def test_a_super_records_the_figures_and_reads_them_back(self):
        req = self._req()
        analysis = self._approved(req)
        self._auth('ah-su')
        res = self.client.post(self._url(req, analysis),
                               {'actual_hours': '4.0', 'charged_hours': '4.0'}, format='json')
        self.assertEqual(res.status_code, 200)
        row = [a for a in res.data['analyses'] if a['id'] == analysis.id][0]
        # STRINGS on the wire. A bare Decimal serialises as a float, and a float is not what an
        # invoice is made of.
        self.assertEqual(row['actual_hours'], '4.0')
        self.assertEqual(row['charged_hours'], '4.0')
        self.assertEqual(row['charge_note'], '')

    def test_the_organisation_may_not_set_the_figure_that_prices_its_own_work(self):
        req = self._req()
        analysis = self._approved(req)
        self._auth('ah-oa')
        res = self.client.post(self._url(req, analysis), {'actual_hours': '0'}, format='json')
        self.assertEqual(res.status_code, 403)
        analysis.refresh_from_db()
        self.assertIsNone(analysis.actual_hours)

    def test_an_analysis_from_another_request_is_404_not_403(self):
        """The org fence IS the request lookup: a cross-request id must not resolve, and must not
        confirm that it exists either."""
        mine, theirs = self._req(), self._req(organisation=self.other)
        other_analysis = self._approved(theirs)
        self._auth('ah-su')
        res = self.client.post(f'{BASE}{mine.id}/analysis/{other_analysis.id}/hours/',
                               {'actual_hours': '4.0'}, format='json')
        self.assertEqual(res.status_code, 404)
        other_analysis.refresh_from_db()
        self.assertIsNone(other_analysis.actual_hours)

    def test_a_refusal_comes_back_as_a_code_the_screen_can_act_on(self):
        req = self._req()
        analysis = self._approved(req)
        self._auth('ah-su')
        res = self.client.post(self._url(req, analysis),
                               {'actual_hours': '5.0', 'charged_hours': '0'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['code'], 'charge_note_required')

    def test_with_the_feature_dark_the_endpoint_does_not_exist(self):
        req = self._req()
        analysis = self._approved(req)
        self._auth('ah-su')
        with override_settings(REQUESTS_ENABLED=False):
            res = self.client.post(self._url(req, analysis), {'actual_hours': '4.0'},
                                   format='json')
        self.assertEqual(res.status_code, 404)

    def test_the_figures_are_OWNER_ONLY(self):
        """The organisation reads these numbers in the closing-report PROSE, which is where they
        were published. A second machine-readable copy in the org payload recreates the "two
        figures, which is true?" problem TD-202 removed from the AI."""
        from apps.scholarship.serializers_admin import OrgRequestOrgSerializer

        req = self._req()
        request_hours.record_hours(self._approved(req), self.super, actual_hours='4.0')
        payload = OrgRequestOrgSerializer(req).data
        blob = str(payload)
        self.assertNotIn('actual_hours', blob)
        self.assertNotIn('charged_hours', blob)
        self.assertNotIn('charge_note', blob)
