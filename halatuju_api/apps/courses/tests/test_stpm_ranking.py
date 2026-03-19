"""
Tests for STPM ranking engine v2 (quiz-informed).

Covers all scoring components from the design doc Section 11:
- CGPA margin (+20 max)
- Field match (+12 max, from Q2-Q4 field_key signals)
- RIASEC alignment (+8 max, from subject seed + Q5 cross-domain)
- Efficacy modifier (+4 to -2)
- Goal alignment (+4 max)
- Interview penalty (-3)
- Resilience discount (0 to -3)
- Result framing (3 modes)
"""
from apps.courses.stpm_ranking import (
    BASE_SCORE,
    calculate_stpm_fit_score,
    get_result_framing,
    get_stpm_ranked_results,
    _get_field_match_score,
    _get_riasec_alignment,
    _get_efficacy_modifier,
    _get_goal_alignment,
    _get_resilience_discount,
)


def _course(**overrides):
    """Helper: build a minimal course dict."""
    base = {
        'course_id': 'TEST001',
        'course_name': 'Test Course',
        'university': 'UM',
        'stream': 'science',
        'min_cgpa': 3.0,
        'min_muet_band': 3,
        'req_interview': False,
        'no_colorblind': False,
        'field_key': '',
        'riasec_type': '',
        'difficulty_level': '',
    }
    base.update(overrides)
    return base


# ── Base score + CGPA margin ─────────────────────────────────────────

class TestBaseAndCgpa:
    def test_base_score_no_signals(self):
        score, reasons = calculate_stpm_fit_score(_course(), 3.0, {})
        assert score == BASE_SCORE

    def test_cgpa_margin_adds_bonus(self):
        score, reasons = calculate_stpm_fit_score(_course(min_cgpa=2.5), 3.5, {})
        assert score == BASE_SCORE + 20  # 1.0 margin × 20 = +20 (capped)

    def test_cgpa_margin_capped_at_20(self):
        score1, _ = calculate_stpm_fit_score(_course(min_cgpa=1.0), 3.5, {})
        score2, _ = calculate_stpm_fit_score(_course(min_cgpa=1.0), 4.0, {})
        # Both margins > 1.0, should both cap at +20
        assert score1 == BASE_SCORE + 20
        assert score2 == BASE_SCORE + 20

    def test_cgpa_margin_negative_gives_no_bonus(self):
        score, _ = calculate_stpm_fit_score(_course(min_cgpa=3.5), 3.0, {})
        assert score == BASE_SCORE  # margin is -0.5, no bonus

    def test_cgpa_margin_partial(self):
        score, _ = calculate_stpm_fit_score(_course(min_cgpa=3.0), 3.5, {})
        assert score == BASE_SCORE + 10  # 0.5 margin × 20 = +10


# ── Field match (max +12) ────────────────────────────────────────────

class TestFieldMatch:
    def test_primary_field_key_match_gives_8(self):
        signals = {'field_key': {'field_key_mekanikal': 2}}
        score, _ = _get_field_match_score('mekanikal', signals)
        assert score == 8

    def test_primary_match_automotif_via_mekanikal(self):
        """field_key_mekanikal maps to ['mekanikal', 'automotif']."""
        signals = {'field_key': {'field_key_mekanikal': 2}}
        score, _ = _get_field_match_score('automotif', signals)
        assert score == 8

    def test_secondary_field_interest_match_gives_4(self):
        """Q2 broad interest matches course field_key via parent mapping."""
        signals = {
            'field_interest': {'field_engineering': 3},
            'field_key': {},
        }
        score, _ = _get_field_match_score('mekanikal', signals)
        assert score == 4

    def test_no_match_gives_0(self):
        signals = {'field_key': {'field_key_perubatan': 2}}
        score, _ = _get_field_match_score('mekanikal', signals)
        assert score == 0

    def test_empty_field_key_gives_0(self):
        signals = {'field_key': {'field_key_mekanikal': 2}}
        score, _ = _get_field_match_score('', signals)
        assert score == 0

    def test_no_signals_gives_0(self):
        score, _ = _get_field_match_score('mekanikal', {})
        assert score == 0

    def test_cross_domain_adds_2(self):
        signals = {'cross_domain': {'cross_R': 1}}
        score, _ = _get_field_match_score('mekanikal', signals)
        assert score == 2

    def test_primary_plus_cross_capped_at_12(self):
        signals = {
            'field_key': {'field_key_mekanikal': 2},
            'cross_domain': {'cross_R': 1},
        }
        score, _ = _get_field_match_score('mekanikal', signals)
        assert score == 10  # 8 + 2 = 10 (under cap)

    def test_field_match_law(self):
        signals = {'field_key': {'field_key_law': 2}}
        score, _ = _get_field_match_score('undang-undang', signals)
        assert score == 8


