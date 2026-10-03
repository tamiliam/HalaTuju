"""TD-151 (2) and TD-323 — a payslip's monthly figure outside the plausibility window is a misread, not a fact.

It takes the existing "unreliable read" path (`_salary_monthly_amount` → None → income 'unknown',
verify at interview), exactly as net > gross already does — no new state, no new copy. The bounds
and where they come from are in `income_engine/salary_figures.py` and docs/decisions.md 2026-10-02.

Helpers are borrowed through the MODULE so no TestCase is collected twice (lessons.md 2026-09-30).
"""
from django.test import SimpleTestCase

from apps.scholarship.income_engine import earner_monthly_income
from apps.scholarship.income_engine import (_member_has_epf_value, member_income_evidenced,
                                            slip_epf_divergence)
from apps.scholarship.income_engine.salary_figures import (_SLIP_MONTHLY_MAX, _SLIP_MONTHLY_MIN,
                                                           _epf_monthly_salary,
                                                           _salary_monthly_amount, epf_band_salary,
                                                           epf_figure_refused, slip_figure_refused)
from apps.scholarship.income_shown import income_shown
from apps.scholarship.tests import test_income_engine as tie
from apps.scholarship.tests import test_income_evidence_homes as hom


class SalaryPlausibilityTest(SimpleTestCase):

    def test_a_hundredfold_misread_with_no_net_to_contradict_it_is_unusable(self):
        # #66's ringgit|sen concatenation (RM326.00 → 32600) on a slip that printed no net: the
        # net > gross rule cannot fire, so only the window catches it.
        self.assertIsNone(_salary_monthly_amount({'gross_income': '32600'}))

    def test_a_dropped_decimal_misread_is_unusable(self):
        self.assertIsNone(_salary_monthly_amount({'gross_income': 'RM0.50'}))
        self.assertIsNone(_salary_monthly_amount({'net_income': 'RM17.00'}))

    def test_the_window_edges(self):
        self.assertEqual(_salary_monthly_amount({'gross_income': str(_SLIP_MONTHLY_MIN)}), 100.0)
        self.assertEqual(_salary_monthly_amount({'gross_income': str(_SLIP_MONTHLY_MAX)}), 20000.0)
        self.assertIsNone(_salary_monthly_amount({'gross_income': '99.99'}))
        self.assertIsNone(_salary_monthly_amount({'gross_income': '20000.01'}))

    def test_the_real_extremes_we_hold_still_read(self):
        # The smallest and largest real monthly figures in the 2026-10-02 corpus measurement.
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM357.22'}), 357.22)
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM9,900.04'}), 9900.04)

    def test_an_implausible_year_to_date_falls_back_to_the_month(self):
        # A YTD misread (×100) must not inflate the figure, nor throw the good month away.
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM3,000',
                                                 'gross_income_ytd': 'RM3,600,000'}), 3000.0)

    def test_the_window_applies_before_the_currency_conversion(self):
        # Review F4b: a S$7,000 Singapore slip is inside the window in its OWN currency and is then
        # converted (×3.15 → RM22,050) — above the ceiling, and rightly kept: the window judges
        # what the document printed, not the ringgit figure we derive from it.
        from django.test import override_settings
        app = tie._app([tie._bill('salary_slip', {'gross_income': 'S$7,000.00',
                                                  'employer': 'Acme Pte Ltd'})])
        app.status = 'submitted'
        with override_settings(SGD_TO_MYR_RATE=3.15):
            amt, src = earner_monthly_income(app, 'father')
        self.assertEqual(src, 'salary')
        self.assertAlmostEqual(amt, 22050.0, places=2)

    def test_the_engine_reads_an_implausible_slip_as_unknown(self):
        app = tie._app([tie._bill('salary_slip', {'gross_income': '32600'})])
        self.assertEqual(earner_monthly_income(app, 'father'), (None, 'unknown'))


