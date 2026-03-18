"""
Tests for the STPM quiz engine — RIASEC seed calculation, branch routing,
grade-adaptive Q4, cross-domain Q5 filtering, and signal accumulation.
"""
import pytest

from apps.courses.stpm_quiz_engine import (
    calculate_riasec_seed,
    get_primary_seed,
    determine_branch,
    has_extra_cross_stream_subject,
    get_stpm_quiz_questions,
    resolve_q3_and_q4,
    process_stpm_quiz,
)
from apps.courses.stpm_quiz_data import (
    STPM_SIGNAL_TAXONOMY,
    SUBJECT_RIASEC_MAP,
)


# ── RIASEC seed calculation ──────────────────────────────────────

class TestRiasecSeed:

    def test_science_subjects_physics_chem_math(self):
        """Physics(R2,I1) + Chemistry(I2,R1) + MathT(I2,C1) = R:3, I:5, C:1"""
        seed = calculate_riasec_seed(['physics', 'chemistry', 'mathematics_t'])
        assert seed == {'R': 3, 'I': 5, 'C': 1}

    def test_arts_subjects_econ_acc_biz(self):
        """Economics(E2,C1) + Accounting(C2,E1) + Business(E2,S1) = E:5, C:3, S:1"""
        seed = calculate_riasec_seed(['economics', 'accounting', 'business_studies'])
        assert seed == {'E': 5, 'C': 3, 'S': 1}

    def test_mixed_subjects_bio_econ_geo(self):
        """Biology(I2,S1) + Economics(E2,C1) + Geography(I2,R1)"""
        seed = calculate_riasec_seed(['biology', 'economics', 'geography'])
        assert seed == {'I': 4, 'S': 1, 'E': 2, 'C': 1, 'R': 1}

    def test_pa_excluded(self):
        """PA (pengajian_am) should be excluded from seed calculation."""
        seed = calculate_riasec_seed(['physics', 'pengajian_am', 'chemistry'])
        assert 'pengajian_am' not in str(seed)
        assert seed == {'R': 3, 'I': 3}  # No MathT here

    def test_unknown_subject_ignored(self):
        """Unknown subjects are silently ignored."""
        seed = calculate_riasec_seed(['physics', 'underwater_basket_weaving'])
        assert seed == {'R': 2, 'I': 1}

    def test_empty_subjects(self):
        seed = calculate_riasec_seed([])
        assert seed == {}

    def test_single_subject(self):
        seed = calculate_riasec_seed(['physics'])
        assert seed == {'R': 2, 'I': 1}

    def test_all_subjects_have_mappings(self):
        """Every subject in the RIASEC map should produce non-empty scores."""
        for subj in SUBJECT_RIASEC_MAP:
            seed = calculate_riasec_seed([subj])
            assert seed, f'{subj} produced empty seed'


class TestPrimarySeed:

    def test_single_winner(self):
        assert get_primary_seed({'R': 3, 'I': 5, 'C': 1}) == ['I']

    def test_tie_preserved(self):
        primary = get_primary_seed({'R': 3, 'I': 3, 'C': 1})
        assert set(primary) == {'R', 'I'}

    def test_empty(self):
        assert get_primary_seed({}) == []


# ── Branch routing ───────────────────────────────────────────────

class TestBranchRouting:

    def test_science_branch(self):
        assert determine_branch(['physics', 'chemistry', 'mathematics_t']) == 'science'

    def test_arts_branch(self):
        assert determine_branch(['economics', 'accounting', 'business_studies']) == 'arts'

    def test_mixed_branch(self):
        assert determine_branch(['biology', 'economics', 'geography']) == 'mixed'

    def test_science_with_ict(self):
        """ICT is a science subject."""
        assert determine_branch(['physics', 'ict', 'mathematics_t']) == 'science'

    def test_arts_with_math_m(self):
        """Math M is an arts subject."""
        assert determine_branch(['economics', 'mathematics_m', 'accounting']) == 'arts'

    def test_one_from_each_is_mixed(self):
        """One science + one arts + one either = mixed."""
        assert determine_branch(['physics', 'economics', 'geography']) == 'mixed'

    def test_pa_does_not_count(self):
        """PA is excluded — doesn't affect branch calculation."""
        assert determine_branch(['pengajian_am', 'physics', 'chemistry']) == 'science'


class TestCrossStreamDetection:

    def test_science_with_arts_subject(self):
        assert has_extra_cross_stream_subject(
            ['physics', 'chemistry', 'mathematics_t', 'economics'], 'science'
        ) is True

    def test_pure_science_no_cross(self):
        assert has_extra_cross_stream_subject(
            ['physics', 'chemistry', 'mathematics_t'], 'science'
        ) is False

    def test_arts_with_science_subject(self):
        assert has_extra_cross_stream_subject(
            ['economics', 'accounting', 'business_studies', 'biology'], 'arts'
        ) is True

    def test_mixed_always_false(self):
        assert has_extra_cross_stream_subject(
            ['biology', 'economics', 'geography'], 'mixed'
        ) is False


# ── Question generation ──────────────────────────────────────────

