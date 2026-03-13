import pytest
from apps.courses.stpm_ranking import calculate_stpm_fit_score, get_stpm_ranked_results


class TestStpmFitScore:
    def test_base_score(self):
        """Programme with no signals gets base score only."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        score, reasons = calculate_stpm_fit_score(programme, student_cgpa=3.0, signals={})
        assert score == 50  # base

    def test_cgpa_margin_bonus(self):
        """Higher CGPA margin increases score."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 2.5, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        score, reasons = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals={})
        assert score > 50  # CGPA margin +1.0 should add bonus
        assert any('CGPA' in r for r in reasons)

    def test_cgpa_margin_capped(self):
        """CGPA margin bonus capped at max."""
        prog = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 1.0, 'min_muet_band': 1,
            'req_interview': False, 'no_colorblind': False,
        }
        score1, _ = calculate_stpm_fit_score(prog, student_cgpa=3.5, signals={})
        score2, _ = calculate_stpm_fit_score(prog, student_cgpa=4.0, signals={})
        # Both well above min — should be capped at same max
        assert score2 - score1 <= 5  # small or zero difference once capped

    def test_field_interest_match(self):
        """Field interest matching stream adds bonus."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'BACELOR KEJURUTERAAN', 'university': 'UTM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        signals_match = {'field_interest': ['field_mechanical', 'field_electrical']}
        signals_no_match = {'field_interest': ['field_arts', 'field_music']}
        score_match, _ = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_match)
        score_no, _ = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_no_match)
        assert score_match > score_no

    def test_field_interest_match_dict_format(self):
        """Field interest works with dict format from quiz engine."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'BACELOR KEJURUTERAAN', 'university': 'UTM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        # Quiz engine returns dicts: {signal_name: score}
        signals_match = {'field_interest': {'field_mechanical': 3, 'field_electrical': 2}}
        signals_no_match = {'field_interest': {'field_arts': 3}}
        score_match, reasons = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_match)
        score_no, _ = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_no_match)
        assert score_match > score_no
        assert any('Field' in r for r in reasons)

    def test_interview_penalty(self):
        """Interview requirement adds slight penalty."""
        base = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'no_colorblind': False,
        }
        prog_no = {**base, 'req_interview': False}
        prog_yes = {**base, 'req_interview': True}
        score_no, _ = calculate_stpm_fit_score(prog_no, student_cgpa=3.5, signals={})
        score_yes, _ = calculate_stpm_fit_score(prog_yes, student_cgpa=3.5, signals={})
        assert score_no > score_yes


class TestStpmRankedResults:
    def test_sorted_by_score_desc(self):
        """Programmes returned in descending score order."""
        programmes = [
            {'program_id': 'A', 'program_name': 'Low', 'university': 'X',
             'stream': 'arts', 'min_cgpa': 3.5, 'min_muet_band': 4,
             'req_interview': False, 'no_colorblind': False},
            {'program_id': 'B', 'program_name': 'High', 'university': 'Y',
             'stream': 'science', 'min_cgpa': 2.0, 'min_muet_band': 2,
             'req_interview': False, 'no_colorblind': False},
        ]
        result = get_stpm_ranked_results(programmes, student_cgpa=3.5, signals={})
        assert result[0]['program_id'] == 'B'  # higher CGPA margin → higher score

    def test_empty_list(self):
        """Empty input returns empty list."""
        result = get_stpm_ranked_results([], student_cgpa=3.0, signals={})
        assert result == []

    def test_fit_score_in_output(self):
        """Each programme in output has fit_score and fit_reasons."""
        programmes = [
            {'program_id': 'A', 'program_name': 'Test', 'university': 'UM',
             'stream': 'science', 'min_cgpa': 2.5, 'min_muet_band': 3,
             'req_interview': False, 'no_colorblind': False},
        ]
        result = get_stpm_ranked_results(programmes, student_cgpa=3.0, signals={})
        assert 'fit_score' in result[0]
        assert 'fit_reasons' in result[0]
        assert isinstance(result[0]['fit_score'], (int, float))
        assert isinstance(result[0]['fit_reasons'], list)

    def test_merit_score_survives_ranking(self):
        """merit_score passes through ranking pipeline."""
        programmes = [
            {'program_id': 'X', 'program_name': 'Test', 'university': 'UM',
             'stream': 'science', 'min_cgpa': 2.0, 'min_muet_band': 3,
             'req_interview': False, 'no_colorblind': False,
             'merit_score': 95.5},
        ]
        ranked = get_stpm_ranked_results(programmes, student_cgpa=3.5, signals={})
        assert 'merit_score' in ranked[0]
        assert ranked[0]['merit_score'] == 95.5
