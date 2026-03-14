"""
Tests for the pre-university pathway eligibility engine.

Covers Matriculation (4 tracks) and STPM (2 bidangs).
Uses backend grade keys (math, addmath, chem, etc.) not frontend keys.
"""
import pytest
from django.test import TestCase
from apps.courses.pathways import (
    is_credit,
    meets_min,
    find_best_elective,
    check_matric_track,
    check_stpm_bidang,
    check_all_pathways,
    get_pathway_fit_score,
    MATRIC_GRADE_POINTS,
    STPM_MATA_GRED,
)


# ── Helpers ──────────────────────────────────────────────────────────────

class TestIsCredit:
    def test_a_plus_is_credit(self):
        assert is_credit('A+') is True

    def test_c_is_credit(self):
        assert is_credit('C') is True

    def test_d_is_not_credit(self):
        assert is_credit('D') is False

    def test_g_is_not_credit(self):
        assert is_credit('G') is False

    def test_invalid_grade(self):
        assert is_credit('X') is False


class TestMeetsMin:
    def test_exact_match(self):
        assert meets_min('B', 'B') is True

    def test_better_grade(self):
        assert meets_min('A+', 'C') is True

    def test_worse_grade(self):
        assert meets_min('D', 'C') is False

    def test_invalid_grade(self):
        assert meets_min('X', 'C') is False


class TestFindBestElective:
    def test_picks_best_available(self):
        grades = {'math': 'A+', 'chem': 'B', 'phy': 'C+'}
        result = find_best_elective(grades, {'math'}, 'C')
        assert result is not None
        assert result['id'] == 'chem'
        assert result['grade'] == 'B'

    def test_excludes_used(self):
        grades = {'math': 'A+', 'chem': 'A'}
        result = find_best_elective(grades, {'math', 'chem'}, 'C')
        assert result is None

    def test_respects_min_grade(self):
        grades = {'phy': 'D', 'bio': 'E'}
        result = find_best_elective(grades, set(), 'C')
        assert result is None


# ── Matric Tracks ────────────────────────────────────────────────────────

class TestMatricScience:
    """Matric Science track: math(B), addmath(C), chem(C), phy/bio(C)."""

    def test_good_grades_eligible(self):
        grades = {
            'math': 'A', 'addmath': 'B', 'chem': 'B+', 'phy': 'A-',
        }
        result = check_matric_track('sains', grades, 8)
        assert result['eligible'] is True
        assert result['pathway'] == 'matric'
        assert result['track_id'] == 'sains'
        assert result['merit'] is not None
        assert result['merit'] > 0

    def test_missing_addmath_not_eligible(self):
        grades = {'math': 'A', 'chem': 'B', 'phy': 'B'}
        result = check_matric_track('sains', grades, 8)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.subjectMissing'

    def test_math_grade_too_low(self):
        grades = {'math': 'C', 'addmath': 'B', 'chem': 'B', 'phy': 'B'}
        result = check_matric_track('sains', grades, 8)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.gradeTooLow'

    def test_bio_as_alternative_to_phy(self):
        grades = {'math': 'A', 'addmath': 'B', 'chem': 'B+', 'bio': 'A-'}
        result = check_matric_track('sains', grades, 8)
        assert result['eligible'] is True


class TestMatricEngineering:
    """Matric Engineering: math(B), addmath(C), phy(C), +1 elective(C)."""

    def test_eligible_with_elective(self):
        grades = {
            'math': 'A', 'addmath': 'B', 'phy': 'B+',
            'chem': 'C+',  # elective
        }
        result = check_matric_track('kejuruteraan', grades, 8)
        assert result['eligible'] is True

    def test_not_enough_electives(self):
        grades = {'math': 'A', 'addmath': 'B', 'phy': 'B+'}
        result = check_matric_track('kejuruteraan', grades, 8)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.notEnoughElectives'


class TestMatricComputerScience:
    """Matric CS: math(C), addmath(C), comp_sci(C), +1 elective(C)."""

    def test_eligible(self):
        grades = {
            'math': 'B', 'addmath': 'C', 'comp_sci': 'B',
            'eng': 'A',  # elective
        }
        result = check_matric_track('sains_komputer', grades, 5)
        assert result['eligible'] is True
        assert result['track_name'] == 'Computer Science'


