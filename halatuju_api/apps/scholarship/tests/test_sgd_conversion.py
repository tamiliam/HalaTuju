"""TD-157 — the officer's document payload says what a Singapore payslip converts to.

`sgd_conversion.sgd_conversion(doc)` takes the slip's monthly figure the engine's way
(`_salary_monthly_amount`) and asks the engine's own `amounts._to_myr` (review F3: one home), and
serves ``{'sgd', 'rate', 'myr'}`` for the cockpit's "Converted from S$X at R = RM Y" note. The note
means "converts at this rate", not "was the slip counted" (a second slip carries it too).

Pinned here:
  * the figures agree with `earner_monthly_income` — the note can never show a ringgit figure the
    means-test did not use;
  * a Malaysian slip, a decided case, and another document type get no note;
  * the officer's detail payload carries it, the STUDENT's document payload does not;
  * an SGD slip costs the officer's GET no extra query (the query-budget fixture has no SGD slip,
    so this pins the predicate's own cost — lessons.md, TD-285).
"""
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship.income_engine import earner_monthly_income
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.serializers import ApplicantDocumentSerializer
from apps.scholarship.sgd_conversion import sgd_conversion
from apps.scholarship.tests.factories import (
    authed_client, make_admin, make_application, make_cohort, make_org, make_programme)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

SG_SLIP = {'name': 'RAVI A/L EXAMPLE', 'employer': 'Example Logistics Pte. Ltd.',
           'currency': 'SGD', 'gross_income': 'S$3,114.00', 'net_income': 'S$2,500.00'}
MY_SLIP = {**SG_SLIP, 'employer': 'Contoh Sdn Bhd', 'currency': 'MYR',
           'gross_income': 'RM3,114.00', 'net_income': 'RM2,500.00'}


def _slip(app, fields, doc_type='salary_slip'):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member='father', storage_path='x',
        vision_fields={'fields': fields, 'student_verdict': 'ok', 'capture': 'ai'})


@override_settings(SGD_TO_MYR_RATE=3.15)
class TestTheNoteFollowsTheConversion(TestCase):
    def test_a_singapore_slip_in_review_is_converted_at_the_rate(self):
        app = make_application('interviewing')
        self.assertEqual(sgd_conversion(_slip(app, SG_SLIP)),
                         {'sgd': '3,114.00', 'rate': '3.15', 'myr': '9,809.10'})

    def test_the_ringgit_figure_is_the_one_the_means_test_used(self):
        app = make_application('interviewing', income_route='salary',
                               income_working_members=['father'])
        doc = _slip(app, SG_SLIP)
        amount, source = earner_monthly_income(app, 'father')
        self.assertEqual(source, 'salary')
        self.assertEqual(sgd_conversion(doc)['myr'], f'{amount:,.2f}')

    def test_a_malaysian_slip_has_no_note(self):
        self.assertIsNone(sgd_conversion(_slip(make_application('interviewing'), MY_SLIP)))

    def test_a_decided_case_keeps_its_recorded_basis_and_says_nothing(self):
        # Owner: "leave out #75" — a recommended case was never converted, so no "converted" claim.
        self.assertIsNone(sgd_conversion(_slip(make_application('recommended'), SG_SLIP)))

    def test_another_document_type_has_no_note(self):
        self.assertIsNone(sgd_conversion(_slip(make_application('interviewing'), SG_SLIP, 'epf')))

    def test_an_unusable_figure_has_no_note(self):
        bad = {**SG_SLIP, 'gross_income': 'S$100.00', 'net_income': 'S$900.00'}   # net > gross
        self.assertIsNone(sgd_conversion(_slip(make_application('interviewing'), bad)))

    def test_the_conversion_has_one_home(self):
        # Review F3: the note asks the engine's own `_to_myr`, never a copy of its gate. If the
        # engine declines to convert (returns the amount unchanged), there is no note.
        from unittest.mock import patch
        doc = _slip(make_application('interviewing'), SG_SLIP)
        with patch('apps.scholarship.income_engine.amounts._to_myr', side_effect=lambda amt, f, app: amt):
            self.assertIsNone(sgd_conversion(doc))
        with patch('apps.scholarship.income_engine.amounts._to_myr', side_effect=lambda amt, f, app: amt * 2):
            self.assertEqual(sgd_conversion(doc)['myr'], '6,228.00')

    def test_a_second_singapore_slip_also_carries_the_note(self):
        # Review F3, the meaning: the engine counts only the FIRST slip with an amount per earner,
        # but the note says what THIS slip converts to at the rate — not that it was the one counted.
        app = make_application('interviewing')
        _slip(app, SG_SLIP)
        second = _slip(app, {**SG_SLIP, 'gross_income': 'S$3,000.00', 'net_income': 'S$2,400.00'})
        self.assertEqual(sgd_conversion(second)['myr'], '9,450.00')

    @override_settings(SGD_TO_MYR_RATE=3.4)
    def test_the_rate_is_the_configured_one_not_a_constant(self):
        got = sgd_conversion(_slip(make_application('interviewing'), SG_SLIP))
        self.assertEqual((got['rate'], got['myr']), ('3.4', '10,587.60'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SGD_TO_MYR_RATE=3.15)
class TestWhoSeesIt(TestCase):
    def _case(self, fields):
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org), owning_organisation=org)
        app = make_application('interviewing', cohort=cohort)
        _slip(app, fields)
        client = authed_client(make_admin('org_admin', owning_org=org))
        return client, f'/api/v1/admin/scholarship/applications/{app.id}/', app

    def test_the_officer_detail_payload_carries_it(self):
        client, url, _ = self._case(SG_SLIP)
        res = client.get(url)
        self.assertEqual(res.status_code, 200)
        slip = next(d for d in res.data['documents'] if d['doc_type'] == 'salary_slip')
        self.assertEqual(slip['sgd_conversion'], {'sgd': '3,114.00', 'rate': '3.15', 'myr': '9,809.10'})

    def test_the_student_payload_does_not(self):
        _, _, app = self._case(SG_SLIP)
        doc = app.documents.get(doc_type='salary_slip')
        self.assertNotIn('sgd_conversion', ApplicantDocumentSerializer(doc).data)

    def test_an_sgd_slip_costs_the_officer_get_no_extra_query(self):
        counts = []
        for fields in (MY_SLIP, SG_SLIP):
            client, url, _ = self._case(fields)
            self.assertEqual(client.get(url).status_code, 200)        # warm-up, as the budgets do
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(client.get(url).status_code, 200)
            counts.append(len(captured))
        self.assertEqual(counts[0], counts[1], f'MYR slip {counts[0]} vs SGD slip {counts[1]} queries')