# ── RIASEC alignment (max +8) ────────────────────────────────────────

class TestRiasecAlignment:
    def test_primary_seed_match_gives_6(self):
        signals = {'riasec_seed': {'riasec_I': 5, 'riasec_R': 3}}
        score, _ = _get_riasec_alignment('I', signals)
        assert score == 6

    def test_secondary_seed_match_gives_3(self):
        signals = {'riasec_seed': {'riasec_I': 5, 'riasec_R': 3, 'riasec_C': 1}}
        score, _ = _get_riasec_alignment('R', signals)
        assert score == 3

    def test_no_match_gives_0(self):
        signals = {'riasec_seed': {'riasec_I': 5, 'riasec_R': 3}}
        score, _ = _get_riasec_alignment('E', signals)
        assert score == 0

    def test_cross_domain_adds_2(self):
        signals = {
            'riasec_seed': {'riasec_I': 5},
            'cross_domain': {'cross_E': 1},
        }
        score, _ = _get_riasec_alignment('E', signals)
        assert score == 2

    def test_primary_plus_cross_capped_at_8(self):
        signals = {
            'riasec_seed': {'riasec_I': 5},
            'cross_domain': {'cross_I': 1},
        }
        score, _ = _get_riasec_alignment('I', signals)
        assert score == 8  # 6 + 2 = 8 = cap

    def test_empty_riasec_type_gives_0(self):
        signals = {'riasec_seed': {'riasec_I': 5}}
        score, _ = _get_riasec_alignment('', signals)
        assert score == 0

    def test_no_signals_gives_0(self):
        score, _ = _get_riasec_alignment('I', {})
        assert score == 0

    def test_tied_primary_seeds(self):
        """When two types tie for highest, both are 'primary'."""
        signals = {'riasec_seed': {'riasec_I': 5, 'riasec_R': 5, 'riasec_C': 1}}
        score_i, _ = _get_riasec_alignment('I', signals)
        score_r, _ = _get_riasec_alignment('R', signals)
        assert score_i == 6
        assert score_r == 6


# ── Efficacy modifier (+4 to -2) ─────────────────────────────────────

class TestEfficacyModifier:
    def test_confirmed_gives_plus4(self):
        signals = {'efficacy': {'efficacy_confirmed': 2}}
        mod, _ = _get_efficacy_modifier(signals)
        assert mod == 4

    def test_confident_gives_plus2(self):
        signals = {'efficacy': {'efficacy_confident': 2}}
        mod, _ = _get_efficacy_modifier(signals)
        assert mod == 2

    def test_open_gives_0(self):
        signals = {'efficacy': {'efficacy_open': 2}}
        mod, _ = _get_efficacy_modifier(signals)
        assert mod == 0

    def test_redirect_gives_minus1(self):
        signals = {'efficacy': {'efficacy_redirect': 1}}
        mod, _ = _get_efficacy_modifier(signals)
        assert mod == -1

    def test_mismatch_gives_minus2(self):
        signals = {'efficacy': {'efficacy_mismatch': 0}}
        mod, _ = _get_efficacy_modifier(signals)
        assert mod == -2

    def test_no_signals_gives_0(self):
        mod, _ = _get_efficacy_modifier({})
        assert mod == 0