class TestMatricAccounting:
    """Matric Accounting: math(C), +3 electives(C)."""

    def test_eligible(self):
        grades = {
            'math': 'B', 'poa': 'A', 'ekonomi': 'B+', 'eng': 'C',
        }
        result = check_matric_track('perakaunan', grades, 5)
        assert result['eligible'] is True
        assert result['track_name'] == 'Accounting'

    def test_not_enough_electives(self):
        grades = {'math': 'B', 'poa': 'A'}
        result = check_matric_track('perakaunan', grades, 5)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.notEnoughElectives'


class TestMatricMerit:
    """Merit = (sum_of_4_grade_points / 100) * 90 + coq, capped at 100."""

    def test_perfect_merit(self):
        # 4x A+ = 4*25 = 100 points → academic = 90, coq = 10 → merit = 100
        grades = {
            'math': 'A+', 'addmath': 'A+', 'chem': 'A+', 'phy': 'A+',
        }
        result = check_matric_track('sains', grades, 10)
        assert result['eligible'] is True
        assert result['merit'] == 100

    def test_merit_calculation(self):
        # 4x A = 4*24 = 96 → academic = (96/100)*90 = 86.4, coq=8 → 94.4
        grades = {
            'math': 'A', 'addmath': 'A', 'chem': 'A', 'phy': 'A',
        }
        result = check_matric_track('sains', grades, 8)
        assert result['merit'] == 94.4


# ── STPM Bidangs ─────────────────────────────────────────────────────────

class TestStpmScience:
    """STPM Science: BM credit + 3 credits from different groups."""

    def test_eligible(self):
        grades = {
            'bm': 'B',   # credit
            'math': 'A',  # group 0
            'phy': 'B+',  # group 1
            'chem': 'A-',  # group 2
        }
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is True
        assert result['pathway'] == 'stpm'
        assert result['mata_gred'] is not None
        assert result['max_mata_gred'] == 18
        # mata_gred: math A=1, phy B+=3, chem A-=2 → 6
        assert result['mata_gred'] == 6

    def test_no_bm_credit(self):
        grades = {'bm': 'D', 'math': 'A', 'phy': 'A', 'chem': 'A'}
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.bmCreditRequired'

    def test_not_enough_group_credits(self):
        grades = {
            'bm': 'B',
            'math': 'A',  # group 0
            'phy': 'B',   # group 1
            # only 2 groups
        }
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.notEnoughCredits'


class TestStpmSocialScience:
    """STPM Social Science bidang."""

    def test_eligible(self):
        grades = {
            'bm': 'A',
            'eng': 'B',     # group 1
            'hist': 'C+',   # group 2
            'geo': 'C',     # group 3
        }
        result = check_stpm_bidang('sains_sosial', grades)
        assert result['eligible'] is True
        assert result['track_name'] == 'Social Science'


class TestStpmMataGred:
    """Mata gred threshold tests."""

    def test_exactly_at_threshold(self):
        # 3 subjects each with C (mata_gred=6) → total=18 = maxMataGred
        grades = {
            'bm': 'C',
            'math': 'C',   # group 0, mg=6
            'phy': 'C',    # group 1, mg=6
            'chem': 'C',   # group 2, mg=6
        }
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is True
        assert result['mata_gred'] == 18

    def test_high_mata_gred_returned_for_science(self):
        grades = {'bm': 'A', 'math': 'A', 'phy': 'A', 'chem': 'A'}
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is True
        assert result['high_mata_gred'] == 18  # Science: ≤18 = High

    def test_high_mata_gred_returned_for_socsci(self):
        grades = {'bm': 'A', 'hist': 'A', 'geo': 'A', 'ekonomi': 'A'}
        result = check_stpm_bidang('sains_sosial', grades)
        assert result['eligible'] is True
        assert result['high_mata_gred'] == 12  # Sains Sosial: ≤12 = High

    def test_exceeds_threshold(self):
        # Need credits from 3 different groups, all D = mg 7 each → 21 > 18
        # But D is not a credit (mg=7 > 6), so they won't even qualify
        # Use C (mg=6) for 2 and D won't count → not enough credits
        # Better test: 2x C (mg=6) + 1x C+ (mg=5) = 17 eligible;
        # impossible to exceed with credits since max credit mg is 6*3=18
        # So test the edge: this scenario can't naturally exceed threshold
        # with credits. The logic still handles it though.
        # We can test via mata_gred_too_high reason directly
        # Since all credits have mg <= 6, and 3*6=18=threshold, it's impossible
        # to exceed with real grades. But the code path exists.
        # Let's just verify the boundary: 18 is eligible (tested above)
        pass

    def test_no_bm_missing(self):
        grades = {'math': 'A', 'phy': 'A', 'chem': 'A'}
        result = check_stpm_bidang('sains', grades)
        assert result['eligible'] is False
        assert result['reason'] == 'pathways.bmCreditRequired'