class TestQuizQuestions:

    def test_science_branch_returns_correct_q2(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'],
            {'physics': 'A'},
            'en',
        )
        assert result['branch'] == 'science'
        assert result['questions'][1]['id'] == 'q2s_field'

    def test_arts_branch_returns_correct_q2(self):
        result = get_stpm_quiz_questions(
            ['economics', 'accounting', 'business_studies'],
            {},
            'en',
        )
        assert result['branch'] == 'arts'
        assert result['questions'][1]['id'] == 'q2a_field'

    def test_mixed_branch_returns_correct_q2(self):
        result = get_stpm_quiz_questions(
            ['biology', 'economics', 'geography'],
            {},
            'en',
        )
        assert result['branch'] == 'mixed'
        assert result['questions'][1]['id'] == 'q2m_field'

    def test_initial_questions_are_q1_and_q2(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'en'
        )
        assert len(result['questions']) == 2
        assert result['questions'][0]['id'] == 'q1_readiness'

    def test_q3_variants_provided(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'en'
        )
        # Science branch has 6 Q2 options → 6 Q3 variants
        assert 'field_engineering' in result['q3_variants']
        assert 'field_health' in result['q3_variants']
        assert 'field_business' in result['q3_variants']

    def test_trunk_remaining_has_four_questions(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'en'
        )
        assert len(result['trunk_remaining']) == 4
        ids = [q['id'] for q in result['trunk_remaining']]
        assert 'q7_challenge' in ids
        assert 'q10_family' in ids

    def test_q5_science_has_six_options(self):
        """Science students see 6 cross-domain options (5 + stay in lane)."""
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'en'
        )
        assert len(result['q5']['options']) == 6

    def test_q5_arts_has_five_options(self):
        """Arts students see filtered options (no science-side)."""
        result = get_stpm_quiz_questions(
            ['economics', 'accounting', 'business_studies'], {}, 'en'
        )
        opts = result['q5']['options']
        texts = [o['text'] for o in opts]
        # Arts should NOT see 'Business & entrepreneurship' or 'Law & policy'
        assert 'Business & entrepreneurship' not in texts
        # Arts SHOULD see 'Health administration'
        assert 'Health administration' in texts
        # Always has 'stay in lane'
        assert any('stay in my lane' in t for t in texts)

    def test_bm_language(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'bm'
        )
        assert 'universiti' in result['questions'][0]['prompt'].lower()

    def test_ta_language(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'ta'
        )
        assert 'பல்கலைக்கழகத்தில்' in result['questions'][0]['prompt']

    def test_invalid_lang_defaults_to_en(self):
        result = get_stpm_quiz_questions(
            ['physics', 'chemistry', 'mathematics_t'], {}, 'xx'
        )
        assert 'university' in result['questions'][0]['prompt'].lower()


# ── Q3/Q4 resolution ────────────────────────────────────────────

class TestResolveQ3Q4:

    def test_engineering_resolves_q3(self):
        result = resolve_q3_and_q4(
            'field_engineering', 'science',
            {'physics': 'A'}, 'en'
        )
        assert result['q3']['id'] == 'q3s_engineering'

    def test_health_resolves_q3(self):
        result = resolve_q3_and_q4(
            'field_health', 'science',
            {'biology': 'A'}, 'en'
        )
        assert result['q3']['id'] == 'q3s_health'

    def test_business_in_science_branch_gets_arts_q3(self):
        """Science students who pick Business get the arts Q3 variant."""
        result = resolve_q3_and_q4(
            'field_business', 'science',
            {'economics': 'A'}, 'en'
        )
        assert result['q3']['id'] == 'q3a_business'

    def test_q4_strong_when_high_grade(self):
        result = resolve_q3_and_q4(
            'field_engineering', 'science',
            {'physics': 'A', 'mathematics_t': 'A-'}, 'en'
        )
        assert result['q4']['id'] == 'q4_confidence_strong'
        assert 'strong' in result['q4']['prompt'].lower()

    def test_q4_weak_when_low_grade(self):
        result = resolve_q3_and_q4(
            'field_health', 'science',
            {'biology': 'C+', 'chemistry': 'C'}, 'en'
        )
        assert result['q4']['id'] == 'q4_confidence_weak'
        assert 'C+' in result['q4']['prompt']

    def test_q4_weak_at_threshold(self):
        """B- (2.67) is the threshold — should trigger weak."""
        result = resolve_q3_and_q4(
            'field_health', 'science',
            {'biology': 'B-'}, 'en'
        )
        assert result['q4']['id'] == 'q4_confidence_weak'

    def test_q4_strong_just_above_threshold(self):
        """B (3.00) is above threshold — should trigger strong."""
        result = resolve_q3_and_q4(
            'field_health', 'science',
            {'biology': 'B'}, 'en'
        )
        assert result['q4']['id'] == 'q4_confidence_strong'

    def test_q4_education_no_subject_tie(self):
        """Education has no subject tie — uses strong template generically."""
        result = resolve_q3_and_q4(
            'field_education', 'science', {}, 'en'
        )
        assert result['q4']['id'] == 'q4_confidence_strong'

    def test_q4_interpolates_field_name(self):
        result = resolve_q3_and_q4(
            'field_engineering', 'science',
            {'physics': 'A'}, 'en'
        )
        assert 'engineering' in result['q4']['prompt'].lower()

    def test_q4_bm_language(self):
        result = resolve_q3_and_q4(
            'field_engineering', 'science',
            {'physics': 'A'}, 'bm'
        )
        assert 'kejuruteraan' in result['q4']['prompt'].lower()

    def test_unknown_field_returns_none_q3(self):
        result = resolve_q3_and_q4(
            'field_nonexistent', 'science', {}, 'en'
        )
        assert result['q3'] is None


