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
        self.assertEqual(classify_pathway(app), 'matric')

    def test_value_aliases_map(self):
        self.assertEqual(classify_pathway(self._app(chosen_pathway='poly')), 'poly')
        # post-SPM "university" = a public-university diploma (not a degree).
        self.assertEqual(classify_pathway(self._app(chosen_pathway='university')), 'university')
        self.assertEqual(classify_pathway(self._app(intended_pathway='asasi')), 'asasi')

    def test_unestimated_pathways_are_unknown(self):
        for pw in ('kkom', 'iljtm', 'ilkbs'):
            self.assertEqual(classify_pathway(self._app(chosen_pathway=pw)), 'unknown', pw)

    def test_single_considered_used_when_undecided(self):
        app = self._app(pathway_certainty='uncertain', pathways_considered=['stpm'])
        self.assertEqual(classify_pathway(app), 'stpm')

    def test_multiple_considered_is_unknown(self):
        app = self._app(pathway_certainty='uncertain', pathways_considered=['stpm', 'asasi'])
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
        self.assertEqual(classify_pathway(app), 'poly')

    def test_chosen_programme_classifies_by_name(self):
        # A non-Politeknik diploma (MOHE-coded id) = a public-university diploma.
        uadip = self._app(chosen_programme={'course_id': 'UM0010001',
                          'course_name': 'Diploma Pengurusan'})
        self.assertEqual(classify_pathway(uadip), 'university')
        asasi = self._app(chosen_programme={'course_id': '', 'course_name': 'Asasi Sains'})
        self.assertEqual(classify_pathway(asasi), 'asasi')
        pismp = self._app(chosen_programme={'course_id': 'IPG-1',
                          'course_name': 'PISMP Perguruan'})
        self.assertEqual(classify_pathway(pismp), 'pismp')

    def test_chosen_programme_kkom_gives_no_estimate(self):
        app = self._app(chosen_programme={'course_id': 'KKOM-DIP-1',
                        'course_name': 'Diploma Kolej Komuniti'})
        self.assertEqual(classify_pathway(app), 'unknown')

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
        self.assertEqual(est['total'], 0)

    def test_known_pathway_shortfall_and_total(self):
        # Politeknik: ~RM120/mth x 36 mth = 4,320 -> rounded to RM4,300.
        est = estimate_funding(self._app(chosen_pathway='poly', pathway_certainty='sure'))
        self.assertTrue(est['known'])
        self.assertEqual(est['monthly'], 120)
        self.assertEqual(est['months'], 36)
        self.assertEqual(est['total'], 4300)

    def test_each_pathway_total(self):
        cases = {'stpm': 9000, 'matric': 2000, 'asasi': 7000,
                 'poly': 4300, 'university': 6600, 'pismp': 10800}
        for pw, total in cases.items():
            est = estimate_funding(self._app(chosen_pathway=pw, pathway_certainty='sure'))
            self.assertEqual(est['total'], total, pw)

    def test_programme_months_overrides_default(self):
        app = self._app(chosen_pathway='university', pathway_certainty='sure')
        FundingNeed.objects.create(application=app, categories=['fees'], programme_months=24)
        est = estimate_funding(app)
        self.assertEqual(est['months'], 24)
        self.assertEqual(est['total'], 5300)  # 220 x 24 = 5,280 -> rounds to 5,300

    def test_variable_flags(self):
        self.assertTrue(estimate_funding(self._app(chosen_pathway='asasi',
                        pathway_certainty='sure'))['variable'])
        self.assertTrue(estimate_funding(self._app(chosen_pathway='university',
                        pathway_certainty='sure'))['variable'])
        self.assertFalse(estimate_funding(self._app(chosen_pathway='poly',
                         pathway_certainty='sure'))['variable'])

    def test_practical_flags(self):
        for pw in ('poly', 'university', 'pismp'):
            self.assertTrue(estimate_funding(self._app(chosen_pathway=pw,
                            pathway_certainty='sure'))['practical'], pw)
        for pw in ('stpm', 'matric', 'asasi'):
            self.assertFalse(estimate_funding(self._app(chosen_pathway=pw,
                             pathway_certainty='sure'))['practical'], pw)

    def test_no_device_in_estimate(self):
        # Device is deliberately excluded (tranche support is unsuitable for a lump sum).
        est = estimate_funding(self._app(chosen_pathway='stpm', pathway_certainty='sure'))
        self.assertNotIn('one_off', est)
        self.assertNotIn('device', str(est))
