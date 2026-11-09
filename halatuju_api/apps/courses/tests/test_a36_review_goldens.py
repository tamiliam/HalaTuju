"""
Audit sprint A3.6, review follow-up: small golden cases for the rules a mutation run showed unguarded.

`test_a36_engine_goldens.py` reads 35 grade profiles over every course row, but the catalogue never
uses some rules in a way those profiles can tell apart (a legacy `tech` / `voc` key, `comp_sci` as the
only science, a PISMP Tamil-stream row with a bare pass, an exact `min_pass`, the aggregate ceiling,
the order of the JSON and TVET steps). An adversarial mutation run changed each of them and every
golden still passed. These cases are hand-built so each one tells its rule apart; the expected
readings were taken on the pre-split code (5c37b085f) and must never be edited to make a split green.

Each eligibility case is one (student grades, requirement row) pair and records the verdict and the
audit trail. Each fit case is one `calculate_fit_score` call. No database, no fixtures, no network.
"""
import json
from pathlib import Path

from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.ranking_engine import calculate_fit_score

GOLDEN_FILE = Path(__file__).resolve().parent / 'fixtures' / 'a36_review_goldens.json'


def _read(grades, req):
    s = StudentProfile(grades=grades, gender='Lelaki', nationality='Warganegara', colorblind=False,
                       disability=False)
    ok, audit = check_eligibility(s, req)
    return {'ok': ok, 'audit': [f"{a['label']} {'ok' if a['passed'] else 'FAIL ' + str(a['reason'])}"
                                for a in audit]}


def _rule(flag, grades):
    return (grades, {flag: 1})


_AGG = [{'allowed_groups': [['bm'], ['eng'], ['math']], 'min_count': 3, 'min_grade': 'C'}]   # A + B + C = 11
_ALL = {'bm': 'A', 'eng': 'B', 'math': 'C'}
_PISMP_BT = {'source_type': 'pismp', 'course_id': '50PD0401'}   # characters 4-5 of the id are the zone
_PISMP_BC = {'source_type': 'pismp', 'course_id': '50PD0301'}
_ORDER_ROW = {
    'pass_bm': 1, 'credit_stv': 1, 'credit_sf': 1,
    'subject_group_req': [{'subjects': ['bm', 'eng'], 'min_count': 2, 'min_grade': 'C'}],
    'complex_requirements': {'or_groups': [{'count': 1, 'grade': 'A', 'subjects': ['phy', 'chem']}]},
    'min_credits': 2, 'min_pass': 4,
}