# ── Signal accumulation ──────────────────────────────────────────

class TestSignalAccumulation:

    SCIENCE_SUBJECTS = ['physics', 'chemistry', 'mathematics_t']
    SCIENCE_GRADES = {'physics': 'A', 'chemistry': 'B+', 'mathematics_t': 'A-'}

    def _make_science_answers(self, **overrides):
        """Build a standard set of science branch answers."""
        defaults = [
            {'question_id': 'q1_readiness', 'option_index': 0},       # decided
            {'question_id': 'q2s_field', 'option_index': 0},          # engineering
            {'question_id': 'q3s_engineering', 'option_index': 0},    # mechanical
            {'question_id': 'q4_confidence_strong', 'option_index': 0},  # confirmed
            {'question_id': 'q5_cross_domain', 'option_index': 5},    # stay in lane
            {'question_id': 'q7_challenge', 'option_index': 0},       # dig in
            {'question_id': 'q8_motivation', 'option_index': 0},      # love studying
            {'question_id': 'q9_career', 'option_index': 0},          # professional
            {'question_id': 'q10_family', 'option_index': 1},         # moderate
        ]
        return defaults

    def test_riasec_seed_included(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        riasec = result['student_signals']['riasec_seed']
        assert riasec['riasec_I'] == 5
        assert riasec['riasec_R'] == 3

    def test_field_interest_accumulated(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        assert 'field_engineering' in result['student_signals']['field_interest']

    def test_field_key_accumulated(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        assert 'field_key_mekanikal' in result['student_signals']['field_key']

    def test_efficacy_signal(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        assert 'efficacy_confirmed' in result['student_signals']['efficacy']

    def test_context_signals(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        ctx = result['student_signals']['context']
        assert 'crystallisation_high' in ctx
        assert 'family_influence_moderate' in ctx

    def test_signal_strength_levels(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        ss = result['signal_strength']
        assert ss['riasec_I'] == 'strong'       # score 5
        assert ss['riasec_C'] == 'moderate'     # score 1

    def test_branch_in_output(self):
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        assert result['branch'] == 'science'

    def test_arts_branch_accumulation(self):
        answers = [
            {'question_id': 'q1_readiness', 'option_index': 1},       # general direction
            {'question_id': 'q2a_field', 'option_index': 0},          # business
            {'question_id': 'q3a_business', 'option_index': 0},       # marketing
            {'question_id': 'q4_confidence_strong', 'option_index': 1},  # open
            {'question_id': 'q5_cross_domain', 'option_index': 4},    # stay in lane
            {'question_id': 'q7_challenge', 'option_index': 1},       # get help
            {'question_id': 'q8_motivation', 'option_index': 1},      # career
            {'question_id': 'q9_career', 'option_index': 1},          # employment
            {'question_id': 'q10_family', 'option_index': 0},         # high
        ]
        subjects = ['economics', 'accounting', 'business_studies']
        grades = {'economics': 'A', 'accounting': 'B+', 'business_studies': 'B'}

        result = process_stpm_quiz(answers, subjects, grades)
        assert result['branch'] == 'arts'
        assert 'field_business' in result['student_signals']['field_interest']
        assert 'field_key_pemasaran' in result['student_signals']['field_key']
        assert 'riasec_E' in result['student_signals']['riasec_seed']

    def test_all_signal_categories_present(self):
        """Output always has all 9 taxonomy categories, even if empty."""
        result = process_stpm_quiz(
            self._make_science_answers(),
            self.SCIENCE_SUBJECTS,
            self.SCIENCE_GRADES,
        )
        for cat in STPM_SIGNAL_TAXONOMY:
            assert cat in result['student_signals']

    def test_invalid_question_id_raises(self):
        answers = [{'question_id': 'nonexistent', 'option_index': 0}]
        with pytest.raises(ValueError, match='Unknown question_id'):
            process_stpm_quiz(
                answers, self.SCIENCE_SUBJECTS, self.SCIENCE_GRADES
            )

    def test_missing_option_index_raises(self):
        answers = [{'question_id': 'q1_readiness'}]
        with pytest.raises(ValueError, match='Missing option_index'):
            process_stpm_quiz(
                answers, self.SCIENCE_SUBJECTS, self.SCIENCE_GRADES
            )

    def test_option_index_out_of_range_raises(self):
        answers = [{'question_id': 'q1_readiness', 'option_index': 99}]
        with pytest.raises(ValueError, match='out of range'):
            process_stpm_quiz(
                answers, self.SCIENCE_SUBJECTS, self.SCIENCE_GRADES
            )