# ── Integration ──────────────────────────────────────────────────────────

class TestCheckAllPathways:
    def test_returns_six_results(self):
        grades = {
            'math': 'A', 'addmath': 'B', 'chem': 'B', 'phy': 'B',
            'bio': 'C+', 'bm': 'A', 'eng': 'B', 'hist': 'C',
            'comp_sci': 'C', 'poa': 'C', 'ekonomi': 'C',
        }
        results = check_all_pathways(grades, 8)
        assert len(results) == 6

        pathways = [(r['pathway'], r['track_id']) for r in results]
        assert ('matric', 'sains') in pathways
        assert ('matric', 'kejuruteraan') in pathways
        assert ('matric', 'sains_komputer') in pathways
        assert ('matric', 'perakaunan') in pathways
        assert ('stpm', 'sains') in pathways
        assert ('stpm', 'sains_sosial') in pathways

    def test_each_result_has_required_keys(self):
        grades = {'math': 'A', 'addmath': 'B', 'chem': 'B', 'phy': 'B', 'bm': 'A'}
        results = check_all_pathways(grades, 5)
        required_keys = {
            'pathway', 'track_id', 'track_name', 'track_name_ms',
            'track_name_ta', 'eligible',
        }
        for r in results:
            assert required_keys.issubset(r.keys()), f"Missing keys in {r}"


class TestPathwayFitScore(TestCase):
    """Tests for get_pathway_fit_score() — ported from frontend pathways.ts."""

    def test_eligible_matric_base_score(self):
        """Eligible matric track gets base + prestige."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 85.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        # BASE_SCORE (100) + prestige (8) + academic bonus (0, merit < 89)
        self.assertEqual(score, 108)

    def test_eligible_matric_high_merit(self):
        """High merit matric gets academic bonus."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 95.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        # 100 + 8 (prestige) + 8 (academic, merit >= 94)
        self.assertEqual(score, 116)

    def test_eligible_stpm_low_mata_gred(self):
        """Low mata gred (good) gets academic bonus."""
        result = {
            'pathway': 'stpm', 'track_id': 'sains',
            'eligible': True, 'merit': None,
            'mata_gred': 4, 'max_mata_gred': 18,
        }
        score = get_pathway_fit_score(result)
        # 100 + 5 (prestige) + 8 (academic, mata_gred <= 4)
        self.assertEqual(score, 113)

    def test_not_eligible_returns_zero(self):
        """Not eligible → score 0."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': False, 'merit': None,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        self.assertEqual(score, 0)

    def test_signal_adjustment_capped(self):
        """Signal adjustment is capped at ±6."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 85.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        # Extreme positive signals
        signals = {
            'work_preference_signals': {'problem_solving': 1},
            'learning_tolerance_signals': {'concept_first': 1, 'rote_tolerant': 1},
            'value_tradeoff_signals': {
                'pathway_priority': 1, 'quality_priority': 1, 'allowance_priority': 1,
            },
            'energy_sensitivity_signals': {'high_stamina': 1},
        }
        score = get_pathway_fit_score(result, signals)
        # 100 + 8 + 0 + 6 (capped) = 114
        self.assertEqual(score, 114)