# ── Goal alignment (max +4) ──────────────────────────────────────────

class TestGoalAlignment:
    def test_professional_plus_medicine_gives_4(self):
        signals = {'career_goal': {'goal_professional': 2}}
        score, _ = _get_goal_alignment('perubatan', signals)
        assert score == 4

    def test_professional_plus_nonreg_gives_0(self):
        signals = {'career_goal': {'goal_professional': 2}}
        score, _ = _get_goal_alignment('pemasaran', signals)
        assert score == 0

    def test_postgrad_plus_research_gives_4(self):
        signals = {'career_goal': {'goal_postgrad': 2}}
        score, _ = _get_goal_alignment('bioteknologi', signals)
        assert score == 4

    def test_entrepreneurial_plus_business_gives_3(self):
        signals = {'career_goal': {'goal_entrepreneurial': 2}}
        score, _ = _get_goal_alignment('perniagaan', signals)
        assert score == 3

    def test_employment_universal_gives_3(self):
        signals = {'career_goal': {'goal_employment': 2}}
        score, _ = _get_goal_alignment('mekanikal', signals)
        assert score == 3

    def test_no_career_goal_gives_0(self):
        score, _ = _get_goal_alignment('perubatan', {})
        assert score == 0

    def test_no_field_key_gives_0(self):
        signals = {'career_goal': {'goal_professional': 2}}
        score, _ = _get_goal_alignment('', signals)
        assert score == 0


# ── Resilience discount (0 to -3) ────────────────────────────────────

class TestResilienceDiscount:
    def test_redirect_plus_high_gives_minus3(self):
        signals = {'resilience': {'resilience_redirect': 1}}
        discount, _ = _get_resilience_discount('high', signals)
        assert discount == -3

    def test_redirect_plus_moderate_gives_minus1(self):
        signals = {'resilience': {'resilience_redirect': 1}}
        discount, _ = _get_resilience_discount('moderate', signals)
        assert discount == -1

    def test_supported_plus_high_gives_minus1(self):
        signals = {'resilience': {'resilience_supported': 1}}
        discount, _ = _get_resilience_discount('high', signals)
        assert discount == -1

    def test_redirect_plus_low_gives_0(self):
        signals = {'resilience': {'resilience_redirect': 1}}
        discount, _ = _get_resilience_discount('low', signals)
        assert discount == 0

    def test_high_resilience_no_discount(self):
        signals = {'resilience': {'resilience_high': 2}}
        discount, _ = _get_resilience_discount('high', signals)
        assert discount == 0

    def test_no_difficulty_gives_0(self):
        signals = {'resilience': {'resilience_redirect': 1}}
        discount, _ = _get_resilience_discount('', signals)
        assert discount == 0

    def test_no_signals_gives_0(self):
        discount, _ = _get_resilience_discount('high', {})
        assert discount == 0


# ── Interview penalty ─────────────────────────────────────────────────

class TestInterviewPenalty:
    def test_interview_subtracts_3(self):
        score_yes, _ = calculate_stpm_fit_score(
            _course(req_interview=True), 3.0, {},
        )
        score_no, _ = calculate_stpm_fit_score(
            _course(req_interview=False), 3.0, {},
        )
        assert score_no - score_yes == 3

    def test_interview_reason_in_output(self):
        _, reasons = calculate_stpm_fit_score(
            _course(req_interview=True), 3.0, {},
        )
        assert any('Interview' in r for r in reasons)


# ── Full score integration ────────────────────────────────────────────