ELIGIBILITY_CASES = {
    # The science group counts comp_sci and addsci as well as phy / chem / bio / sci.
    'sci_group_comp_sci_only_credit': _rule('credit_science_group', {'comp_sci': 'B', 'bm': 'C'}),
    'sci_group_comp_sci_only_pass': _rule('credit_science_group', {'comp_sci': 'D', 'bm': 'C'}),
    'sci_group_none': _rule('credit_science_group', {'bm': 'A'}),
    # The legacy `tech` and `voc` keys, with no science and no maths.
    'math_sci_tech_legacy_tech_credit': _rule('credit_math_sci_tech', {'tech': 'C'}),
    'math_sci_tech_legacy_tech_pass': _rule('credit_math_sci_tech', {'tech': 'D'}),
    'stv_legacy_voc_credit': _rule('credit_stv', {'voc': 'B'}),
    'stv_legacy_voc_pass': _rule('credit_stv', {'voc': 'D'}),
    'stv_legacy_tech_credit': _rule('credit_stv', {'tech': 'C'}),
    'pass_stv_legacy_voc_pass': _rule('pass_stv', {'voc': 'E'}),
    'pass_stv_legacy_tech_pass': _rule('pass_stv', {'tech': 'E'}),
    'pass_sci_tech_legacy_tech_pass': _rule('pass_science_tech', {'tech': 'E'}),
    # Additional Maths stands in for a science on the sfmt row, with no maths or science.
    'sfmt_addmath_only_credit': _rule('credit_sfmt', {'addmath': 'C'}),
    'sfmt_addmath_only_pass': _rule('credit_sfmt', {'addmath': 'D'}),
    'sf_phy_only_credit': _rule('credit_sf', {'phy': 'C'}),
    'sf_addmath_only': _rule('credit_sf', {'addmath': 'A'}),
    # Credit and pass are different tests: a D is a pass, never a credit.
    'islam_credit': _rule('credit_islam', {'islam': 'B'}),
    'islam_pass_only': _rule('credit_islam', {'islam': 'D'}),
    'islam_absent': _rule('credit_islam', {'bm': 'A'}),
    'pass_sci_pass': _rule('pass_sci', {'sci': 'D'}),
    'pass_sci_fail_grade': _rule('pass_sci', {'sci': 'G'}),
    'pass_sci_absent': _rule('pass_sci', {'bm': 'A'}),
    'math_b_pass': _rule('credit_math_b', {'math': 'B'}),
    'math_b_credit_below_b': _rule('credit_math_b', {'math': 'C+'}),
    'math_b_addmath_does_not_stand_in': _rule('credit_math_b', {'addmath': 'A'}),
    # The count thresholds are inclusive: exactly min_pass passes (or min_credits credits) qualify.
    'min_pass_exact': ({'bm': 'E', 'eng': 'D', 'math': 'C', 'sci': 'G'}, {'min_pass': 3}),
    'min_pass_one_short': ({'bm': 'E', 'eng': 'D', 'math': 'C', 'sci': 'G'}, {'min_pass': 4}),
    'min_credit_exact': ({'bm': 'B', 'eng': 'C', 'math': 'D', 'sci': 'G'}, {'min_credits': 2}),
    'min_credit_one_short': ({'bm': 'B', 'eng': 'C', 'math': 'D', 'sci': 'G'}, {'min_credits': 3}),
    # PISMP medium-of-instruction gate: zone 03 needs a credit in b_cina, zone 04 in b_tamil; it stops the check.
    'pismp_04_credit': ({'b_tamil': 'C', 'bm': 'A'}, {**_PISMP_BT, 'pass_bm': 1}),
    'pismp_04_pass_only': ({'b_tamil': 'D', 'bm': 'A'}, {**_PISMP_BT, 'pass_bm': 1}),
    'pismp_04_absent': ({'b_cina': 'A', 'bm': 'A'}, {**_PISMP_BT, 'pass_bm': 1}),
    'pismp_03_credit': ({'b_cina': 'C', 'bm': 'A'}, {**_PISMP_BC, 'pass_bm': 1}),
    'pismp_03_pass_only': ({'b_cina': 'D', 'b_tamil': 'A+', 'bm': 'A'}, {**_PISMP_BC, 'pass_bm': 1}),
    'pismp_05_no_gate': ({'bm': 'A'}, {'source_type': 'pismp', 'course_id': '50PD0501', 'pass_bm': 1}),
    'pismp_id_too_short': ({'bm': 'A'}, {'source_type': 'pismp', 'course_id': '50PD4', 'pass_bm': 1}),
    'non_pismp_04_no_gate': ({'bm': 'A'}, {'source_type': 'ua', 'course_id': '50PD0401', 'pass_bm': 1}),
    # The aggregate ceiling of a diversity rule: A + B + C = 11 units.
    'agg_ceiling_equal': (_ALL, {'subject_group_req': _AGG, 'req_group_diversity': 1,
                                 'max_aggregate_units': 11}),
    'agg_ceiling_one_under': (_ALL, {'subject_group_req': _AGG, 'req_group_diversity': 1,
                                     'max_aggregate_units': 10}),
    'agg_ceiling_default_100': (_ALL, {'subject_group_req': _AGG, 'req_group_diversity': 1}),
    'agg_ceiling_json_string': (_ALL, {'subject_group_req': json.dumps(_AGG), 'req_group_diversity': 1,
                                       'max_aggregate_units': '11'}),
    'agg_ceiling_without_diversity_flag': (_ALL, {'subject_group_req': _AGG, 'max_aggregate_units': 3}),
    # One row that reaches the TVET/poly step AND both JSON steps: the audit trail pins their order.
    'order_tvet_then_json_fails': ({'bm': 'C', 'eng': 'D', 'math': 'E', 'phy': 'G'}, _ORDER_ROW),
    'order_tvet_then_json_passes': ({'bm': 'A', 'eng': 'B', 'math': 'C', 'phy': 'A'}, _ORDER_ROW),
}


def read_eligibility():
    return {name: _read(grades, req) for name, (grades, req) in ELIGIBILITY_CASES.items()}


# ---------------------------------------------------------------- fit

_FIELD = {'field_digital': 3, 'field_creative': 2}   # both map to the field 'multimedia'
_PREFS = {'work_preference_signals': {'hands_on': 2, 'creative': 1},
          'learning_tolerance_signals': {'learning_by_doing': 2, 'project_based': 1},
          'environment_signals': {'workshop_environment': 1}}
FIT_CASES = {
    'field_one_match': ({'field_interest': {'field_digital': 3}}, 'it-perisian'),
    'field_two_matches': ({'field_interest': _FIELD}, 'multimedia'),
    'field_two_matches_wrapped': ({'student_signals': {'field_interest': _FIELD}}, 'multimedia'),
    'field_no_match': ({'field_interest': _FIELD}, 'perakaunan'),
    'field_blank_key': ({'field_interest': _FIELD}, ''),
    # Several reasons at once: the sentence joins them with commas and "and".
    'many_reasons': (_PREFS, ''),
    'many_reasons_and_field': ({**_PREFS, 'field_interest': _FIELD}, 'multimedia'),
}
_TAGS = {'work_modality': 'hands_on', 'cognitive_type': 'abstract', 'environment': 'workshop',
         'learning_style': ['project_based'], 'people_interaction': 'high_people',
         'outcome': 'pathway_friendly', 'career_structure': 'stable', 'credential_status': 'regulated',
         'creative_output': 'design', 'service_orientation': 'neutral', 'interaction_type': 'mixed'}


def read_fit():
    out = {}
    for name, (profile, field_key) in FIT_CASES.items():
        score, reasons = calculate_fit_score(profile, 'C1', 'I1', {'C1': _TAGS}, {'I1': {}},
                                             field_key=field_key)
        out[name] = {'score': score, 'reasons': reasons}
    return out


# ---------------------------------------------------------------- the tests

def _expected():
    return json.loads(GOLDEN_FILE.read_text(encoding='utf-8'))


def test_review_eligibility_cases():
    assert read_eligibility() == _expected()['eligibility']


def test_review_fit_cases():
    assert read_fit() == _expected()['fit']