class EpfBandFloorTest(SimpleTestCase):
    """TD-323 after review F1: the EPF estimate takes the payslip FLOOR, for the band only."""

    def test_the_band_figure_takes_the_floor_and_no_ceiling(self):
        # A single RM110 employee share over a twelve-month statement: RM83.33 a month.
        self.assertIsNone(epf_band_salary({'employee_contribution_total': 'RM110.00',
                                           'months_counted': '12'}))
        self.assertEqual(epf_band_salary({'employee_contribution_total': '11',
                                          'months_counted': '1'}), _SLIP_MONTHLY_MIN)
        self.assertEqual(epf_band_salary({'employee_contribution_total': 'RM2,750.00',
                                          'months_counted': '1'}), 25000.0)       # no ceiling

    def test_the_unwindowed_reader_is_what_it_was(self):
        self.assertEqual(_epf_monthly_salary({'employee_contribution_total': 'RM110.00',
                                              'months_counted': '12'}), 83.33)
        self.assertEqual(_epf_monthly_salary({'employee_contribution_total': 'RM2,750.00',
                                              'months_counted': '1'}), 25000.0)

    def test_an_employer_less_statement_still_reads_as_unemployed(self):
        self.assertEqual(epf_band_salary({'employer_number': '000000000'}), 0.0)
        self.assertFalse(epf_figure_refused({'employer_number': '000000000'}))

    def test_the_real_statements_we_hold_still_read(self):
        # The lowest and highest of the five corpus statements with a table (2026-10-03).
        self.assertEqual(epf_band_salary({'employer_contribution_total': 'RM1071.00',
                                          'employee_contribution_total': 'RM906.00',
                                          'months_counted': '5'}), 1647.69)
        self.assertEqual(epf_band_salary({'employer_contribution_total': 'RM5707.00',
                                          'employee_contribution_total': 'RM4587.00',
                                          'months_counted': '6'}), 7316.67)

    def test_the_refusal_for_each_kind(self):
        self.assertTrue(epf_figure_refused({'employee_contribution_total': 'RM110.00',
                                            'months_counted': '12'}))
        self.assertFalse(epf_figure_refused({'employee_contribution_total': 'RM2,750.00',
                                             'months_counted': '1'}))           # high stays a figure
        self.assertFalse(epf_figure_refused({}))                     # nothing read: nothing refused
        self.assertTrue(slip_figure_refused({'gross_income': '32600'}))            # the window
        self.assertTrue(slip_figure_refused({'gross_income': '1000', 'net_income': '9000'}))  # net>gross
        self.assertTrue(slip_figure_refused({'gross_income': 'RM0.00'}))           # a zero
        self.assertFalse(slip_figure_refused({'gross_income': 'RM1,800.00'}))
        self.assertFalse(slip_figure_refused({'period': '08/2026'}))               # nothing read


#: Review F1's two shapes: a statement implying RM25,000 a month (over the payslip ceiling), and one
#: implying RM83.33 (under the floor).
EPF_HIGH = {'employee_contribution_total': 'RM2,750.00', 'months_counted': '1'}
EPF_LOW = {'employee_contribution_total': 'RM110.00', 'months_counted': '12'}


class EachReaderClassOnTheReviewShapes(hom.IncomeHomesBase):
    """One test per reader class, on real documents: the band, the divergence anomaly, and the
    evidence/submission gates. The > RM20,000 shape behaves exactly as before the batch in all
    three; the < RM100 shape changes the BAND figure only, and nobody is newly blocked."""

    def _with_epf(self, fields, slip=None):
        app = self._app(route='salary', members=('father',))
        self._ic(app)
        hom._doc(app, 'epf', 'father', fields=fields)
        if slip:
            hom._doc(app, 'salary_slip', 'father', fields={'gross_income': slip})
        return app

    def test_band_a_high_estimate_stays_a_figure(self):
        self.assertEqual(earner_monthly_income(self._with_epf(EPF_HIGH), 'father'),
                         (25000.0, 'epf_estimate'))

    def test_band_a_sub_floor_estimate_is_no_figure(self):
        self.assertEqual(earner_monthly_income(self._with_epf(EPF_LOW), 'father'),
                         (None, 'unknown'))

    def test_divergence_still_fires_on_a_small_slip_beside_a_high_epf(self):
        d = slip_epf_divergence(self._with_epf(EPF_HIGH, slip='RM2,000.00'), 'father')
        self.assertIsNotNone(d, 'a doctored RM2,000 slip beside a real RM25,000 EPF went silent')
        self.assertEqual(d['epf_implied'], 25000.0)

    def test_evidence_and_gates_still_count_both_shapes_as_read(self):
        for name, fields in (('high', EPF_HIGH), ('low', EPF_LOW)):
            with self.subTest(shape=name):
                app = self._with_epf(fields)
                self.assertTrue(member_income_evidenced(app, 'father'))
                # Read on its own too: the gate's predicate reaches EPF through `income_shown`, so a
                # window on this one would go unseen by the line above (a silent bite, 2026-10-03).
                self.assertTrue(_member_has_epf_value(app, 'father'))
                self.assertTrue(income_shown(app, 'father').shown)
                self.assertTrue(self.served_household(app))


class TheRefusalIsServedToTheOfficerOnly(hom.IncomeHomesBase):
    """TD-323 review F2: `figure_refused` is on the OFFICER's document payload and nowhere on the
    student's — pinned in both directions, through the real serializers."""

    def test_officer_has_it_and_student_does_not(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.sgd_conversion import AdminApplicantDocumentSerializer
        app = self._app(route='salary', members=('father',))
        self._ic(app)
        cases = (('salary_slip', {'gross_income': '32600'}, True),
                 ('salary_slip', {'gross_income': 'RM1,800.00'}, False),
                 ('epf', EPF_LOW, True),
                 ('epf', EPF_HIGH, False))
        for doc_type, fields, refused in cases:
            with self.subTest(doc_type=doc_type, fields=fields):
                doc = hom._doc(app, doc_type, 'father', fields=fields)
                officer = AdminApplicantDocumentSerializer(doc).data
                student = ApplicantDocumentSerializer(doc).data
                self.assertIs(officer['figure_refused'], refused)
                self.assertNotIn('figure_refused', student)
                self.assertIsNotNone(student['income_proof_check'])   # the check itself is there...
                self.assertNotIn('figure_refused', student['income_proof_check'])   # ...without it
                self.assertNotIn('figure_refused', officer['income_proof_check'])
        ic = app.documents.filter(doc_type='parent_ic').first()
        self.assertIsNone(AdminApplicantDocumentSerializer(ic).data['figure_refused'])