class TestFullScore:
    def test_maximum_possible_score(self):
        """All bonuses maxed, no penalties: 50+20+12+8+4+4 = 98."""
        course = _course(
            min_cgpa=2.0,
            field_key='mekanikal',
            riasec_type='R',
            difficulty_level='low',
            req_interview=False,
        )
        signals = {
            'riasec_seed': {'riasec_R': 5, 'riasec_I': 3},
            'field_key': {'field_key_mekanikal': 2},
            'field_interest': {'field_engineering': 3},
            'cross_domain': {'cross_R': 1},
            'efficacy': {'efficacy_confirmed': 2},
            'career_goal': {'goal_professional': 2},
            'resilience': {'resilience_high': 2},
        }
        score, _ = calculate_stpm_fit_score(course, 3.0, signals)
        # 50 + 20 + 10(field: 8 primary + 2 cross) + 8(riasec: 6+2) + 4(eff) + 4(goal) = 96
        # Note: field is 8+2=10, not 12 (no secondary on top of primary)
        assert score >= 90
        assert score <= 98

    def test_minimum_possible_score(self):
        """All penalties, no bonuses."""
        course = _course(
            min_cgpa=4.0,
            field_key='perubatan',
            riasec_type='I',
            difficulty_level='high',
            req_interview=True,
        )
        signals = {
            'efficacy': {'efficacy_mismatch': 0},
            'resilience': {'resilience_redirect': 1},
        }
        score, _ = calculate_stpm_fit_score(course, 3.0, signals)
        # 50 + 0(cgpa) + 0(field) + 0(riasec) + (-2)(eff) + 0(goal) + (-3)(interview) + (-3)(resilience) = 42
        assert score == 42

    def test_no_quiz_still_works(self):
        """Without quiz signals, scoring falls back to CGPA + base only."""
        course = _course(min_cgpa=2.5)
        score, reasons = calculate_stpm_fit_score(course, 3.5, {})
        assert score == 70  # 50 + 20

    def test_backwards_compatible_with_v1_signals(self):
        """Old-style signals (field_interest dict) still produce a score."""
        course = _course(min_cgpa=3.0, field_key='mekanikal')
        signals = {'field_interest': {'field_engineering': 3}}
        score, _ = calculate_stpm_fit_score(course, 3.5, signals)
        assert score > BASE_SCORE  # gets CGPA bonus + field secondary


# ── Result framing ────────────────────────────────────────────────────

class TestResultFraming:
    def test_confirmatory_mode(self):
        signals = {'context': {'crystallisation_high': 2}}
        framing = get_result_framing(signals)
        assert framing['mode'] == 'confirmatory'
        assert 'aligns' in framing['heading']

    def test_guided_mode(self):
        signals = {'context': {'crystallisation_moderate': 2}}
        framing = get_result_framing(signals)
        assert framing['mode'] == 'guided'
        assert 'interests' in framing['heading']

    def test_discovery_mode(self):
        signals = {'context': {'crystallisation_low': 2}}
        framing = get_result_framing(signals)
        assert framing['mode'] == 'discovery'
        assert 'exploring' in framing['heading']

    def test_default_is_guided(self):
        framing = get_result_framing({})
        assert framing['mode'] == 'guided'

    def test_framing_has_subtitle(self):
        framing = get_result_framing({'context': {'crystallisation_high': 2}})
        assert 'subtitle' in framing
        assert len(framing['subtitle']) > 0


# ── Ranked results ────────────────────────────────────────────────────

