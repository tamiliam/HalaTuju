"""Tests for the per-pathway funding-need estimate (``funding_estimate.py``)."""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.funding_estimate import classify_pathway, estimate_funding
from apps.scholarship.models import (
    FundingNeed, ScholarshipApplication, ScholarshipCohort,
)


class _Base(TestCase):
    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'fe-{self.id()}', nric='030101-14-1234', name='Priya')
        self._n = 0

    def _app(self, **kw):
        # Fresh cohort per call so multiple apps for the same profile don't trip the
        # one-application-per-(profile, cohort) constraint.
        self._n += 1
        cohort = ScholarshipCohort.objects.create(
            code=f'c{self._n}', name='B40', year=2026 + self._n)
        return ScholarshipApplication.objects.create(
            cohort=cohort, profile=self.profile, status='profile_complete', **kw)


class TestClassify(_Base):
    def test_sure_chosen_pathway_wins(self):
        app = self._app(pathway_certainty='sure', chosen_pathway='matric')
        self.assertEqual(classify_pathway(app), 'matrik')

    def test_value_aliases_map(self):
        self.assertEqual(classify_pathway(self._app(chosen_pathway='poly')), 'poly_diploma')
        self.assertEqual(classify_pathway(self._app(chosen_pathway='university')), 'degree')
        self.assertEqual(classify_pathway(self._app(intended_pathway='asasi')), 'asasi')

    def test_single_considered_used_when_undecided(self):
        app = self._app(pathway_certainty='uncertain', pathways_considered=['stpm'])
        self.assertEqual(classify_pathway(app), 'stpm')

    def test_multiple_considered_is_unknown(self):
        app = self._app(pathway_certainty='uncertain', pathways_considered=['stpm', 'pismp'])
        self.assertEqual(classify_pathway(app), 'unknown')

    def test_blank_is_unknown(self):
        self.assertEqual(classify_pathway(self._app()), 'unknown')

    def test_chosen_programme_classifies_when_pathway_blank(self):
        # #62: offer-letter auto-fill set the programme (a Poly diploma) but left
        # chosen_pathway blank and considered 3 pathways -> classify via the programme.
        app = self._app(
            pathway_certainty='sure', chosen_pathway='', intended_pathway='',
            pathways_considered=['university', 'iljtm', 'ilkbs'],
            chosen_programme={'course_id': 'POLY-DIP-016',
                              'course_name': 'Diploma Kejuruteraan Elektronik (Komunikasi)'})
        self.assertEqual(classify_pathway(app), 'poly_diploma')

    def test_chosen_programme_classifies_by_name(self):
        deg = self._app(chosen_programme={'course_id': 'XY1234567',
                        'course_name': 'Ijazah Sarjana Muda Kejuruteraan'})
        self.assertEqual(classify_pathway(deg), 'degree')
        asasi = self._app(chosen_programme={'course_id': '', 'course_name': 'Asasi Sains'})
        self.assertEqual(classify_pathway(asasi), 'asasi')
        pismp = self._app(chosen_programme={'course_id': 'IPG-1',
                          'course_name': 'PISMP Pendidikan Sarjana Muda'})
        self.assertEqual(classify_pathway(pismp), 'pismp')

    def test_explicit_pathway_beats_programme(self):
        app = self._app(pathway_certainty='sure', chosen_pathway='stpm',
                        chosen_programme={'course_id': 'POLY-DIP-1',
                                          'course_name': 'Diploma X'})
        self.assertEqual(classify_pathway(app), 'stpm')

    def test_unreadable_programme_is_unknown(self):
        app = self._app(chosen_programme={'course_id': '', 'course_name': 'Something Unmappable'})
        self.assertEqual(classify_pathway(app), 'unknown')
        self.assertEqual(classify_pathway(self._app(chosen_programme={})), 'unknown')


class TestEstimate(_Base):
    def test_unknown_pathway_gives_no_estimate(self):
        est = estimate_funding(self._app())
        self.assertFalse(est['known'])
        self.assertEqual(est['total'], (0, 0))

    def test_stpm_has_the_highest_monthly(self):
        # STPM (transport + tuition + books) should exceed matrik (small top-up).
        stpm = estimate_funding(self._app(chosen_pathway='stpm', pathway_certainty='sure'))
        matrik = estimate_funding(self._app(chosen_pathway='matric', pathway_certainty='sure'))
        self.assertGreater(stpm['monthly_total'][0], matrik['monthly_total'][0])
        self.assertIn('transport', stpm['monthly'])

    def test_total_uses_programme_months(self):
        app = self._app(chosen_pathway='stpm', pathway_certainty='sure')
        FundingNeed.objects.create(application=app, categories=['transport'], programme_months=18)
        est = estimate_funding(app)
        m_lo = est['monthly_total'][0]
        o_lo = est['one_off_total'][0]
        self.assertEqual(est['programme_months'], 18)
        self.assertEqual(est['total'][0], m_lo * 18 + o_lo)

    def test_total_annualises_when_months_unknown(self):
        est = estimate_funding(self._app(chosen_pathway='matric', pathway_certainty='sure'))
        self.assertIsNone(est['programme_months'])
        self.assertEqual(est['total'][0], est['monthly_total'][0] * 12 + est['one_off_total'][0])

    def test_device_is_in_every_known_pathway(self):
        for pw in ('matric', 'asasi', 'stpm', 'poly', 'pismp', 'university'):
            est = estimate_funding(self._app(chosen_pathway=pw, pathway_certainty='sure'))
            self.assertIn('device', est['one_off'], pw)

    def test_degree_is_flagged_for_review(self):
        est = estimate_funding(self._app(chosen_pathway='university', pathway_certainty='sure'))
        self.assertTrue(est['review'])
