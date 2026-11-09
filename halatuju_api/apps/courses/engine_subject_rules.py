"""The JSON requirement checkers of the eligibility engine: subject-group rules and OR-groups.

Moved verbatim out of `engine.py` (audit sprint A3.6, a moves-only split). `engine.py` re-exports
both, so every `from apps.courses.engine import ...` is unchanged. Nothing here changed.
"""

import json
import itertools

from .engine_grades import AGGREGATE_GRADE_POINTS, is_attempted, map_subject_code

# ============================================
# COMPLEX REQUIREMENT CHECKERS
# ============================================

def check_complex_requirements(student_grades, complex_req_json_str):
    """
    Evaluates university OR-group requirements from complex_requirements JSON.

    Format: {"or_groups": [{"count": N, "grade": "B", "subjects": [...]}]}

    Logic: Each OR group must be satisfied (AND logic between groups).
    Within each group, need 'count' subjects with at least 'grade' (OR logic).

    Accepts either a JSON string (from CSV) or a dict (from Django JSONField).
    """
    # Already a dict (from Django JSONField / DB load)
    if isinstance(complex_req_json_str, dict):
        data = complex_req_json_str
    else:
        # String path (from CSV)
        if not complex_req_json_str or not isinstance(complex_req_json_str, str) or complex_req_json_str.strip() == "":
            return True, None

        if isinstance(complex_req_json_str, float):
            import math
            if math.isnan(complex_req_json_str):
                return True, None

        complex_req_str = str(complex_req_json_str).strip()
        if not complex_req_str or complex_req_str.lower() == "nan":
            return True, None

        try:
            data = json.loads(complex_req_str)
        except json.JSONDecodeError:
            return False, "Invalid Complex Requirement Format"

    or_groups = data.get('or_groups', [])
    if not or_groups and not data.get('count_once'):
        return True, None

    for group_idx, group in enumerate(or_groups):
        min_count = group.get('count', 1)
        min_grade = group.get('grade', 'E')
        subjects = group.get('subjects', [])

        if not subjects:
            continue

        # A subject counts once per group (owner ruling): DISTINCT student keys, so a code listed
        # twice, or two codes folding to one key (Sains Pertanian / Pertanian), is one subject.
        # Each code maps to ONE key, so the distinct set IS the maximum matching.
        threshold = AGGREGATE_GRADE_POINTS.get(min_grade, 8)
        met = {map_subject_code(subj) for subj in subjects}
        count_ok = sum(1 for key in met
                       if student_grades.get(key) and AGGREGATE_GRADE_POINTS.get(student_grades[key], 10) <= threshold)

        if count_ok < min_count:
            subj_list = ', '.join(subjects[:5]) + ('...' if len(subjects) > 5 else '')
            return False, f"Complex Req Fail: Need {min_count} from [{subj_list}] with grade {min_grade} (Found {count_ok})"

    # Bumi Sprint D1: count-once blocks ("N more subjects not yet counted"), see spm_count_once.py.
    if data.get('count_once'):
        from .spm_count_once import count_once_failure
        failure = count_once_failure(student_grades, data['count_once'])
        if failure:
            return False, failure
    return True, None


def check_subject_group_logic(student_grades, rule_json_str, max_agg_units, check_diversity=False):
    """
    Evaluates complex subject group rules from a JSON string or list.

    Accepts either a JSON string (from CSV) or a list (from Django JSONField).
    """
    # Already a list (from Django JSONField / DB load)
    if isinstance(rule_json_str, list):
        rules = rule_json_str
    elif not rule_json_str or not isinstance(rule_json_str, str) or rule_json_str.strip() == "":
        return True, None
    else:
        try:
            rules = json.loads(rule_json_str)
        except json.JSONDecodeError:
            return False, "Invalid Requirement Format"

    if isinstance(rules, list):
        for rule in rules:
            min_grade = rule.get("min_grade", "E")
            min_count = rule.get("min_count", 1)

            if "allowed_groups" in rule and check_diversity:
                allowed_groups = rule.get("allowed_groups", [])
                valid_entries = []

                for g_idx, subjects_in_group in enumerate(allowed_groups):
                    for subj in subjects_in_group:
                        student_key = map_subject_code(subj)
                        grade = student_grades.get(student_key)

                        if grade and is_attempted(grade):
                            pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                            threshold_pts = AGGREGATE_GRADE_POINTS.get(min_grade, 8)

                            valid_entries.append({
                                "subj": student_key,
                                "group": g_idx,
                                "points": pts,
                                "grade": grade,
                                "meets_grade": pts <= threshold_pts
                            })

                best_per_group = {}
                for entry in valid_entries:
                    g = entry['group']
                    if g not in best_per_group or entry['points'] < best_per_group[g]['points']:
                        best_per_group[g] = entry

                available_subjects = list(best_per_group.values())

                if len(available_subjects) < min_count:
                    return False, f"Not enough subject groups (Found {len(available_subjects)}, Need {min_count})"

                found_valid_combo = False

                for combo in itertools.combinations(available_subjects, min_count):
                    passes_grade_req = sum(1 for e in combo if e['meets_grade']) == min_count
                    total_pts = sum(e['points'] for e in combo)
                    passes_agg = total_pts <= max_agg_units

                    if passes_grade_req and passes_agg:
                        found_valid_combo = True
                        break

                if not found_valid_combo:
                    return False, f"Diversity/Aggregate Failed (Max Units: {max_agg_units})"

            elif "subjects" in rule:
                subjects = rule.get("subjects", [])
                count_ok = 0
                if not subjects:
                    # Empty subjects = count from ALL student grades
                    # Used by PISMP: "any 5 subjects at A- or better"
                    for grade in student_grades.values():
                        if grade:
                            pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                            threshold = AGGREGATE_GRADE_POINTS.get(min_grade, 8)
                            if pts <= threshold:
                                count_ok += 1
                    if count_ok < min_count:
                        return False, f"Need {min_count} subjects at grade {min_grade} (have {count_ok})"
                    continue

                for subj in subjects:
                    student_key = map_subject_code(subj)
                    grade = student_grades.get(student_key)
                    if grade:
                        pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                        threshold = AGGREGATE_GRADE_POINTS.get(min_grade, 8)
                        if pts <= threshold:
                            count_ok += 1

                if count_ok < min_count:
                    return False, f"Subject Count Fail: Need {min_count} from {subjects} with grade {min_grade}"

    return True, None