class TestRankedResults:
    def test_sorted_by_score_desc(self):
        courses = [
            _course(course_id='A', course_name='Low', min_cgpa=3.5),
            _course(course_id='B', course_name='High', min_cgpa=2.0),
        ]
        result = get_stpm_ranked_results(courses, 3.5, {})
        assert result[0]['course_id'] == 'B'

    def test_empty_list(self):
        assert get_stpm_ranked_results([], 3.0, {}) == []

    def test_fit_score_in_output(self):
        courses = [_course()]
        result = get_stpm_ranked_results(courses, 3.0, {})
        assert 'fit_score' in result[0]
        assert 'fit_reasons' in result[0]

    def test_merit_score_survives(self):
        courses = [_course(merit_score=95.5)]
        ranked = get_stpm_ranked_results(courses, 3.5, {})
        assert ranked[0]['merit_score'] == 95.5

    def test_quiz_signals_affect_ordering(self):
        """Course matching quiz signals should rank higher."""
        courses = [
            _course(course_id='A', course_name='AAA', min_cgpa=3.0,
                    field_key='pemasaran', riasec_type='E'),
            _course(course_id='B', course_name='BBB', min_cgpa=3.0,
                    field_key='mekanikal', riasec_type='R'),
        ]
        signals = {
            'riasec_seed': {'riasec_R': 5, 'riasec_I': 3},
            'field_key': {'field_key_mekanikal': 2},
        }
        ranked = get_stpm_ranked_results(courses, 3.5, signals)
        assert ranked[0]['course_id'] == 'B'  # mekanikal matches R seed + field_key

    def test_university_tier_breaks_tie(self):
        """At equal score, research uni ranks above focused uni."""
        courses = [
            _course(course_id='A', course_name='AAA', min_cgpa=3.0,
                    university='Universiti Utara Malaysia'),
            _course(course_id='B', course_name='BBB', min_cgpa=3.0,
                    university='Universiti Malaya'),
        ]
        ranked = get_stpm_ranked_results(courses, 3.0, {})
        # Same score, same min_cgpa → UM (tier 3) beats UUM (tier 1)
        assert ranked[0]['course_id'] == 'B'

    def test_competitiveness_breaks_tie(self):
        """At equal score and uni tier, higher min_cgpa ranks first."""
        # Both min_cgpa values are >1.0 below student_cgpa so CGPA margin
        # is capped equally — only the tiebreaker differs.
        courses = [
            _course(course_id='A', course_name='AAA', min_cgpa=2.0,
                    university='Universiti Utara Malaysia'),
            _course(course_id='B', course_name='BBB', min_cgpa=2.5,
                    university='Universiti Utara Malaysia'),
        ]
        ranked = get_stpm_ranked_results(courses, 3.5, {})
        # B has higher min_cgpa (more competitive) → ranks first
        assert ranked[0]['course_id'] == 'B'

    def test_difficulty_breaks_tie(self):
        """At equal score, uni, and min_cgpa, higher difficulty ranks first."""
        courses = [
            _course(course_id='A', course_name='AAA', min_cgpa=3.0,
                    university='UM', difficulty_level='low'),
            _course(course_id='B', course_name='BBB', min_cgpa=3.0,
                    university='UM', difficulty_level='high'),
        ]
        ranked = get_stpm_ranked_results(courses, 3.0, {})
        assert ranked[0]['course_id'] == 'B'

    def test_name_breaks_final_tie(self):
        """When everything else is equal, alphabetical name wins."""
        courses = [
            _course(course_id='A', course_name='Zoology', min_cgpa=3.0),
            _course(course_id='B', course_name='Accounting', min_cgpa=3.0),
        ]
        ranked = get_stpm_ranked_results(courses, 3.0, {})
        assert ranked[0]['course_id'] == 'B'  # Accounting < Zoology

    def test_score_always_trumps_tier(self):
        """Score is primary — a focused uni with higher score beats research uni."""
        courses = [
            _course(course_id='A', course_name='AAA', min_cgpa=3.5,
                    university='Universiti Malaya'),        # tier 3, low margin
            _course(course_id='B', course_name='BBB', min_cgpa=2.0,
                    university='Universiti Utara Malaysia'),  # tier 1, high margin
        ]
        ranked = get_stpm_ranked_results(courses, 3.5, {})
        # B has much higher CGPA margin → higher score → ranks first despite lower tier
        assert ranked[0]['course_id'] == 'B'
